"""S7: reading properties of the notation (PROTOCOL-S7.md).

Measures, on the frozen files of S1, how much text a line-by-line reader meets in a tok model and
in the XML of the same model: lines, characters, block depth, line length, statements with an
arrow, keywords. Writes results/S7/tables/*.csv and results/S7/s7-summary.json.

    .venv/Scripts/python scripts/s7_reading.py
"""

import json
import os
import subprocess
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from common import RESULTS, ROOT, SEED, read_jsonl, write_json

TOK = ROOT / "tools" / "bin" / "tok-1.0.3-windows-x86_64" / "tok.exe"
VAR = RESULTS / "S1" / "variants"
OUT = RESULTS / "S7"
TABLES = OUT / "tables"

# corpus -> (file as exported, smallest standard form)
XML_VARIANTS = {
    "N": ("bundle-di", "bundle-sem-min"),
    "V": ("xml", "xml-core-min"),
    "R": ("xml", "xml-core-min"),
    "C": ("xml", "xml-core-min"),
    "D": ("dmn", "dmn-sem-min"),
}
MEASURES = [
    "tok_lines", "tok_statements", "tok_chars", "tok_depth_max", "tok_line_len_max",
    "tok_line_len_mean", "tok_line_len_median", "tok_arrow_lines", "tok_arrow_share",
    "tok_table_rows", "tok_keywords_distinct", "xml_lines", "xml_chars", "core_chars",
    "flow_nodes", "tok_lines_per_node",
]
COMPARISONS = [
    ("xml_lines", "tok_lines", "lines of the file as exported over lines of tok"),
    ("xml_chars", "tok_chars", "characters of the file as exported over characters of tok"),
    ("core_chars", "tok_chars", "characters of the smallest standard form over characters of tok"),
]


def strip_comment(line: str) -> str:
    """The line without its comment: `#` outside a double-quoted string starts a comment."""
    out, in_str, esc = [], False, False
    for ch in line:
        if in_str:
            out.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "#":
            break
        out.append(ch)
    return "".join(out)


def measure_tok(text: str) -> dict:
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    lines = [ln.rstrip("\r") for ln in lines]
    chars = sum(len(ln) for ln in lines)
    statements, depths, lengths, arrows, rows, odd = [], [], [], 0, 0, 0
    keywords: Counter = Counter()
    for ln in lines:
        stripped = ln.strip()
        if not stripped:
            continue
        if stripped.startswith("|"):
            rows += 1
            statements.append(ln)
            lengths.append(len(ln))
            continue
        body = strip_comment(ln)
        if not body.strip():
            continue
        statements.append(ln)
        lengths.append(len(ln))
        indent = len(body) - len(body.lstrip(" "))
        if indent % 2:
            odd += 1
        depths.append(indent // 2)
        kw = body.strip().split()[0]
        keywords[kw] += 1
        if kw in ("flow", "message"):
            arrows += 1
    n = len(statements)
    return {
        "tok_lines": len(lines),
        "tok_statements": n,
        "tok_chars": chars,
        "tok_depth_max": max(depths) if depths else 0,
        "tok_indent_odd_lines": odd,
        "tok_line_len_max": max(lengths) if lengths else 0,
        "tok_line_len_mean": float(np.mean(lengths)) if lengths else 0.0,
        "tok_line_len_median": float(np.median(lengths)) if lengths else 0.0,
        "tok_arrow_lines": arrows,
        "tok_arrow_share": arrows / n if n else 0.0,
        "tok_table_rows": rows,
        "tok_keywords_distinct": len(keywords),
        "_keywords": keywords,
    }


def measure_xml(data: bytes) -> tuple[int, int]:
    text = data.decode("utf-8", "replace")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return len(lines), sum(len(ln.rstrip("\r")) for ln in lines)


def fmt_check(path: Path) -> bool:
    p = subprocess.run([str(TOK), "fmt", str(path), "--check"], capture_output=True,
                       env={**os.environ, "TOK_LANG": "en"}, timeout=120)
    return p.returncode == 0


def geo_ci(r, n_boot=10_000, seed=SEED):
    r = np.asarray(r, float)
    lr = np.log(r)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(lr), size=(n_boot, len(lr)))
    boots = np.exp(lr[idx].mean(axis=1))
    return float(np.exp(lr.mean())), float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))


