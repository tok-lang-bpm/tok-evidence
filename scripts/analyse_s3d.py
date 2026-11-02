"""S3d, analysis (PROTOCOL-S3d.md §5): Claude agents against S3, Beam's cold start and agent.

    .venv/Scripts/python scripts/analyse_s3d.py

Writes results/S3d/main/tables/ (runs-scored.csv, means.csv, paired.csv, tools.csv).
"""

import pandas as pd

import analyse_s3 as a
from common import RESULTS

BEAM = "beam:cloud"


def compare(df_s3d, df_base, model, comp, mine, other):
    """paired() compares the columns "TOK" and "XML": `mine` plays "TOK", `other` plays "XML"."""
    x = df_s3d[(df_s3d.model == model) & (df_s3d.rep == mine)].assign(rep="TOK")
    y = df_base[(df_base.model == model) & (df_base.rep == other)].assign(rep="XML")
    out = []
    for col, label in a.PRIMARY + a.SECONDARY:
        for r in a.paired(pd.concat([x, y]), col):
            r.update(comparison=comp, label=label, primary=col in dict(a.PRIMARY))
            out.append(r)
    return out


def main():
    tab = RESULTS / "S3d" / "main" / "tables"
    tab.mkdir(parents=True, exist_ok=True)
    d = a.score_runs("../S3d/main")  # score_runs reads RESULTS / "S3" / phase
    d.to_csv(tab / "runs-scored.csv", index=False)
    s3 = pd.read_csv(RESULTS / "S3" / "main" / "tables" / "runs-scored.csv")
    cols = [x for x, _ in a.PRIMARY + a.SECONDARY]
    means = pd.concat([s3, d]).groupby(["model", "rep"])[cols].mean().round(3)
    means.to_csv(tab / "means.csv")

    res = []
    for m in ("haiku", "sonnet"):
        res += compare(d, s3, m, "A: TOKAGENT - S3 XML", "TOKAGENT", "XML")
        res += compare(d, s3, m, "B: TOKAGENT - S3 TOK", "TOKAGENT", "TOK")
    res += compare(d, d, BEAM, "C: TOK - XML (cold start)", "TOK", "XML")
    res += compare(d, d, BEAM, "A: TOKAGENT - XML", "TOKAGENT", "XML")
    res += compare(d, d, BEAM, "B: TOKAGENT - TOK", "TOKAGENT", "TOK")
    res = pd.DataFrame(res).rename(columns={"mean_TOK": "mean_first", "mean_XML": "mean_second"})
    prim = res.primary & res.p_wilcoxon.notna()
    res.loc[prim, "p_holm"] = a.holm(res.loc[prim, "p_wilcoxon"])  # 21 tests
    res.to_csv(tab / "paired.csv", index=False)

    runs = pd.read_json(RESULTS / "S3d" / "main" / "runs.jsonl", lines=True)
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
