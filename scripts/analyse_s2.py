"""S2, analysis (PROTOCOL.md §5.2): detection, warning and localisation per operator and validator.

    .venv/Scripts/python scripts/analyse_s2.py
"""

import json
import re
from collections import Counter

import numpy as np
import pandas as pd

from common import RESULTS, SEED, read_jsonl
from s2_faults import DESCRIPTION, MUT, OPERATORS

S2 = RESULTS / "S2"
TAB = S2 / "tables"


def wilson(k, n, z=1.96):
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def mentions(text, ids):
    return any(re.search(rf"(?<![\w-]){re.escape(i)}(?![\w-])", text or "") for i in ids)


def tok_view(r):
    errs = Counter(d["code"] for d in r["diagnostics"] if d["severity"] == "error")
    warns = Counter(d["code"] for d in r["diagnostics"] if d["severity"] != "error")
    return errs, warns, r["diagnostics"]


def outcomes():
    meta = {}
    for p in MUT.rglob("meta.json"):
        m = json.loads(p.read_text(encoding="utf-8"))
        meta[str(p.parent.relative_to(MUT)).replace("\\", "/")] = m
    tok = {r["dir"]: r for r in read_jsonl(S2 / "raw" / "tok.jsonl")}
    xsd = {r["dir"]: r for r in read_jsonl(S2 / "raw" / "xsd.jsonl")}

    def lint_map(cfg):
        out = {}
        for r in json.load(open(S2 / "raw" / f"lint-{cfg}.json", encoding="utf-8")):
            d = str(__import__("pathlib").Path(r["file"]).parent.relative_to(MUT)).replace("\\", "/")
            out[d] = r
        return out

    lints = {cfg: lint_map(cfg) for cfg in ("recommended", "correctness")}
    rows = []
    for d, m in meta.items():
        if m["operator"] == "base":
            continue
        b = m["base"] + "/base"
        ids = [i for i in m["ids"] if i]
        row = {"dir": d, "base": m["base"], "operator": m["operator"], "site": m["site"]}
        # tok
        e0, w0, _ = tok_view(tok[b])
        e1, w1, diags = tok_view(tok[d])
        new_e, new_w = e1 - e0, w1 - w0
        row["tok"] = "detected" if new_e else ("warned" if new_w else "missed")
        new_codes = set(new_e) | set(new_w)
        loc = [x for x in diags if x["code"] in new_codes and (x.get("id") in ids or mentions(x["message"], ids)
                                                                or (x.get("line") in m.get("tok_lines", [])))]
        row["tok_localised"] = bool(loc)
        row["tok_codes"] = " ".join(sorted(new_e)) or " ".join(sorted(new_w))
        row["tok_ms"] = tok[d]["ms"]
        # XML Schema
        def norm(e):
            return re.sub(r"line \d+", "", e["message"])
        x0, x1 = Counter(norm(e) for e in xsd[b]["errors"]), Counter(norm(e) for e in xsd[d]["errors"])
        new_x = x1 - x0
        row["xsd"] = "detected" if new_x else "missed"
        row["xsd_localised"] = any(e["line"] in m.get("xml_lines", []) or mentions(e["message"], ids)
                                   for e in xsd[d]["errors"] if norm(e) in new_x)
        row["xsd_ms"] = xsd[d]["ms"]
        # bpmnlint, two rule sets; the import warnings of bpmn-moddle count as warnings
        for cfg, lm in lints.items():
            l0, l1 = lm[b], lm[d]
            err0 = Counter((x["rule"], x["id"]) for x in l0["reports"] if x["category"] == "error")
            err1 = Counter((x["rule"], x["id"]) for x in l1["reports"] if x["category"] == "error")
            war0 = Counter((x["rule"], x["id"]) for x in l0["reports"] if x["category"] != "error") + Counter(l0["warnings"])
            war1 = Counter((x["rule"], x["id"]) for x in l1["reports"] if x["category"] != "error") + Counter(l1["warnings"])
            ne, nw = err1 - err0, war1 - war0
            if l1.get("error") and not l0.get("error"):
                ne = Counter({("import-error", None): 1})
            row[f"lint_{cfg}"] = "detected" if ne else ("warned" if nw else "missed")
            row[f"lint_{cfg}_localised"] = any((k[1] in ids) if isinstance(k, tuple) else mentions(str(k), ids)
                                               for k in list(ne) + list(nw))
            row[f"lint_{cfg}_rules"] = " ".join(sorted({k[0] if isinstance(k, tuple) else "moddle-warning" for k in (ne or nw)}))
            row[f"lint_{cfg}_ms"] = l1["ms"]
        # the XML side as a user of both tools sees it: schema or linter (correctness rules)
        row["xml_any"] = "detected" if "detected" in (row["xsd"], row["lint_correctness"]) else (
            "warned" if row["lint_correctness"] == "warned" else "missed")
        row["xml_any_localised"] = row["xsd_localised"] or row["lint_correctness_localised"]
        rows.append(row)
    return pd.DataFrame(rows)


