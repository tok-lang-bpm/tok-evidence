"""S1, analysis (PROTOCOL.md §4.4): tables of results/S1/tables/ from the raw counts.

    .venv/Scripts/python scripts/analyse_s1.py
"""

import json

import numpy as np
import pandas as pd

from common import RESULTS, SEED, TOKENIZERS, read_jsonl

S1 = RESULTS / "S1"
TAB = S1 / "tables"
UNITS = ["bytes", "chars", "lines", *TOKENIZERS]

# (corpus, XML variant, tok variant, label) — the comparisons of §4.2
COMPARISONS = [
    ("N", "bundle-sem-min", "tok", "standard files, semantic, minified (strongest XML)"),
    ("N", "bundle-sem", "tok", "standard files, semantic, as tok writes them"),
    ("N", "bundle-di", "tok", "standard files with diagrams, as tok writes them"),
    ("N", "bundle-di-min", "tok", "standard files with diagrams, minified"),
    ("N", "xml-sem-min", "tok", "BPMN only, semantic, minified"),
    ("N", "xml-di", "tok", "BPMN only, with diagram"),
]
for c in ("R", "C", "V"):
    COMPARISONS += [
        (c, "xml-core-min", "tok", "core BPMN: no diagram, no vendor extensions, minified (strongest XML)"),
        (c, "xml-sem-min", "tok", "no diagram, minified"),
        (c, "xml", "tok", "file as exported by the tool"),
        (c, "xml", "tok+layout", "file as exported, against tok with its layout sidecar"),
        (c, "xml-core-min", "tok-compact", "strongest XML against compact tok (flow chains)"),
    ]


COMPARISONS += [
    ("D", "dmn-sem-min", "tok", "DMN without the diagram (DMNDI), minified (strongest XML)"),
    ("D", "dmn", "tok", "DMN file as published in the DMN TCK"),
]


def geo_ci(r, n_boot=10_000, seed=SEED):
    r = np.asarray(r, float)
    lr = np.log(r)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(lr), size=(n_boot, len(lr)))
    boots = np.exp(lr[idx].mean(axis=1))
    return float(np.exp(lr.mean())), float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))


def ratio_table(counts):
    wide = counts.pivot_table(index=["corpus", "model"], columns="variant", values=UNITS, aggfunc="first")
    rows = []
    for corpus, xv, tv, label in COMPARISONS:
        sub = wide.xs(corpus, level="corpus")
        for unit in UNITS:
            if (unit, xv) not in sub.columns or (unit, tv) not in sub.columns:
                continue
            x, t = sub[(unit, xv)], sub[(unit, tv)]
            ok = x.notna() & t.notna() & (t > 0)
            r = (x[ok] / t[ok]).to_numpy()
            if not len(r):
                continue
            g, lo, hi = geo_ci(r)
            rows.append({"corpus": corpus, "xml": xv, "tok": tv, "comparison": label, "unit": unit, "files": len(r),
                         "geo_mean": g, "ci_low": lo, "ci_high": hi, "median": float(np.median(r)),
                         "q1": float(np.quantile(r, 0.25)), "q3": float(np.quantile(r, 0.75)),
                         "min": float(r.min()), "max": float(r.max()),
                         "sum_xml": float(x[ok].sum()), "sum_tok": float(t[ok].sum())})
    return pd.DataFrame(rows)


