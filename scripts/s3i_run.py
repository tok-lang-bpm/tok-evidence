"""S3i: skills and tools of the agent arm (PROTOCOL-S3i.md; pilot §1–7, main phase §8).

Agent arms on the held-out PMo texts, with tok 1.0.3 unchanged:

- `TOKAGENT-B`: the tok skill (SKILL.md of tok 1.0.3) with the one-page reference of the reference
  arm appended, and the tool `check` only (pilot);
- `TOKAGENT-C`: a lean skill (prompts/skill-lean-tok.md) with the same one-page reference, and the
  tool `check` only (pilot, main);
- `XMLAGENT-A`: the BPMN XML skill of tok 1.0.3 with the one-page BPMN XML reference of the
  reference arm appended, and the tool `check_bpmn` only (pilot, main);
- `XMLAGENT-C`: the lean BPMN XML skill (prompts/skill-lean-xml.md, the mirror of the lean tok
  skill) with the same BPMN XML reference, and the tool `check_bpmn` only (main).

Claude models run through the Claude command line (as S3d), the Ollama models (gpt-oss, Beam)
through scripts/s3c_run.py's MCP client (as S3c). The judge is the judge of S3.

    .venv/Scripts/python scripts/s3i_run.py --phase feasibility|pilot|main [--models sonnet,haiku,gpt-oss:120b-cloud,beam:cloud]
        [--arms TOKAGENT-C,XMLAGENT-A,XMLAGENT-C] [--workers 2]

The pilot ran 15 texts (seed 20261030) with the arms TOKAGENT-B, TOKAGENT-C and XMLAGENT-A on
Sonnet, Haiku and gpt-oss; the main phase runs the 45 held-out texts with the arms TOKAGENT-C,
XMLAGENT-A and XMLAGENT-C on the four models. Writes results/S3i/<phase>/runs/<run>/ and
results/S3i/<phase>/runs.jsonl. Resumable.
"""

import argparse
import json
import random
import subprocess
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import s3_run
import s3c_run
from common import RESULTS, ROOT, append_jsonl, log, read_jsonl, sha256

BIN = s3c_run.BIN
RELEASE = ROOT / "tools" / "bin" / "tok-1.0.3-windows-x86_64"  # the released 1.0.3, whose MCP server has check_bpmn
MCP_BINARY = {"TOK": s3c_run.TOK_MCP, "XML": RELEASE / "tok-mcp.exe"}
SKILL_TOK, SKILL_BPMN = s3c_run.SKILL, BIN / "SKILL-bpmn.md"
SKILL_LEAN = ROOT / "prompts" / "skill-lean-tok.md"
SKILL_LEAN_XML = ROOT / "prompts" / "skill-lean-xml.md"
PROMPTS = ROOT / "prompts"
TASKS = json.load(open(ROOT / "data" / "derived" / "pmo" / "tasks.json", encoding="utf-8"))  # PMo (feasibility, pilot, main)
TASK_SETS = {"feasibility": TASKS, "pilot": TASKS, "main": TASKS, "pet": s3_run.TASKS}  # PET for the phase pet (§9)
PILOT_TASKS = sorted(random.Random(20261030).sample(TASKS["main"], 15))
CLAUDE = {"haiku": "haiku", "sonnet": "sonnet"}
MAX_CALLS = s3c_run.MAX_CALLS
s3c_run.TOOLS = ("check", "fmt", "reference", "check_bpmn")  # the superset the MCP client may list; each arm narrows it
_lock = threading.Lock()


def read(p):
    return p.read_text(encoding="utf-8")


def tok_reference():
    return read(PROMPTS / "cheatsheet-tok-1.0.1.md") + read(PROMPTS / "reference-tok-example.md").replace(
        "EXAMPLE", read(PROMPTS / "examples" / "application.tok").strip())


def xml_reference():
    return read(PROMPTS / "reference-xml.md").replace("EXAMPLE", read(PROMPTS / "examples" / "application.bpmn").strip())


