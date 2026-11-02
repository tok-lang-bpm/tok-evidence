"""An independent reader of BPMN 2.0 XML: the process graph of a file, without tok.

It reads elements by their local names in the BPMN model namespace, so it accepts the XML of
any tool. Used as the judge of the studies (S1 fidelity, S3 validity and fidelity).
"""

import re
from collections import Counter

from common import BPMN_NS, parse_xml

TASKS = {
    "task": "task", "userTask": "user", "serviceTask": "service", "sendTask": "send",
    "receiveTask": "receive", "manualTask": "manual", "businessRuleTask": "rule",
    "scriptTask": "script",
}
ACTIVITIES = {"subProcess", "transaction", "adHocSubProcess", "callActivity"}
EVENTS = {"startEvent", "endEvent", "intermediateCatchEvent", "intermediateThrowEvent", "boundaryEvent"}
GATEWAYS = {
    "exclusiveGateway": "exclusive", "parallelGateway": "parallel", "inclusiveGateway": "inclusive",
    "eventBasedGateway": "event", "complexGateway": "complex",
}
DATA = {"dataObjectReference", "dataStoreReference", "dataInput", "dataOutput"}
TRIGGERS = {
    "messageEventDefinition": "message", "timerEventDefinition": "timer",
    "errorEventDefinition": "error", "escalationEventDefinition": "escalation",
    "signalEventDefinition": "signal", "conditionalEventDefinition": "conditional",
    "compensateEventDefinition": "compensation", "cancelEventDefinition": "cancel",
    "linkEventDefinition": "link", "terminateEventDefinition": "terminate",
}


def local(tag):
    return tag.split("}", 1)[1] if isinstance(tag, str) and "}" in tag else tag


def ns(tag):
    return tag[1:].split("}", 1)[0] if isinstance(tag, str) and tag.startswith("{") else None


def norm_name(s):
    return re.sub(r"\s+", " ", (s or "").replace("&#10;", " ")).strip()


def node_kind(el):
    n = local(el.tag)
    if n in TASKS:
        return "task:" + TASKS[n]
    if n in ACTIVITIES:
        if n == "subProcess" and el.get("triggeredByEvent") == "true":
            return "activity:eventSubProcess"
        return "activity:" + n
    if n in GATEWAYS:
        return "gateway:" + GATEWAYS[n]
    if n in EVENTS:
        defs = sorted(TRIGGERS[local(c.tag)] for c in el if local(c.tag) in TRIGGERS)
        trig = "+".join(defs) if len(defs) <= 1 else "multiple"
        return "event:" + n.replace("Event", "") + ":" + (trig or "none")
    return None


class Graph:
    """Nodes (id → kind, name, process id, lane names), sequence flows, message flows."""

    def __init__(self):
        self.nodes = {}
        self.flows = []  # (id, source, target, has condition)
        self.default_flows = set()
        self.message_flows = []
        self.pools = []  # names of participants
        self.lanes = {}  # lane id → name
        self.lane_of = {}  # node id → lane name (innermost)
        self.data = Counter()
        self.errors = []

    # --- summaries used by the studies
    def kinds(self):
        return Counter(k for k, _, _ in self.nodes.values())

    def named(self):
        return Counter((k, n) for k, n, _ in self.nodes.values())

    def flow_pairs(self):
        c = Counter()
        for _, s, t, _ in self.flows:
            a, b = self.nodes.get(s), self.nodes.get(t)
            if a and b:
                c[(a[0], a[1], b[0], b[1])] += 1
        return c

    def activities(self):
        return {i: v for i, v in self.nodes.items() if v[0].startswith(("task:", "activity:"))}

    def successors(self):
        out = {i: [] for i in self.nodes}
        for _, s, t, _ in self.flows:
            if s in out and t in self.nodes:
                out[s].append(t)
        return out

    def activity_order(self):
        """Pairs (a, b) of activities where b follows a through gateways and events only."""
        succ = self.successors()
        acts = self.activities()
        pairs = set()
        for a in acts:
            seen, stack = set(), list(succ.get(a, []))
            while stack:
                n = stack.pop()
                if n in seen:
                    continue
                seen.add(n)
                if n in acts:
                    pairs.add((a, n))
                else:
                    stack.extend(succ.get(n, []))
        return pairs


def read(data: bytes) -> Graph:
    g = Graph()
    root = parse_xml(data)
    if local(root.tag) != "definitions" or ns(root.tag) != BPMN_NS:
        g.errors.append("the root element is not bpmn:definitions")
    for el in root.iter():
        if not isinstance(el.tag, str) or ns(el.tag) != BPMN_NS:
            continue
        n = local(el.tag)
        k = node_kind(el)
        if k:
            proc = next((a.get("id") for a in el.iterancestors() if local(a.tag) in ("process", "subProcess", "transaction", "adHocSubProcess")), None)
            g.nodes[el.get("id")] = (k, norm_name(el.get("name")), proc)
        elif n == "sequenceFlow":
            cond = any(local(c.tag) == "conditionExpression" for c in el)
            g.flows.append((el.get("id"), el.get("sourceRef"), el.get("targetRef"), cond))
        elif n == "messageFlow":
            g.message_flows.append((el.get("id"), el.get("sourceRef"), el.get("targetRef")))
        elif n == "participant":
            g.pools.append(norm_name(el.get("name")))
        elif n == "lane":
            g.lanes[el.get("id")] = norm_name(el.get("name"))
        elif n in DATA:
            g.data[n] += 1
        if n in GATEWAYS or n in TASKS or n in ACTIVITIES:
            if el.get("default"):
                g.default_flows.add(el.get("default"))
    # lanes: the innermost lane that lists a node
    for lane in root.iter(f"{{{BPMN_NS}}}lane"):
        depth = sum(1 for a in lane.iterancestors() if local(a.tag) == "lane")
        for ref in lane.findall(f"{{{BPMN_NS}}}flowNodeRef"):
            nid = (ref.text or "").strip()
            prev = g.lane_of.get(nid)
            if prev is None or depth >= prev[1]:
                g.lane_of[nid] = (norm_name(lane.get("name")), depth)
    g.lane_of = {k: v[0] for k, v in g.lane_of.items()}
    return g


def structural_problems(g: Graph):
    """The judge's minimum: a start and an end event, and every flow between known nodes."""
    probs = list(g.errors)
    kinds = g.kinds()
    if not any(k.startswith("event:start") for k in kinds):
        probs.append("no start event")
    if not any(k.startswith("event:end") for k in kinds):
        probs.append("no end event")
    for fid, s, t, _ in g.flows:
        if s not in g.nodes or t not in g.nodes:
            probs.append(f"sequence flow {fid} refers to an unknown node")
    return probs
