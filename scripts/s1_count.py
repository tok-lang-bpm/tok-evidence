"""S1, step 2: characters, lines, bytes and tokens of every variant (PROTOCOL.md §4.1).

Reads results/S1/variants/, writes results/S1/raw/counts.csv.

    .venv/Scripts/python scripts/s1_count.py [--workers 8]
"""

import argparse
import csv
from concurrent.futures import ProcessPoolExecutor

from common import RESULTS, TOKENIZERS, load_tokenizers, log

VAR = RESULTS / "S1" / "variants"
_tk = None


def _init():
    global _tk
    _tk = load_tokenizers()


def count(path):
    data = path.read_bytes()
    text = data.decode("utf-8", "replace")
    corpus, model, variant = path.relative_to(VAR).parts[0], "/".join(path.relative_to(VAR).parts[1:-1]), path.name
    row = {"corpus": corpus, "model": model, "variant": variant, "bytes": len(data), "chars": len(text),
           "lines": text.count("\n") + (0 if text.endswith("\n") or not text else 1)}
    for name in TOKENIZERS:
        row[name] = _tk[name](text)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    files = sorted(p for p in VAR.rglob("*") if p.is_file())
    log(f"{len(files)} variant files")
    out = RESULTS / "S1" / "raw" / "counts.csv"
    with ProcessPoolExecutor(args.workers, initializer=_init) as ex, out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, ["corpus", "model", "variant", "bytes", "chars", "lines", *TOKENIZERS])
        w.writeheader()
        for i, row in enumerate(ex.map(count, files, chunksize=32)):
            w.writerow(row)
            if i % 1000 == 0:
                log(f"{i} counted")
    log(f"written {out}")


if __name__ == "__main__":
    main()
