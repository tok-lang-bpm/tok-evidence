"""S3i, analysis (PROTOCOL-S3i.md §5 for the pilot, §8.3 for the main phase): the S3i arms against the
S3h arms on the same texts.

    .venv/Scripts/python scripts/analyse_s3i.py --phase pilot|main|pet

Writes results/S3i/<phase>/tables/: runs-scored.csv (the S3i runs and the comparison arms on the
same texts and models: S3h for the PMo phases; S3, S3b, S3c and S3d for the PET phase), means.csv,
paired.csv (mean differences with bootstrap intervals; in the main and PET phases the Wilcoxon
p-values and the Holm adjustment over the 32 confirmatory tests), tools.csv (calls, tool calls,
runs ending at the budget) and, in the main and PET phases, codes.csv (the diagnostics tok check
leaves in the final model of each arm).
"""

import argparse
import json
import subprocess
from collections import Counter

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

import analyse_s3 as a
from common import RESULTS, ROOT, SEED, read_jsonl

a.TASKS = {t["id"]: t for t in json.load(open(ROOT / "data" / "derived" / "pmo" / "tasks.json", encoding="utf-8"))["tasks"]}
TOK_RELEASE = ROOT / "tools" / "bin" / "tok-1.0.3-windows-x86_64" / "tok.exe"
COLS = ["valid_final", "valid_first", "total_tokens", "input_tokens", "output_tokens", "attempts", "tool_calls", "seconds", "cost_usd", "flow_f1", "act_f1"]
OUTCOMES = ("valid_final", "total_tokens", "output_tokens", "attempts", "flow_f1", "cost_usd")
COMPARE = {
    "pilot": [("B - A: skill+reference, check only vs published agent", "TOKAGENT-B", "TOKAGENT"),
              ("C - A: lean skill vs published agent", "TOKAGENT-C", "TOKAGENT"),
              ("B - TOK: skill+reference agent vs tok reference arm", "TOKAGENT-B", "TOK"),
              ("C - TOK: lean agent vs tok reference arm", "TOKAGENT-C", "TOK"),
              ("XMLAGENT - XML: BPMN skill agent vs XML reference arm", "XMLAGENT-A", "XML"),
              ("B - XMLAGENT: tok agent vs BPMN XML agent", "TOKAGENT-B", "XMLAGENT-A"),
              ("C - XMLAGENT: lean tok agent vs BPMN XML agent", "TOKAGENT-C", "XMLAGENT-A")],
    "main": [("(a) notation, lean skills: TOKAGENT-C - XMLAGENT-C", "TOKAGENT-C", "XMLAGENT-C"),
             ("(b) notation, published skills: TOKAGENT - XMLAGENT-A", "TOKAGENT", "XMLAGENT-A"),
             ("(c) skill, tok: TOKAGENT-C - TOKAGENT", "TOKAGENT-C", "TOKAGENT"),
             ("(d) agent against reference, tok: TOKAGENT-C - TOK", "TOKAGENT-C", "TOK"),
             ("skill, BPMN XML: XMLAGENT-C - XMLAGENT-A", "XMLAGENT-C", "XMLAGENT-A"),
             ("agent against reference, BPMN XML, lean skill: XMLAGENT-C - XML", "XMLAGENT-C", "XML"),
             ("agent against reference, BPMN XML, published skill: XMLAGENT-A - XML", "XMLAGENT-A", "XML"),
             ("lean tok agent against XML reference: TOKAGENT-C - XML", "TOKAGENT-C", "XML")],
}
COMPARE["pet"] = COMPARE["main"]
CONFIRMATORY = {"main": ({"(a)", "(b)", "(c)", "(d)"}, {"valid_final", "total_tokens"})}  # 4 comparisons × 2 outcomes × 4 models = 32 tests
CONFIRMATORY["pet"] = CONFIRMATORY["main"]
# the comparison arms on the same texts: (study table, arms taken)
SOURCES = {"pilot": [("S3h/main", ("XML", "TOK", "TOKAGENT"))], "main": [("S3h/main", ("XML", "TOK", "TOKAGENT"))],
           "pet": [("S3/main", ("XML", "TOK")), ("S3b/main", ("XML", "TOK")), ("S3c/main", ("TOKAGENT",)), ("S3d/main", ("XML", "TOK", "TOKAGENT"))]}
