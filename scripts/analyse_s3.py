"""S3, analysis (PROTOCOL.md §6.6, §6.7): fidelity of every final model and the paired comparison.

    .venv/Scripts/python scripts/analyse_s3.py --phase pilot|main
"""

import argparse
import json
import re

import numpy as np
import pandas as pd
from rapidfuzz import fuzz
from scipy.optimize import linear_sum_assignment
from scipy.stats import wilcoxon

import bpmn_graph
from common import RESULTS, ROOT, SEED, read_jsonl

TASKS = {t["id"]: t for t in json.load(open(ROOT / "data" / "derived" / "pet" / "tasks.json", encoding="utf-8"))["tasks"]}
STOP = set("a an the of to for and or in on at by with from into onto is are be been its it their his her this that which "
           "as if then than so all any each".split())
PRONOUNS = {"she", "he", "it", "they", "him", "her", "them", "we", "i", "you", "his", "its", "their"}


def norm(s):
    return " ".join(w for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if w not in STOP)


def sim(a, b):
    a, b = norm(a), norm(b)
    return fuzz.token_set_ratio(a, b) / 100 if a and b else 0.0


def prf(tp, n_pred, n_gold):
    p = tp / n_pred if n_pred else 0.0
    r = tp / n_gold if n_gold else np.nan
    f = 2 * p * r / (p + r) if (p + r) and not np.isnan(r) else (0.0 if not np.isnan(r) else np.nan)
    return p, r, f


def fidelity(bpmn_path, task, thr=0.5):
    g = bpmn_graph.read(open(bpmn_path, "rb").read())
    acts = g.activities()
    m_ids = list(acts)
    gold = task["activities"]
    res = {"model_tasks": len(m_ids), "gold_activities": len(gold)}
    if not m_ids or not gold:
        mapping = {}
    else:
        S = np.array([[sim(ga["label"], acts[m][1]) for m in m_ids] for ga in gold])
        r, c = linear_sum_assignment(-S)
        mapping = {m_ids[j]: gold[i]["id"] for i, j in zip(r, c) if S[i, j] >= thr}
    tp = len(mapping)
    res["act_p"], res["act_r"], res["act_f1"] = prf(tp, len(m_ids), len(gold))
    gold_pairs = {tuple(p) for p in task["order"]}
    m_pairs = g.activity_order()
    tp_f = sum(1 for a, b in m_pairs if a in mapping and b in mapping and (mapping[a], mapping[b]) in gold_pairs)
    res["flow_p"], res["flow_r"], res["flow_f1"] = prf(tp_f, len(m_pairs), len(gold_pairs))
    perf = [ga for ga in gold if ga["performer"] and norm(ga["performer"]) and not set(norm(ga["performer"]).split()) <= PRONOUNS]
    inv = {v: k for k, v in mapping.items()}
    ok = sum(1 for ga in perf if ga["id"] in inv and sim(g.lane_of.get(inv[ga["id"]], ""), ga["performer"]) >= 0.5)
    res["perf_acc"] = ok / len(perf) if perf else np.nan
    res["lanes"] = len(g.lanes)
    return res


def score_runs(phase):
    base = RESULTS / "S3" / phase
    rows = []
    for r in read_jsonl(base / "runs.jsonl"):
        task = TASKS[r["task"]]
        row = {k: r[k] for k in ("run", "model", "rep", "task", "repetition", "attempts", "loop_ok", "valid_first", "valid_final",
                                 "input_tokens", "output_tokens", "first_input_tokens", "first_output_tokens", "seconds")}
        row["total_tokens"] = r["input_tokens"] + r["output_tokens"]
        row["model_ids"] = " ".join(r["model_ids"])
        for when, key, valid in (("final", "final_bpmn", r["valid_final"]), ("first", "first_bpmn", r["valid_first"])):
            path = (base / r[key]) if r.get(key) else None
            fid = {}
            if path and path.exists():
                try:
                    for thr in (0.4, 0.5, 0.6):
                        f = fidelity(path, task, thr)
                        if thr == 0.5:
                            fid.update(f)
                        else:
                            fid[f"flow_f1_t{int(thr * 10)}"] = f["flow_f1"]
                            fid[f"act_f1_t{int(thr * 10)}"] = f["act_f1"]
                except Exception:
                    fid = {}
            for k in ("act_f1", "flow_f1", "perf_acc", "flow_f1_t4", "flow_f1_t6", "act_f1_t4", "act_f1_t6", "model_tasks"):
                v = fid.get(k, np.nan)
                row[f"{when}_{k}_cond"] = v if valid else np.nan          # valid models only
                no_gold = k.startswith("flow") and not task["order"]
                row[f"{when}_{k}_itt"] = np.nan if no_gold else (v if valid and not pd.isna(v) else (0.0 if k != "model_tasks" else np.nan))
        rows.append(row)
    return pd.DataFrame(rows)


