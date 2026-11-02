"""S1, step 1: the variants of every model of the corpora (PROTOCOL.md §4.2, §4.3).

Writes results/S1/variants/<corpus>/<model>/<variant> files and results/S1/raw/files.jsonl
(one record per model: origin, checksums, the tok diagnostics, import status, fidelity).

    .venv/Scripts/python scripts/s1_prepare.py [--workers 8]
"""

import argparse
import json
import re
import shutil
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import bpmn_graph
from common import (PROJECTS, RAW, RESULTS, core_bpmn, log, minify, run_tok, sha256,
                    without_diagram, write_json)

OUT = RESULTS / "S1"
VAR = OUT / "variants"
DMNDI_NS = "https://www.omg.org/spec/DMN/20191111/DMNDI/"


# ------------------------------------------------------------------ corpus N

def corpus_n():
    """(name, path) of every tok document of the project, deduplicated by content."""
    tok = PROJECTS / "tok"
    groups = [
        ("examples", sorted((tok / "examples").glob("*.tok"))),
        # the conformance cases with an expected BPMN file are the cases without errors
        ("conformance", sorted(p for p in (tok / "conformance" / "cases").glob("*.tok")
                               if (tok / "conformance" / "expected" / (p.stem + ".bpmn")).exists())),
        ("guide", sorted((PROJECTS / "tok-book" / "examples").glob("*.tok"))),
        ("course", sorted((PROJECTS / "tok-course" / "przyklady").glob("*.tok"))),
    ]
    seen, out = set(), []
    for group, paths in groups:
        for p in paths:
            h = sha256(p.read_bytes())
            if h in seen:
                continue
            seen.add(h)
            out.append((f"{group}/{p.stem}", p))
    return out


def strip_dmndi(data: bytes) -> bytes:
    from lxml import etree

    from common import parse_xml

    root = parse_xml(data)
    for e in list(root.iter()):
        if isinstance(e.tag, str) and e.tag.startswith("{" + DMNDI_NS) and e.getparent() is not None \
                and not e.getparent().tag.startswith("{" + DMNDI_NS):
            e.getparent().remove(e)
    return minify(etree.tostring(root, encoding="utf-8"))


