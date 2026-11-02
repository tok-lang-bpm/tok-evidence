#!/usr/bin/env bash
# Records the machine, the versions of the tools and the checksums of the inputs.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
PY=.venv/Scripts/python; [ -x "$PY" ] || PY=.venv/bin/python
TOK=tools/bin/tok-1.0.2-windows-x86_64/tok.exe
{
  echo "date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "os: $(uname -srm)"
  powershell -NoProfile -Command "\$c=Get-CimInstance Win32_Processor; \$m=Get-CimInstance Win32_ComputerSystem; \$o=Get-CimInstance Win32_OperatingSystem; 'cpu: ' + \$c.Name.Trim() + ' (' + \$c.NumberOfCores + ' cores, ' + \$c.NumberOfLogicalProcessors + ' threads)'; 'ram_gb: ' + [math]::Round(\$m.TotalPhysicalMemory/1GB,1); 'windows: ' + \$o.Caption + ' ' + \$o.Version" 2>/dev/null | tr -d '\r'
  echo "gpu: $(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null || echo none)"
  echo "tok: $($TOK --version)"
  echo "python: $($PY --version 2>&1)"
  echo "node: $(node --version)"
  echo "bpmnlint: $(node -p "require('./tools/node/node_modules/bpmnlint/package.json').version")"
  echo "bpmn-moddle: $(node -p "require('./tools/node/node_modules/bpmn-moddle/package.json').version")"
  echo "ollama: $(ollama --version 2>&1 | tail -1)"
  echo "claude-cli: $(claude --version 2>&1 | head -1)"
} > environment/machine.txt
"$PY" -m pip freeze > environment/requirements.txt
{
  sha256sum tools/tok-1.0.2-windows-x86_64.zip tools/bin/tok-1.0.2-windows-x86_64/tok.exe
  sha256sum data/raw/xsd/*.xsd data/raw/pet/PETv1.1-relations.json
  find data/raw/tokenizers -type f \( -name "tokenizer.json" -o -path "*tiktoken*" \) -print0 | sort -z | xargs -0 sha256sum
  echo "miwg-suite commit $(git -C data/raw/miwg-suite rev-parse HEAD)"
  for r in tok tok-book tok-course; do
    [ -d "../$r/.git" ] && echo "$r commit $(git -C "../$r" rev-parse HEAD)"
  done
  echo "miwg-suite bpmn files $(find data/raw/miwg-suite -iname '*.bpmn' -not -path '*/.git/*' -not -path '*/Work in Progress/*' | wc -l)"
} > environment/checksums.txt
echo "environment recorded"
