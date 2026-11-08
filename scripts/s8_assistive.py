"""S8: the text as assistive technologies deliver it (PROTOCOL-S8.md).

Measures, on the frozen files of S1, what a screen reader speaks for a tok model and for its XML
(NVDA's English symbol table, levels none, some, most and all), how many rows of a 40- and an
80-cell braille display a reader pans through, and how many screens a reader moves across at
200 % and 400 % magnification to see the diagram or to read the reflowed text. Writes
results/S8/tables/*.csv and results/S8/s8-summary.json.

    .venv/Scripts/python scripts/s8_assistive.py
"""

import hashlib
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

from common import RAW, RESULTS, SEED, parse_xml, read_jsonl, write_json

VAR = RESULTS / "S1" / "variants"
OUT = RESULTS / "S8"
TABLES = OUT / "tables"
NVDA = RAW / "nvda" / "symbols-en.dic"

# corpus -> the file as exported (S7)
EXPORTED = {"N": "xml-di", "V": "xml", "R": "xml", "C": "xml", "D": "dmn"}
BPMN_CORPORA = ("N", "V", "R", "C")
LEVELS = {"none": 0, "some": 100, "most": 200, "all": 300, "char": 1000}
SPEECH_LEVELS = ("none", "some", "most", "all")
WIDTHS = (40, 80)
ZOOMS = (2, 4)
SCREEN_W, SCREEN_H = 1280, 720
CHAR_W, LINE_H = 0.6 * 14, 1.4 * 14
DC = "{http://www.omg.org/spec/DD/20100524/DC}"
DI = "{http://www.omg.org/spec/DD/20100524/DI}"


# ------------------------------------------------------------------ NVDA symbol table

def _unescape(s: str) -> str:
    out, i = [], 0
    table = {"\\": "\\", "#": "#", "t": "\t", "n": "\n", "r": "\r", "f": "\f", "v": "\v", "0": "\0"}
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s) and s[i + 1] in table:
            out.append(table[s[i + 1]])
            i += 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def load_symbols(path: Path):
    """(complex: list of (identifier, regex)), (symbols: identifier -> (replacement, level))."""
    complex_, symbols, section = [], {}, None
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        if not raw.strip() or raw.startswith("#"):
            continue
        if raw.rstrip() in ("complexSymbols:", "symbols:"):
            section = raw.rstrip()[:-1]
            continue
        parts = raw.split("\t")
        ident = _unescape(parts[0])
        if section == "complexSymbols":
            complex_.append((ident, parts[1]))
        elif section == "symbols":
            fields = [p for p in parts[1:]]
            # a trailing "# display name" field is not part of the definition
            fields = [f for f in fields if not f.startswith("#")]
            replacement = _unescape(fields[0]) if fields else ""
            level = fields[1].strip() if len(fields) > 1 and fields[1].strip() else "all"
            symbols[ident] = (replacement, LEVELS.get(level, LEVELS["all"]))
    return complex_, symbols


class Speaker:
    """The spoken form of a line under NVDA's symbol processing at one punctuation level."""

    def __init__(self, path: Path):
        complex_, symbols = load_symbols(path)
        self.symbols = symbols
        self.complex_ids = [c for c, _ in complex_]
        simple = sorted((s for s in symbols if s not in set(self.complex_ids)), key=len, reverse=True)
        groups = [f"(?P<c{i}>{rx})" for i, (_, rx) in enumerate(complex_)]
        groups.append("(?P<simple>" + "|".join(re.escape(s) for s in simple) + ")")
        self.rx = re.compile("|".join(groups))

    def speak(self, line: str, level: int) -> tuple[str, int]:
        """(spoken text, number of words that name symbols)."""
        sym_words = 0

        def sub(m):
            nonlocal sym_words
            if m.lastgroup == "simple":
                ident = m.group(0)
            else:
                ident = self.complex_ids[int(m.lastgroup[1:])]
            repl, lvl = self.symbols.get(ident, ("", LEVELS["all"]))
            if lvl <= level and repl:
                sym_words += count_words(repl)
                return f" {repl} "
            return " "

        return self.rx.sub(sub, line), sym_words


WORD = re.compile(r"[^\W_]+")
CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z])")


def count_words(text: str) -> int:
    return sum(len(CAMEL.split(w)) for w in WORD.findall(text))


# ------------------------------------------------------------------ measures

def lines_of(data: bytes) -> list[str]:
    text = data.decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n")
    return [ln for ln in text.split("\n") if ln.strip()]


