"""S4: performance of the released program (PROTOCOL.md §7).

Every operation is a separate start of the program, timed from outside, five times; the
median is reported. Corpus models (N and R) and generated models of n flow nodes
(`tok_bench::process(n)` of the tagged sources, written by `tok-bench`'s example
`generate`), n = 10 … 3 000.

    .venv/Scripts/python scripts/s4_perf.py --generator PATH_TO_generate.exe
"""

import argparse
import json
import shutil
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np

from common import RESULTS, TOK, log, read_jsonl, write_json

S4 = RESULTS / "S4"
SIZES = [10, 30, 100, 300, 1000, 3000]
RUNS = 5


def timed(args, cwd):
    t0 = time.perf_counter()
    p = subprocess.run([str(TOK), *args], cwd=cwd, capture_output=True)
    return time.perf_counter() - t0, p.returncode


def bench(file: Path, ops, work: Path):
    out = {}
    for op in ops:
        args = {"check": ["check", file.name], "fmt": ["fmt", file.name], "bpmn": ["bpmn", file.name, "-o", "o.bpmn"],
                "bpmn-nolayout": ["bpmn", "--no-layout", file.name, "-o", "s.bpmn"], "svg": ["svg", file.name, "-o", "o.svg"],
                "import": ["import", file.name, "-o", "imported.tok"]}[op]
        ts, codes = [], set()
        for _ in range(RUNS):
            dt, code = timed(args, work)
            ts.append(dt)
            codes.add(code)
        out[op] = {"median_s": statistics.median(ts), "min_s": min(ts), "max_s": max(ts), "exit": sorted(codes)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--generator", required=True)
    args = ap.parse_args()
    S4.mkdir(parents=True, exist_ok=True)
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        # the start of the program alone
        t = [timed(["--version"], work)[0] for _ in range(20)]
        startup = {"median_s": statistics.median(t), "min_s": min(t)}
        log(f"start of the program: {startup['median_s'] * 1000:.1f} ms")
        files = read_jsonl(RESULTS / "S1" / "raw" / "files.jsonl")
        for r in files:
            if r["status"] != "ok" or r["corpus"] not in ("N", "R"):
                continue
            src = RESULTS / "S1" / "variants" / r["corpus"] / Path(r["name"]) / ("tok" if r["corpus"] == "N" else "xml")
            f = work / ("m.tok" if r["corpus"] == "N" else "m.bpmn")
            shutil.copy(src, f)
            ops = ["check", "fmt", "bpmn", "svg"] if r["corpus"] == "N" else ["import"]
            rows.append({"set": r["corpus"], "model": r["name"], "flow_nodes": r["flow_nodes"], **{f"{k}_s": v["median_s"] for k, v in bench(f, ops, work).items()}})
        log(f"corpus models: {len(rows)}")
        for n in SIZES:
            text = subprocess.run([args.generator, "process", str(n)], capture_output=True, check=True).stdout
            f = work / "g.tok"
            f.write_bytes(text)
            res = bench(f, ["check", "bpmn-nolayout", "bpmn", "svg"], work)
            nodes = sum(1 for ln in text.decode().splitlines() if ln.split()[:1] and ln.split()[0] in ("start", "end", "user", "task", "xor", "boundary"))
            rows.append({"set": "generated", "model": f"process({n})", "flow_nodes": nodes, "lines": text.count(b"\n"),
                         **{f"{k}_s": v["median_s"] for k, v in res.items()}, "exits": {k: v["exit"] for k, v in res.items()}})
            log(f"process({n}): " + ", ".join(f"{k} {v['median_s'] * 1000:.0f} ms" for k, v in res.items()))
    write_json(S4 / "timings.json", {"startup": startup, "runs_per_measure": RUNS, "rows": rows})
    gen = [r for r in rows if r["set"] == "generated"]
    fits = {}
    for op in ("check", "bpmn-nolayout", "bpmn", "svg"):
        x = np.log([r["flow_nodes"] for r in gen]); y = np.log([r[f"{op}_s"] - startup["min_s"] if r[f"{op}_s"] > startup["min_s"] else r[f"{op}_s"] for r in gen])
        big = [i for i, r in enumerate(gen) if r["flow_nodes"] >= 100]
        b, a = np.polyfit(x[big], y[big], 1)
        fits[op] = {"exponent_n_ge_100": b}
    corpus = [r for r in rows if r["set"] == "N"]
    summary = {"startup_ms": startup["median_s"] * 1000,
               "corpus_N_median_ms": {op: 1000 * statistics.median(r[f"{op}_s"] for r in corpus) for op in ("check", "fmt", "bpmn", "svg")},
               "corpus_N_max_ms": {op: 1000 * max(r[f"{op}_s"] for r in corpus) for op in ("check", "fmt", "bpmn", "svg")},
               "corpus_R_import_median_ms": 1000 * statistics.median(r["import_s"] for r in rows if r["set"] == "R"),
               "generated_ms": {r["model"]: {op: 1000 * r[f"{op}_s"] for op in ("check", "bpmn-nolayout", "bpmn", "svg")} for r in gen},
               "scaling": fits}
    write_json(S4 / "summary.json", summary)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
