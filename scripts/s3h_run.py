"""S3h: the held-out tasks of the PMo dataset (PROTOCOL-S3h.md).

The design of the language-model study on new texts: Claude Haiku 5.5, Claude Sonnet 5.5,
gpt-oss 120B and Beam, each in the three arms of S3, S3c and S3d, one repetition:

- `XML`, `TOK`: the reference arms, the harness of S3 (scripts/s3_run.py, unchanged; tok 1.0.2);
- `TOKAGENT`: the agent arm, the skill and the MCP server of tok 1.0.3, the harness of S3c for
  the Ollama models (scripts/s3c_run.py, unchanged) and of S3d for Claude (scripts/s3d_run.py,
  unchanged).

Claude runs through the Claude command line, gpt-oss and Beam through Ollama.

    .venv/Scripts/python scripts/s3h_run.py --phase feasibility|main [--workers 2]

Writes results/S3h/<phase>/runs/<run>/ and results/S3h/<phase>/runs.jsonl. Resumable.
"""

import argparse
import json
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import s3_run
import s3c_run
import s3d_run
from common import RESULTS, ROOT, log, read_jsonl, sha256

TASKS_FILE = ROOT / "data" / "derived" / "pmo" / "tasks.json"
s3_run.TASKS = json.load(open(TASKS_FILE, encoding="utf-8"))
CLAUDE = ("haiku", "sonnet")
OLLAMA = ("gpt-oss:120b-cloud", "beam:cloud")
ARMS = ("XML", "TOK", "TOKAGENT")


def call_model(model, system, user, seed):
    return s3_run.call_claude(model, system, user) if model in CLAUDE else s3d_run.call_beam(model, system, user, seed)


s3_run.call_model = call_model


def frozen():
    out = s3d_run.frozen()
    out.update({str(p.relative_to(ROOT)).replace("\\", "/"): sha256(p.read_bytes())
                for p in (Path(__file__), ROOT / "scripts" / "s3d_run.py", ROOT / "scripts" / "pmo_gold.py", TASKS_FILE)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["feasibility", "main"], required=True)
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()
    phase_dir = RESULTS / "S3h" / args.phase
    phase_dir.mkdir(parents=True, exist_ok=True)
    s3d_run._phase_dir = phase_dir  # the provider's record of the Ollama calls of the reference arms
    fz, now = phase_dir / "frozen.json", frozen()
    if args.phase == "main" and fz.exists() and json.loads(fz.read_text()) != now:
        raise SystemExit("the harness, the tasks, the skill or the tok programs changed after the study started")
    fz.write_text(json.dumps(now, indent=1), encoding="utf-8", newline="\n")
    tasks = s3_run.TASKS["pilot"] if args.phase == "feasibility" else s3_run.TASKS["main"]
    specs = [{"model": m, "rep": a, "task": t, "repetition": 1} for m in CLAUDE + OLLAMA for a in ARMS for t in tasks]
    random.Random(s3_run.ORDER_SEED).shuffle(specs)
    rid = lambda s: f"{s['model'].replace(':', '-')}__{s['rep']}__{s['task']}__r{s['repetition']}"
    done = {x["run"] for x in read_jsonl(phase_dir / "runs.jsonl")}
    todo = [s for s in specs if rid(s) not in done]
    log(f"S3h {args.phase}: {len(specs)} runs, {len(todo)} to do")
    counter = {"n": 0}

    def safe(s):
        try:
            if s["rep"] != "TOKAGENT":
                r = s3_run.run_one(s, phase_dir)
            elif s["model"] in CLAUDE:
                r = s3d_run.run_claude_agent(s, phase_dir)
            else:
                r = s3c_run.run_one(s, phase_dir)
            counter["n"] += 1
            log(f"[{counter['n']}/{len(todo)}] {r['run']}: calls {r['attempts']}, tools {r.get('tool_calls_by_name', '-')}, "
                f"valid first {r['valid_first']}, final {r['valid_final']}, tokens {r['input_tokens']}+{r['output_tokens']}, {r['seconds']:.0f} s")
        except s3c_run.ProviderLimit as ex:
            log(f"run {rid(s)}: {ex}; left for a resumed run")
        except Exception as ex:
            log(f"run {rid(s)} failed: {type(ex).__name__}: {ex}")

    pools = {"claude": ThreadPoolExecutor(3)} | {m: ThreadPoolExecutor(args.workers) for m in OLLAMA}
    for f in [pools["claude" if s["model"] in CLAUDE else s["model"]].submit(safe, s) for s in todo]:
        f.result()
    log("finished")


if __name__ == "__main__":
    main()
