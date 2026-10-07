#!/usr/bin/env bash
# Round r1 smoke of the ExecuTorch Mac arm (Qwen3 0.6B own export, llama_main XNNPACK).
# Run it inside a measurement window:
#   python3 ~/code/standup/tools/quiet/quiet_hold.py et-r1-smoke -- bash scripts/executorch/smoke_r1_mac.sh <out-dir>
#
# 1. <out-dir>: the stock Release binary, short-chat and long-context-1024-gen256,
#    cold x 3 then warm x 3 per task, 30 s apart (smoke_mac.py), after a 60 s lead
#    pause for the load of earlier jobs to decay.
# 2. <out-dir>/diag-logbuild: the logging build of the same source (witness of the
#    thread pool size, the pte metadata and the warmup path): short-chat cold and
#    warm, long-context cold, one launch each.
# 3. <out-dir>/diag-threads12: the stock binary with --cpu_threads 12 (the M4 Max's
#    performance cores; the default heuristic counts no efficiency core on this chip),
#    one cold launch per task.
# Diagnostic launches are not part of the smoke table's 12 launches.
#
# Env: ET_DIR (source tree), ET_VENV (python with the repo's deps), MODEL_DIR, PROMPTS_DIR.
set -euo pipefail
OUT="${1:?usage: $0 <out-dir>}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
ET_DIR="${ET_DIR:-$HOME/code/executorch-convert/et-v1.5.1/executorch}"
ET_VENV="${ET_VENV:-$HOME/code/executorch-convert/.venv-et151}"
MODEL_DIR="${MODEL_DIR:-$HOME/code/edge-llm-bench/models/executorch}"
PROMPTS_DIR="${PROMPTS_DIR:?set PROMPTS_DIR to the dir of <task>.qwen3.txt (make_prompts.py)}"
PTE="$MODEL_DIR/Qwen3-0.6B-ET1.5.1-xnnpack-8da4w-emb8-ctx2048.pte"
STOCK="$ET_DIR/cmake-out/examples/models/llama/llama_main"
LOGB="$ET_DIR/cmake-out-log/examples/models/llama/llama_main"
smoke() { "$ET_VENV/bin/python" "$REPO/scripts/executorch/smoke_mac.py" --pte "$PTE" \
  --tokenizer "$MODEL_DIR/tokenizer.json" --prompts-dir "$PROMPTS_DIR" --suffix qwen3 "$@"; }

echo "== smoke r1 $(date '+%H:%M:%S') QUIET_OK=${QUIET_OK:-unset}"
smoke --llama-main "$STOCK" --out-dir "$OUT" --lead-pause 60
echo "== diag logbuild $(date '+%H:%M:%S')"
smoke --llama-main "$LOGB" --out-dir "$OUT/diag-logbuild" --tasks short-chat --regimes cold warm --runs 1 --lead-pause 30
smoke --llama-main "$LOGB" --out-dir "$OUT/diag-logbuild" --tasks long-context-1024-gen256 --regimes cold --runs 1 --lead-pause 30
echo "== diag threads12 $(date '+%H:%M:%S')"
smoke --llama-main "$STOCK" --out-dir "$OUT/diag-threads12" --regimes cold --runs 1 --lead-pause 30 --extra-args "--cpu_threads 12"
echo "== done $(date '+%H:%M:%S')"
