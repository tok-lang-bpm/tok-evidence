"""S3: language models write process models from PET texts (PROTOCOL.md §6).

Every run: one task, one representation (XML or TOK), one model, one repetition. The model
gets the system prompt (the reference of the language) and the instruction with the text;
its answer is validated (TOK: tok check, errors and warnings; XML: well-formedness, the OMG schema, the
correctness rules of bpmnlint and the minimum of the judge); while there are errors and at
most three times, the instruction, the previous answer and the messages are sent again. Each
call is independent (no chat state): every model gets exactly the same context.

    .venv/Scripts/python scripts/s3_run.py --phase pilot|main [--models haiku,sonnet,qwen3:4b]
        [--reps 2] [--claude-workers 3]

Writes results/S3/<phase>/runs/<run>/ (every prompt, answer, model file and validator
output) and results/S3/<phase>/runs.jsonl (one record per finished run). Resumable.
"""

import argparse
import hashlib
import json
import random
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import bpmn_graph
from common import RAW, RESULTS, ROOT, SEED, TOK, append_jsonl, log, read_jsonl, run_tok, sha256

PROMPTS = ROOT / "prompts"
TASKS = json.load(open(ROOT / "data" / "derived" / "pet" / "tasks.json", encoding="utf-8"))
MAX_ATTEMPTS = 4  # the first answer and at most three corrections
ORDER_SEED = 20261030  # the order of the runs of the main study
MAX_MESSAGE_LINES = 40
OLLAMA = "http://127.0.0.1:11434/api/chat"
CLAUDE_MODELS = {"haiku": "haiku", "sonnet": "sonnet"}
WORKDIR = Path(tempfile.mkdtemp(prefix="tok-evidence-s3-"))  # empty: no project settings for the CLI
_write_lock = threading.Lock()
_lint_lock = threading.Lock()


# ------------------------------------------------------------------ prompts

def read(p):
    return (PROMPTS / p).read_text(encoding="utf-8")


def system_prompt(rep):
    if rep == "TOK":
        ref = read("cheatsheet-tok-1.0.1.md") + read("reference-tok-example.md").replace(
            "EXAMPLE", (PROMPTS / "examples" / "application.tok").read_text(encoding="utf-8").strip())
        lang = "tok (a plain-text language for BPMN 2.0 process models)"
    else:
        ref = read("reference-xml.md").replace(
            "EXAMPLE", (PROMPTS / "examples" / "application.bpmn").read_text(encoding="utf-8").strip())
        lang = "BPMN 2.0 XML"
    return read("system.md").replace("{LANGUAGE}", lang).replace("{REFERENCE}", ref)


FENCE = {"TOK": "tok", "XML": "xml"}
VALIDATOR = {"TOK": "The tok checker", "XML": "The BPMN validator (XML Schema and model rules)"}


def instruction(rep, text):
    return read("instruction.md").replace("{FENCE}", FENCE[rep]).replace("{TEXT}", text)


def feedback(rep, text, answer, messages):
    return (read("feedback.md").replace("{INSTRUCTION}", instruction(rep, text)).replace("{FENCE}", FENCE[rep])
            .replace("{ANSWER}", answer).replace("{VALIDATOR}", VALIDATOR[rep]).replace("{MESSAGES}", messages))


def frozen():
    """Checksums of everything that defines the prompts and the harness."""
    files = sorted(PROMPTS.rglob("*.*")) + [Path(__file__), ROOT / "scripts" / "lint.mjs", ROOT / "scripts" / "bpmn_graph.py"]
    out = {str(p.relative_to(ROOT)).replace("\\", "/"): sha256(p.read_bytes()) for p in files}
    out["system:TOK"] = sha256(system_prompt("TOK").encode())
    out["system:XML"] = sha256(system_prompt("XML").encode())
    return out


# ------------------------------------------------------------------ models