ENV_TOK = """## Environment of this session

You work through the tool `check` of the tok MCP server. There are no file tools and no shell: give the
document to the tool as `text`, and give your final model in your last answer, in one fenced code block
marked ```tok. The person you work for reads only that answer. The reference of the language is included
below; no other reference is available.

"""
ENV_XML = """## Environment of this session

You work through the tool `check_bpmn` of the tok MCP server, which checks BPMN 2.0 XML with the rules of
the standard: give the XML to the tool as `xml`. Where the skill says `tok check FILE.bpmn`, call
`check_bpmn`. There are no file tools and no shell, and the files `references/...` named in the skill are
not available; the BPMN XML reference included below replaces them. Give your final model in your last
answer, in one fenced code block marked ```xml. The person you work for reads only that answer.

"""
ARMS = {
    "TOKAGENT-B": {"rep": "TOK", "tools": ("check",), "system": lambda: ENV_TOK + read(SKILL_TOK) + "\n\n## Language reference\n\n" + tok_reference()},
    "TOKAGENT-C": {"rep": "TOK", "tools": ("check",), "system": lambda: ENV_TOK + read(SKILL_LEAN) + "\n\n## Language reference\n\n" + tok_reference()},
    "XMLAGENT-A": {"rep": "XML", "tools": ("check_bpmn",), "system": lambda: ENV_XML + read(SKILL_BPMN) + "\n\n## BPMN XML reference\n\n" + xml_reference()},
    "XMLAGENT-C": {"rep": "XML", "tools": ("check_bpmn",), "system": lambda: ENV_XML + read(SKILL_LEAN_XML) + "\n\n## BPMN XML reference\n\n" + xml_reference()},
}
PHASE_ARMS = {"feasibility": ("TOKAGENT-B", "TOKAGENT-C", "XMLAGENT-A"), "pilot": ("TOKAGENT-B", "TOKAGENT-C", "XMLAGENT-A"),
              "main": ("TOKAGENT-C", "XMLAGENT-A", "XMLAGENT-C"), "pet": ("TOKAGENT-C", "XMLAGENT-A", "XMLAGENT-C")}
PHASE_MODELS = {"feasibility": ("sonnet", "haiku", "gpt-oss:120b-cloud"), "pilot": ("sonnet", "haiku", "gpt-oss:120b-cloud"),
                "main": ("sonnet", "haiku", "gpt-oss:120b-cloud", "beam:cloud"), "pet": ("sonnet", "haiku", "gpt-oss:120b-cloud", "beam:cloud")}
DRAFT_ARG = {"check": "text", "check_bpmn": "xml"}


class Server(s3c_run.McpServer):
    """The MCP client of S3c, started on a given tok-mcp binary."""

    def __init__(self, binary):
        self.dir = Path(tempfile.mkdtemp(prefix="tok-evidence-s3i-"))
        self.p = subprocess.Popen([str(binary)], cwd=self.dir, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.n = 0
        init = self.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "tok-evidence", "version": "1"}})
        self.server = init.get("serverInfo")
        self.notify("notifications/initialized")
        self.tools = self.request("tools/list")["tools"]


# ------------------------------------------------------------------ judging

def judge(d, name, text, rep):
    if rep == "TOK":
        return s3c_run.judge_tok(d, name, text)
    path = d / f"{name}.bpmn"
    path.write_text(text, encoding="utf-8", newline="\n")
    return {"errors": None, "warnings": None, "codes": [], "bpmn": path, "judge": s3_run.judge(path)}


