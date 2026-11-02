"""S6: tok at both ends of process mining (PROTOCOL-S6.md).

For every BPMN model of the PMo dataset (48 models, data/derived/pmo/tasks.json):

1. `tok import` reads the BPMN file into tok;
2. the simulation is added: every activity takes `duration="exp(10m)"`, every flow leaving an
   exclusive gateway without a condition gets an equal share of `p=`, every flow leaving an
   inclusive gateway `p=0.5`, and `simulate cases=500 seed=20261031 arrival="exp(1h)"`;
3. `tok check`, then `tok sim --xes` writes the event log (XES, IEEE 1849-2016);
4. PM4Py replays the log on the original BPMN file (token-based replay: fitness and precision);
5. PM4Py discovers a model with the inductive miner (noise threshold 0) and writes it as BPMN;
6. `tok import` reads the discovered BPMN file, `tok check` checks it, `tok bpmn` writes it again,
   and the round trip is compared node by node and flow by flow;
7. the ordering of activities (activity → activity through gateways and events) of the
   discovered model is compared with that of the original model;
8. PM4Py reads the BPMN file that `tok bpmn` writes from the simulation model, and the number of
   sequence flows it finds is recorded (PM4Py 2.7.15 takes sequence flows from the `incoming`
   and `outgoing` elements of the nodes).

Activities are identified by their BPMN id in the log and in both models.

    .venv/Scripts/python scripts/s6_mining.py [--pilot]

Writes results/S6/models/<id>/ (every file) and results/S6/tables/s6-models.csv, s6-summary.json.
"""

import json
import re
import subprocess
import sys
from collections import Counter

import pandas as pd
import pm4py
from pm4py.util import constants

import bpmn_graph
from common import RAW, RESULTS, ROOT, log, sha256, write_json

TOK = ROOT / "tools" / "bin" / "tok-1.0.3-local-2f5f1c1" / "tok.exe"
PILOT = "--pilot" in sys.argv  # a test of the harness on five models, in results/scratch/
OUT = RESULTS / ("scratch" if PILOT else "") / "S6"
TASKS = json.load(open(ROOT / "data" / "derived" / "pmo" / "tasks.json", encoding="utf-8"))
ACTIVITY = re.compile(r"^(\s*)(task|user|service|manual|script|send|receive|rule|call|business|sub|transaction)\s")
FLOW = re.compile(r"^\s*flow\s+(\S+)\s+->\s+(\S+)(.*)$")
SPLIT = re.compile(r"^\s*(xor|or)\s+(\S+)")
constants.SHOW_PROGRESS_BAR = False
SIMULATE = 'simulate cases=500 seed=20261031 arrival="exp(1h)"'