PRIMARY = [("valid_final", "valid after feedback"), ("total_tokens", "total tokens per run"), ("final_flow_f1_itt", "flow F1 (invalid = 0)")]
SECONDARY = [("valid_first", "valid at the first attempt"), ("attempts", "attempts"), ("output_tokens", "output tokens"),
             ("seconds", "wall time (s)"), ("final_act_f1_itt", "activity F1 (invalid = 0)"), ("final_perf_acc_itt", "performer accuracy (invalid = 0)"),
             ("final_flow_f1_cond", "flow F1 (valid models)"), ("final_act_f1_cond", "activity F1 (valid models)"),
             ("final_flow_f1_t4_itt", "flow F1, threshold 0.4"), ("final_flow_f1_t6_itt", "flow F1, threshold 0.6"),
             ("first_flow_f1_itt", "flow F1 of the first attempt (invalid = 0)"), ("input_tokens", "input tokens")]


def paired(df, col):
    out = []
    for model, g in df.groupby("model"):
        w = g.groupby(["task", "rep"])[col].mean().unstack("rep")
        if "TOK" not in w or "XML" not in w:
            continue
        w = w.dropna()
        d = (w["TOK"] - w["XML"]).to_numpy()
        rng = np.random.default_rng(SEED)
        boots = d[rng.integers(0, len(d), size=(10_000, len(d)))].mean(1) if len(d) else np.array([np.nan])
        try:
            p = wilcoxon(w["TOK"], w["XML"]).pvalue if np.any(d != 0) else 1.0
        except ValueError:
            p = np.nan
        out.append({"model": model, "outcome": col, "tasks": len(d), "mean_XML": w["XML"].mean(), "mean_TOK": w["TOK"].mean(),
                    "mean_diff": d.mean() if len(d) else np.nan, "median_diff": np.median(d) if len(d) else np.nan,
                    "ci_low": np.quantile(boots, 0.025), "ci_high": np.quantile(boots, 0.975), "p_wilcoxon": p,
                    "tasks_TOK_better": int((d > 0).sum()), "tasks_XML_better": int((d < 0).sum())})
    return out


def holm(p):
    p = np.asarray(p, float)
    order = np.argsort(p)
    adj = np.empty_like(p)
    running = 0
    for rank, i in enumerate(order):
        running = max(running, min(1, (len(p) - rank) * p[i]))
        adj[i] = running
    return adj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["pilot", "main"], required=True)
    args = ap.parse_args()
    tab = RESULTS / "S3" / args.phase / "tables"
    tab.mkdir(parents=True, exist_ok=True)
    df = score_runs(args.phase)
    df.to_csv(tab / "runs-scored.csv", index=False)
    means = df.groupby(["model", "rep"])[[c for c, _ in PRIMARY + SECONDARY]].mean().round(3)
    means.to_csv(tab / "means.csv")
    res = []
    for col, label in PRIMARY + SECONDARY:
        for r in paired(df, col):
            r["label"], r["primary"] = label, col in dict(PRIMARY)
            res.append(r)
    res = pd.DataFrame(res)
    if len(res):
        prim = res.primary & res.p_wilcoxon.notna()
        res.loc[prim, "p_holm"] = holm(res.loc[prim, "p_wilcoxon"])
    res.to_csv(tab / "paired.csv", index=False)
    print(means.T.to_string())
    if len(res):
        print(res[["model", "label", "tasks", "mean_XML", "mean_TOK", "mean_diff", "ci_low", "ci_high", "p_wilcoxon", "p_holm"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
