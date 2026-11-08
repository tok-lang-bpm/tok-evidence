# tok evidence

Data, scripts and results of the study reported in *tok: a textual concrete syntax of BPMN and DMN for humans and AI agents* (Marek Deja, 2026), preprint [hal-05848142](https://hal.science/hal-05848142) and [arXiv:2611.07945](https://doi.org/10.48550/arXiv.2611.07945), and of the measurements added for *Process models as text: a plain-text notation of BPMN for screen readers, terminals and AI agents* (Marek Deja, 2026), in `results/uais/`. tok is a plain-text notation for BPMN 2.0.2 process models and DMN 1.5 decisions: https://github.com/tok-lang-bpm/tok.

Archived at Zenodo: https://doi.org/10.5281/zenodo.23881048 (all versions; version 1.0.0: 10.5281/zenodo.23881049; version 1.1.0: 10.5281/zenodo.24058705).

## Measurements

| Folder | Measurement | Software |
|---|---|---|
| `results/S1/` | size of tok models against the BPMN XML of 893 files exported by 37 tools, in bytes and in tokens; fidelity of the import | tok 1.0.2 |
| `results/S2/` | detection and localisation of 1 411 injected modelling faults by `tok check`, the OMG XML Schema and bpmnlint | tok 1.0.2 |
| `results/S3*/` | four language models writing process models from the PET and PMo texts in six arms (below) | tok 1.0.2 and 1.0.3 |
| `results/S4/` | speed of the engine on the models of corpus N, on the import and on generated models | tok 1.0.3 |
| `results/S5/` | conformance suites of the tagged sources (DMN TCK, MIWG reference models, Camunda Modeler files, tok conformance corpus) | tok 1.0.3 |
| `results/S6/` | simulation, replay, discovery with PM4Py and import of the 48 models of the PMo dataset | tok 1.0.3, PM4Py 2.7.15 |
| `results/combined/` | the tables of the language-model study across folders, as reported in the paper (`scripts/build_tables.py`) | |

## Measurements for screen readers, braille displays and magnification

The folder `results/uais/` holds three measurements without a language model, on the files of `S1` and on the final models of `S3i`.

| Folder | Measurement | Software |
|---|---|---|
| `results/uais/S7/` | reading properties of 1 167 models (corpora N, V, R, C, D): lines, characters, block depth, line length, statements with an arrow, keywords, against the XML of the same models (`scripts/s7_reading.py`) | tok 1.0.3 (`tok fmt --check`) |
| `results/uais/S8/` | the same models as three assistive technologies deliver them: spoken words and symbol words under the English symbol table of the screen reader NVDA at the punctuation levels none, some, most and all, lines at which the indentation changes, rows of 40- and 80-cell braille displays, screens and horizontal scrolling of the diagram and screens of the reflowed text at 200 % and 400 % magnification (`scripts/s8_assistive.py`, `scripts/analyse_s8.py`) | NVDA symbol table, release 2026.3 (`data/raw/nvda/`) |
| `results/uais/S8b/` | the same speech and braille measures for the final models of the lean-skill agents of `S3i` (`TOKAGENT-C` against `XMLAGENT-C`, same language model and text, both valid; 258 pairs), and the count of agent-written BPMN XML files with a diagram (`scripts/s8b_agent_outputs.py`, `scripts/analyse_s8b.py`) | NVDA symbol table, release 2026.3 |

The scripts write to `results/S7/`, `results/S8/` and `results/S8b/`; the release keeps their output under `results/uais/`. `S7` and `S8` read the variants of the models that `scripts/s1_prepare.py` writes to `results/S1/variants/`.

## Language-model study

Claude Haiku 5.5 and Claude Sonnet 5.5 (through the Claude command line) and gpt-oss 120B and Beam (through Ollama) write a process model for each text. The arms cross the representation with the condition; the code of an arm is the field `rep` of a run.

| Code | Arm |
|---|---|
| `XML` | BPMN XML, reference: one-page reference, the checker's messages, at most four attempts |
| `TOK` | tok, reference: one-page reference, the messages of `tok check` 1.0.2, at most four attempts |
| `XMLAGENT-A` | BPMN XML, agent with the distributed skill of tok 1.0.3 and the tool `check_bpmn`, at most 12 model calls |
| `TOKAGENT` | tok, agent with the distributed skill of tok 1.0.3 and the tools `check`, `fmt`, `reference`, at most 12 model calls |
| `XMLAGENT-C` | BPMN XML, agent with the lean skill (`prompts/skill-lean-xml.md`) and the tool `check_bpmn` |
| `TOKAGENT-C` | tok, agent with the lean skill (`prompts/skill-lean-tok.md`) and the tool `check` |

| Task set | Folders |
|---|---|
| PET, 42 texts (`data/derived/pet/`) | `S3/main` (Claude, `XML`, `TOK`), `S3b/main` (gpt-oss, `XML`, `TOK`), `S3c/main` (gpt-oss, `TOKAGENT`), `S3d/main` (Claude `TOKAGENT`; Beam `XML`, `TOK`, `TOKAGENT`), `S3i/pet` (four models, `XMLAGENT-A`, `XMLAGENT-C`, `TOKAGENT-C`) |
| PMo, 45 texts (`data/derived/pmo/`) | `S3h/main` (four models, `XML`, `TOK`, `TOKAGENT`), `S3i/main` (four models, `XMLAGENT-A`, `XMLAGENT-C`, `TOKAGENT-C`) |

`S3i/channel/` holds the probe of the tool-call channel of Beam. Each folder has `runs.jsonl`, one line per run, and `runs/`, one folder per run with the prompt, the answers or the transcript of the agent, the model files and the output of the judge; `frozen.json` records the checksums of the scripts, prompts and programs of the folder. The judge is the OMG XML Schema, the correctness rules of bpmnlint 12.0.0, a start and an end event, and flows between known nodes.

## Software

tok 1.0.2 and 1.0.3 are archived at Zenodo (10.5281/zenodo.23769633, all versions). The tok agent arms use a build of the 1.0.3 sources (commit 2f5f1c1), whose tool `check` is the program of the release; the BPMN XML agent arms use the released 1.0.3 programs. The programs are not part of this package; `environment/checksums.txt` lists their checksums, `environment/machine.txt` the machine and the versions of the other tools.

## Running the scripts

Python 3.12 and Node.js 22 or newer:

```
python -m venv .venv
.venv/Scripts/python -m pip install -r environment/requirements.txt
bash scripts/fetch_data.sh
```

The release archives of tok go to `tools/bin/` under the names in `environment/checksums.txt`. The scripts are the versions that produced the results; their comments refer to the planning documents of the study, which are not part of this package.

## Licence

Scripts: GPL-3.0-or-later. Results and derived data: CC BY 4.0. The English symbol table of NVDA in `data/raw/nvda/` (NV Access, https://github.com/nvaccess/nvda, release 2026.3) keeps its licence, the GNU General Public License. The PET dataset (Bellan et al., MIT licence) and the PMo dataset (Brissard et al., CC BY 4.0) keep their licences; the XML Schemas in `data/raw/xsd/` are those published by the OMG.
