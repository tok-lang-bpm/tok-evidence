"""S3i §8.6: the tool-call channel of Beam (PROTOCOL-S3i.md).

The feasibility check of the main phase showed that Beam's calls of `check_bpmn` through Ollama
arrive with empty arguments (`{}`), while its calls of `check` with a tok document arrive intact.
The probe asks Beam to pass a given document to the checker tool unchanged, and records whether the
document arrives, for documents that differ in length and in the number of double quotes:

- the tok model and the BPMN XML model of one task (the XML export of the tok model);
- the same two documents with every double quote kept, but shortened or lengthened, so that length
  and quotes are separated.

    .venv/Scripts/python scripts/s3i_channel.py [--repeats 3] [--part documents|schema]

Writes results/S3i/channel/calls.jsonl (one line per call: document, length, quotes, arrived,
tool name, arguments keys, length of the arguments text) and results/S3i/channel/documents/.

The second part (`--part schema`) sends the BPMN XML document through variants of the tool
definition, which the harness defines itself and does not run: `check_bpmn` as published, without
its property `description`, with `xml` renamed `text`, with the property `xml` alone and a
one-sentence description, and the tool `check` of tok with the XML as `text`
(results/S3i/channel/calls-schema.jsonl, tool-definitions.json).
"""

import argparse
import json
import subprocess
import time

import s3c_run
import s3i_run
from common import RESULTS, ROOT, append_jsonl, log, sha256

OUT = RESULTS / "S3i" / "channel"
TOK_RELEASE = ROOT / "tools" / "bin" / "tok-1.0.3-windows-x86_64" / "tok.exe"
SYSTEM = ("You are a relay. The user gives you a document. Call the tool {tool} once with the document, "
          "unchanged, as the argument `{arg}`, and then answer with the single word done.")
USER = "Pass this document to the tool unchanged:\n\n{doc}"


def documents():
    """The tok document of pmo-05 from the S3h reference arm of Sonnet, its BPMN XML export, and variants."""
    tok_src = (RESULTS / "S3h" / "main" / "runs" / "sonnet__TOK__pmo-05__r1" / "attempt-1.tok")
    tok_text = tok_src.read_text(encoding="utf-8")
    d = OUT / "documents"
    d.mkdir(parents=True, exist_ok=True)
    (d / "model.tok").write_text(tok_text, encoding="utf-8", newline="\n")
    subprocess.run([str(TOK_RELEASE), "bpmn", "--no-layout", "model.tok", "-o", "model.bpmn"], cwd=d, capture_output=True)
    xml_text = (d / "model.bpmn").read_text(encoding="utf-8")
    # variants: the XML cut to the length of the tok text (first lines), the tok text repeated to the length of the XML
    xml_short = xml_text[: len(tok_text)]
    xml_short = xml_short[: xml_short.rfind("\n")] + "\n"
    tok_long = tok_text
    while len(tok_long) < len(xml_text):
        tok_long += "\n" + tok_text
    tok_long = tok_long[: len(xml_text)]
    tok_long = tok_long[: tok_long.rfind("\n")] + "\n"
    plain = "\n".join("line %d of a plain text without any quote character, written to fill the same length as the xml" % i for i in range(1, 10_000))
    plain = plain[: len(xml_text)]
    plain = plain[: plain.rfind("\n")] + "\n"
    docs = {"tok": (tok_text, "check", "text"), "xml": (xml_text, "check_bpmn", "xml"),
            "xml-cut-to-tok-length": (xml_short, "check_bpmn", "xml"), "tok-repeated-to-xml-length": (tok_long, "check", "text"),
            "plain-text-of-xml-length-as-tok": (plain, "check", "text"), "plain-text-of-xml-length-as-xml": (plain, "check_bpmn", "xml")}
    for name, (text, _, _) in docs.items():
        (d / f"{name}.txt").write_text(text, encoding="utf-8", newline="\n")
    return docs


