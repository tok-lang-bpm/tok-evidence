"""Build the combined tables of the language-model study (six arms, four models, two task sets).

Writes, for each deliverable folder given:
  models-runs.csv          one row per run of the language-model study (six arms, four models, two task sets)
  models-comparisons.csv   paired comparisons per model and task set (Holm over the primary tests)
  models-tools.csv         calls and tool calls of the agent arms
  models-cost-claude.csv   cost and cached input of the Claude models, per arm

    python scripts/build_tables.py results/combined
"""
import json
import sys
from pathlib import Path

import pandas as pd

EV = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EV / "scripts"))
import analyse_s3 as a  # noqa: E402

MODEL = {"haiku": "Claude Haiku 5.5", "sonnet": "Claude Sonnet 5.5", "gpt-oss:120b-cloud": "gpt-oss 120B", "beam:cloud": "Beam"}
TASKS = {name: {t["id"]: t for t in json.load(open(EV / "data" / "derived" / name / "tasks.json", encoding="utf-8"))["tasks"]}
         for name in ("pet", "pmo")}
# arm of the evidence repository -> (condition, representation, tok version)
ARM = {"XML": ("reference", "BPMN XML", "1.0.2"), "TOK": ("reference", "tok", "1.0.2"),
       "TOKAGENT": ("agent, distributed skill", "tok", "1.0.3"), "XMLAGENT-A": ("agent, distributed skill", "BPMN XML", "1.0.3"),
       "TOKAGENT-C": ("agent, lean skill", "tok", "1.0.3"), "XMLAGENT-C": ("agent, lean skill", "BPMN XML", "1.0.3")}
# (table of the evidence repository, arms taken, task set, scored on the fly from runs.jsonl or read from tables/)
SOURCES = [("S3/main", ["XML", "TOK"], "PET", False), ("S3b/main", ["XML", "TOK"], "PET", False),
           ("S3c/main", ["TOKAGENT"], "PET", False), ("S3d/main", ["XML", "TOK", "TOKAGENT"], "PET", False),
           ("S3h/main", ["XML", "TOK", "TOKAGENT"], "PMo", False),
           ("S3i/main", ["TOKAGENT-C", "XMLAGENT-A", "XMLAGENT-C"], "PMo", True),
           ("S3i/pet", ["TOKAGENT-C", "XMLAGENT-A", "XMLAGENT-C"], "PET", True)]
KEEP = {"valid_first": "valid_first", "valid_final": "valid", "attempts": "model_calls", "input_tokens": "input_tokens",
        "output_tokens": "output_tokens", "total_tokens": "total_tokens", "seconds": "seconds",
        "final_flow_f1_itt": "flow_f1", "final_act_f1_itt": "activity_f1", "final_perf_acc_itt": "performer_accuracy",
        "final_flow_f1_cond": "flow_f1_valid_models", "final_act_f1_cond": "activity_f1_valid_models",
        "cost_usd": "cost_usd", "cache_read_tokens": "cache_read_tokens", "tool_calls": "tool_calls",
        "ended_by_budget": "ended_by_budget", "loop_ok": "final_without_errors_or_warnings"}
EXTRA = ("cost_usd", "cache_read_tokens", "tool_calls", "ended_by_budget", "tool_calls_by_name")

frames = []
for table, arms, taskset, on_the_fly in SOURCES:
    if on_the_fly:
        a.TASKS = TASKS[taskset.lower()]
        d = a.score_runs("../" + table)  # score_runs reads RESULTS / "S3" / phase
        a.TASKS = TASKS["pet"]
    else:
        d = pd.read_csv(EV / "results" / table / "tables" / "runs-scored.csv")
    d = d[d.rep.isin(arms) & d.model.isin(MODEL)].copy()
    raw = {r["run"]: r for r in a.read_jsonl(EV / "results" / table / "runs.jsonl")}
    for x in raw.values():  # reference runs record cost and cache reads per attempt
        log = x.get("attempt_log") or []
        if "cost_usd" not in x and log and any(at.get("cost_usd") is not None for at in log):
            x["cost_usd"] = sum(at.get("cost_usd") or 0 for at in log)
        if "cache_read_tokens" not in x and log and any(at.get("cache_read_tokens") is not None for at in log):
            x["cache_read_tokens"] = sum(at.get("cache_read_tokens") or 0 for at in log)
    for col in EXTRA:
        d[col] = d.run.map(lambda x, c=col: raw.get(x, {}).get(c))
    d["task_set"] = taskset
    d["condition"] = d.rep.map(lambda r: ARM[r][0])
    d["representation"] = d.rep.map(lambda r: ARM[r][1])
    d["tok_version"] = d.rep.map(lambda r: ARM[r][2])
    d["model_name"] = d.model.map(MODEL)
    d["source"] = table
    frames.append(d)
runs = pd.concat(frames, ignore_index=True)
runs["arm"] = runs.representation + ", " + runs.condition
out = runs[["model_name", "task_set", "condition", "representation", "tok_version", "task", "repetition", *KEEP]].rename(
    columns={"model_name": "model", **KEEP})

