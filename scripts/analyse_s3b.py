"""S3b, analysis (PROTOCOL-S3b.md §5): the functions of analyse_s3.py applied to results/S3b/main.

    .venv/Scripts/python scripts/analyse_s3b.py

Writes results/S3b/main/tables/ (runs-scored.csv, means.csv, paired.csv) and
directions.csv: the sign of the TOK − XML difference of each primary outcome for the three
models of S3b and the two of the main study.
"""

import pandas as pd

import analyse_s3 as a
from common import RESULTS

PHASE = "../S3b/main"  # score_runs reads RESULTS / "S3" / phase


def main():
    tab = RESULTS / "S3b" / "main" / "tables"
    tab.mkdir(parents=True, exist_ok=True)
    df = a.score_runs(PHASE)
    df.to_csv(tab / "runs-scored.csv", index=False)
    means = df.groupby(["model", "rep"])[[c for c, _ in a.PRIMARY + a.SECONDARY]].mean().round(3)
    means.to_csv(tab / "means.csv")
    res = []
    for col, label in a.PRIMARY + a.SECONDARY:
        for r in a.paired(df, col):
            r["label"], r["primary"] = label, col in dict(a.PRIMARY)
            res.append(r)
    res = pd.DataFrame(res)
    prim = res.primary & res.p_wilcoxon.notna()
    res.loc[prim, "p_holm"] = a.holm(res.loc[prim, "p_wilcoxon"])  # nine tests: three outcomes, three models
    res.to_csv(tab / "paired.csv", index=False)

    main_res = pd.read_csv(RESULTS / "S3" / "main" / "tables" / "paired.csv")
    both = pd.concat([main_res.assign(study="main"), res.assign(study="S3b")])
    both = both[both.primary.astype(bool)]
    sign = lambda r: "0" if r.ci_low <= 0 <= r.ci_high else ("TOK higher" if r.mean_diff > 0 else "XML higher")
    both["direction (95 % CI)"] = both.apply(sign, axis=1)
    both[["study", "model", "label", "mean_XML", "mean_TOK", "mean_diff", "ci_low", "ci_high", "p_holm", "direction (95 % CI)"]] \
        .round(4).to_csv(tab / "directions.csv", index=False)

    print(means.T.to_string())
    print(res[["model", "label", "tasks", "mean_XML", "mean_TOK", "mean_diff", "ci_low", "ci_high", "p_wilcoxon", "p_holm"]]
          .round(3).to_string(index=False))


if __name__ == "__main__":
    main()
