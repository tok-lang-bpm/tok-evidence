"""S2: fault injection (PROTOCOL.md §5).

For every base model (valid documents of corpus N with a start event, an end event and at
least four flow nodes), every fault operator is applied at up to three sites, once as an
edit of the tok text and once as the same edit of the semantic BPMN XML that tok exports
from the unmodified document. Both mutants and the unmodified pair are then checked by tok,
by the OMG XML Schema and by bpmnlint (two rule sets).

    .venv/Scripts/python scripts/s2_faults.py [--workers 8]

Writes results/S2/mutants/<base>/<operator>-<site>/ (m.tok, m.bpmn, meta.json) and
results/S2/raw/{tok,xsd,lint-recommended,lint-correctness}.jsonl.
"""

import argparse
import copy
import json
import re
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import bpmn_graph
from common import BPMN_NS, RAW, RESULTS, append_jsonl, log, read_jsonl, run_tok

S2 = RESULTS / "S2"
MUT = S2 / "mutants"
VAR = RESULTS / "S1" / "variants" / "N"
UNDEFINED = "undefined_node"
NODE_KW = ("start|end|catch|throw|boundary|task|user|manual|service|script|rule|send|receive|call|"
           "sub|adhoc|eventsub|transaction|xor|and|or|eventgw|complex")
DECL = re.compile(rf"^(\s*)({NODE_KW})\s+([A-Za-z_][A-Za-z0-9_-]*)(.*)$")
FLOW = re.compile(r"^(\s*)flow\s+(.+?)\s*$")
OPERATORS = ["F01", "F02", "F03", "F04", "F05", "F06", "F07", "F08", "F09", "F10", "F11", "F12", "F13", "F14"]
DESCRIPTION = {
    "F01": "flow to an undefined node", "F02": "duplicate identifier", "F03": "no start event",
    "F04": "no end event", "F05": "disconnected activity", "F06": "exclusive split without conditions",
    "F07": "deadlock: exclusive split joined by a parallel join", "F08": "activity of an undefined lane",
    "F09": "boundary event on an undefined activity", "F10": "start event with an incoming flow",
    "F11": "end event with an outgoing flow", "F12": "sequence flow between two pools",
    "F13": "malformed condition expression", "F14": "self-loop",
}


# ------------------------------------------------------------------ the tok side

class TokDoc:
    """The lines of a tok document with its declarations and flow statements."""

    def __init__(self, text):
        self.lines = text.split("\n")
        self.decl = {}  # id → line index
        self.kind = {}  # id → keyword
        self.flows = []  # (line index, ids, rest)
        self.ok = True
        for i, ln in enumerate(self.lines):
            m = DECL.match(ln)
            if m and not ln.lstrip().startswith("flow "):
                self.decl.setdefault(m.group(3), i)
                self.kind.setdefault(m.group(3), m.group(2))
                continue
            m = FLOW.match(ln)
            if m:
                body = m.group(2)
                parts = [p.strip() for p in body.split("->")]
                if '"' in body.rsplit("->", 1)[0] or len(parts) < 2:
                    self.ok = False  # a label before an arrow: not parsed, the model is skipped
                    continue
                ids = [p.split()[0] for p in parts]
                rest = parts[-1][len(ids[-1]):]
                if any(len(p.split()) != 1 for p in parts[:-1]):
                    self.ok = False
                    continue
                self.flows.append((i, ids, rest))

    def text(self):
        return "\n".join(self.lines)

    def edges(self):
        return [(i, a, b) for i, ids, _ in self.flows for a, b in zip(ids, ids[1:])]

    def remove_nodes_from_flows(self, nodes):
        """Every flow touching one of the nodes removed; chains are split around them."""
        edited = []
        for i, ids, rest in sorted(self.flows, reverse=True):
            if not any(n in ids for n in nodes):
                continue
            indent = FLOW.match(self.lines[i]).group(1)
            segs, cur = [], []
            for x in ids:
                if x in nodes:
                    if cur:
                        segs.append(cur)
                    cur = []
                else:
                    cur.append(x)
            if cur:
                segs.append(cur)
            new = []
            for s in segs:
                if len(s) >= 2:
                    tail = rest if s[-1] == ids[-1] else ""
                    new.append(f"{indent}flow {' -> '.join(s)}{tail}")
            # the line is replaced in place, so the indexes of the other lines stay valid
            self.lines[i] = "\n".join(new) if new else None
            edited.append(i)
        return edited

    def remove_decl(self, node):
        i = self.decl[node]
        self.lines[i] = None

    def finish(self):
        self.lines = [ln for ln in self.lines if ln is not None]

    def append(self, line):
        while self.lines and self.lines[-1].strip() == "":
            self.lines.pop()
        self.lines.append(line)
        self.lines.append("")
        return len(self.lines) - 2


