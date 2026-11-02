"""S3c: language models as agents, with the agent skill of tok and the tok MCP server.

The model gets the agent skill of tok (SKILL.md of tok 1.0.3) as its system prompt and the
tools `check`, `fmt` and `reference` of the tok MCP server (tok-mcp 1.0.3, started by this
script and spoken to over standard input and output, as an MCP client does). It calls the
tools itself, as often as it wants within the budget, and ends with its model in a fenced
block. The final model is judged by the judge of S3 (scripts/s3_run.py, unchanged).

    .venv/Scripts/python scripts/s3c_run.py --phase feasibility|main [--models gpt-oss:120b-cloud,gemma4:31b-cloud]
        [--workers 2] [--tasks doc-1.2,...]

Writes results/S3c/<phase>/runs/<run>/ (every message, tool call and tool result, the model
files and the judge's output) and results/S3c/<phase>/runs.jsonl (one record per run, in the
fields of S3, read by analyse_s3.py). Resumable.
"""

import argparse
import json
import random
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import s3_run
from common import RESULTS, ROOT, append_jsonl, log, read_jsonl, sha256

BIN = ROOT / "tools" / "bin" / "tok-1.0.3-local-2f5f1c1"
TOK, TOK_MCP, SKILL = BIN / "tok.exe", BIN / "tok-mcp.exe", BIN / "SKILL.md"
MODELS = "gpt-oss:120b-cloud,gemma4:31b-cloud"
OLLAMA = "http://127.0.0.1:11434/api/chat"
TOOLS = ("check", "fmt", "reference")
MAX_CALLS = 12  # model calls per run (each answer, with or without tool calls, is one)
MAX_TOOL_TEXT = 60_000  # characters of one tool result given back to the model
LIMIT_WAIT, LIMIT_TRIES = 900, 8
ENVIRONMENT = """## Environment of this session

You work through the tools of the tok MCP server: `check`, `fmt` and `reference`. There are no
file tools and no shell: give documents to the tools as `text`, and give your final model in your
last answer, in one fenced code block marked ```tok. The person you work for reads only that
answer.

"""
_lock = threading.Lock()


class ProviderLimit(RuntimeError):
    pass


# ------------------------------------------------------------------ the tok MCP server

class McpServer:
    """One tok-mcp process per run, in an empty folder; JSON-RPC 2.0 over standard input and output."""

    def __init__(self):
        self.dir = Path(tempfile.mkdtemp(prefix="tok-evidence-s3c-"))
        self.p = subprocess.Popen([str(TOK_MCP)], cwd=self.dir, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL)
        self.n = 0
        init = self.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                           "clientInfo": {"name": "tok-evidence", "version": "1"}})
        self.server = init.get("serverInfo")
        self.notify("notifications/initialized")
        self.tools = [t for t in self.request("tools/list")["tools"] if t["name"] in TOOLS]

    def notify(self, method, params=None):
        self.p.stdin.write((json.dumps({"jsonrpc": "2.0", "method": method, **({"params": params} if params else {})}) + "\n").encode())
        self.p.stdin.flush()

    def request(self, method, params=None):
        self.n += 1
        msg = {"jsonrpc": "2.0", "id": self.n, "method": method, **({"params": params} if params is not None else {})}
        self.p.stdin.write((json.dumps(msg) + "\n").encode())
        self.p.stdin.flush()
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError("tok-mcp closed its output")
            d = json.loads(line)
            if d.get("id") == self.n:
                if "error" in d:
                    raise RuntimeError(f"tok-mcp: {d['error']}")
                return d["result"]

    def call(self, name, arguments):
        if name not in TOOLS:
            return {"isError": True, "text": f"unknown tool {name!r}; the tools are {', '.join(TOOLS)}"}
        try:
            r = self.request("tools/call", {"name": name, "arguments": arguments if isinstance(arguments, dict) else {}})
        except RuntimeError as ex:
            return {"isError": True, "text": str(ex)}
        text = "".join(c.get("text", "") for c in r.get("content", []) if c.get("type") == "text")
        if not text and "structuredContent" in r:
            text = json.dumps(r["structuredContent"], ensure_ascii=False)
        return {"isError": bool(r.get("isError")), "text": text}

    def close(self):
        try:
            self.p.stdin.close()
            self.p.wait(timeout=10)
        except Exception:
            self.p.kill()


def ollama_tools(server):
    return [{"type": "function", "function": {"name": t["name"], "description": t.get("description", ""),
                                              "parameters": t.get("inputSchema", {"type": "object"})}} for t in server.tools]


# ------------------------------------------------------------------ the model