def main():
    TABLES.mkdir(parents=True, exist_ok=True)
    records = [r for r in read_jsonl(RESULTS / "S1" / "raw" / "files.jsonl") if r.get("status") == "ok"]
    rows, kw_by_corpus, missing = [], {}, []
    for r in records:
        corpus, name = r["corpus"], r["name"]
        d = VAR / corpus / name
        exported, smallest = XML_VARIANTS[corpus]
        tok_path = d / "tok"
        if not tok_path.exists() or not (d / exported).exists() or not (d / smallest).exists():
            missing.append(f"{corpus}/{name}")
            continue
        m = measure_tok(tok_path.read_text(encoding="utf-8"))
        kw_by_corpus.setdefault(corpus, Counter()).update(m.pop("_keywords"))
        xl, xc = measure_xml((d / exported).read_bytes())
        _, cc = measure_xml((d / smallest).read_bytes())
        row = {"corpus": corpus, "model": name, "tool": r.get("tool", ""), "flow_nodes": r.get("flow_nodes"),
               **m, "xml_lines": xl, "xml_chars": xc, "core_chars": cc,
               "tok_canonical": fmt_check(tok_path)}
        row["tok_lines_per_node"] = row["tok_lines"] / row["flow_nodes"] if row["flow_nodes"] else np.nan
        rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(TABLES / "reading-by-model.csv", index=False, encoding="utf-8", lineterminator="\n")

    # summary per corpus and measure
    summ = []
    for corpus, sub in df.groupby("corpus", sort=False):
        for meas in MEASURES:
            v = sub[meas].dropna().astype(float)
            if v.empty:
                continue
            summ.append({"corpus": corpus, "measure": meas, "files": int(v.size), "mean": float(v.mean()),
                         "median": float(v.median()), "q1": float(v.quantile(0.25)), "q3": float(v.quantile(0.75)),
                         "min": float(v.min()), "max": float(v.max())})
    pd.DataFrame(summ).to_csv(TABLES / "reading-summary.csv", index=False, encoding="utf-8", lineterminator="\n")

    # depth distribution
    dist = (df.groupby(["corpus", "tok_depth_max"]).size().reset_index(name="files"))
    dist["share"] = dist["files"] / dist.groupby("corpus")["files"].transform("sum")
    dist.to_csv(TABLES / "depth-distribution.csv", index=False, encoding="utf-8", lineterminator="\n")

    # keywords
    kws = []
    for corpus, c in kw_by_corpus.items():
        total = sum(c.values())
        for kw, n in c.most_common():
            kws.append({"corpus": corpus, "keyword": kw, "lines": n, "share": n / total})
    pd.DataFrame(kws).to_csv(TABLES / "keywords.csv", index=False, encoding="utf-8", lineterminator="\n")

    # ratios
    rat = []
    for corpus, sub in df.groupby("corpus", sort=False):
        for x, t, label in COMPARISONS:
            ok = sub[x].notna() & sub[t].notna() & (sub[t] > 0)
            r = (sub.loc[ok, x] / sub.loc[ok, t]).to_numpy(dtype=float)
            if not len(r):
                continue
            g, lo, hi = geo_ci(r)
            rat.append({"corpus": corpus, "numerator": x, "denominator": t, "comparison": label, "files": len(r),
                        "geo_mean": g, "ci_low": lo, "ci_high": hi, "median": float(np.median(r)),
                        "q1": float(np.quantile(r, 0.25)), "q3": float(np.quantile(r, 0.75)),
                        "min": float(r.min()), "max": float(r.max())})
    pd.DataFrame(rat).to_csv(TABLES / "ratios.csv", index=False, encoding="utf-8", lineterminator="\n")

    summary = {
        "files_measured": {c: int(n) for c, n in df["corpus"].value_counts().items()},
        "files_missing_variants": missing,
        "tok_canonical": {c: int(sub["tok_canonical"].sum()) for c, sub in df.groupby("corpus")},
        "tok_indent_odd_lines_total": int(df["tok_indent_odd_lines"].sum()),
        "depth_max_overall": {c: int(sub["tok_depth_max"].max()) for c, sub in df.groupby("corpus")},
        "share_depth_at_most_2": {c: float((sub["tok_depth_max"] <= 2).mean()) for c, sub in df.groupby("corpus")},
        "tok_version": "1.0.3 release binary (fmt --check)",
        "seed": SEED,
    }
    write_json(OUT / "s7-summary.json", summary)
    print(json.dumps(summary, indent=1))
    print(pd.DataFrame(rat)[["corpus", "comparison", "files", "geo_mean", "ci_low", "ci_high", "median"]].to_string())


if __name__ == "__main__":
    main()
