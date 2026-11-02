"""S3d: Claude Haiku and Sonnet as agents with the skill and the MCP server of tok, and Beam
(Reflection, open weights) both from the cold start of S3b and as an agent (PROTOCOL-S3d.md).

The agent arm (`TOKAGENT`) is the design of S3c: the agent skill of tok 1.0.3 as the system
prompt (after the same note on the environment), the tools `check`, `fmt` and `reference` of
tok-mcp 1.0.3 and nothing else, at most 12 model calls. Claude runs through the Claude command
line in print mode, in an empty folder, with only that MCP server; Beam through Ollama with the
harness of S3c (scripts/s3c_run.py, unchanged). The cold-start arms of Beam (`XML`, `TOK`) are
the harness of S3 (scripts/s3_run.py, unchanged; tok 1.0.2 as in S3b).

    .venv/Scripts/python scripts/s3d_run.py --phase feasibility|main [--part claude|beam|all] [--workers 2]

Writes results/S3d/<phase>/runs/<run>/ and results/S3d/<phase>/runs.jsonl. Resumable.
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
import s3c_run
from common import RESULTS, ROOT, append_jsonl, log, read_jsonl, sha256

CLAUDE = {"haiku": "haiku", "sonnet": "sonnet"}
BEAM = "beam:cloud"
TOOLS = ["mcp__tok__" + t for t in s3c_run.TOOLS]
OTHER_TOOLS = ["mcp__tok__" + t for t in ("export", "import", "sim", "eval")]
_lock = threading.Lock()
_phase_dir = None


# ------------------------------------------------------------------ Claude as an agent

def claude_agent(model, system, user, d):
    w = Path(tempfile.mkdtemp(prefix="tok-evidence-s3d-"))
    (w / "system.md").write_text(system, encoding="utf-8", newline="\n")
    (w / "mcp.json").write_text(json.dumps({"mcpServers": {"tok": {"command": str(s3c_run.TOK_MCP), "args": []}}}), encoding="utf-8")
    cmd = ["claude", "-p", "--model", CLAUDE[model], "--system-prompt-file", str(w / "system.md"), "--mcp-config", str(w / "mcp.json"),
           "--strict-mcp-config", "--tools", "", "--allowedTools", ",".join(TOOLS), "--disallowedTools", ",".join(OTHER_TOOLS),
           "--disable-slash-commands", "--no-session-persistence", "--max-turns", str(s3c_run.MAX_CALLS),
           "--output-format", "stream-json", "--verbose"]
    for attempt in range(8):
        t0 = time.perf_counter()
        p = subprocess.run(cmd, input=user.encode("utf-8"), capture_output=True, cwd=w, timeout=1800)
        events = []
        for line in p.stdout.decode("utf-8", "replace").splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        result = next((e for e in events if e.get("type") == "result"), None)
        init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})
        if result and not (result.get("is_error") and result.get("subtype") not in ("error_max_turns",)):
            break
        msg = str((result or {}).get("result", "") or p.stderr.decode("utf-8", "replace"))[:300]
        wait = 600 if any(x in msg.lower() for x in ("limit", "quota", "rate")) else 30 * (attempt + 1)
        log(f"claude {model}: error ({msg[:120]}); waiting {wait} s")
        time.sleep(wait)
    else:
        raise RuntimeError("claude: repeated errors")
    local = ("cwd", "original_cwd", "memory_paths", "messaging_socket_path", "powershell_path")  # paths of the machine
    kept = [{k: v for k, v in e.items() if k not in local} if e.get("type") == "system" else e for e in events]
    (d / "events.jsonl").write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in kept) + "\n", encoding="utf-8", newline="\n")
    if init.get("tools") != TOOLS or init.get("skills") or init.get("slash_commands"):
        raise RuntimeError(f"the session had other tools or skills: {init.get('tools')} {init.get('skills')}")
    calls, first_draft, texts = [], None, []
    for e in events:
        if e.get("type") != "assistant":
            continue
        for c in e.get("message", {}).get("content", []):
            if c.get("type") == "tool_use":
                name = c.get("name", "").removeprefix("mcp__tok__")
                calls.append(name)
                if name == "check" and first_draft is None and isinstance(c.get("input", {}).get("text"), str):
                    first_draft = c["input"]["text"]
            elif c.get("type") == "text":
                texts.append(c.get("text", ""))
    final = result.get("result") or (texts[-1] if texts else "")
    u = result.get("usage", {})
    return {"final": final, "first_draft": first_draft, "calls": calls, "turns": result.get("num_turns"),
            "ended_by_budget": result.get("subtype") == "error_max_turns",
            "input_tokens": u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0),
            "cache_read_tokens": u.get("cache_read_input_tokens", 0), "output_tokens": u.get("output_tokens", 0),
            "first_input_tokens": None, "first_output_tokens": None, "seconds": time.perf_counter() - t0,
            "model_ids": sorted(result.get("modelUsage", {})), "cost_usd": result.get("total_cost_usd"),
            "mcp": init.get("mcp_servers")}


def run_claude_agent(spec, phase_dir):
    model, task_id, r = spec["model"], spec["task"], spec["repetition"]
    run_id = f"{model}__TOKAGENT__{task_id}__r{r}"
    d = phase_dir / "runs" / run_id
    d.mkdir(parents=True, exist_ok=True)
    task = next(t for t in s3_run.TASKS["tasks"] if t["id"] == task_id)
    system = s3c_run.ENVIRONMENT + s3c_run.SKILL.read_text(encoding="utf-8")
    user = s3_run.instruction("TOK", task["text"])
    (d / "system.md").write_text(system, encoding="utf-8", newline="\n")
    (d / "instruction.md").write_text(user, encoding="utf-8", newline="\n")
    a = claude_agent(model, system, user, d)
    final_text, how = s3_run.extract(a["final"], "TOK")
    final = s3c_run.judge_tok(d, "final", final_text)
    first = s3c_run.judge_tok(d, "first", a["first_draft"]) if a["first_draft"] else final
    out = {"run": run_id, "model": model, "rep": "TOKAGENT", "task": task_id, "repetition": r,
           "attempts": a["turns"], "tool_calls": len(a["calls"]),
           "tool_calls_by_name": {n: a["calls"].count(n) for n in s3c_run.TOOLS},
           "ended_by_budget": a["ended_by_budget"], "extracted": how,
           "loop_ok": final["errors"] == 0 and final["warnings"] == 0, "final_codes": final["codes"],
           "valid_first": first["judge"]["valid"], "valid_final": final["judge"]["valid"],
           "final_bpmn": str(final["bpmn"].relative_to(phase_dir)).replace("\\", "/") if final["bpmn"] else None,
           "first_bpmn": str(first["bpmn"].relative_to(phase_dir)).replace("\\", "/") if first["bpmn"] else None,
           "input_tokens": a["input_tokens"], "cache_read_tokens": a["cache_read_tokens"], "output_tokens": a["output_tokens"],
           "first_input_tokens": 0, "first_output_tokens": 0, "seconds": a["seconds"], "model_ids": a["model_ids"],
           "cost_usd": a["cost_usd"], "mcp": a["mcp"], "date": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "final_judge": final["judge"], "first_judge": first["judge"]}
    (d / "run.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8", newline="\n")
    with _lock:
        append_jsonl(phase_dir / "runs.jsonl", json.loads(json.dumps(out, default=str)))
    return out


# ------------------------------------------------------------------ Beam from the cold start (harness of S3)

def call_beam(model, system, user, seed):
    d = s3c_run.chat(model, [{"role": "system", "content": system}, {"role": "user", "content": user}], [])
    m = d.get("message", {})
    with _lock:
        append_jsonl(_phase_dir / "calls.jsonl", {"date": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "model": d.get("model"),
                                                 "prompt_sha256": sha256(user.encode()), "done_reason": d.get("done_reason"),
                                                 "prompt_eval_count": d.get("prompt_eval_count"), "eval_count": d.get("eval_count"),
                                                 "thinking": m.get("thinking") or ""})
    return {"text": m.get("content", ""), "input_tokens": d.get("prompt_eval_count", 0), "cache_read_tokens": 0,
            "output_tokens": d.get("eval_count", 0), "thinking_tokens": None, "seconds": d["_seconds"],
            "model_ids": [d.get("model")], "seed": None, "done_reason": d.get("done_reason")}


s3_run.call_model = call_beam


def frozen():
    files = [Path(__file__), ROOT / "scripts" / "s3c_run.py", ROOT / "scripts" / "s3_run.py", ROOT / "scripts" / "bpmn_graph.py",
             ROOT / "scripts" / "lint.mjs", s3c_run.TOK, s3c_run.TOK_MCP, s3c_run.SKILL]
    out = {str(p.relative_to(ROOT)).replace("\\", "/"): sha256(p.read_bytes()) for p in files}
    out.update(s3_run.frozen())
    return out


def main():
    global _phase_dir
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["feasibility", "main"], required=True)
    ap.add_argument("--part", choices=["claude", "beam", "all"], default="all")
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()
    _phase_dir = phase_dir = RESULTS / "S3d" / args.phase
    phase_dir.mkdir(parents=True, exist_ok=True)
    fz, now = phase_dir / "frozen.json", frozen()
    if args.phase == "main" and fz.exists() and json.loads(fz.read_text()) != now:
        raise SystemExit("the harness, the skill or the tok programs changed after the study started")
    fz.write_text(json.dumps(now, indent=1), encoding="utf-8", newline="\n")
    tasks = s3_run.TASKS["pilot"] if args.phase == "feasibility" else s3_run.TASKS["main"]
    specs = []
    if args.part in ("claude", "all"):
        specs += [{"kind": "claude", "model": m, "rep": "TOKAGENT", "task": t, "repetition": 1} for m in CLAUDE for t in tasks]
    if args.part in ("beam", "all"):
        specs += [{"kind": "beam-agent", "model": BEAM, "rep": "TOKAGENT", "task": t, "repetition": 1} for t in tasks]
        reps = 1 if args.phase == "feasibility" else 2  # the cold start as in S3b; the agent arms have one repetition, as in S3c
        specs += [{"kind": "beam-cold", "model": BEAM, "rep": rp, "task": t, "repetition": r}
                  for rp in ("XML", "TOK") for t in tasks for r in range(1, reps + 1)]
    random.Random(s3_run.ORDER_SEED).shuffle(specs)
    rid = lambda s: f"{s['model'].replace(':', '-')}__{s['rep']}__{s['task']}__r{s['repetition']}"
    done = {x["run"] for x in read_jsonl(phase_dir / "runs.jsonl")}
    todo = [s for s in specs if rid(s) not in done]
    log(f"S3d {args.phase}: {len(specs)} runs, {len(todo)} to do")
    counter = {"n": 0}

    def safe(s):
        try:
            if s["kind"] == "claude":
                r = run_claude_agent(s, phase_dir)
            elif s["kind"] == "beam-agent":
                r = s3c_run.run_one(s, phase_dir)
            else:
                r = s3_run.run_one(s, phase_dir)
            counter["n"] += 1
            log(f"[{counter['n']}/{len(todo)}] {r['run']}: calls {r['attempts']}, tools {r.get('tool_calls_by_name', '-')}, "
                f"valid first {r['valid_first']}, final {r['valid_final']}, tokens {r['input_tokens']}+{r['output_tokens']}, {r['seconds']:.0f} s")
        except s3c_run.ProviderLimit as ex:
            log(f"run {rid(s)}: {ex}; left for a resumed run")
        except Exception as ex:
            log(f"run {rid(s)} failed: {type(ex).__name__}: {ex}")

    pools = {k: ThreadPoolExecutor(args.workers) for k in ("claude", "beam-agent", "beam-cold")}
    for f in [pools[s["kind"]].submit(safe, s) for s in todo]:
        f.result()
    log("finished")


if __name__ == "__main__":
    main()
