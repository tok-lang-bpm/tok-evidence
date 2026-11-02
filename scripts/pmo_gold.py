"""S3h: the held-out tasks and their gold standard from the PMo dataset (PROTOCOL-S3h.md §3).

Writes data/derived/pmo/tasks.json in the format of data/derived/pet/tasks.json: for every
description its text, the activities of its BPMN model (the names of tasks and sub-processes,
with the name of the innermost lane as the performer), its gateways, and the ordering of
activities (activity → activity through gateways and events, as the judge reads a model);
three pilot descriptions; the remaining descriptions as the main tasks. Pairs 49–54 (PET-7)
come from PET and are left out, and so is pair 20 (the text of PET document doc-1.3).

    .venv/Scripts/python scripts/pmo_gold.py
"""

import numpy as np

import bpmn_graph
from common import RAW, ROOT, write_json

SRC = RAW / "pmo"
OUT = ROOT / "data" / "derived" / "pmo" / "tasks.json"
FROM_PET = {"20"} | {f"{i:02d}" for i in range(49, 55)}  # pair 20 is the text of PET doc-1.3


def gold(data):
    g = bpmn_graph.read(data)
    acts = g.activities()
    return {
        "activities": [{"id": i, "label": v[1], "performer": g.lane_of.get(i) or None} for i, v in sorted(acts.items())],
        "gateways": [{"id": i, "type": v[0], "words": v[1]} for i, v in sorted(g.nodes.items()) if v[0].startswith("gateway")],
        "order": sorted([a, b] for a, b in g.activity_order()),
        "actors": sorted({x for x in g.lanes.values() if x}),
    }


def main():
    tasks = []
    for p in sorted((SRC / "descriptions").glob("*.txt")):
        pid = p.stem
        if pid in FROM_PET:
            continue
        text = p.read_text(encoding="utf-8").strip()
        g = gold((SRC / "bpmn" / f"{pid}.bpmn").read_bytes())
        tasks.append({"id": f"pmo-{pid}", "words": len(text.split()), "text": text, **g})
    words = np.array([t["words"] for t in tasks])
    pilot = []
    for q in (25, 50, 75):
        target = np.percentile(words, q)
        cand = sorted((abs(t["words"] - target), t["id"]) for t in tasks if t["id"] not in pilot)
        pilot.append(cand[0][1])
    write_json(OUT, {"source": "PMo dataset 1.0.0 (Brissard, Cuppens and Zouaq 2025; doi:10.5281/zenodo.15857589), pairs 01–19, 21–48 and 55",
                     "pilot": pilot, "main": [t["id"] for t in tasks if t["id"] not in pilot], "tasks": tasks})
    acts = sum(len(t["activities"]) for t in tasks)
    print(f"{len(tasks)} descriptions, {int(words.sum())} words (median {int(np.median(words))}), {acts} activities, "
          f"{sum(len(t['order']) for t in tasks)} ordering pairs, {sum(1 for t in tasks if t['actors'])} with lanes; pilot {pilot}")
    for t in tasks:
        if not t["activities"] or not t["order"]:
            print("  no activities or no ordering:", t["id"])


if __name__ == "__main__":
    main()
