"""S3h, analysis (PROTOCOL-S3h.md §5): the three arms on the held-out tasks, per model.

    .venv/Scripts/python scripts/analyse_s3h.py

Writes results/S3h/main/tables/ (runs-scored.csv, means.csv, paired.csv, tools.csv).
"""

import json

import pandas as pd

import analyse_s3 as a
from common import RESULTS, ROOT

a.TASKS = {t["id"]: t for t in json.load(open(ROOT / "data" / "derived" / "pmo" / "tasks.json", encoding="utf-8"))["tasks"]}
COMPARISONS = [("TOK - XML", "TOK", "XML"), ("TOKAGENT - XML", "TOKAGENT", "XML"), ("TOKAGENT - TOK", "TOKAGENT", "TOK")]


def main():
    tab = RESULTS / "S3h" / "main" / "tables"
    tab.mkdir(parents=True, exist_ok=True)
    d = a.score_runs("../S3h/main")  # score_runs reads RESULTS / "S3" / phase
    d.to_csv(tab / "runs-scored.csv", index=False)
    cols = [x for x, _ in a.PRIMARY + a.SECONDARY]
    means = d.groupby(["model", "rep"])[cols].mean().round(3)
    means.to_csv(tab / "means.csv")
    res = []
    for model in sorted(d.model.unique()):
        for comp, mine, other in COMPARISONS:
            x = d[(d.model == model) & (d.rep == mine)].assign(rep="TOK")
            y = d[(d.model == model) & (d.rep == other)].assign(rep="XML")
            for col, label in a.PRIMARY + a.SECONDARY:
                for r in a.paired(pd.concat([x, y]), col):
                    r.update(comparison=comp, label=label, primary=col in dict(a.PRIMARY))
                    res.append(r)
    res = pd.DataFrame(res).rename(columns={"mean_TOK": "mean_first", "mean_XML": "mean_second"})
    prim = res.primary & res.p_wilcoxon.notna()
    res.loc[prim, "p_holm"] = a.holm(res.loc[prim, "p_wilcoxon"])  # 36 tests
    res.to_csv(tab / "paired.csv", index=False)

    runs = pd.read_json(RESULTS / "S3h" / "main" / "runs.jsonl", lines=True)
    ag = runs[runs.rep == "TOKAGENT"].reset_index(drop=True)
    tools = pd.concat([ag[["model", "attempts", "tool_calls", "ended_by_budget", "loop_ok"]],
                       pd.json_normalize(ag.tool_calls_by_name).add_prefix("calls_")], axis=1)
    tools.assign(used_check=tools.calls_check > 0).groupby("model").mean(numeric_only=True).round(3).to_csv(tab / "tools.csv")

    print(means.T.to_string())
    print(res[res.primary][["comparison", "model", "label", "tasks", "mean_second", "mean_first", "mean_diff", "ci_low", "ci_high", "p_holm"]]
          .round(3).to_string(index=False))
    print(pd.read_csv(tab / "tools.csv").to_string(index=False))


if __name__ == "__main__":
    main()
