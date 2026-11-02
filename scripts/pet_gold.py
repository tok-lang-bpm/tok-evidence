"""S3: the tasks and the gold standard from PET v1.1 (PROTOCOL.md §6.2, §6.6).

Writes data/derived/pet/tasks.json: for every document its text, its activities (the
activity words plus the activity data linked by `uses`), their performers (`actor
performer`), the gateways, and the ordering of activities (activity → activity through
gateways only, following `flow`); and the three pilot documents.

    .venv/Scripts/python scripts/pet_gold.py
"""

import json
import re

import numpy as np

from common import RAW, ROOT, write_json

OUT = ROOT / "data" / "derived" / "pet" / "tasks.json"


def detok(tokens):
    t = " ".join(tokens)
    t = re.sub(r"\s+([.,;:!?)\]])", r"\1", t)
    t = re.sub(r"([(\[])\s+", r"\1", t)
    t = re.sub(r"\s+'s\b", "'s", t)
    return t


def spans(doc):
    """Entities: (sentence, first word) → {type, words}."""
    out, cur = {}, None
    for tok, tag, sid, wid in zip(doc["tokens"], doc["ner_tags"], doc["sentence-IDs"], doc["tokens-IDs"]):
        if tag.startswith("B-"):
            cur = (sid, wid)
            out[cur] = {"type": tag[2:], "words": [tok]}
        elif tag.startswith("I-") and cur is not None and out[cur]["type"] == tag[2:] and cur[0] == sid:
            out[cur]["words"].append(tok)
        else:
            cur = None
    return out


def gold(doc):
    ents = spans(doc)
    rels = [((r["source-head-sentence-ID"], r["source-head-word-ID"]), r["relation-type"],
             (r["target-head-sentence-ID"], r["target-head-word-ID"])) for r in doc["relations"]]
    acts = {k: v for k, v in ents.items() if v["type"] == "Activity"}
    gws = {k: v for k, v in ents.items() if v["type"] in ("XOR Gateway", "AND Gateway")}
    label = {k: " ".join(v["words"]) for k, v in acts.items()}
    for s, t, o in rels:
        if t == "uses" and s in acts and o in ents and ents[o]["type"] == "Activity Data":
            label[s] += " " + " ".join(ents[o]["words"])
    performer = {}
    for s, t, o in rels:
        if t == "actor performer" and s in acts and o in ents:
            performer.setdefault(s, " ".join(ents[o]["words"]))
    succ = {}
    for s, t, o in rels:
        if t == "flow":
            succ.setdefault(s, []).append(o)
    order = set()
    for a in acts:
        seen, stack = set(), list(succ.get(a, []))
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            if n in acts:
                order.add((a, n))
            elif n in gws:
                stack.extend(succ.get(n, []))
    key = lambda k: f"{k[0]}.{k[1]}"
    return {
        "activities": [{"id": key(k), "label": label[k], "performer": performer.get(k)} for k in sorted(acts)],
        "gateways": [{"id": key(k), "type": v["type"], "words": " ".join(v["words"])} for k, v in sorted(gws.items())],
        "order": sorted([key(a), key(b)] for a, b in order),
        "actors": sorted({" ".join(v["words"]) for v in ents.values() if v["type"] == "Actor"}),
    }


def main():
    docs = json.load(open(RAW / "pet" / "PETv1.1-relations.json", encoding="utf-8"))
    tasks = []
    for d in docs:
        g = gold(d)
        tasks.append({"id": d["document name"], "words": len(d["tokens"]), "text": detok(d["tokens"]), **g})
    words = np.array([t["words"] for t in tasks])
    pilot = []
    for p in (25, 50, 75):
        target = np.percentile(words, p)
        cand = sorted((abs(t["words"] - target), t["id"]) for t in tasks if t["id"] not in pilot)
        pilot.append(cand[0][1])
    write_json(OUT, {"source": "PET v1.1 (patriziobellan86/PETv1.1, PETv1.1-relations.json)", "pilot": pilot,
                     "main": [t["id"] for t in tasks if t["id"] not in pilot], "tasks": tasks})
    acts = sum(len(t["activities"]) for t in tasks)
    print(f"{len(tasks)} documents, {acts} activities, {sum(len(t['order']) for t in tasks)} ordering pairs; pilot {pilot}")


if __name__ == "__main__":
    main()