def schema_variants(check, check_bpmn):
    """Second part: the BPMN XML document through variants of the tool definition (the tools are not run)."""
    import copy
    v = {}
    v["check_bpmn as published"] = (copy.deepcopy(check_bpmn), "xml")
    t = copy.deepcopy(check_bpmn)
    del t["function"]["parameters"]["properties"]["description"]
    v["check_bpmn without the property description"] = (t, "xml")
    t = copy.deepcopy(check_bpmn)
    props = t["function"]["parameters"]["properties"]
    props["text"] = props.pop("xml")
    props["text"]["description"] = "The BPMN 2.0 XML. Give either text or path."
    v["check_bpmn with xml renamed text"] = (t, "text")
    v["check_bpmn with the property xml only"] = ({"type": "function", "function": {"name": "check_bpmn", "description": "Check BPMN 2.0 XML and list its diagnostics.",
                                                   "parameters": {"type": "object", "properties": {"xml": {"type": "string", "description": "The BPMN 2.0 XML."}}, "required": ["xml"]}}}, "xml")
    v["check (tok) with the XML as text"] = (copy.deepcopy(check), "text")
    return v


def one_call(model, system, user, tools, arg):
    t0 = time.perf_counter()
    resp = s3c_run.chat(model, [{"role": "system", "content": system}, {"role": "user", "content": user}], tools)
    m = resp.get("message", {})
    calls = m.get("tool_calls") or []
    a = (calls[0].get("function", {}).get("arguments") if calls else None)
    arrived = isinstance(a, dict) and isinstance(a.get(arg), str) and len(a[arg]) > 0
    return {"model": resp.get("model"), "tool_calls": len(calls), "tool": calls[0]["function"].get("name") if calls else None,
            "argument_keys": sorted(a.keys()) if isinstance(a, dict) else type(a).__name__ if a is not None else None,
            "argument_length": len(a[arg]) if arrived else 0, "arrived": arrived, "argument": a[arg] if arrived else None,
            "eval_count": resp.get("eval_count"), "thinking_chars": len(m.get("thinking") or ""), "content": (m.get("content") or "")[:200],
            "seconds": round(time.perf_counter() - t0, 1), "date": time.strftime("%Y-%m-%dT%H:%M:%S%z")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--model", default="beam:cloud")
    ap.add_argument("--part", choices=["documents", "schema"], default="documents")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    docs = documents()
    servers = {}
    for rep, binary in s3i_run.MCP_BINARY.items():
        s = s3i_run.Server(binary)
        servers[rep] = s3c_run.ollama_tools(s)
        s.close()
    check = next(t for t in servers["TOK"] if t["function"]["name"] == "check")
    check_bpmn = next(t for t in servers["XML"] if t["function"]["name"] == "check_bpmn")
    if args.part == "documents":
        tools_of = {"check": [check], "check_bpmn": [check_bpmn]}
        for name, (text, tool, arg) in docs.items():
            for i in range(args.repeats):
                r = one_call(args.model, SYSTEM.format(tool=tool, arg=arg), USER.format(doc=text), tools_of[tool], arg)
                row = {"document": name, "length": len(text), "quotes": text.count('"'), "lines": text.count("\n"), "sha256": sha256(text.encode()),
                       "repeat": i + 1, **{k: v for k, v in r.items() if k != "argument"}, "identical": r["arrived"] and r["argument"].strip() == text.strip()}
                append_jsonl(OUT / "calls.jsonl", row)
                log(f"{name} ({len(text)} chars, {row['quotes']} quotes) repeat {i + 1}: arrived {r['arrived']}, identical {row['identical']}, keys {r['argument_keys']}, eval {r['eval_count']}")
    else:
        text = docs["xml"][0]
        for name, (tool, arg) in schema_variants(check, check_bpmn).items():
            for i in range(args.repeats):
                r = one_call(args.model, SYSTEM.format(tool=tool["function"]["name"], arg=arg), USER.format(doc=text), [tool], arg)
                row = {"variant": name, "document": "xml", "length": len(text), "quotes": text.count('"'), "sha256": sha256(text.encode()),
                       "tool_definition_sha256": sha256(json.dumps(tool, sort_keys=True).encode()), "repeat": i + 1,
                       **{k: v for k, v in r.items() if k != "argument"}, "identical": r["arrived"] and r["argument"].strip() == text.strip()}
                append_jsonl(OUT / "calls-schema.jsonl", row)
                log(f"{name} repeat {i + 1}: arrived {r['arrived']}, identical {row['identical']}, keys {r['argument_keys']}, eval {r['eval_count']}")
        (OUT / "tool-definitions.json").write_text(json.dumps({k: v[0] for k, v in schema_variants(check, check_bpmn).items()}, indent=1), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
