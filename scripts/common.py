"""Paths, the frozen tok program, XML helpers and the tokenizers shared by the studies."""

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# the main study: tok 1.0.2 (PROTOCOL.md); the formative study has its own copy of the
# scripts in formative/scripts/
TOK = ROOT / "tools" / "bin" / "tok-1.0.2-windows-x86_64" / "tok.exe"
RAW = ROOT / "data" / "raw"
RESULTS = ROOT / "results"
PROJECTS = ROOT.parent  # the folder that holds the tok, tok-book and tok-course checkouts
SEED = 20261029

BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
DC_NS = "http://www.omg.org/spec/DD/20100524/DC"
DI_NS = "http://www.omg.org/spec/DD/20100524/DI"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


def run_tok(args, cwd=None, timeout=120):
    """Runs the frozen tok program; returns (exit code, stdout, stderr, seconds)."""
    t0 = time.perf_counter()
    p = subprocess.run(
        [str(TOK), *map(str, args)],
        cwd=cwd,
        capture_output=True,
        timeout=timeout,
        env={**os.environ, "TOK_LANG": "en"},
    )
    dt = time.perf_counter() - t0
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace"), dt


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


def append_jsonl(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


# ------------------------------------------------------------------ XML variants

def _parser():
    from lxml import etree

    return etree.XMLParser(remove_blank_text=False, resolve_entities=False, huge_tree=True, no_network=True)


def parse_xml(data: bytes):
    from lxml import etree

    return etree.fromstring(data, _parser())


def minify(data: bytes) -> bytes:
    """The same XML without indentation, whitespace between elements and comments."""
    from lxml import etree

    root = etree.fromstring(data, etree.XMLParser(remove_blank_text=True, remove_comments=True,
                                                  resolve_entities=False, huge_tree=True, no_network=True))
    _strip_tail_whitespace(root)
    return etree.tostring(root, encoding="utf-8", xml_declaration=False)


def _strip_tail_whitespace(el):
    for e in el.iter():
        if e.tail is not None and not e.tail.strip():
            e.tail = None
        if len(e) and e.text is not None and not e.text.strip():
            e.text = None


def without_diagram(data: bytes) -> bytes:
    """The XML without its bpmndi:BPMNDiagram elements (the semantic part only), minified."""
    root = parse_xml(data)
    for d in root.findall(f".//{{{BPMNDI_NS}}}BPMNDiagram"):
        d.getparent().remove(d)
    from lxml import etree

    return minify(etree.tostring(root, encoding="utf-8"))


def core_bpmn(data: bytes) -> bytes:
    """The smallest standard BPMN of the same model: no diagram, no extension elements, no
    elements or attributes of namespaces other than BPMN (and xsi), minified."""
    from lxml import etree

    root = parse_xml(data)
    for d in root.findall(f".//{{{BPMNDI_NS}}}BPMNDiagram"):
        d.getparent().remove(d)
    for e in root.findall(f".//{{{BPMN_NS}}}extensionElements"):
        e.getparent().remove(e)
    for e in list(root.iter()):
        if not isinstance(e.tag, str):
            continue
        ns = etree.QName(e).namespace
        if ns not in (BPMN_NS,) and e is not root and e.getparent() is not None:
            e.getparent().remove(e)
            continue
        for a in list(e.attrib):
            q = etree.QName(a)
            if q.namespace not in (None, XSI_NS):
                del e.attrib[a]
    etree.cleanup_namespaces(root, top_nsmap={"bpmn": BPMN_NS}, keep_ns_prefixes=["xsi"])
    return minify(etree.tostring(root, encoding="utf-8"))


# ------------------------------------------------------------------ tokenizers

TOKENIZERS = ["o200k_base", "cl100k_base", "qwen3", "deepseek_v3", "mistral_nemo"]
_HF = {
    "qwen3": "Qwen__Qwen3-4B",
    "deepseek_v3": "deepseek-ai__DeepSeek-V3",
    "mistral_nemo": "mistralai__Mistral-Nemo-Instruct-2407",
}


def load_tokenizers():
    """name → function(text) → number of tokens."""
    os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(RAW / "tokenizers" / "tiktoken"))
    import tiktoken
    from tokenizers import Tokenizer

    out = {}
    for name in ("o200k_base", "cl100k_base"):
        enc = tiktoken.get_encoding(name)
        out[name] = lambda t, enc=enc: len(enc.encode(t, disallowed_special=()))
    for name, folder in _HF.items():
        tk = Tokenizer.from_file(str(RAW / "tokenizers" / folder / "tokenizer.json"))
        out[name] = lambda t, tk=tk: len(tk.encode(t, add_special_tokens=False).ids)
    return out


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)
    sys.stdout.flush()