def call_claude(model, system, user):
    sysfile = WORKDIR / f"system-{sha256(system.encode())[:12]}.md"
    if not sysfile.exists():
        sysfile.write_text(system, encoding="utf-8", newline="\n")
    cmd = ["claude", "-p", "--model", CLAUDE_MODELS[model], "--system-prompt-file", str(sysfile), "--tools", "",
           "--disable-slash-commands", "--strict-mcp-config", "--no-session-persistence", "--output-format", "json"]
    for attempt in range(8):
        t0 = time.perf_counter()
        p = subprocess.run(cmd, input=user.encode("utf-8"), capture_output=True, cwd=WORKDIR, timeout=900)
        dt = time.perf_counter() - t0
        try:
            d = json.loads(p.stdout.decode("utf-8"))
        except json.JSONDecodeError:
            d = {"is_error": True, "result": (p.stdout + p.stderr).decode("utf-8", "replace")[-500:]}
        if not d.get("is_error"):
            u = d.get("usage", {})
            return {"text": d.get("result", ""), "input_tokens": u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0),
                    "cache_read_tokens": u.get("cache_read_input_tokens", 0), "output_tokens": u.get("output_tokens", 0),
                    "thinking_tokens": (u.get("output_tokens_details") or {}).get("thinking_tokens"),
                    "seconds": dt, "model_ids": list(d.get("modelUsage", {}).keys()), "cost_usd": d.get("total_cost_usd")}
        msg = str(d.get("result", ""))[:300]
        wait = 600 if re.search(r"limit|quota|rate", msg, re.I) else 30 * (attempt + 1)
        log(f"claude {model}: error ({msg[:120]}); waiting {wait} s")
        time.sleep(wait)
    raise RuntimeError("claude: repeated errors")


def gpu_temperature():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=20).stdout.strip()
        return int(out.splitlines()[0])
    except Exception:
        return None


