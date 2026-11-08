"""S8: the summary per corpus which the UAIS manuscript reports (results/S8/tables/s8-paper.csv).

Reads results/S8/tables/s8-by-model.csv and s8-ratios.csv and writes, per corpus, the medians of
the measures, the shares of spoken words which name symbols (all files of a corpus pooled), the
share of the spoken words of tok which the arrow and the quotes take, the share of tok models with
no change of indentation, the median share of lines which fit a 40-cell display, and the share of
diagrams which need horizontal scrolling.

    .venv/Scripts/python scripts/analyse_s8.py
"""

import pandas as pd

from common import RESULTS

T = RESULTS / "S8" / "tables"


def main():
    df = pd.read_csv(T / "s8-by-model.csv")
    rat = pd.read_csv(T / "s8-ratios.csv")
    rows = []
    for corpus, s in df.groupby("corpus", sort=False):
        row = {"corpus": corpus, "files": len(s)}
        for lvl in ("none", "some", "most", "all"):
            row[f"tok_words_{lvl}_median"] = s[f"tok_words_{lvl}"].median()
            row[f"xml_words_{lvl}_median"] = s[f"xml_words_{lvl}"].median()
            row[f"tok_symbol_share_{lvl}"] = s[f"tok_symbol_words_{lvl}"].sum() / s[f"tok_words_{lvl}"].sum()
            row[f"xml_symbol_share_{lvl}"] = s[f"xml_symbol_words_{lvl}"].sum() / s[f"xml_words_{lvl}"].sum()
            row[f"tok_arrow_share_{lvl}"] = s[f"tok_arrow_words_{lvl}"].sum() / s[f"tok_words_{lvl}"].sum()
            row[f"tok_quote_share_{lvl}"] = s[f"tok_quote_words_{lvl}"].sum() / s[f"tok_words_{lvl}"].sum()
        row["tok_indent_changes_median"] = s["tok_indent_changes"].median()
        row["xml_indent_changes_median"] = s["xml_indent_changes"].median()
        row["tok_indent_zero_share"] = (s["tok_indent_changes"] == 0).mean()
        for w in (40, 80):
            row[f"tok_braille_rows_{w}_median"] = s[f"tok_braille_rows_{w}"].median()
            row[f"xml_braille_rows_{w}_median"] = s[f"xml_braille_rows_{w}"].median()
            row[f"tok_fit_{w}_median"] = s[f"tok_fit_{w}"].median()
            row[f"xml_fit_{w}_median"] = s[f"xml_fit_{w}"].median()
        if "diagram_screens_2x" in s and s["diagram_screens_2x"].notna().any():
            for z in (2, 4):
                v = s[f"diagram_hscroll_{z}x"].dropna().astype(bool)
                row[f"diagrams_{z}x"] = int(v.size)
                row[f"diagram_hscroll_{z}x_share"] = float(v.mean())
                row[f"diagram_screens_{z}x_median"] = s[f"diagram_screens_{z}x"].median()
                row[f"text_screens_{z}x_median"] = s[f"text_screens_{z}x"].median()
        for _, r in rat[rat["corpus"] == corpus].iterrows():
            key = f"ratio_{r['numerator']}"
            row[key] = r["geo_mean"]
            row[key + "_ci_low"] = r["ci_low"]
            row[key + "_ci_high"] = r["ci_high"]
        rows.append(row)
    out = pd.DataFrame(rows)
    out.to_csv(T / "s8-paper.csv", index=False, encoding="utf-8", lineterminator="\n")
    pd.set_option("display.width", 250)
    print(out.set_index("corpus").T.to_string())


if __name__ == "__main__":
    main()