def record(d, phase_dir, spec, a, first_draft, turns_n, calls, tools):
    arm = ARMS[spec["arm"]]
    final_text, how = s3_run.extract(a["final"], arm["rep"])
    final = judge(d, "final", final_text, arm["rep"])
    first = judge(d, "first", first_draft, arm["rep"]) if first_draft else final
    out = {"run": spec["run"], "model": spec["model"], "rep": spec["arm"], "task": spec["task"], "repetition": 1,
           "attempts": turns_n, "tool_calls": len(calls), "tool_calls_by_name": {n: calls.count(n) for n in tools},
           "ended_by_budget": a["ended_by_budget"], "extracted": how,
           "loop_ok": (final["errors"] == 0 and final["warnings"] == 0) if final["errors"] is not None else final["judge"]["valid"],
           "final_codes": final["codes"], "valid_first": first["judge"]["valid"], "valid_final": final["judge"]["valid"],
           "final_bpmn": str(final["bpmn"].relative_to(phase_dir)).replace("\\", "/") if final["bpmn"] else None,
           "first_bpmn": str(first["bpmn"].relative_to(phase_dir)).replace("\\", "/") if first["bpmn"] else None,
           "input_tokens": a["input_tokens"], "cache_read_tokens": a["cache_read_tokens"], "output_tokens": a["output_tokens"],
           "first_input_tokens": 0, "first_output_tokens": 0, "seconds": a["seconds"], "model_ids": a["model_ids"],
           "cost_usd": a.get("cost_usd"), "date": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "final_judge": final["judge"], "first_judge": first["judge"]}
    (d / "run.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8", newline="\n")
    with _lock:
        append_jsonl(phase_dir / "runs.jsonl", json.loads(json.dumps(out, default=str)))
    return out


# ------------------------------------------------------------------ Ollama agent (client of S3c)

def task_of(spec):
    return next(t for t in TASK_SETS[spec["phase"]]["tasks"] if t["id"] == spec["task"])


