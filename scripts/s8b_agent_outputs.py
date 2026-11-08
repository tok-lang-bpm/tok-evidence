"""S8b: speech and braille for the final models of the lean-skill agent runs of S3i (PROTOCOL-S8b.md).

Pairs the final tok model of TOKAGENT-C with the final BPMN XML of XMLAGENT-C for the same language
model and text, when both are valid, and measures both with the functions of S8. Writes
results/S8b/tables/*.csv and results/S8b/s8b-summary.json.

    .venv/Scripts/python scripts/s8b_agent_outputs.py
"""

import json

import numpy as np
import pandas as pd

from common import RESULTS, SEED, write_json
from s8_assistive import LEVELS, NVDA, SPEECH_LEVELS, WIDTHS, Speaker, braille, geo_ci, lines_of, speech

OUT = RESULTS / "S8b"
TABLES = OUT / "tables"
SETS = {"PMo": RESULTS / "S3i" / "main" / "runs", "PET": RESULTS / "S3i" / "pet" / "runs"}
MODELS = {"sonnet": "Claude Sonnet 5.5", "haiku": "Claude Haiku 5.5", "gpt-oss-120b-cloud": "gpt-oss 120B"}
TOK_ARM, XML_ARM = "TOKAGENT-C", "XMLAGENT-C"


def measure(path, sp):
    ls = lines_of(path.read_bytes())
    m = speech(ls, sp)
    m.update(braille(ls))
    m["lines"] = len(ls)
    m["chars"] = sum(len(x) for x in ls)
    return m


def main():
    TABLES.mkdir(parents=True, exist_ok=True)
    sp = Speaker(NVDA)
    rows, unpaired = [], []
    for task_set, runs in SETS.items():
        for model, label in MODELS.items():
            tok_runs = {d.name.split("__")[2]: d for d in runs.glob(f"{model}__{TOK_ARM}__*")}
            for task, td in sorted(tok_runs.items()):
                xd = runs / td.name.replace(TOK_ARM, XML_ARM)
                if not xd.exists():
                    unpaired.append(td.name)
                    continue
                tr = json.loads((td / "run.json").read_text(encoding="utf-8"))
                xr = json.loads((xd / "run.json").read_text(encoding="utf-8"))
                tf, xf = td / "final.tok", xd / "final.bpmn"
                ok = bool(tr.get("valid_final")) and bool(xr.get("valid_final")) and tf.exists() and xf.exists()
                row = {"task_set": task_set, "model": label, "task": task, "pair_valid": ok,
                       "tok_valid": bool(tr.get("valid_final")), "xml_valid": bool(xr.get("valid_final"))}
                if ok:
                    row.update({f"tok_{k}": v for k, v in measure(tf, sp).items()})
                    row.update({f"xml_{k}": v for k, v in measure(xf, sp).items()})
                rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(TABLES / "s8b-by-run.csv", index=False, encoding="utf-8", lineterminator="\n")
    pairs = df[df["pair_valid"]].copy()

    measures = [f"words_{n}" for n in SPEECH_LEVELS] + [f"symbol_words_{n}" for n in SPEECH_LEVELS] + \
        ["indent_changes"] + [f"braille_rows_{w}" for w in WIDTHS] + [f"fit_{w}" for w in WIDTHS] + ["lines", "chars"]
    ratio_measures = [f"words_{n}" for n in SPEECH_LEVELS] + [f"braille_rows_{w}" for w in WIDTHS] + ["lines", "chars"]

    def groups():
        for (ts, m), sub in pairs.groupby(["task_set", "model"], sort=True):
            yield ts, m, sub
        yield "all", "all", pairs

    summ, rat = [], []
    for ts, m, sub in groups():
        for meas in measures:
            for rep in ("tok", "xml"):
                v = sub[f"{rep}_{meas}"].astype(float)
                summ.append({"task_set": ts, "model": m, "representation": rep, "measure": meas, "pairs": len(v),
                             "median": float(v.median()), "q1": float(v.quantile(0.25)), "q3": float(v.quantile(0.75))})
        for meas in ratio_measures:
            a, b = sub[f"xml_{meas}"].astype(float), sub[f"tok_{meas}"].astype(float)
            ok = (a > 0) & (b > 0)
            r = (a[ok] / b[ok]).to_numpy()
            if not len(r):
                continue
            g, lo, hi = geo_ci(r)
            rat.append({"task_set": ts, "model": m, "measure": meas, "pairs": len(r), "geo_mean": g,
                        "ci_low": lo, "ci_high": hi, "median": float(np.median(r)),
                        "min": float(r.min()), "max": float(r.max())})
    pd.DataFrame(summ).to_csv(TABLES / "s8b-summary.csv", index=False, encoding="utf-8", lineterminator="\n")
    rt = pd.DataFrame(rat)
    rt.to_csv(TABLES / "s8b-ratios.csv", index=False, encoding="utf-8", lineterminator="\n")
    summary = {
        "runs_paired": int(len(df)), "pairs_both_valid": int(len(pairs)),
        "pairs_by_set_and_model": {f"{ts} / {m}": int(len(s)) for (ts, m), s in pairs.groupby(["task_set", "model"])},
        "runs_without_partner": unpaired, "arms": [TOK_ARM, XML_ARM], "seed": SEED,
    }
    write_json(OUT / "s8b-summary.json", summary)
    print(json.dumps(summary, indent=1))
    pd.set_option("display.width", 200)
    print(rt[rt["measure"].isin(["words_some", "words_none", "braille_rows_40", "lines", "chars"])].to_string())


if __name__ == "__main__":
    main()