TASK_FILES = {"pilot": "pmo", "main": "pmo", "pet": "pet"}


def score(phase_dir, rows):
    out = []
    for r in rows:
        task = a.TASKS[r["task"]]
        row = {k: r.get(k) for k in ("run", "model", "rep", "task", "attempts", "tool_calls", "valid_first", "valid_final",
                                     "input_tokens", "output_tokens", "seconds", "cost_usd", "ended_by_budget", "loop_ok")}
        row["total_tokens"] = r["input_tokens"] + r["output_tokens"]
        fid = {}
        p = (phase_dir / r["final_bpmn"]) if r.get("final_bpmn") else None
        if p and p.exists() and r["valid_final"]:
            try:
                fid = a.fidelity(p, task, 0.5)
            except Exception:
                fid = {}
        row["flow_f1"] = np.nan if not task["order"] else (fid.get("flow_f1", 0.0) if r["valid_final"] else 0.0)
        row["act_f1"] = fid.get("act_f1", 0.0) if r["valid_final"] else 0.0
        out.append(row)
    return pd.DataFrame(out)


def paired(df, col, first, second):
    out = []
    for model, g in df.groupby("model"):
        w = g.pivot_table(index="task", columns="rep", values=col, aggfunc="mean")
        if first not in w or second not in w:
            continue
        w = w[[first, second]].dropna()
        d = (w[first] - w[second]).to_numpy()
        if not len(d):
            continue
        rng = np.random.default_rng(SEED)
        boots = d[rng.integers(0, len(d), size=(10_000, len(d)))].mean(1)
        try:
            p = wilcoxon(w[first], w[second]).pvalue if np.any(d != 0) else 1.0
        except ValueError:
            p = np.nan
        out.append({"model": model, "outcome": col, "tasks": len(d), "mean_first": w[first].mean(), "mean_second": w[second].mean(),
                    "mean_diff": d.mean(), "median_diff": float(np.median(d)), "ci_low": np.quantile(boots, 0.025), "ci_high": np.quantile(boots, 0.975),
                    "p_wilcoxon": p, "tasks_first_better": int((d > 0).sum()), "tasks_second_better": int((d < 0).sum())})
    return out