def main():
    TAB.mkdir(parents=True, exist_ok=True)
    counts = pd.read_csv(S1 / "raw" / "counts.csv")
    files = pd.DataFrame(read_jsonl(S1 / "raw" / "files.jsonl"))
    # Claude counts, merged as one more unit where they exist
    cl = pd.DataFrame([r for r in read_jsonl(S1 / "raw" / "claude-counts.jsonl") if "count" in r and not r.get("error")])
    if len(cl):
        counts = counts.merge(cl[["corpus", "model", "variant", "count"]].rename(columns={"count": "claude"}),
                              on=["corpus", "model", "variant"], how="left")
        UNITS.append("claude")
    ratios = ratio_table(counts)
    ratios.to_csv(TAB / "ratios.csv", index=False)

    # the headline table: o200k and Claude, strongest and as-written XML
    head = ratios[ratios.unit.isin(["o200k_base", "claude", "qwen3", "deepseek_v3", "mistral_nemo", "cl100k_base"])]
    head.to_csv(TAB / "ratios-tokens.csv", index=False)

    # agreement of the Claude counts with o200k
    if "claude" in counts:
        cc = counts.dropna(subset=["claude"])
        agree = {"pairs": int(len(cc)), "pearson_r": float(np.corrcoef(cc.claude, cc.o200k_base)[0, 1]),
                 "claude_per_o200k_median": float(np.median(cc.claude / cc.o200k_base)),
                 "by_variant": cc.assign(r=cc.claude / cc.o200k_base).groupby("variant").r.median().to_dict()}
        json.dump(agree, open(TAB / "claude-vs-o200k.json", "w"), indent=1)

    # tokens per flow node (o200k), and the size relation
    nodes = files[files.status == "ok"][["corpus", "name", "flow_nodes"]].rename(columns={"name": "model"})
    per = counts.merge(nodes, on=["corpus", "model"])
    per = per[per.flow_nodes > 0]
    per["o200k_per_node"] = per.o200k_base / per.flow_nodes
    per.groupby(["corpus", "variant"]).o200k_per_node.describe().round(1).to_csv(TAB / "tokens-per-node.csv")
    fit = []
    for (corpus, variant), g in per.groupby(["corpus", "variant"]):
        if len(g) > 5:
            b, a = np.polyfit(np.log(g.flow_nodes), np.log(g.o200k_base), 1)
            fit.append({"corpus": corpus, "variant": variant, "files": len(g), "exponent": b, "tokens_at_10_nodes": float(np.exp(a) * 10 ** b)})
    pd.DataFrame(fit).to_csv(TAB / "size-fit.csv", index=False)

    # ratio by tool (V), strongest XML and as exported
    wide = counts[counts.corpus == "V"].pivot_table(index="model", columns="variant", values="o200k_base")
    tools = files[files.corpus == "V"].set_index("name").tool
    byt = pd.DataFrame({"tool": tools.reindex(wide.index), "core": wide["xml-core-min"] / wide["tok"], "as_exported": wide["xml"] / wide["tok"]})
    byt.groupby("tool").agg(files=("core", "size"), core_geo=("core", lambda r: float(np.exp(np.log(r).mean()))),
                            exported_geo=("as_exported", lambda r: float(np.exp(np.log(r).mean())))).round(2) \
        .sort_values("exported_geo").to_csv(TAB / "ratio-by-tool.csv")

    # import, check and fidelity (V, R, C)
    x = files[files.corpus.isin(["V", "R", "C"])]
    imp = x.groupby("corpus").status.value_counts().unstack(fill_value=0)
    imp.to_csv(TAB / "import-status.csv")
    ok = x[x.status == "ok"].copy()
    ok["route"] = ok.fidelity_route.fillna("not exported")
    ok.groupby(["corpus", "route"]).size().unstack(fill_value=0).to_csv(TAB / "fidelity-routes.csv")
    fid_rows, lost = [], {}
    for _, r in ok.iterrows():
        f = r.fidelity
        if not isinstance(f, dict):
            continue
        row = {"corpus": r.corpus, "model": r["name"], "route": r.route}
        for k in ("kinds", "named", "flows", "pools", "lanes", "message_flows"):
            row[k + "_total"], row[k + "_kept"] = f[k]["total"], f[k]["kept"]
        fid_rows.append(row)
        for k in ("kinds", "named", "flows"):
            for item, n in f[k]["lost"]:
                key = (k, json.dumps(item, ensure_ascii=False))
                lost[key] = lost.get(key, 0) + n
    fid = pd.DataFrame(fid_rows)
    agg = fid.groupby(["corpus", "route"]).sum(numeric_only=True)
    out = pd.DataFrame(index=agg.index)
    for k in ("kinds", "named", "flows", "pools", "lanes", "message_flows"):
        out[k + "_kept_share"] = (agg[k + "_kept"] / agg[k + "_total"]).round(4)
        out[k + "_total"] = agg[k + "_total"]
    out["files"] = fid.groupby(["corpus", "route"]).size()
    out.to_csv(TAB / "fidelity.csv")
    pd.DataFrame([{"what": k, "item": i, "lost": n} for (k, i), n in sorted(lost.items(), key=lambda kv: -kv[1])]) \
        .head(60).to_csv(TAB / "fidelity-lost-top.csv", index=False)
    blk = ok[ok.route == "not exported"].blocking.dropna().explode().value_counts()
    blk.to_csv(TAB / "export-blocking-codes.csv")
    print(head[head.unit == "o200k_base"][["corpus", "xml", "tok", "files", "geo_mean", "ci_low", "ci_high", "median", "q1", "q3"]].round(2).to_string(index=False))
    if "claude" in UNITS:
        print(head[head.unit == "claude"][["corpus", "xml", "tok", "files", "geo_mean", "ci_low", "ci_high", "median"]].round(2).to_string(index=False))
    print(out.to_string())


if __name__ == "__main__":
    main()