def leading(ln: str) -> int:
    lead = ln[: len(ln) - len(ln.lstrip())]
    return sum(4 if ch == "\t" else 1 for ch in lead)


def speech(lines: list[str], sp: Speaker) -> dict:
    out = {}
    for name in SPEECH_LEVELS:
        lvl = LEVELS[name]
        words = sym = 0
        for ln in lines:
            spoken, s = sp.speak(ln.strip(), lvl)
            words += count_words(spoken)
            sym += s
        out[f"words_{name}"] = words
        out[f"symbol_words_{name}"] = sym
    prev, changes = None, 0
    for ln in lines:
        d = leading(ln)
        if prev is not None and d != prev:
            changes += 1
        prev = d
    out["indent_changes"] = changes
    return out


def braille(lines: list[str]) -> dict:
    out = {}
    for w in WIDTHS:
        out[f"braille_rows_{w}"] = sum(max(1, math.ceil(len(ln) / w)) for ln in lines)
        out[f"fit_{w}"] = sum(len(ln) <= w for ln in lines) / len(lines) if lines else np.nan
    return out


def diagram_extent(data: bytes):
    root = parse_xml(data)
    xs, ys = [], []
    for b in root.iter(DC + "Bounds"):
        x, y = float(b.get("x", 0)), float(b.get("y", 0))
        w, h = float(b.get("width", 0)), float(b.get("height", 0))
        xs += [x, x + w]
        ys += [y, y + h]
    for p in root.iter(DI + "waypoint"):
        xs.append(float(p.get("x", 0)))
        ys.append(float(p.get("y", 0)))
    if not xs:
        return None
    return max(xs) - min(xs), max(ys) - min(ys)


def magnification(extent, tok_lines: list[str]) -> dict:
    out = {}
    for z in ZOOMS:
        if extent is not None:
            w, h = extent
            cols = math.ceil(w * z / SCREEN_W)
            out[f"diagram_screens_{z}x"] = cols * math.ceil(h * z / SCREEN_H)
            out[f"diagram_hscroll_{z}x"] = cols > 1
        else:
            out[f"diagram_screens_{z}x"] = np.nan
            out[f"diagram_hscroll_{z}x"] = np.nan
        per_row = math.floor(SCREEN_W / z / CHAR_W)
        per_screen = math.floor(SCREEN_H / z / LINE_H)
        rows = sum(max(1, math.ceil(len(ln) / per_row)) for ln in tok_lines)
        out[f"text_screens_{z}x"] = math.ceil(rows / per_screen)
    return out


def geo_ci(r, n_boot=10_000, seed=SEED):
    r = np.asarray(r, float)
    lr = np.log(r)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(lr), size=(n_boot, len(lr)))
    boots = np.exp(lr[idx].mean(axis=1))
    return float(np.exp(lr.mean())), float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))


