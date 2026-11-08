"""S8b: whether the BPMN XML which the agents wrote carries a diagram (results/S8b/s8b-diagrams.json).

Counts, for the final models of the arm XMLAGENT-C of S3i (Claude Sonnet 5.5, Claude Haiku 5.5,
gpt-oss 120B; PET and PMo), the files with a BPMNDI diagram (an element BPMNDiagram or BPMNShape).

    .venv/Scripts/python scripts/analyse_s8b.py
"""

from common import RESULTS, write_json
from s8b_agent_outputs import MODELS, SETS, XML_ARM


def main():
    files = with_diagram = 0
    for runs in SETS.values():
        for model in MODELS:
            for d in runs.glob(f"{model}__{XML_ARM}__*"):
                f = d / "final.bpmn"
                if not f.exists():
                    continue
                files += 1
                text = f.read_text(encoding="utf-8", errors="replace")
                if "BPMNDiagram" in text or "BPMNShape" in text:
                    with_diagram += 1
    out = {"xml_agent_final_models": files, "with_diagram": with_diagram}
    write_json(RESULTS / "S8b" / "s8b-diagrams.json", out)
    print(out)


if __name__ == "__main__":
    main()