def call_ollama(model, system, user, seed):
    # the GPU of a laptop (kept under about 85 °C): above 80 °C the next call waits until 75 °C
    t = gpu_temperature()
    if t is not None and t > 80:
        log(f"GPU at {t} °C: waiting until 75 °C")
        while (t := gpu_temperature()) is not None and t > 75:
            time.sleep(15)
    body = {"model": model, "stream": False, "think": False,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": {"num_ctx": 16384, "num_predict": 8192, "seed": seed}}
    t0 = time.perf_counter()
    req = urllib.request.Request(OLLAMA, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        d = json.loads(r.read())
    time.sleep(5)  # a short pause after every local call
    return {"text": d["message"]["content"], "input_tokens": d.get("prompt_eval_count", 0), "cache_read_tokens": 0,
            "output_tokens": d.get("eval_count", 0), "thinking_tokens": None, "seconds": time.perf_counter() - t0,
            "model_ids": [d.get("model")], "seed": seed, "done_reason": d.get("done_reason")}


def call_model(model, system, user, seed):
    return call_claude(model, system, user) if model in CLAUDE_MODELS else call_ollama(model, system, user, seed)


# ------------------------------------------------------------------ answers and validators

def extract(text, rep):
    blocks = re.findall(r"```([A-Za-z0-9_-]*)[ \t]*\r?\n(.*?)```", text, re.S)
    want = {"TOK": ("tok",), "XML": ("xml", "bpmn")}[rep]
    for lang, body in reversed(blocks):
        if lang.lower() in want:
            return body.strip() + "\n", "fenced"
    if blocks:
        return blocks[-1][1].strip() + "\n", "fenced, other language"
    return text.strip() + "\n", "whole answer"


def lint(path):
    lst = Path(str(path) + ".list.json")
    out = Path(str(path) + ".lint.json")
    lst.write_text(json.dumps([str(path)]), encoding="utf-8")
    res = {}
    for cfg in ("correctness", "recommended"):
        subprocess.run(["node", str(ROOT / "scripts" / "lint.mjs"), str(lst), str(out), cfg], check=True, capture_output=True)
        res[cfg] = json.load(open(out, encoding="utf-8"))[0]
    lst.unlink()
    out.unlink()
    return res


_schema = threading.local()


def schema():
    from lxml import etree

    if not hasattr(_schema, "s"):
        _schema.s = etree.XMLSchema(etree.parse(str(RAW / "xsd" / "BPMN20.xsd")))
    return _schema.s


def judge(path):
    """The same judge for both representations, on BPMN XML (PROTOCOL.md §6.6)."""
    from lxml import etree

    j = {"exists": path is not None and Path(path).exists()}
    if not j["exists"]:
        j["valid"] = False
        return j
    data = Path(path).read_bytes()
    try:
        doc = etree.fromstring(data, etree.XMLParser(resolve_entities=False, no_network=True))
        j["well_formed"] = True
    except etree.XMLSyntaxError as ex:
        j.update(well_formed=False, problems=[f"not well-formed XML: {ex}"[:300]], valid=False)
        return j
    s = schema()
    j["xsd_valid"] = s.validate(etree.ElementTree(doc))
    j["xsd_errors"] = [f"line {e.line}: {e.message}"[:300] for e in s.error_log][:20]
    try:
        g = bpmn_graph.read(data)
        j["structural"] = bpmn_graph.structural_problems(g)
    except Exception as ex:
        j["structural"] = [f"cannot read the process: {ex}"[:300]]
    li = lint(path)
    j["lint_correctness"] = [f"{x['rule']}: {x['id']}: {x['message']}" for x in li["correctness"]["reports"] if x["category"] == "error"]
    j["lint_recommended_errors"] = sum(1 for x in li["recommended"]["reports"] if x["category"] == "error")
    j["lint_import_error"] = li["correctness"].get("error")
    j["moddle_warnings"] = li["correctness"]["warnings"][:20]
    j["valid"] = bool(j["xsd_valid"] and not j["structural"] and not j["lint_correctness"] and not j["lint_import_error"])
    return j


def validate_xml(d, k, model_text):
    """The validator of the XML loop: the judge itself; its messages are the feedback."""
    path = d / f"attempt-{k}.bpmn"
    path.write_text(model_text, encoding="utf-8", newline="\n")
    j = judge(path)
    msgs = []
    if j.get("well_formed") is False:
        msgs = j["problems"]
    else:
        msgs = j.get("xsd_errors", []) + j.get("structural", []) + j.get("lint_correctness", [])
        if j.get("lint_import_error"):
            msgs.append("the file cannot be read: " + j["lint_import_error"])
    return {"ok": j["valid"], "messages": msgs, "judge": j, "bpmn": path}


def validate_tok(d, k, model_text):
    path = d / f"attempt-{k}.tok"
    path.write_text(model_text, encoding="utf-8", newline="\n")
    code, out, err, _ = run_tok(["check", path.name, "--lang", "en"], cwd=d)
    code2, js, _, _ = run_tok(["check", path.name, "--json"], cwd=d)
    try:
        diags = json.loads(js)["diagnostics"]
        errors = [x for x in diags if x["severity"] == "error"]
        # errors and warnings are fed back, as the agent skill of tok 1.0.2 says; notes are not
        warnings = [x for x in diags if x["severity"] == "warning"]
        msgs = [f"line {x.get('line')}: {x['severity']} {x['code']}: {x['message']}" for x in errors + warnings]
    except (json.JSONDecodeError, KeyError):
        errors, warnings, msgs = [{"code": "CRASH"}], [], [(out + err).strip()[-500:]]
    res = {"ok": not errors and not warnings, "messages": msgs, "check_output": out[-4000:], "bpmn": None,
           "errors": len(errors), "warnings": len(warnings)}
    if not errors:
        bp = d / f"attempt-{k}.bpmn"
        code3, out3, err3, _ = run_tok(["bpmn", "--no-layout", path.name, "-o", bp.name], cwd=d)
        res["bpmn"] = bp if bp.exists() else None
        res["export_output"] = (out3 + err3)[-1000:]
    return res


# ------------------------------------------------------------------ one run

def run_one(spec, phase_dir):
    model, rep, task_id, r = spec["model"], spec["rep"], spec["task"], spec["repetition"]
    run_id = f"{model.replace(':', '-')}__{rep}__{task_id}__r{r}"
    d = phase_dir / "runs" / run_id
    d.mkdir(parents=True, exist_ok=True)
    task = next(t for t in TASKS["tasks"] if t["id"] == task_id)
    system = system_prompt(rep)
    (d / "system.md").write_text(system, encoding="utf-8", newline="\n")
    attempts, t0 = [], time.perf_counter()
    user = instruction(rep, task["text"])
    final = None
    for k in range(1, MAX_ATTEMPTS + 1):
        seed = int(hashlib.sha256(f"{run_id}|{k}".encode()).hexdigest()[:8], 16) % (2 ** 31)
        (d / f"attempt-{k}.prompt.txt").write_text(user, encoding="utf-8", newline="\n")
        resp = call_model(model, system, user, seed)
        (d / f"attempt-{k}.answer.txt").write_text(resp["text"], encoding="utf-8", newline="\n")
        model_text, how = extract(resp["text"], rep)
        v = validate_tok(d, k, model_text) if rep == "TOK" else validate_xml(d, k, model_text)
        rec = {"attempt": k, "extracted": how, "ok": v["ok"], "messages": v["messages"][:MAX_MESSAGE_LINES],
               **{x: resp.get(x) for x in ("input_tokens", "cache_read_tokens", "output_tokens", "thinking_tokens", "seconds", "model_ids", "cost_usd", "seed", "done_reason")}}
        attempts.append(rec)
        final = v
        if v["ok"]:
            break
        msgs = "\n".join(f"- {m}" for m in v["messages"][:MAX_MESSAGE_LINES]) or "- the answer contains no model"
        user = feedback(rep, task["text"], model_text.strip(), msgs)
    first_judge = judge(d / "attempt-1.bpmn") if (d / "attempt-1.bpmn").exists() else {"valid": False, "exists": False}
    final_bpmn = final.get("bpmn")
    final_judge = judge(final_bpmn) if final_bpmn else {"valid": False, "exists": False}
    out = {"run": run_id, "model": model, "rep": rep, "task": task_id, "repetition": r,
           "attempts": len(attempts), "loop_ok": attempts[-1]["ok"], "valid_first": first_judge["valid"],
           "valid_final": final_judge["valid"], "final_bpmn": str(Path(final_bpmn).relative_to(phase_dir)).replace("\\", "/") if final_bpmn else None,
           "first_bpmn": "runs/" + run_id + "/attempt-1.bpmn" if (d / "attempt-1.bpmn").exists() else None,
           "input_tokens": sum(a["input_tokens"] or 0 for a in attempts), "output_tokens": sum(a["output_tokens"] or 0 for a in attempts),
           "first_input_tokens": attempts[0]["input_tokens"], "first_output_tokens": attempts[0]["output_tokens"],
           "seconds": time.perf_counter() - t0, "model_ids": sorted({m for a in attempts for m in (a["model_ids"] or []) if m}),
           "date": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "attempt_log": attempts, "final_judge": final_judge, "first_judge": first_judge}
    (d / "run.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8", newline="\n")
    with _write_lock:
        append_jsonl(phase_dir / "runs.jsonl", json.loads(json.dumps(out, default=str)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["pilot", "main"], required=True)
    ap.add_argument("--models", default="haiku,sonnet,qwen3:4b")
    ap.add_argument("--reps", type=int, default=None)
    ap.add_argument("--claude-workers", type=int, default=3)
    args = ap.parse_args()
    phase_dir = RESULTS / "S3" / args.phase
    phase_dir.mkdir(parents=True, exist_ok=True)
    reps = args.reps or (1 if args.phase == "pilot" else 2)
    tasks = TASKS["pilot"] if args.phase == "pilot" else TASKS["main"]
    models = args.models.split(",")
    if args.phase == "main":
        fz = phase_dir / "frozen.json"
        now = frozen()
        if fz.exists() and json.loads(fz.read_text()) != now:
            raise SystemExit("the prompts or the harness changed after the main study started")
        fz.write_text(json.dumps(now, indent=1), encoding="utf-8", newline="\n")
    specs = [{"model": m, "rep": rp, "task": t, "repetition": r} for m in models for rp in ("XML", "TOK") for t in tasks for r in range(1, reps + 1)]
    random.Random(ORDER_SEED).shuffle(specs)
    done = {x["run"] for x in read_jsonl(phase_dir / "runs.jsonl")}
    rid = lambda s: f"{s['model'].replace(':', '-')}__{s['rep']}__{s['task']}__r{s['repetition']}"
    todo = [s for s in specs if rid(s) not in done]
    log(f"{args.phase}: {len(specs)} runs, {len(todo)} to do; models {models}")
    claude = [s for s in todo if s["model"] in CLAUDE_MODELS]
    local = [s for s in todo if s["model"] not in CLAUDE_MODELS]
    counter = {"n": 0}

    def safe(s):
        try:
            r = run_one(s, phase_dir)
            counter["n"] += 1
            log(f"[{counter['n']}/{len(todo)}] {r['run']}: attempts {r['attempts']}, valid first {r['valid_first']}, final {r['valid_final']}, tokens {r['input_tokens']}+{r['output_tokens']}, {r['seconds']:.0f} s")
        except Exception as ex:
            log(f"run {rid(s)} failed: {type(ex).__name__}: {ex}")

    with ThreadPoolExecutor(args.claude_workers) as cex, ThreadPoolExecutor(1) as lex:
        fut = [cex.submit(safe, s) for s in claude] + [lex.submit(safe, s) for s in local]
        for f in fut:
            f.result()
    log("finished")


if __name__ == "__main__":
    main()