def run_ollama(spec, phase_dir):
    arm = ARMS[spec["arm"]]
    d = phase_dir / "runs" / spec["run"]
    d.mkdir(parents=True, exist_ok=True)
    task = task_of(spec)
    system, user = arm["system"](), s3_run.instruction(arm["rep"], task["text"])
    (d / "system.md").write_text(system, encoding="utf-8", newline="\n")
    (d / "instruction.md").write_text(user, encoding="utf-8", newline="\n")
    server = Server(MCP_BINARY[arm["rep"]])
    server.tools = [t for t in server.tools if t["name"] in arm["tools"]]
    tools = s3c_run.ollama_tools(server)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    turns, first_draft, calls, t0 = [], None, [], time.perf_counter()
    try:
        for k in range(1, MAX_CALLS + 1):
            resp = s3c_run.chat(spec["model"], messages, tools)
            m = resp.get("message", {})
            tool_calls = m.get("tool_calls") or []
            turn = {"call": k, "input_tokens": resp.get("prompt_eval_count", 0), "output_tokens": resp.get("eval_count", 0),
                    "seconds": resp["_seconds"], "model": resp.get("model"), "done_reason": resp.get("done_reason"),
                    "content": m.get("content", ""), "thinking": m.get("thinking") or "", "tool_calls": []}
            messages.append({"role": "assistant", "content": m.get("content", ""),
                             **({"tool_calls": tool_calls} if tool_calls else {}), **({"thinking": m["thinking"]} if m.get("thinking") else {})})
            for c in tool_calls:
                fn = c.get("function", {})
                name, args = fn.get("name"), fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                if name in arm["tools"]:
                    out = server.call(name, args)
                else:
                    out = {"isError": True, "text": f"unknown tool {name!r}; the tool is {', '.join(arm['tools'])}"}
                text = out["text"][:s3c_run.MAX_TOOL_TEXT]
                turn["tool_calls"].append({"name": name, "arguments": args, "is_error": out["isError"], "result": text})
                calls.append(name)
                if name in DRAFT_ARG and first_draft is None and isinstance(args.get(DRAFT_ARG[name]), str):
                    first_draft = args[DRAFT_ARG[name]]
                messages.append({"role": "tool", "tool_name": name, "content": text})
            turns.append(turn)
            if not tool_calls:
                break
    finally:
        server.close()
    (d / "transcript.json").write_text(json.dumps(turns, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    a = {"final": turns[-1]["content"] if turns else "", "ended_by_budget": bool(turns and turns[-1]["tool_calls"]),
         "input_tokens": sum(t["input_tokens"] or 0 for t in turns), "cache_read_tokens": 0,
         "output_tokens": sum(t["output_tokens"] or 0 for t in turns), "seconds": time.perf_counter() - t0,
         "model_ids": sorted({t["model"] for t in turns if t["model"]})}
    return record(d, phase_dir, spec, a, first_draft, len(turns), calls, arm["tools"])


# ------------------------------------------------------------------ Claude agent (command line, as S3d)

ALL_MCP = ["check", "check_bpmn", "fmt", "export", "import", "sim", "eval", "reference"]


def run_claude(spec, phase_dir):
    arm = ARMS[spec["arm"]]
    d = phase_dir / "runs" / spec["run"]
    d.mkdir(parents=True, exist_ok=True)
    task = task_of(spec)
    system, user = arm["system"](), s3_run.instruction(arm["rep"], task["text"])
    (d / "system.md").write_text(system, encoding="utf-8", newline="\n")
    (d / "instruction.md").write_text(user, encoding="utf-8", newline="\n")
    allowed = ["mcp__tok__" + t for t in arm["tools"]]
    other = ["mcp__tok__" + t for t in ALL_MCP if t not in arm["tools"]]
    w = Path(tempfile.mkdtemp(prefix="tok-evidence-s3i-"))
    (w / "system.md").write_text(system, encoding="utf-8", newline="\n")
    (w / "mcp.json").write_text(json.dumps({"mcpServers": {"tok": {"command": str(MCP_BINARY[arm["rep"]]), "args": []}}}), encoding="utf-8")
    cmd = ["claude", "-p", "--model", CLAUDE[spec["model"]], "--system-prompt-file", str(w / "system.md"), "--mcp-config", str(w / "mcp.json"),
           "--strict-mcp-config", "--tools", "", "--allowedTools", ",".join(allowed), "--disallowedTools", ",".join(other),
           "--disable-slash-commands", "--no-session-persistence", "--max-turns", str(MAX_CALLS),
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
        log(f"claude {spec['model']}: error ({msg[:120]}); waiting {wait} s")
        time.sleep(wait)
    else:
        raise RuntimeError("claude: repeated errors")
    local = ("cwd", "original_cwd", "memory_paths", "messaging_socket_path", "powershell_path")
    kept = [{k: v for k, v in e.items() if k not in local} if e.get("type") == "system" else e for e in events]
    (d / "events.jsonl").write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in kept) + "\n", encoding="utf-8", newline="\n")
    if init.get("tools") != allowed or init.get("skills") or init.get("slash_commands"):
        raise RuntimeError(f"the session had other tools or skills: {init.get('tools')} {init.get('skills')}")
    calls, first_draft, texts = [], None, []
    for e in events:
        if e.get("type") != "assistant":
            continue
        for c in e.get("message", {}).get("content", []):
            if c.get("type") == "tool_use":
                name = c.get("name", "").removeprefix("mcp__tok__")
                calls.append(name)
                if name in DRAFT_ARG and first_draft is None and isinstance(c.get("input", {}).get(DRAFT_ARG[name]), str):
                    first_draft = c["input"][DRAFT_ARG[name]]
            elif c.get("type") == "text":
                texts.append(c.get("text", ""))
    u = result.get("usage", {})
    a = {"final": result.get("result") or (texts[-1] if texts else ""), "ended_by_budget": result.get("subtype") == "error_max_turns",
         "input_tokens": u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0),
         "cache_read_tokens": u.get("cache_read_input_tokens", 0), "output_tokens": u.get("output_tokens", 0),
         "seconds": time.perf_counter() - t0, "model_ids": sorted(result.get("modelUsage", {})), "cost_usd": result.get("total_cost_usd")}
    return record(d, phase_dir, spec, a, first_draft, result.get("num_turns"), calls, arm["tools"])