# paired comparisons: the per-task mean over repetitions, as in the analysis of the study
LEAN, DIST, REF = "agent, lean skill", "agent, distributed skill", "reference"
COMPARE = [  # (name, first arm, second arm, primary)
    ("tok, reference − BPMN XML, reference", (REF, "tok"), (REF, "BPMN XML"), True),
    ("tok, agent (lean skill) − BPMN XML, agent (lean skill)", (LEAN, "tok"), (LEAN, "BPMN XML"), True),
    ("tok, agent (lean skill) − tok, agent (distributed skill)", (LEAN, "tok"), (DIST, "tok"), True),
    ("tok, agent (lean skill) − tok, reference", (LEAN, "tok"), (REF, "tok"), True),
    ("tok, agent (distributed skill) − BPMN XML, agent (distributed skill)", (DIST, "tok"), (DIST, "BPMN XML"), False),
    ("BPMN XML, agent (lean skill) − BPMN XML, agent (distributed skill)", (LEAN, "BPMN XML"), (DIST, "BPMN XML"), False),
    ("tok, agent (distributed skill) − tok, reference", (DIST, "tok"), (REF, "tok"), False),
    ("tok, agent (lean skill) − BPMN XML, reference", (LEAN, "tok"), (REF, "BPMN XML"), False),
    ("BPMN XML, agent (lean skill) − BPMN XML, reference", (LEAN, "BPMN XML"), (REF, "BPMN XML"), False)]
OUTCOMES = [("valid", "valid", True), ("total_tokens", "total tokens per run", True), ("flow_f1", "flow F1 (invalid = 0)", True),
            ("valid_first", "valid at the first attempt", False), ("output_tokens", "output tokens", False),
            ("seconds", "wall time (s)", False), ("model_calls", "model calls", False), ("cost_usd", "cost (USD, Claude)", False),
            ("activity_f1", "activity F1 (invalid = 0)", False), ("performer_accuracy", "performer accuracy (invalid = 0)", False),
            ("flow_f1_valid_models", "flow F1 (valid models)", False)]
rows = []
for model, taskset in out[["model", "task_set"]].drop_duplicates().itertuples(index=False):
    m = out[(out.model == model) & (out.task_set == taskset)]
    for name, first, second, primary_c in COMPARE:
        x = m[(m.condition == first[0]) & (m.representation == first[1])]
        y = m[(m.condition == second[0]) & (m.representation == second[1])]
        if x.empty or y.empty:
            continue
        both = pd.concat([x.assign(rep="TOK"), y.assign(rep="XML")]).assign(model=model)
        for col, label, primary_o in OUTCOMES:
            if both[col].isna().all():
                continue
            for r in a.paired(both, col):
                rows.append({"model": model, "task_set": taskset, "comparison": name, "outcome": label, "primary": primary_c and primary_o,
                             "tasks": r["tasks"], "mean_first": r["mean_TOK"], "mean_second": r["mean_XML"], "mean_difference": r["mean_diff"],
                             "median_difference": r["median_diff"], "ci95_low": r["ci_low"], "ci95_high": r["ci_high"],
                             "p_wilcoxon": r["p_wilcoxon"]})
comp = pd.DataFrame(rows)
prim = comp.primary & comp.p_wilcoxon.notna()
comp.loc[prim, "p_holm"] = a.holm(comp.loc[prim, "p_wilcoxon"])

# tools of the agent arms
ag = runs[runs.condition != REF].copy()
calls = pd.json_normalize(ag.tool_calls_by_name.apply(lambda x: x if isinstance(x, dict) else {})).fillna(0)
calls.index = ag.index
for t in ("check", "check_bpmn", "fmt", "reference"):
    ag[f"calls_{t}"] = calls[t] if t in calls else 0.0
ag["used_checker"] = (ag.calls_check + ag.calls_check_bpmn) > 0
tools = ag.groupby(["task_set", "model_name", "arm"]).agg(
    runs=("run", "size"), model_calls=("attempts", "mean"), tool_calls=("tool_calls", "mean"),
    share_ended_by_budget=("ended_by_budget", "mean"), share_final_without_errors_or_warnings=("loop_ok", "mean"),
    calls_check=("calls_check", "mean"), calls_check_bpmn=("calls_check_bpmn", "mean"), calls_fmt=("calls_fmt", "mean"),
    calls_reference=("calls_reference", "mean"), share_runs_with_checker=("used_checker", "mean")).reset_index().rename(columns={"model_name": "model"})

# cost of the Claude models
cl = runs[runs.model.isin(["haiku", "sonnet"])].copy()
cl["cache_read_tokens"] = pd.to_numeric(cl.cache_read_tokens, errors="coerce")
cost = cl.groupby(["task_set", "model_name", "arm"]).agg(
    runs=("run", "size"), mean_cost_usd=("cost_usd", "mean"), mean_input_tokens=("input_tokens", "mean"),
    mean_output_tokens=("output_tokens", "mean"), mean_cache_read_tokens=("cache_read_tokens", "mean")).reset_index().rename(columns={"model_name": "model"})
cost["cache_read_share_of_input"] = cost.mean_cache_read_tokens / cost.mean_input_tokens

for folder in sys.argv[1:]:
    Path(folder).mkdir(parents=True, exist_ok=True)
    out.to_csv(Path(folder) / "models-runs.csv", index=False)
    comp.round(6).to_csv(Path(folder) / "models-comparisons.csv", index=False)
    tools.round(4).to_csv(Path(folder) / "models-tools.csv", index=False)
    cost.round(4).to_csv(Path(folder) / "models-cost-claude.csv", index=False)
pd.set_option("display.width", 250)
print(out.groupby(["task_set", "model", "condition", "representation"]).size().to_string())
print("primary tests:", int(prim.sum()))
print(comp[comp.primary][["task_set", "model", "comparison", "outcome", "mean_second", "mean_first", "mean_difference", "ci95_low", "ci95_high", "p_holm"]]
      .round(3).to_string(index=False))