# ------------------------------------------------------------------ the XML side

def xml_doc(data):
    from lxml import etree

    return etree.fromstring(data, etree.XMLParser(remove_blank_text=False))


def by_id(root, i):
    r = root.xpath("//*[@id=$i]", i=i)
    return r[0] if r else None


def q(name):
    return f"{{{BPMN_NS}}}{name}"


def xml_remove_node_flows(root, nodes):
    for f in list(root.iter(q("sequenceFlow"))):
        if f.get("sourceRef") in nodes or f.get("targetRef") in nodes:
            f.getparent().remove(f)


def xml_remove_nodes(root, nodes):
    xml_remove_node_flows(root, nodes)
    for n in nodes:
        e = by_id(root, n)
        if e is not None:
            e.getparent().remove(e)
    for r in list(root.iter(q("flowNodeRef"))):
        if (r.text or "").strip() in nodes:
            r.getparent().remove(r)


def xml_add_flow(root, parent_of, source, target, fid="injected_flow"):
    from lxml import etree

    src = by_id(root, parent_of)
    f = etree.SubElement(src.getparent(), q("sequenceFlow"))
    f.set("id", fid)
    f.set("sourceRef", source)
    f.set("targetRef", target)
    return f


def xml_line_of(data, ids):
    root = xml_doc(data)
    return sorted({e.sourceline for i in ids for e in root.xpath("//*[@id=$i]", i=i)})


# ------------------------------------------------------------------ operators

