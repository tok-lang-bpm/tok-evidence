"""S3b: open-weight models through Ollama cloud (PROTOCOL-S3b.md).

Uses the harness of the main study, scripts/s3_run.py, unchanged, and replaces only its model
call. Before any run the checksums of the prompts and the harness are compared with
results/S3/main/frozen.json.

    .venv/Scripts/python scripts/s3b_run.py [--models gpt-oss:120b-cloud,gemma4:31b-cloud,nemotron-3-super:cloud]
        [--workers 2]

Writes results/S3b/main/runs/<run>/ and results/S3b/main/runs.jsonl. Resumable.
"""

import argparse
import json
import random
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import s3_run
from common import RESULTS, append_jsonl, log, read_jsonl, sha256

MODELS = "gpt-oss:120b-cloud,gemma4:31b-cloud,nemotron-3-super:cloud"
_calls_lock = threading.Lock()
OLLAMA = "http://127.0.0.1:11434/api/chat"
LIMIT_WAIT = 900  # seconds after HTTP 429
LIMIT_TRIES = 8


class ProviderLimit(RuntimeError):
    pass


def call_ollama_cloud(model, system, user, seed):
    body = {"model": model, "stream": False,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    errors = limits = 0
    while True:
        t0 = time.perf_counter()
        req = urllib.request.Request(OLLAMA, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=900) as r:
                d = json.loads(r.read())
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
            continue
        except Exception as e:  # timeouts, broken connections
            errors += 1
            if errors > 3:
                raise
            log(f"{model}: {type(e).__name__}: {str(e)[:120]}; waiting {30 * errors} s")
            time.sleep(30 * errors)
            continue
        m = d.get("message", {})
        with _calls_lock:  # the provider's record of the call, with the reasoning text (s3_run keeps the answer)
            append_jsonl(RESULTS / "S3b" / "main" / "calls.jsonl", {
                "date": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "model": d.get("model"), "prompt_sha256": sha256(user.encode()),
                **{k: d.get(k) for k in ("done_reason", "prompt_eval_count", "eval_count", "total_duration", "load_duration",
                                         "prompt_eval_duration", "eval_duration")},
                "thinking": m.get("thinking") or ""})
        return {"text": m.get("content", ""), "input_tokens": d.get("prompt_eval_count", 0), "cache_read_tokens": 0,
                "output_tokens": d.get("eval_count", 0), "thinking_tokens": None, "seconds": time.perf_counter() - t0,
                "model_ids": [d.get("model")], "seed": None, "done_reason": d.get("done_reason"),
                "thinking_chars": len(m.get("thinking") or "")}


s3_run.call_model = call_ollama_cloud


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=MODELS)
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()
    models = args.models.split(",")
    phase_dir = RESULTS / "S3b" / "main"
    phase_dir.mkdir(parents=True, exist_ok=True)

    main_frozen = json.loads((RESULTS / "S3" / "main" / "frozen.json").read_text())
    if s3_run.frozen() != main_frozen:
        raise SystemExit("the prompts or the harness differ from the main study")
    now = dict(main_frozen, **{"scripts/s3b_run.py": sha256(Path(__file__).read_bytes())})
    fz = phase_dir / "frozen.json"
    if fz.exists() and json.loads(fz.read_text()) != now:
        raise SystemExit("the harness of S3b changed after the study started")
    fz.write_text(json.dumps(now, indent=1), encoding="utf-8", newline="\n")

    specs = [{"model": m, "rep": rp, "task": t, "repetition": r}
             for m in models for rp in ("XML", "TOK") for t in s3_run.TASKS["main"] for r in (1, 2)]
    random.Random(s3_run.ORDER_SEED).shuffle(specs)
    done = {x["run"] for x in read_jsonl(phase_dir / "runs.jsonl")}
    rid = lambda s: f"{s['model'].replace(':', '-')}__{s['rep']}__{s['task']}__r{s['repetition']}"
    todo = [s for s in specs if rid(s) not in done]
    log(f"S3b: {len(specs)} runs, {len(todo)} to do; models {models}")
    counter = {"n": 0}
    stopped = set()

    def safe(s):
        if s["model"] in stopped:
            return
        try:
            r = s3_run.run_one(s, phase_dir)
            counter["n"] += 1
            log(f"[{counter['n']}/{len(todo)}] {r['run']}: attempts {r['attempts']}, valid first {r['valid_first']}, "
                f"final {r['valid_final']}, tokens {r['input_tokens']}+{r['output_tokens']}, {r['seconds']:.0f} s")
        except ProviderLimit as ex:
            stopped.add(s["model"])
            log(f"run {rid(s)}: {ex}; the remaining runs of {s['model']} are left for a resumed run")
        except Exception as ex:
            log(f"run {rid(s)} failed: {type(ex).__name__}: {ex}")

    pools = {m: ThreadPoolExecutor(args.workers) for m in models}
    fut = [pools[s["model"]].submit(safe, s) for s in todo]
    for f in fut:
        f.result()
    for p in pools.values():
        p.shutdown()
    log("finished")


if __name__ == "__main__":
    main()