VALIDATORS = ["tok", "xsd", "lint_correctness", "lint_recommended", "xml_any"]


def cluster_ci(df, col, value="detected", n_boot=10_000, seed=SEED):
    """95 % interval of a rate by resampling base models (mutants of one model are not independent)."""
    g = df.groupby("base")[col].agg(lambda s: ((s == value).sum(), len(s)))
    k = np.array([a for a, _ in g]); n = np.array([b for _, b in g])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(k), size=(n_boot, len(k)))
    rates = k[idx].sum(1) / n[idx].sum(1)
    return float(np.quantile(rates, 0.025)), float(np.quantile(rates, 0.975))


def main():
    TAB.mkdir(parents=True, exist_ok=True)
    df = outcomes()
    df.to_csv(TAB / "mutants.csv", index=False)
    rows = []
    for op in OPERATORS:
        sub = df[df.operator == op]
        row = {"operator": op, "fault": DESCRIPTION[op], "mutants": len(sub), "base_models": sub.base.nunique()}
        for v in VALIDATORS:
            n = len(sub)
            k = int((sub[v] == "detected").sum()) if n else 0
            w = int((sub[v] == "warned").sum()) if n else 0
            loc = int(sub[f"{v}_localised"].sum()) if n else 0
            lo, hi = wilson(k, n)
            row.update({f"{v}_detected": k, f"{v}_warned": w, f"{v}_localised": loc,
                        f"{v}_signalled_rate": (k + w) / n if n else np.nan,
                        f"{v}_rate": k / n if n else np.nan, f"{v}_ci": f"{lo:.2f}-{hi:.2f}" if n else ""})
        rows.append(row)
    tab = pd.DataFrame(rows)
    tab.to_csv(TAB / "detection-by-operator.csv", index=False)
    overall = []
    for v in VALIDATORS:
        k, w, n = int((df[v] == "detected").sum()), int((df[v] == "warned").sum()), len(df)
        lo, hi = cluster_ci(df, v)
        detected = df[df[v] == "detected"]
        slo, shi = cluster_ci(df.assign(sig=df[v].isin(["detected", "warned"]).map({True: "s", False: "-"})), "sig", value="s")
        overall.append({"validator": v, "mutants": n, "detected": k, "rate": k / n, "cluster_ci_low": lo, "cluster_ci_high": hi,
                        "signalled_rate": (k + w) / n, "signalled_ci_low": slo, "signalled_ci_high": shi,
                        "warned": w, "localised_of_detected": float(detected[f"{v}_localised"].mean()) if len(detected) else np.nan,
                        "operators_detected_all": int(sum(1 for op in OPERATORS if len(df[df.operator == op]) and (df[df.operator == op][v] == "detected").all()))})
    pd.DataFrame(overall).to_csv(TAB / "detection-overall.csv", index=False)
    times = {v: float(df[f"{v}_ms"].median()) for v in ("tok", "xsd", "lint_correctness", "lint_recommended")}
    json.dump({"median_ms_per_file": times, "note": "tok: a separate process per file (start of the program included); xsd and bpmnlint: in one warm process"},
              open(TAB / "timing.json", "w"), indent=1)
    # which diagnostics found each operator
    codes = []
    for op in OPERATORS:
        sub = df[df.operator == op]
        if len(sub):
            codes.append({"operator": op, "tok_codes": dict(Counter(" ".join(sub.tok_codes).split()).most_common(6)),
                          "lint_rules": dict(Counter(" ".join(sub.lint_correctness_rules).split()).most_common(6))})
    json.dump(codes, open(TAB / "diagnostics-by-operator.json", "w"), indent=1, ensure_ascii=False)
    show = ["operator", "mutants"] + [f"{v}_rate" for v in VALIDATORS] + [f"{v}_signalled_rate" for v in ("tok", "xml_any")]
    print(tab[show].round(2).to_string(index=False))
    print(pd.DataFrame(overall).round(3).to_string(index=False))
    print(times)


if __name__ == "__main__":
    main()