def chat(model, messages, tools):
    body = {"model": model, "stream": False, "messages": messages, "tools": tools}
    errors = limits = 0
    while True:
        t0 = time.perf_counter()
        req = urllib.request.Request(OLLAMA, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=900) as r:
                d = json.loads(r.read())
            d["_seconds"] = time.perf_counter() - t0
            return d
        except urllib.error.HTTPError as e:
            msg = e.read()[:300].decode("utf-8", "replace")
            if e.code == 429:
                limits += 1
                if limits > LIMIT_TRIES:
                    raise ProviderLimit(f"{model}: HTTP 429 {LIMIT_TRIES} times: {msg}")
                log(f"{model}: limit of the provider ({msg[:120]}); waiting {LIMIT_WAIT} s")
                time.sleep(LIMIT_WAIT)
                continue
            errors += 1
            if errors > 3 or e.code in (401, 402, 403, 404):
                raise RuntimeError(f"{model}: HTTP {e.code}: {msg}")
            log(f"{model}: HTTP {e.code} ({msg[:120]}); waiting {30 * errors} s")
            time.sleep(30 * errors)
        except Exception as e:
            errors += 1
            if errors > 3:
                raise
            log(f"{model}: {type(e).__name__}: {str(e)[:120]}; waiting {30 * errors} s")
            time.sleep(30 * errors)


# ------------------------------------------------------------------ judging a tok text

def judge_tok(d, name, text):
    """tok check (1.0.3) and, without errors, the BPMN of `tok bpmn --no-layout` judged by the judge of S3."""
    path = d / f"{name}.tok"
    path.write_text(text, encoding="utf-8", newline="\n")
    p = subprocess.run([str(TOK), "check", path.name, "--json"], cwd=d, capture_output=True, text=True, encoding="utf-8")
    try:
        diags = json.loads(p.stdout)["diagnostics"]
    except (json.JSONDecodeError, KeyError):
        diags = [{"severity": "error", "code": "CRASH", "message": (p.stdout + p.stderr)[-300:]}]
    errors = [x for x in diags if x["severity"] == "error"]
    warnings = [x for x in diags if x["severity"] == "warning"]
    res = {"errors": len(errors), "warnings": len(warnings), "codes": sorted({x["code"] for x in errors + warnings}), "bpmn": None}
    if not errors:
        bp = d / f"{name}.bpmn"
        subprocess.run([str(TOK), "bpmn", "--no-layout", path.name, "-o", bp.name], cwd=d, capture_output=True)
        if bp.exists():
            res["bpmn"] = bp
    res["judge"] = s3_run.judge(res["bpmn"]) if res["bpmn"] else {"valid": False, "exists": False}
    return res


# ------------------------------------------------------------------ one run

