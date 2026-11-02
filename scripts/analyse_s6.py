"""S6, description of the models whose log does not fit the original model (exploratory, after the data).

For every simulated model: the number of pools, event-based, inclusive and parallel gateways of the
simulation model, the cases that reach an end event, and whether PM4Py accepts the Petri net of the
original BPMN file for alignments (an easy sound net); for the models with a log fitness below 1,
the alignment-based fitness where PM4Py computes it, and the token-based fitness of the same log on
the original BPMN file with every intermediate event that has one incoming and one outgoing flow
bypassed (its incoming flow led to its successor; the log has no events for intermediate events).

    .venv/Scripts/python scripts/analyse_s6.py

Writes results/S6/tables/s6-unfit.csv.
"""

import re
import tempfile
from pathlib import Path

import pandas as pd
from lxml import etree
import pm4py
from pm4py.util import constants

import s6_mining as s
from common import RESULTS

constants.SHOW_PROGRESS_BAR = False


BPMN = "{http://www.omg.org/spec/BPMN/20100524/MODEL}"


def bypass_intermediate_events(path):
    """A copy of the BPMN file without the intermediate events that have one incoming and one outgoing flow."""
    tree = etree.parse(str(path))
    root = tree.getroot()
    flows = {f.get("id"): f for f in root.iter(BPMN + "sequenceFlow")}
    removed = 0
    for tag in ("intermediateCatchEvent", "intermediateThrowEvent"):
        for ev in list(root.iter(BPMN + tag)):
            inc = [f for f in flows.values() if f.get("targetRef") == ev.get("id")]
            out = [f for f in flows.values() if f.get("sourceRef") == ev.get("id")]
            if len(inc) != 1 or len(out) != 1:
                continue
            succ = out[0].get("targetRef")
            inc[0].set("targetRef", succ)
            for el in root.iter():  # the successor's incoming reference follows the flow
                if el.get("id") == succ:
                    for ref in el.findall(BPMN + "incoming"):
                        if ref.text and ref.text.strip() == out[0].get("id"):
                            ref.text = inc[0].get("id")
            out[0].getparent().remove(out[0])
            del flows[out[0].get("id")]
            ev.getparent().remove(ev)
            removed += 1
    target = Path(tempfile.mkdtemp()) / "bypassed.bpmn"
    tree.write(str(target), xml_declaration=True, encoding="UTF-8")
    return target, removed


def main():
    df = pd.read_csv(RESULTS / "S6" / "tables" / "s6-models.csv")
    rows = []
    for r in df[df.original_fitness < 1].itertuples():
        d = RESULTS / "S6" / "models" / r.model
        text = (d / "simulation.tok").read_text(encoding="utf-8")
        count = lambda kw: len(re.findall(rf"^\s*{kw}\s", text, re.M))
        ended = sum(int(m) for m in re.findall(r"^\s+\S+\s+(\d+)\s+[\d.]+%$", (d / "sim.txt").read_text(encoding="utf-8").split("Cycle time")[0], re.M))
        log = s.read_log(d / "log.xes")
        net = s.petri_of_bpmn(d / "original.bpmn")
        try:
            al = pm4py.fitness_alignments(log, *net)["log_fitness"]
            easy_sound = True
        except Exception:
            al, easy_sound = None, False
        bypassed, removed = bypass_intermediate_events(d / "original.bpmn")
        fit_bypassed = pm4py.fitness_token_based_replay(log, *s.petri_of_bpmn(bypassed))["log_fitness"] if removed else None
        rows.append({"model": r.model, "original_fitness": r.original_fitness, "original_fit_traces": r.original_fit_traces,
                     "pools": count("pool"), "eventgw": count("eventgw"), "or": count("or"), "and": count("and"),
                     "cases_ended": ended, "petri_net_easy_sound": easy_sound, "alignment_fitness": al,
                     "intermediate_events_bypassed": removed, "fitness_with_events_bypassed": fit_bypassed})
    out = pd.DataFrame(rows)
    out.to_csv(RESULTS / "S6" / "tables" / "s6-unfit.csv", index=False)
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