def prepare_n(item):
    name, src = item
    rec = {"corpus": "N", "name": name, "source": str(src.relative_to(PROJECTS)).replace("\\", "/"),
           "sha256": sha256(src.read_bytes())}
    code, out, err, _ = run_tok(["check", src, "--json"])
    try:
        diag = json.loads(out)
        rec["errors"] = diag.get("errors", 0)
    except json.JSONDecodeError:
        rec["errors"] = None
        rec["check_output"] = (out + err)[-2000:]
    if rec["errors"] != 0:
        rec["status"] = "excluded: tok check reports errors"
        return rec
    d = VAR / "N" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "tok").write_bytes(src.read_bytes())
    code, fmt, err, _ = run_tok(["fmt", src])
    if code == 0:
        (d / "tok-fmt").write_bytes(fmt.encode("utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        code, out, err, _ = run_tok(["export", src, "-o", tmp / "di"])
        bpmn_di = sorted((tmp / "di").glob("*.bpmn"))
        if code != 0 or not bpmn_di:
            rec["status"] = "excluded: no BPMN (decision-only document or export error)"
            rec["export_output"] = (out + err)[-2000:]
            shutil.rmtree(d)
            return rec
        code, out, err, _ = run_tok(["bpmn", "--no-layout", src, "-o", tmp / "sem.bpmn"])
        sem = (tmp / "sem.bpmn").read_bytes()
        di = bpmn_di[0].read_bytes()
        dmn = [p.read_bytes() for p in sorted((tmp / "di").glob("*.dmn"))]
        forms = [p.read_bytes() for p in sorted((tmp / "di").glob("*.form"))]
    (d / "xml-sem").write_bytes(sem)
    (d / "xml-di").write_bytes(di)
    (d / "xml-sem-min").write_bytes(minify(sem))
    (d / "xml-di-min").write_bytes(minify(di))
    forms_min = [json.dumps(json.loads(f), separators=(",", ":"), ensure_ascii=False).encode("utf-8") for f in forms]
    nl = b"\n"
    (d / "bundle-sem").write_bytes(nl.join([sem, *[strip_dmndi(x) for x in dmn], *forms]))
    (d / "bundle-di").write_bytes(nl.join([di, *dmn, *forms]))
    (d / "bundle-sem-min").write_bytes(nl.join([minify(sem), *[strip_dmndi(x) for x in dmn], *forms_min]))
    (d / "bundle-di-min").write_bytes(nl.join([minify(di), *[minify(x) for x in dmn], *forms_min]))
    g = bpmn_graph.read(sem)
    rec.update(status="ok", dmn_files=len(dmn), form_files=len(forms), flow_nodes=len(g.nodes),
               sequence_flows=len(g.flows), kinds=dict(g.kinds()))
    return rec


# ------------------------------------------------------------------ corpora V, R, C

def corpus_xml():
    out = []
    suite = RAW / "miwg-suite"
    for p in sorted(suite.rglob("*")):
        if p.suffix.lower() != ".bpmn" or ".git" in p.parts or "Work in Progress" in p.parts:
            continue
        rel = p.relative_to(suite)
        corpus = "R" if rel.parts[0] == "Reference" else "V"
        out.append((corpus, rel.parts[0], "/".join(rel.parts), p))
    for p in sorted((PROJECTS / "tok" / "conformance" / "import").glob("*.bpmn")):
        out.append(("C", "Camunda Modeler", p.name, p))
    return out


def fidelity(orig, back):
    """What of the original survives the import and export: kinds, names, flows."""
    res = {}
    for key, a, b in (("kinds", orig.kinds(), back.kinds()),
                      ("named", orig.named(), back.named()),
                      ("flows", orig.flow_pairs(), back.flow_pairs())):
        total = sum(a.values())
        kept = sum((a & b).values())
        res[key] = {"total": total, "kept": kept,
                    "lost": [[list(k) if isinstance(k, tuple) else k, v] for k, v in (a - b).most_common(20)],
                    "added": [[list(k) if isinstance(k, tuple) else k, v] for k, v in (b - a).most_common(20)]}
    res["pools"] = {"total": len(orig.pools), "kept": sum((Counter(orig.pools) & Counter(back.pools)).values())}
    res["lanes"] = {"total": len(orig.lanes), "kept": sum((Counter(orig.lanes.values()) & Counter(back.lanes.values())).values())}
    res["message_flows"] = {"total": len(orig.message_flows), "kept": min(len(orig.message_flows), len(back.message_flows))}
    return res


def prepare_xml(item):
    corpus, tool, rel, src = item
    data = src.read_bytes()
    name = rel.replace("/", "__").removesuffix(".bpmn").removesuffix(".BPMN")
    rec = {"corpus": corpus, "tool": tool, "name": name, "source": rel, "sha256": sha256(data)}
    d = VAR / corpus / name
    try:
        orig = bpmn_graph.read(data)
        variants = {"xml": data, "xml-min": minify(data), "xml-sem-min": without_diagram(data),
                    "xml-core-min": core_bpmn(data)}
    except Exception as ex:  # not well-formed XML: excluded, reason kept
        rec["status"] = f"excluded: not well-formed XML ({type(ex).__name__}: {str(ex)[:200]})"
        return rec
    rec.update(flow_nodes=len(orig.nodes), sequence_flows=len(orig.flows), kinds=dict(orig.kinds()))
    if not orig.nodes and not orig.message_flows:
        rec["status"] = "excluded: no flow nodes"
        return rec
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        f = tmp / "in.bpmn"
        f.write_bytes(data)
        code, out, err, _ = run_tok(["import", f, "-o", tmp / "m.tok"])
        rec["import_exit"] = code
        rec["import_messages"] = (out + err)[-3000:]
        if code != 0 or not (tmp / "m.tok").exists():
            rec["status"] = "import failed"
            return rec
        code2, compact, err2, _ = run_tok(["import", "--no-flow-ids", f])
        tok_text = (tmp / "m.tok").read_bytes()
        side = tmp / "m.tok.layout"
        layout = side.read_bytes() if side.exists() else b""
        code3, out3, err3, _ = run_tok(["check", tmp / "m.tok", "--json"])
        try:
            rec["tok_check_errors"] = json.loads(out3).get("errors")
        except json.JSONDecodeError:
            rec["tok_check_errors"] = None
        code4, out4, err4, _ = run_tok(["bpmn", "--no-layout", "--no-sidecar", tmp / "m.tok", "-o", tmp / "back.bpmn"])
        back = (tmp / "back.bpmn").read_bytes() if (tmp / "back.bpmn").exists() else None
        rec["fidelity_route"] = "as imported" if back is not None else None
        if back is None:
            # second route (DEVIATIONS.md): the executable mark removed, the rest unchanged
            text = tok_text.decode("utf-8")
            lines = text.split("\n")
            lines = [re.sub(r" executable(?=\s|$)", "", ln) if i == 0 or ln.lstrip().startswith("pool ") else ln
                     for i, ln in enumerate(lines)]
            (tmp / "ne.tok").write_text("\n".join(lines), encoding="utf-8", newline="\n")
            code5, out5, err5, _ = run_tok(["bpmn", "--no-layout", "--no-sidecar", tmp / "ne.tok", "-o", tmp / "back2.bpmn"])
            if (tmp / "back2.bpmn").exists():
                back = (tmp / "back2.bpmn").read_bytes()
                rec["fidelity_route"] = "executable mark removed"
            else:
                code6, out6, err6, _ = run_tok(["check", tmp / "ne.tok", "--json"])
                try:
                    rec["blocking"] = sorted({x["code"] for x in json.loads(out6)["diagnostics"] if x.get("severity") == "error"})
                except (json.JSONDecodeError, KeyError):
                    rec["blocking"] = None
    d.mkdir(parents=True, exist_ok=True)
    for k, v in variants.items():
        (d / k).write_bytes(v)
    (d / "tok").write_bytes(tok_text)
    if code2 == 0:
        (d / "tok-compact").write_bytes(compact.encode("utf-8"))
    (d / "tok+layout").write_bytes(tok_text + b"\n" + layout)
    rec["status"] = "ok"
    if back is not None:
        rec["fidelity"] = fidelity(orig, bpmn_graph.read(back))
    else:
        rec["fidelity"] = None
        rec["export_messages"] = (out4 + err4)[-2000:]
    return rec


# ------------------------------------------------------------------ corpus D

def corpus_dmn():
    root = PROJECTS / "tok" / "conformance" / "dmn-tck"
    return [("D", p.parent.parent.name, str(p.relative_to(root)).replace("\\", "/"), p) for p in sorted(root.rglob("*.dmn"))]


def without_dmndi(data: bytes) -> bytes:
    """The DMN file without its DMNDI element (any DMN version), minified."""
    from lxml import etree

    from common import parse_xml

    root = parse_xml(data)
    for e in list(root.iter()):
        if isinstance(e.tag, str) and etree.QName(e).localname == "DMNDI" and e.getparent() is not None:
            e.getparent().remove(e)
    return minify(etree.tostring(root, encoding="utf-8"))


def prepare_dmn(item):
    corpus, level, rel, src = item
    data = src.read_bytes()
    name = rel.replace("/", "__").removesuffix(".dmn")
    rec = {"corpus": corpus, "tool": level, "name": name, "source": rel, "sha256": sha256(data)}
    try:
        variants = {"dmn": data, "dmn-min": minify(data), "dmn-sem-min": without_dmndi(data)}
    except Exception as ex:
        rec["status"] = f"excluded: not well-formed XML ({type(ex).__name__})"
        return rec
    code, out, err, _ = run_tok(["import", src])
    rec["import_exit"] = code
    if code != 0 or not out.strip():
        rec["status"] = "import failed"
        rec["import_messages"] = (out + err)[-2000:]
        return rec
    d = VAR / corpus / name
    d.mkdir(parents=True, exist_ok=True)
    for k, v in variants.items():
        (d / k).write_bytes(v)
    (d / "tok").write_bytes(out.encode("utf-8"))
    rec["status"] = "ok"
    rec["flow_nodes"] = 0
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    if VAR.exists():
        shutil.rmtree(VAR)
    raw = OUT / "raw" / "files.jsonl"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.unlink(missing_ok=True)
    n, x = corpus_n(), corpus_xml()
    log(f"corpus N: {len(n)} documents; corpora V/R/C: {len(x)} files")
    recs = []
    with ThreadPoolExecutor(args.workers) as ex:
        recs += list(ex.map(prepare_n, n))
        log("N done")
        recs += list(ex.map(prepare_xml, x))
        recs += list(ex.map(prepare_dmn, corpus_dmn()))
    with raw.open("w", encoding="utf-8", newline="\n") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    summary = Counter((r["corpus"], r["status"].split(":")[0]) for r in recs)
    write_json(OUT / "raw" / "prepare-summary.json", {f"{a} {b}": v for (a, b), v in sorted(summary.items())})
    for (a, b), v in sorted(summary.items()):
        log(f"{a:2} {b:30} {v}")


if __name__ == "__main__":
    main()