def sites(candidates):
    """The first, the middle and the last candidate, without repetition."""
    if not candidates:
        return []
    idx = sorted({0, len(candidates) // 2, len(candidates) - 1})
    return [candidates[i] for i in idx]


def mutants(tok_text, xml_data):
    """Yields (operator, site number, tok text, xml bytes, meta) for one base model."""
    from lxml import etree

    base = TokDoc(tok_text)
    g = bpmn_graph.read(xml_data)
    root0 = xml_doc(xml_data)
    order = [i for i, _ in sorted(base.decl.items(), key=lambda kv: kv[1]) if i in g.nodes]
    acts = [i for i in order if g.nodes[i][0].startswith(("task:", "activity:"))]
    starts = [i for i in order if g.nodes[i][0].startswith("event:start")]
    ends = [i for i in order if g.nodes[i][0].startswith("event:end")]
    parent = {i: by_id(root0, i).getparent().get("id") for i in order if by_id(root0, i) is not None}
    out_edges = {}
    for _, s, t, _ in g.flows:
        out_edges.setdefault(s, []).append(t)
    in_count = {}
    for _, s, t, _ in g.flows:
        in_count[t] = in_count.get(t, 0) + 1

    def emit(op, k, doc, root, meta):
        doc.finish()
        return op, k, doc.text(), etree.tostring(root, encoding="utf-8", xml_declaration=True), meta

    # F01: the target of the last hop of a flow statement renamed
    cands = [(i, ids) for i, ids, _ in base.flows]
    for k, (i, ids) in enumerate(sites(cands)):
        s, t = ids[-2], ids[-1]
        f = next((f for f in root0.iter(q("sequenceFlow")) if f.get("sourceRef") == s and f.get("targetRef") == t), None)
        if f is None:
            continue
        d, r = TokDoc(tok_text), copy.deepcopy(root0)
        ln = d.lines[i]
        j = ln.rfind(t)
        d.lines[i] = ln[:j] + UNDEFINED + ln[j + len(t):]
        fr = by_id(r, f.get("id"))
        fr.set("targetRef", UNDEFINED)
        yield emit("F01", k, d, r, {"ids": [s, t, f.get("id"), UNDEFINED], "tok_lines": [i + 1]})
    # F02: a node's identifier set to that of the first node
    for k, b in enumerate(sites(order[1:])):
        a = order[0]
        d, r = TokDoc(tok_text), copy.deepcopy(root0)
        i = d.decl[b]
        m = DECL.match(d.lines[i])
        d.lines[i] = m.group(1) + m.group(2) + " " + a + m.group(4)
        by_id(r, b).set("id", a)
        yield emit("F02", k, d, r, {"ids": [a, b], "tok_lines": [i + 1, base.decl[a] + 1]})
    # F03, F04: every start event / every end event removed with its flows
    for op, nodes in (("F03", starts), ("F04", ends)):
        if nodes:
            d, r = TokDoc(tok_text), copy.deepcopy(root0)
            lines = d.remove_nodes_from_flows(set(nodes))
            for n in nodes:
                d.remove_decl(n)
            xml_remove_nodes(r, set(nodes))
            yield emit(op, 0, d, r, {"ids": list(nodes), "tok_lines": []})
    # F05: every flow into and out of an activity removed
    connected = [a for a in acts if a in out_edges or in_count.get(a)]
    for k, a in enumerate(sites(connected)):
        d, r = TokDoc(tok_text), copy.deepcopy(root0)
        d.remove_nodes_from_flows({a})
        xml_remove_node_flows(r, {a})
        yield emit("F05", k, d, r, {"ids": [a], "tok_lines": [base.decl[a] + 1]})
    # F06: an exclusive split without conditions and default
    xs = [i for i in order if g.nodes[i][0] == "gateway:exclusive" and len(out_edges.get(i, [])) >= 2
          and (any(c for _, s, _, c in g.flows if s == i) or by_id(root0, i).get("default"))]
    for k, x in enumerate(sites(xs)):
        d, r = TokDoc(tok_text), copy.deepcopy(root0)
        lines = []
        for i, ids, rest in d.flows:
            if ids[0] == x and len(ids) == 2:
                new = re.sub(r'\s+when="[^"]*"', "", d.lines[i])
                new = re.sub(r"\s+default(?=\s|$)", "", new)
                if new != d.lines[i]:
                    d.lines[i] = new
                    lines.append(i + 1)
        for f in r.iter(q("sequenceFlow")):
            if f.get("sourceRef") == x:
                for c in f.findall(q("conditionExpression")):
                    f.remove(c)
        by_id(r, x).attrib.pop("default", None)
        yield emit("F06", k, d, r, {"ids": [x], "tok_lines": lines or [base.decl[x] + 1]})
    # F07: the join of exclusive branches made parallel
    joins = [i for i in order if g.nodes[i][0] == "gateway:exclusive" and in_count.get(i, 0) >= 2 and len(out_edges.get(i, [])) == 1]
    for k, j in enumerate(sites(joins)):
        d, r = TokDoc(tok_text), copy.deepcopy(root0)
        i = d.decl[j]
        d.lines[i] = re.sub(r"^(\s*)xor\b", r"\1and", d.lines[i])
        e = by_id(r, j)
        e.tag = q("parallelGateway")
        e.attrib.pop("default", None)
        yield emit("F07", k, d, r, {"ids": [j], "tok_lines": [i + 1]})
    # F08: not expressible in tok (an activity is placed inside its lane block); no pairs
    # F09: the activity of a boundary event renamed
    bds = [i for i in order if g.nodes[i][0].startswith("event:boundary")]
    for k, b in enumerate(sites(bds)):
        d, r = TokDoc(tok_text), copy.deepcopy(root0)
        i = d.decl[b]
        new = re.sub(r"\bon=([A-Za-z_][A-Za-z0-9_-]*)", "on=" + UNDEFINED, d.lines[i])
        if new == d.lines[i]:
            continue
        d.lines[i] = new
        by_id(r, b).set("attachedToRef", UNDEFINED)
        yield emit("F09", k, d, r, {"ids": [b, UNDEFINED], "tok_lines": [i + 1]})
    # F10, F11: a flow into a start event / out of an end event, from/to the first activity
    for op, events in (("F10", starts), ("F11", ends)):
        for k, ev in enumerate(sites(events)):
            a = next((x for x in acts if parent.get(x) == parent.get(ev)), None)
            if a is None:
                continue
            s, t = (a, ev) if op == "F10" else (ev, a)
            d, r = TokDoc(tok_text), copy.deepcopy(root0)
            ln = d.append(f"flow {s} -> {t}")
            xml_add_flow(r, s, s, t)
            yield emit(op, k, d, r, {"ids": [s, t, "injected_flow"], "tok_lines": [ln + 1]})
    # F12: a sequence flow from an activity of one process to one of another
    procs = []
    for a in acts:
        p = parent.get(a)
        if p and by_id(root0, p) is not None and bpmn_graph.local(by_id(root0, p).tag) == "process" and p not in [x[0] for x in procs]:
            procs.append((p, a))
    if len(procs) >= 2:
        (p1, a1), (p2, a2) = procs[0], procs[1]
        d, r = TokDoc(tok_text), copy.deepcopy(root0)
        ln = d.append(f"flow {a1} -> {a2}")
        xml_add_flow(r, a1, a1, a2)
        yield emit("F12", 0, d, r, {"ids": [a1, a2, "injected_flow"], "tok_lines": [ln + 1]})
    # F13: an unbalanced parenthesis in a condition
    conds = [(i, ids) for i, ids, rest in base.flows if len(ids) == 2 and 'when="' in rest and not re.search(r'when=""', rest)]
    for k, (i, ids) in enumerate(sites(conds)):
        s, t = ids
        f = next((f for f in root0.iter(q("sequenceFlow")) if f.get("sourceRef") == s and f.get("targetRef") == t
                  and f.find(q("conditionExpression")) is not None), None)
        if f is None:
            continue
        d, r = TokDoc(tok_text), copy.deepcopy(root0)
        d.lines[i] = re.sub(r'when="', 'when="(', d.lines[i], count=1)
        c = by_id(r, f.get("id")).find(q("conditionExpression"))
        txt = c.text or ""
        c.text = ("=(" + txt[1:]) if txt.startswith("=") else "(" + txt
        yield emit("F13", k, d, r, {"ids": [s, t, f.get("id")], "tok_lines": [i + 1]})
    # F14: a flow from an activity to itself
    for k, a in enumerate(sites(acts)):
        d, r = TokDoc(tok_text), copy.deepcopy(root0)
        ln = d.append(f"flow {a} -> {a}")
        xml_add_flow(r, a, a, a)
        yield emit("F14", k, d, r, {"ids": [a, "injected_flow"], "tok_lines": [ln + 1]})


# ------------------------------------------------------------------ validators

_local = threading.local()


def xsd_check(path):
    from lxml import etree

    # one schema object per thread: its error log is not shared safely between threads
    if not hasattr(_local, "schema"):
        _local.schema = etree.XMLSchema(etree.parse(str(RAW / "xsd" / "BPMN20.xsd")))
    _schema = _local.schema
    t0 = time.perf_counter()
    try:
        doc = etree.parse(str(path))
        ok = _schema.validate(doc)
        errs = [{"line": e.line, "message": e.message[:300]} for e in _schema.error_log]
    except etree.XMLSyntaxError as ex:
        ok, errs = False, [{"line": ex.lineno, "message": "not well-formed: " + str(ex)[:300]}]
    return {"valid": ok, "errors": errs, "ms": (time.perf_counter() - t0) * 1000}


def tok_check(path):
    code, out, err, dt = run_tok(["check", path.name, "--level", "full", "--json"], cwd=path.parent)
    try:
        d = json.loads(out)
        diags = [{"code": x["code"], "severity": x["severity"], "line": x.get("line"), "id": x.get("id"),
                  "message": x.get("message", "")[:300]} for x in d["diagnostics"]]
    except (json.JSONDecodeError, KeyError):
        diags = [{"code": "CRASH", "severity": "error", "line": None, "id": None, "message": (out + err)[-300:]}]
    return {"exit": code, "diagnostics": diags, "ms": dt * 1000}


def bases():
    files = read_jsonl(RESULTS / "S1" / "raw" / "files.jsonl")
    out = []
    for r in files:
        if r["corpus"] != "N" or r["status"] != "ok":
            continue
        k = r["kinds"]
        if r["flow_nodes"] >= 4 and any(x.startswith("event:start") for x in k) and any(x.startswith("event:end") for x in k):
            out.append(r["name"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    if MUT.exists():
        shutil.rmtree(MUT)
    (S2 / "raw").mkdir(parents=True, exist_ok=True)
    for f in (S2 / "raw").glob("*.jsonl"):
        f.unlink()
    items, skipped = [], []
    for name in bases():
        tok_text = (VAR / name / "tok").read_text(encoding="utf-8")
        xml_data = (VAR / name / "xml-sem").read_bytes()
        if not TokDoc(tok_text).ok:
            skipped.append(name)
            continue
        bd = MUT / name / "base"
        bd.mkdir(parents=True)
        (bd / "m.tok").write_text(tok_text, encoding="utf-8", newline="\n")
        (bd / "m.bpmn").write_bytes(xml_data)
        (bd / "meta.json").write_text(json.dumps({"base": name, "operator": "base"}), encoding="utf-8")
        items.append(bd)
        for op, k, t, x, meta in mutants(tok_text, xml_data):
            md = MUT / name / f"{op}-{k}"
            md.mkdir(parents=True)
            (md / "m.tok").write_text(t, encoding="utf-8", newline="\n")
            (md / "m.bpmn").write_bytes(x)
            meta.update(base=name, operator=op, site=k, xml_lines=xml_line_of(x, meta["ids"]))
            (md / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
            items.append(md)
    log(f"{len(bases())} base models, {len(skipped)} skipped (flow statements not parsed: {skipped}); {len(items)} folders")

    def check(md):
        rec = {"dir": str(md.relative_to(MUT)).replace("\\", "/")}
        return {**rec, **tok_check(md / "m.tok")}, {**rec, **xsd_check(md / "m.bpmn")}

    with ThreadPoolExecutor(args.workers) as ex:
        results = list(ex.map(check, items))
    # written by one thread after all checks: lines appended by several threads at once can be lost
    for t, x in results:
        append_jsonl(S2 / "raw" / "tok.jsonl", t)
        append_jsonl(S2 / "raw" / "xsd.jsonl", x)
    log("tok and schema checks done")
    lst = S2 / "raw" / "lint-list.json"
    lst.write_text(json.dumps([str(md / "m.bpmn") for md in items]), encoding="utf-8")
    import subprocess

    for cfg in ("recommended", "correctness"):
        outp = S2 / "raw" / f"lint-{cfg}.json"
        subprocess.run(["node", str(Path(__file__).parent / "lint.mjs"), str(lst), str(outp), cfg], check=True)
    log("bpmnlint done")


if __name__ == "__main__":
    main()