def codes_left(paths):
    """tok check (released 1.0.3) on final BPMN files: errors, warnings and the codes left."""
    rows = []
    for run, model, rep, path in paths:
        if path is None or not path.exists():
            rows.append({"run": run, "model": model, "rep": rep, "errors": np.nan, "warnings": np.nan, "codes": ""})
            continue
        p = subprocess.run([str(TOK_RELEASE), "check", path.name, "--json"], cwd=path.parent, capture_output=True, text=True, encoding="utf-8")
        try:
            diags = json.loads(p.stdout)["diagnostics"]
        except (json.JSONDecodeError, KeyError):
            diags = [{"severity": "error", "code": "CRASH"}]
        rows.append({"run": run, "model": model, "rep": rep, "errors": sum(x["severity"] == "error" for x in diags),
                     "warnings": sum(x["severity"] == "warning" for x in diags),
                     "codes": " ".join(sorted({x["code"] for x in diags if x["severity"] in ("error", "warning")}))})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["pilot", "main", "pet"], default="pilot")
    args = ap.parse_args()
    phase_dir = RESULTS / "S3i" / args.phase
    tab = phase_dir / "tables"
    tab.mkdir(parents=True, exist_ok=True)
    a.TASKS = {t["id"]: t for t in json.load(open(ROOT / "data" / "derived" / TASK_FILES[args.phase] / "tasks.json", encoding="utf-8"))["tasks"]}
    rows = read_jsonl(phase_dir / "runs.jsonl")
    new = score(phase_dir, rows)
    tasks = sorted(new.task.unique())
    frames, xml_paths = [new], []
    for table, arms in SOURCES[args.phase]:
        src_dir = RESULTS / table
        d = pd.read_csv(src_dir / "tables" / "runs-scored.csv")
        d = d[d.task.isin(tasks) & d.model.isin(new.model.unique()) & d.rep.isin(arms)].rename(
            columns={"final_flow_f1_itt": "flow_f1", "final_act_f1_itt": "act_f1"})
        src_runs = pd.read_json(src_dir / "runs.jsonl", lines=True).drop_duplicates("run").set_index("run")
        for col in ("cost_usd", "tool_calls", "ended_by_budget", "loop_ok"):
            if col in src_runs:
                d[col] = d.run.map(src_runs[col])
        frames.append(d[[c for c in new.columns if c in d.columns]])
        xml_paths += [(run, x["model"], x["rep"], (src_dir / x["final_bpmn"]) if isinstance(x.get("final_bpmn"), str) else None)
                      for run, x in src_runs.iterrows() if x["rep"] == "XML" and x["task"] in tasks and x["model"] in set(new.model)]
    both = pd.concat(frames, ignore_index=True)
    both.to_csv(tab / "runs-scored.csv", index=False)
    means = both.groupby(["model", "rep"])[COLS].mean().round(3)
    means["runs"] = both.groupby(["model", "rep"]).size()
    means.to_csv(tab / "means.csv")

    res = []
    for label, first, second in COMPARE[args.phase]:
        for col in OUTCOMES:
            for r in paired(both, col, first, second):
                r["comparison"] = label
                res.append(r)
    res = pd.DataFrame(res)
    if args.phase in CONFIRMATORY:
        tags, outcomes = CONFIRMATORY[args.phase]
        conf = res.comparison.str[:3].isin(tags) & res.outcome.isin(outcomes) & res.p_wilcoxon.notna()
        res["confirmatory"] = conf
        res.loc[conf, "p_holm"] = a.holm(res.loc[conf, "p_wilcoxon"])
    res.to_csv(tab / "paired.csv", index=False)

    tools = both.groupby(["model", "rep"])[["attempts", "tool_calls", "ended_by_budget", "loop_ok", "valid_first", "valid_final"]].mean(numeric_only=True).round(3)
    tools.to_csv(tab / "tools.csv")

    if args.phase in ("main", "pet"):
        paths = [(r["run"], r["model"], r["rep"], (phase_dir / r["final_bpmn"]) if r.get("final_bpmn") else None) for r in rows if r["rep"].startswith("XML")]
        paths += xml_paths
        codes = codes_left(paths)
        tok_codes = pd.DataFrame([{"run": r["run"], "model": r["model"], "rep": r["rep"], "codes": " ".join(r.get("final_codes") or [])} for r in rows if r["rep"].startswith("TOK")])
        codes = pd.concat([codes, tok_codes], ignore_index=True)
        codes.to_csv(tab / "codes-runs.csv", index=False)
        summary = []
        for (model, rep), g in codes.groupby(["model", "rep"]):
            cnt = Counter(c for s in g.codes for c in s.split())
            summary.append({"model": model, "rep": rep, "runs": len(g), "runs_with_codes_left": int((g.codes != "").sum()),
                            "mean_errors": g.errors.mean() if "errors" in g else np.nan, "mean_warnings": g.warnings.mean() if "warnings" in g else np.nan,
                            "codes": ", ".join(f"{c}:{n}" for c, n in cnt.most_common(8))})
        pd.DataFrame(summary).to_csv(tab / "codes.csv", index=False)

    pd.set_option("display.width", 250)
    print(means.to_string())
    print()
    cols = ["comparison", "model", "outcome", "tasks", "mean_second", "mean_first", "mean_diff", "ci_low", "ci_high", "p_wilcoxon"]
    if "p_holm" in res:
        cols.append("p_holm")
        print(res[res.confirmatory][cols].round(4).to_string(index=False))
        print()
        print(res[~res.confirmatory][cols[:-1]].round(3).to_string(index=False))
    else:
        print(res[cols[:-1]].round(3).to_string(index=False))
    print()
    print(tools.to_string())
    if args.phase in ("main", "pet"):
        print()
        print(pd.read_csv(tab / "codes.csv").to_string(index=False))


if __name__ == "__main__":
    main()
