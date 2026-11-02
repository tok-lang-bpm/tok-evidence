"""S3c, analysis (PROTOCOL-S3c.md §5): the S3c runs against the S3b runs of the same models and tasks.

    .venv/Scripts/python scripts/analyse_s3c.py

Writes results/S3c/main/tables/ (runs-scored.csv, means.csv, paired.csv, tools.csv).
"""

import pandas as pd

import analyse_s3 as a
from common import RESULTS

MODELS = ["gpt-oss:120b-cloud", "gemma4:31b-cloud"]


def main():
    tab = RESULTS / "S3c" / "main" / "tables"
    tab.mkdir(parents=True, exist_ok=True)
    c = a.score_runs("../S3c/main")  # score_runs reads RESULTS / "S3" / phase
    c.to_csv(tab / "runs-scored.csv", index=False)
    b = pd.read_csv(RESULTS / "S3b" / "main" / "tables" / "runs-scored.csv")
    b = b[b.model.isin(MODELS)]
    cols = [x for x, _ in a.PRIMARY + a.SECONDARY]
    means = pd.concat([b, c]).groupby(["model", "rep"])[cols].mean().round(3)
    means.to_csv(tab / "means.csv")

    res = []
    for comp, other in (("A: TOKAGENT - S3b XML", "XML"), ("B: TOKAGENT - S3b TOK", "TOK")):
        # paired() compares the columns "TOK" and "XML": the S3c runs play "TOK", the S3b arm "XML"
        df = pd.concat([c.assign(rep="TOK"), b[b.rep == other].assign(rep="XML")])
        for col, label in a.PRIMARY + a.SECONDARY:
            for r in a.paired(df, col):
                r.update(comparison=comp, label=label, primary=col in dict(a.PRIMARY))
                r["mean_S3c"], r["mean_S3b"] = r.pop("mean_TOK"), r.pop("mean_XML")
                res.append(r)
    res = pd.DataFrame(res)
    prim = res.primary & res.p_wilcoxon.notna()
    res.loc[prim, "p_holm"] = a.holm(res.loc[prim, "p_wilcoxon"])  # twelve tests
    res.to_csv(tab / "paired.csv", index=False)

    runs = pd.read_json(RESULTS / "S3c" / "main" / "runs.jsonl", lines=True)
    tools = pd.concat([runs[["model", "attempts", "tool_calls", "ended_by_budget", "loop_ok"]],
                       pd.json_normalize(runs.tool_calls_by_name).add_prefix("calls_")], axis=1)
    tools.assign(used_check=tools.calls_check > 0).groupby("model").mean(numeric_only=True).round(3).to_csv(tab / "tools.csv")

    print(means.T.to_string())
    print(res[res.primary][["comparison", "model", "label", "tasks", "mean_S3b", "mean_S3c", "mean_diff", "ci_low", "ci_high", "p_holm"]]
          .round(3).to_string(index=False))
    print(pd.read_csv(tab / "tools.csv").to_string(index=False))


if __name__ == "__main__":
    main()