def run_one(spec, phase_dir):
    model, task_id, r = spec["model"], spec["task"], spec["repetition"]
    run_id = f"{model.replace(':', '-')}__TOKAGENT__{task_id}__r{r}"
    d = phase_dir / "runs" / run_id
    d.mkdir(parents=True, exist_ok=True)
    task = next(t for t in s3_run.TASKS["tasks"] if t["id"] == task_id)
    system = ENVIRONMENT + SKILL.read_text(encoding="utf-8")
    user = s3_run.instruction("TOK", task["text"])
    server = McpServer()
    tools = ollama_tools(server)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    turns, first_draft, t0 = [], None, time.perf_counter()
    try:
        for k in range(1, MAX_CALLS + 1):
            resp = chat(model, messages, tools)
            m = resp.get("message", {})
            calls = m.get("tool_calls") or []
            turn = {"call": k, "input_tokens": resp.get("prompt_eval_count", 0), "output_tokens": resp.get("eval_count", 0),
                    "seconds": resp["_seconds"], "model": resp.get("model"), "done_reason": resp.get("done_reason"),
                    "content": m.get("content", ""), "thinking": m.get("thinking") or "", "tool_calls": []}
            messages.append({"role": "assistant", "content": m.get("content", ""),
                             **({"tool_calls": calls} if calls else {}), **({"thinking": m["thinking"]} if m.get("thinking") else {})})
            for c in calls:
                fn = c.get("function", {})
                name, args = fn.get("name"), fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                out = server.call(name, args)
                text = out["text"][:MAX_TOOL_TEXT]
                turn["tool_calls"].append({"name": name, "arguments": args, "is_error": out["isError"], "result": text})
                if name == "check" and first_draft is None and isinstance(args.get("text"), str):
                    first_draft = args["text"]
                messages.append({"role": "tool", "tool_name": name, "content": text})
            turns.append(turn)
            if not calls:
                break
    finally:
        server.close()
    final_text, how = s3_run.extract(turns[-1]["content"] if turns else "", "TOK")
    final = judge_tok(d, "final", final_text)
    first = judge_tok(d, "first", first_draft) if first_draft else final
    (d / "system.md").write_text(system, encoding="utf-8", newline="\n")
    (d / "instruction.md").write_text(user, encoding="utf-8", newline="\n")
    (d / "transcript.json").write_text(json.dumps(turns, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    n_tools = sum(len(t["tool_calls"]) for t in turns)
    out = {"run": run_id, "model": model, "rep": "TOKAGENT", "task": task_id, "repetition": r,
           "attempts": len(turns), "tool_calls": n_tools,
           "tool_calls_by_name": {n: sum(1 for t in turns for c in t["tool_calls"] if c["name"] == n) for n in TOOLS},
           "ended_by_budget": bool(turns and turns[-1]["tool_calls"]), "extracted": how,
           "loop_ok": final["errors"] == 0 and final["warnings"] == 0, "final_codes": final["codes"],
           "valid_first": first["judge"]["valid"], "valid_final": final["judge"]["valid"],
           "final_bpmn": str(final["bpmn"].relative_to(phase_dir)).replace("\\", "/") if final["bpmn"] else None,
           "first_bpmn": str(first["bpmn"].relative_to(phase_dir)).replace("\\", "/") if first["bpmn"] else None,
           "input_tokens": sum(t["input_tokens"] or 0 for t in turns), "output_tokens": sum(t["output_tokens"] or 0 for t in turns),
           "first_input_tokens": turns[0]["input_tokens"] if turns else 0, "first_output_tokens": turns[0]["output_tokens"] if turns else 0,
           "seconds": time.perf_counter() - t0, "model_ids": sorted({t["model"] for t in turns if t["model"]}),
           "mcp_server": server.server, "date": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "final_judge": final["judge"], "first_judge": first["judge"]}
    (d / "run.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8", newline="\n")
    with _lock:
        append_jsonl(phase_dir / "runs.jsonl", json.loads(json.dumps(out, default=str)))
    return out


def frozen():
    files = [Path(__file__), ROOT / "scripts" / "s3_run.py", ROOT / "scripts" / "bpmn_graph.py", ROOT / "scripts" / "lint.mjs",
             ROOT / "prompts" / "instruction.md", TOK, TOK_MCP, SKILL]
    return {str(p.relative_to(ROOT)).replace("\\", "/"): sha256(p.read_bytes()) for p in files}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["feasibility", "main"], required=True)
    ap.add_argument("--models", default=MODELS)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--reps", type=int, default=None)
    ap.add_argument("--tasks", default=None)
    args = ap.parse_args()
    phase_dir = RESULTS / "S3c" / args.phase
    phase_dir.mkdir(parents=True, exist_ok=True)
    reps = args.reps or (1 if args.phase == "feasibility" else 2)
    tasks = args.tasks.split(",") if args.tasks else (s3_run.TASKS["pilot"] if args.phase == "feasibility" else s3_run.TASKS["main"])
    models = args.models.split(",")
    fz, now = phase_dir / "frozen.json", frozen()
    if args.phase == "main" and fz.exists() and json.loads(fz.read_text()) != now:
        raise SystemExit("the harness, the skill or the tok programs changed after the study started")
    fz.write_text(json.dumps(now, indent=1), encoding="utf-8", newline="\n")
    specs = [{"model": m, "task": t, "repetition": r} for m in models for t in tasks for r in range(1, reps + 1)]
    random.Random(s3_run.ORDER_SEED).shuffle(specs)
    rid = lambda s: f"{s['model'].replace(':', '-')}__TOKAGENT__{s['task']}__r{s['repetition']}"
    done = {x["run"] for x in read_jsonl(phase_dir / "runs.jsonl")}
    todo = [s for s in specs if rid(s) not in done]
    log(f"S3c {args.phase}: {len(specs)} runs, {len(todo)} to do; models {models}")
    stopped, counter = set(), {"n": 0}

    def safe(s):
        if s["model"] in stopped:
            return
        try:
            r = run_one(s, phase_dir)
            counter["n"] += 1
            log(f"[{counter['n']}/{len(todo)}] {r['run']}: calls {r['attempts']}, tools {r['tool_calls_by_name']}, "
                f"valid first {r['valid_first']}, final {r['valid_final']}, tokens {r['input_tokens']}+{r['output_tokens']}, {r['seconds']:.0f} s")
        except ProviderLimit as ex:
            stopped.add(s["model"])
            log(f"run {rid(s)}: {ex}; the remaining runs of {s['model']} are left for a resumed run")
        except Exception as ex:
            log(f"run {rid(s)} failed: {type(ex).__name__}: {ex}")

    pools = {m: ThreadPoolExecutor(args.workers) for m in models}
    for f in [pools[s["model"]].submit(safe, s) for s in todo]:
        f.result()
    log("finished")


if __name__ == "__main__":
    main()