def tok(*args, cwd):
    p = subprocess.run([str(TOK), *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout + p.stderr


def diagnostics(path, cwd):
    _, out = tok("check", path, "--json", cwd=cwd)
    try:
        d = json.loads(out[out.index("{"):])["diagnostics"]
    except (ValueError, KeyError, json.JSONDecodeError):
        return None
    return Counter(x["severity"] for x in d), sorted({x["code"] for x in d})


def add_simulation(text):
    """Durations, branch probabilities and the simulate statement, added to an imported tok text."""
    lines = text.splitlines()
    kinds = {m.group(2): m.group(1) for m in map(SPLIT.match, lines) if m}
    out_flows = Counter(m.group(1) for m in map(FLOW.match, lines) if m and m.group(1) in kinds and "when=" not in m.group(3))
    seen = Counter()
    new = []
    for line in lines:
        f = FLOW.match(line)
        if ACTIVITY.match(line) and "duration=" not in line and not line.rstrip().endswith(":"):
            line += ' duration="exp(10m)"'
        elif ACTIVITY.match(line) and line.rstrip().endswith(":"):  # a sub-process with a block
            pass
        elif f and f.group(1) in kinds and "when=" not in f.group(3) and " p=" not in line and out_flows[f.group(1)] > 1:
            src, k = f.group(1), out_flows[f.group(1)]
            seen[src] += 1
            if kinds[src] == "or":
                p = "0.5"
            else:
                share = round(1 / k, 3)
                p = f"{share:.3f}" if seen[src] < k else f"{1 - share * (k - 1):.3f}"
            line += f" p={p}"
        new.append(line)
    return "\n".join(new) + "\n\n" + SIMULATE + "\n"


def read_log(path):
    df = pm4py.read_xes(str(path))
    df = df[df["lifecycle:transition"] == "complete"].copy()
    df["concept:name"] = df["activity"]
    return pm4py.format_dataframe(df, case_id="case:concept:name", activity_key="concept:name", timestamp_key="time:timestamp")


def petri_of_bpmn(path):
    model = pm4py.read_bpmn(str(path))
    for node in model.get_nodes():  # activities by id, as in the log
        if isinstance(node, pm4py.objects.bpmn.obj.BPMN.Activity):
            node._BPMNNode__name = node.get_id()
    return pm4py.convert_to_petri_net(model)


def replay(df, net):
    fit = pm4py.fitness_token_based_replay(df, *net)
    prec = pm4py.precision_token_based_replay(df, *net)
    return fit["log_fitness"], fit["perc_fit_traces"] / 100, prec


def order_f1(orig, disc):
    go, gd = bpmn_graph.read(orig.read_bytes()), bpmn_graph.read(disc.read_bytes())
    ids_o = set(go.activities())
    name_d = {i: v[1] for i, v in gd.activities().items()}  # the discovered tasks carry the ids as names
    po = {(a, b) for a, b in go.activity_order()}
    pd_ = {(name_d[a], name_d[b]) for a, b in gd.activity_order()}
    pd_ = {(a, b) for a, b in pd_ if a in {x.lower() for x in ids_o} | ids_o and b in {x.lower() for x in ids_o} | ids_o}
    po = {(a.lower(), b.lower()) for a, b in po}
    pd_ = {(a.lower(), b.lower()) for a, b in pd_}
    tp = len(po & pd_)
    p = tp / len(pd_) if pd_ else 0.0
    r = tp / len(po) if po else float("nan")
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def roundtrip(a, b):
    ga, gb = bpmn_graph.read(a.read_bytes()), bpmn_graph.read(b.read_bytes())
    kinds = lambda g: sorted(v[0] for v in g.nodes.values())
    flows = lambda g: sorted((g.nodes[s][0], g.nodes[t][0]) for _, s, t, _ in g.flows if s in g.nodes and t in g.nodes)
    return kinds(ga) == kinds(gb) and flows(ga) == flows(gb)


def one(task):
    pid = task["id"].removeprefix("pmo-")
    d = OUT / "models" / task["id"]
    d.mkdir(parents=True, exist_ok=True)
    row = {"model": task["id"], "activities": len(task["activities"])}
    src = RAW / "pmo" / "bpmn" / f"{pid}.bpmn"
    (d / "original.bpmn").write_bytes(src.read_bytes())
    rc, out = tok("import", "original.bpmn", "-o", "original.tok", cwd=d)
    row["imported"] = rc == 0 and (d / "original.tok").exists()
    if not row["imported"]:
        (d / "import.txt").write_text(out, encoding="utf-8")
        return row
    (d / "simulation.tok").write_text(add_simulation((d / "original.tok").read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    sev, codes = diagnostics("simulation.tok", d) or (Counter(error=1), ["CRASH"])
    row["simulation_errors"], row["simulation_codes"] = sev["error"], " ".join(codes)
    if sev["error"]:
        return row
    rc, out = tok("sim", "simulation.tok", "--xes", "log.xes", cwd=d)
    (d / "sim.txt").write_text(out, encoding="utf-8", newline="\n")
    row["simulated"] = rc == 0 and (d / "log.xes").exists()
    if not row["simulated"]:
        return row
    df = read_log(d / "log.xes")
    row["cases"], row["events"] = df["case:concept:name"].nunique(), len(df)
    row["variants"] = len(pm4py.get_variants(df))
    row["logged_activities"] = df["concept:name"].nunique()
    tok("bpmn", "simulation.tok", "-o", "model.bpmn", cwd=d)
    row["pm4py_flows_of_tok_bpmn"] = len(pm4py.read_bpmn(str(d / "model.bpmn")).get_flows())
    row["sequence_flows"] = len(bpmn_graph.read(src.read_bytes()).flows)
    try:
        row["original_fitness"], row["original_fit_traces"], row["original_precision"] = replay(df, petri_of_bpmn(d / "original.bpmn"))
    except Exception as ex:
        row["original_replay_error"] = f"{type(ex).__name__}: {ex}"[:200]
    tree = pm4py.discover_process_tree_inductive(df, noise_threshold=0.0)
    pm4py.write_bpmn(pm4py.convert_to_bpmn(tree), str(d / "discovered.bpmn"))
    row["discovered_fitness"], row["discovered_fit_traces"], row["discovered_precision"] = replay(df, pm4py.convert_to_petri_net(tree))
    rc, out = tok("import", "discovered.bpmn", "-o", "discovered.tok", cwd=d)
    row["discovered_imported"] = rc == 0 and (d / "discovered.tok").exists()
    if not row["discovered_imported"]:
        (d / "import-discovered.txt").write_text(out, encoding="utf-8")
        return row
    sev, codes = diagnostics("discovered.tok", d) or (Counter(error=1), ["CRASH"])
    row["discovered_errors"], row["discovered_warnings"], row["discovered_codes"] = sev["error"], sev["warning"], " ".join(codes)
    rc, _ = tok("bpmn", "discovered.tok", "--no-layout", "-o", "discovered-again.bpmn", cwd=d)
    row["discovered_roundtrip"] = rc == 0 and roundtrip(d / "discovered.bpmn", d / "discovered-again.bpmn")
    row["order_precision"], row["order_recall"], row["order_f1"] = order_f1(d / "original.bpmn", d / "discovered.bpmn")
    return row


def main():
    rows = []
    for t in TASKS["tasks"][:5] if PILOT else TASKS["tasks"]:
        try:
            r = one(t)
        except Exception as ex:
            r = {"model": t["id"], "failure": f"{type(ex).__name__}: {ex}"[:300]}
        log(f"{t['id']}: {json.dumps({k: v for k, v in r.items() if k != 'model'}, default=str)}")
        rows.append(r)
    df = pd.DataFrame(rows)
    (OUT / "tables").mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "tables" / "s6-models.csv", index=False)
    ok = df[df.get("discovered_imported", pd.Series(False, index=df.index)) == True]  # noqa: E712
    num = lambda c, x=df: {"mean": float(x[c].mean()), "median": float(x[c].median()), "min": float(x[c].min()), "max": float(x[c].max())}
    summary = {
        "models": len(df), "imported": int(df.imported.sum()), "simulated": int(df.get("simulated", pd.Series(dtype=bool)).fillna(False).sum()),
        "original_replayed": int(df.original_fitness.notna().sum()),
        "original_fitness": num("original_fitness"), "original_precision": num("original_precision"),
        "original_all_traces_fit": int((df.original_fit_traces == 1).sum()),
        "discovered_fitness": num("discovered_fitness"), "discovered_precision": num("discovered_precision"),
        "discovered_imported": len(ok), "discovered_without_errors": int((ok.discovered_errors == 0).sum()),
        "discovered_without_warnings": int(((ok.discovered_errors == 0) & (ok.discovered_warnings == 0)).sum()),
        "discovered_codes": dict(Counter(c for s in ok.discovered_codes.fillna("") for c in s.split())),
        "discovered_roundtrip": int(ok.discovered_roundtrip.sum()),
        "order_f1": num("order_f1", ok), "order_precision": num("order_precision", ok), "order_recall": num("order_recall", ok),
        "cases": num("cases"), "variants": num("variants"), "events": num("events"),
        "pm4py_reads_flows_of_tok_bpmn": int((df.get("pm4py_flows_of_tok_bpmn", pd.Series(dtype=float)) > 0).sum()),
        "tok": {"program": str(TOK.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(TOK.read_bytes())},
        "pm4py": pm4py.__version__,
    }
    write_json(OUT / "tables" / "s6-summary.json", summary)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