# ------------------------------------------------------------------ main

def frozen():
    files = [Path(__file__), ROOT / "scripts" / "s3c_run.py", ROOT / "scripts" / "s3_run.py", ROOT / "scripts" / "bpmn_graph.py",
             ROOT / "scripts" / "lint.mjs", ROOT / "prompts" / "instruction.md", SKILL_TOK, SKILL_BPMN, SKILL_LEAN, SKILL_LEAN_XML,
             s3c_run.TOK, s3c_run.TOK_MCP, RELEASE / "tok-mcp.exe", RELEASE / "tok.exe", ROOT / "data" / "derived" / "pmo" / "tasks.json",
             ROOT / "data" / "derived" / "pet" / "tasks.json"]
    out = {str(p.relative_to(ROOT)).replace("\\", "/"): sha256(p.read_bytes()) for p in files}
    for a in ARMS:
        out[f"system:{a}"] = sha256(ARMS[a]["system"]().encode())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["feasibility", "pilot", "main", "pet"], required=True)
    ap.add_argument("--models", default=None)
    ap.add_argument("--arms", default=None)
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()
    phase_dir = RESULTS / "S3i" / args.phase
    phase_dir.mkdir(parents=True, exist_ok=True)
    fz, now = phase_dir / "frozen.json", frozen()
    if args.phase in ("pilot", "main", "pet") and fz.exists() and json.loads(fz.read_text()) != now:
        raise SystemExit(f"the harness, the skills or the tok programs changed after the {args.phase} started")
    fz.write_text(json.dumps(now, indent=1), encoding="utf-8", newline="\n")
    tasks = (TASKS["pilot"][:2] if args.phase == "feasibility" else TASK_SETS[args.phase]["main"] if args.phase in ("main", "pet")
             else PILOT_TASKS)
    models = args.models.split(",") if args.models else list(PHASE_MODELS[args.phase])
    arms = args.arms.split(",") if args.arms else list(PHASE_ARMS[args.phase])
    specs = [{"model": m, "arm": a, "task": t, "phase": args.phase} for m in models for a in arms for t in tasks]
    for s in specs:
        s["run"] = f"{s['model'].replace(':', '-')}__{s['arm']}__{s['task']}__r1"
    random.Random(s3_run.ORDER_SEED).shuffle(specs)
    done = {x["run"] for x in read_jsonl(phase_dir / "runs.jsonl")}
    todo = [s for s in specs if s["run"] not in done]
    log(f"S3i {args.phase}: {len(specs)} runs, {len(todo)} to do; tasks {tasks}")
    counter = {"n": 0}

    def safe(s):
        try:
            r = run_claude(s, phase_dir) if s["model"] in CLAUDE else run_ollama(s, phase_dir)
            counter["n"] += 1
            log(f"[{counter['n']}/{len(todo)}] {r['run']}: calls {r['attempts']}, tools {r['tool_calls_by_name']}, valid first {r['valid_first']}, "
                f"final {r['valid_final']}, tokens {r['input_tokens']}+{r['output_tokens']}, {r['seconds']:.0f} s")
        except s3c_run.ProviderLimit as ex:
            log(f"run {s['run']}: {ex}; left for a resumed run")
        except Exception as ex:
            log(f"run {s['run']} failed: {type(ex).__name__}: {ex}")

    pools = {"claude": ThreadPoolExecutor(3)} | {m: ThreadPoolExecutor(args.workers) for m in models if m not in CLAUDE}
    for f in [pools["claude" if s["model"] in CLAUDE else s["model"]].submit(safe, s) for s in todo]:
        f.result()
    log("finished")


if __name__ == "__main__":
    main()