def main():
    TABLES.mkdir(parents=True, exist_ok=True)
    sp = Speaker(NVDA)
    arrow = {n: count_words(sp.speak("->", LEVELS[n])[0]) for n in SPEECH_LEVELS}
    quote = {n: count_words(sp.speak('"', LEVELS[n])[0]) for n in SPEECH_LEVELS}
    records = [r for r in read_jsonl(RESULTS / "S1" / "raw" / "files.jsonl") if r.get("status") == "ok"]
    rows, missing, no_diagram = [], [], []
    for r in records:
        corpus, name = r["corpus"], r["name"]
        d = VAR / corpus / name
        exp = d / EXPORTED[corpus]
        if not (d / "tok").exists() or not exp.exists():
            missing.append(f"{corpus}/{name}")
            continue
        tl, xb = lines_of((d / "tok").read_bytes()), exp.read_bytes()
        xl = lines_of(xb)
        row = {"corpus": corpus, "model": name, "tool": r.get("tool", "")}
        row.update({f"tok_{k}": v for k, v in speech(tl, sp).items()})
        row.update({f"xml_{k}": v for k, v in speech(xl, sp).items()})
        n_arrow = sum(ln.count("->") for ln in tl)
        n_quote = sum(ln.count('"') for ln in tl)
        for n in SPEECH_LEVELS:
            row[f"tok_arrow_words_{n}"] = n_arrow * arrow[n]
            row[f"tok_quote_words_{n}"] = n_quote * quote[n]
        row.update({f"tok_{k}": v for k, v in braille(tl).items()})
        row.update({f"xml_{k}": v for k, v in braille(xl).items()})
        if corpus in BPMN_CORPORA:
            ext = diagram_extent(xb)
            if ext is None:
                no_diagram.append(f"{corpus}/{name}")
            row.update(magnification(ext, tl))
        rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(TABLES / "s8-by-model.csv", index=False, encoding="utf-8", lineterminator="\n")

    measures = [c for c in df.columns if c not in ("corpus", "model", "tool")]
    summ = []
    for corpus, sub in df.groupby("corpus", sort=False):
        for m in measures:
            v = pd.to_numeric(sub[m], errors="coerce").dropna().astype(float)
            if v.empty:
                continue
            summ.append({"corpus": corpus, "measure": m, "files": int(v.size), "mean": float(v.mean()),
                         "median": float(v.median()), "q1": float(v.quantile(0.25)),
                         "q3": float(v.quantile(0.75)), "min": float(v.min()), "max": float(v.max())})
    pd.DataFrame(summ).to_csv(TABLES / "s8-summary.csv", index=False, encoding="utf-8", lineterminator="\n")

    comps = [(f"xml_words_{n}", f"tok_words_{n}", f"spoken words of the XML over tok, level {n}") for n in SPEECH_LEVELS]
    comps += [("xml_indent_changes", "tok_indent_changes", "indentation changes of the XML over tok")]
    comps += [(f"xml_braille_rows_{w}", f"tok_braille_rows_{w}", f"braille rows of the XML over tok, {w} cells") for w in WIDTHS]
    comps += [(f"diagram_screens_{z}x", f"text_screens_{z}x", f"screens of the diagram over screens of the tok text, {z * 100} %") for z in ZOOMS]
    rat = []
    for corpus, sub in df.groupby("corpus", sort=False):
        for x, t, label in comps:
            if x not in sub or t not in sub:
                continue
            a = pd.to_numeric(sub[x], errors="coerce")
            b = pd.to_numeric(sub[t], errors="coerce")
            ok = a.notna() & b.notna() & (a > 0) & (b > 0)
            r = (a[ok] / b[ok]).to_numpy(dtype=float)
            if not len(r):
                continue
            g, lo, hi = geo_ci(r)
            rat.append({"corpus": corpus, "numerator": x, "denominator": t, "comparison": label, "files": len(r),
                        "geo_mean": g, "ci_low": lo, "ci_high": hi, "median": float(np.median(r)),
                        "q1": float(np.quantile(r, 0.25)), "q3": float(np.quantile(r, 0.75)),
                        "min": float(r.min()), "max": float(r.max())})
    pd.DataFrame(rat).to_csv(TABLES / "s8-ratios.csv", index=False, encoding="utf-8", lineterminator="\n")

    hscroll = {}
    for corpus, sub in df[df["corpus"].isin(BPMN_CORPORA)].groupby("corpus"):
        for z in ZOOMS:
            v = sub[f"diagram_hscroll_{z}x"].dropna().astype(bool)
            hscroll[f"{corpus}_{z}x"] = {"diagrams": int(v.size), "need_horizontal_scrolling": int(v.sum()),
                                        "share": float(v.mean()) if v.size else None}
    tag = (RAW / "nvda" / "TAG-COMMIT.txt").read_text(encoding="utf-8").split()
    summary = {
        "files_measured": {c: int(n) for c, n in df["corpus"].value_counts().items()},
        "files_missing_variants": missing,
        "files_without_diagram": no_diagram,
        "horizontal_scrolling": hscroll,
        "words_spoken_for_arrow": arrow,
        "words_spoken_for_quote": quote,
        "nvda_symbols": {"file": "data/raw/nvda/symbols-en.dic", "tag": tag[1] if len(tag) > 1 else "",
                         "commit": tag[0] if tag else "",
                         "sha256": hashlib.sha256(NVDA.read_bytes()).hexdigest()},
        "screen_css_px": [SCREEN_W, SCREEN_H], "font_px": 14, "char_width_em": 0.6, "line_height_em": 1.4,
        "seed": SEED,
    }
    write_json(OUT / "s8-summary.json", summary)
    print(pd.DataFrame(rat)[["corpus", "comparison", "files", "geo_mean", "ci_low", "ci_high", "median"]].to_string())
    print({k: v for k, v in summary.items() if k not in ("files_missing_variants", "files_without_diagram")})


if __name__ == "__main__":
    main()
