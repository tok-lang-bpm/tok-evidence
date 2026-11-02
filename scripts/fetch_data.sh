#!/usr/bin/env bash
# Downloads the external inputs of the studies at their pinned versions and writes their
# checksums to environment/checksums.txt. Run from the root of this folder.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
PY=.venv/Scripts/python; [ -x "$PY" ] || PY=.venv/bin/python
# tok 1.0.1, the release binary of the GitHub release
mkdir -p tools/bin
curl -sfL -o tools/tok-1.0.2-windows-x86_64.zip https://github.com/tok-lang-bpm/tok/releases/download/v1.0.2/tok-1.0.2-windows-x86_64.zip
unzip -o -q tools/tok-1.0.2-windows-x86_64.zip -d tools/bin
# the BPMN 2.0 XML Schema of the OMG
mkdir -p data/raw/xsd
for f in BPMN20.xsd BPMNDI.xsd DC.xsd DI.xsd Semantic.xsd; do
  curl -sfL -o "data/raw/xsd/$f" "https://www.omg.org/spec/BPMN/20100501/$f"
done
# PET v1.1
mkdir -p data/raw/pet
curl -sfL -o data/raw/pet/PETv1.1-relations.json https://raw.githubusercontent.com/patriziobellan86/PETv1.1/master/PETv1.1-relations.json
curl -sfL -o data/raw/pet/README.md https://huggingface.co/datasets/patriziobellan/PET/resolve/main/README.md
# the PMo dataset 1.0.0 (Zenodo 15857589): descriptions and BPMN models
mkdir -p data/raw/pmo
curl -sfL -o data/raw/pmo/pmo-dataset.zip "https://zenodo.org/records/15857589/files/pmo-dataset.zip?download=1"
unzip -o -q data/raw/pmo/pmo-dataset.zip 'descriptions/*' 'bpmn/*' README.md -d data/raw/pmo
# the BPMN MIWG test suite: only the .bpmn files, at a fixed commit
if [ ! -d data/raw/miwg-suite/.git ]; then
  git clone -q --filter=blob:none --no-checkout https://github.com/bpmn-miwg/bpmn-miwg-test-suite.git data/raw/miwg-suite
fi
git -C data/raw/miwg-suite sparse-checkout init --no-cone
printf '%s\n' '/**/*.bpmn' '/**/*.BPMN' '!/Work in Progress/' '/README.md' '/LICENSE*' > data/raw/miwg-suite/.git/info/sparse-checkout
git -C data/raw/miwg-suite checkout -q 85240b8689d835d8bd1a96fbea6af46558ca0568
# the tokenizers
TIKTOKEN_CACHE_DIR="$ROOT/data/raw/tokenizers/tiktoken" "$PY" - <<'PY'
import tiktoken
from huggingface_hub import hf_hub_download
for e in ("o200k_base", "cl100k_base"):
    tiktoken.get_encoding(e)
for repo in ("Qwen/Qwen3-4B", "deepseek-ai/DeepSeek-V3", "mistralai/Mistral-Nemo-Instruct-2407"):
    hf_hub_download(repo, "tokenizer.json", local_dir="data/raw/tokenizers/" + repo.replace("/", "__"))
PY
# the comparison tools
(cd tools/node && npm ci --silent --no-audit --no-fund)
bash scripts/environment.sh
