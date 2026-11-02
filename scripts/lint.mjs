// bpmnlint over many files in one Node.js process (PROTOCOL.md §5.2, §6.5).
//
//   node scripts/lint.mjs LIST.json OUT.json [CONFIG]
//
// LIST.json: an array of file paths. OUT.json: one record per file with the warnings of the
// XML import (bpmn-moddle: unresolved references, unknown elements), the reports of the
// linter (rule, element id, message, category) and the time of the file in milliseconds.
// CONFIG: "recommended" (the recommended rules except no-bpmndi, for semantic files without a
// diagram) or "correctness" (the rules of that set that report errors of the model rather
// than conventions of style; see PROTOCOL.md and DEVIATIONS.md).

import { createRequire } from "node:module";
import { readFileSync, writeFileSync } from "node:fs";
import { performance } from "node:perf_hooks";
import { pathToFileURL } from "node:url";

const require = createRequire(new URL("../tools/node/package.json", import.meta.url));
const { BpmnModdle } = await import(pathToFileURL(require.resolve("bpmn-moddle")).href);
const { Linter } = require("bpmnlint");
const NodeResolver = require("bpmnlint/lib/resolver/node-resolver");

export const CORRECTNESS = [
  "ad-hoc-sub-process", "conditional-flows", "end-event-required", "event-based-gateway",
  "event-sub-process-typed-start-event", "link-event", "no-disconnected",
  "no-duplicate-sequence-flows", "no-implicit-end", "no-implicit-start", "no-implicit-split",
  "single-event-definition", "start-event-required", "sub-process-blank-start-event",
];

function config(name) {
  if (name === "correctness") {
    return { rules: Object.fromEntries(CORRECTNESS.map((r) => [r, "error"])) };
  }
  return { extends: "bpmnlint:recommended", rules: { "no-bpmndi": "off" } };
}

// The incoming and outgoing references of a flow node are optional in BPMN 2.0 XML: the
// sequence flows state their source and target (BPMN 2.0.2, 10.5.1). The rules of bpmnlint
// read only the references, so they are filled in from the flows, as the specification
// derives them, before linting. Returns the number of references added.
function deriveConnections(definitions) {
  let added = 0;
  const visit = (container) => {
    for (const el of container.flowElements || []) {
      if (el.$type === "bpmn:SequenceFlow") {
        const s = el.sourceRef, t = el.targetRef;
        if (s && typeof s === "object") {
          s.outgoing = s.outgoing || [];
          if (!s.outgoing.includes(el)) { s.outgoing.push(el); added++; }
        }
        if (t && typeof t === "object") {
          t.incoming = t.incoming || [];
          if (!t.incoming.includes(el)) { t.incoming.push(el); added++; }
        }
      }
      if (el.flowElements) visit(el);
    }
  };
  for (const root of definitions.rootElements || []) {
    if (root.flowElements) visit(root);
  }
  return added;
}

const [list, out, cfgName = "recommended"] = process.argv.slice(2);
const files = JSON.parse(readFileSync(list, "utf8"));
// a new linter for every file: some rules keep state between runs of one linter
const moddle = new BpmnModdle();
const results = [];
for (const file of files) {
  const t0 = performance.now();
  const rec = { file, warnings: [], reports: [], error: null };
  try {
    const xml = readFileSync(file, "utf8");
    const { rootElement, warnings } = await moddle.fromXML(xml, "bpmn:Definitions");
    rec.warnings = warnings.map((w) => String(w.message).slice(0, 300));
    rec.derived = deriveConnections(rootElement);
    const linter = new Linter({ config: config(cfgName), resolver: new NodeResolver({ require }) });
    const reports = await linter.lint(rootElement);
    for (const [rule, items] of Object.entries(reports)) {
      for (const r of items) {
        rec.reports.push({ rule, id: r.id ?? null, message: String(r.message).slice(0, 300), category: r.category });
      }
    }
  } catch (e) {
    rec.error = String(e && e.message ? e.message : e).slice(0, 500);
  }
  rec.ms = performance.now() - t0;
  results.push(rec);
}
writeFileSync(out, JSON.stringify(results));
