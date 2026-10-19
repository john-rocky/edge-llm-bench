#!/usr/bin/env bash
# r18_graph_inventory.sh LABEL BUNDLE - op / signature inventory of one bundle's TFLite graph:
# r18_extract_tflite.py copies the TFLiteModel section to CAND/graph/LABEL.tflite, then litertlm-convert's
# qwen3_gpuopt_work/tflite_ops.py (read only; venv ~/venvs/ltmain1013) writes CAND/graph/LABEL.ops.txt;
# the .tflite copy is removed afterwards. Each step through quiet_wait.py.
set -uo pipefail
[ $# -eq 2 ] || { echo "usage: $0 LABEL BUNDLE" >&2; exit 2; }
label=$1; bundle=$2
here=$(cd "$(dirname "$0")" && pwd)
G=$HOME/.cache/edge-llm-bench/litert-candidates/graph
mkdir -p "$G"
[ -e "$G/$label.ops.txt" ] && { echo "refusing to overwrite $G/$label.ops.txt" >&2; exit 2; }
QW=(python3 "$HOME/code/standup/tools/quiet/quiet_wait.py" --max-wait 1800 --)
"${QW[@]}" uv run --no-project --with litert-lm==0.18.0 python -I "$here/r18_extract_tflite.py" "$bundle" "$G/$label.tflite" \
  > "$G/$label.extract.txt" 2>&1
rc=$?; cat "$G/$label.extract.txt"; [ $rc -eq 0 ] || exit $rc
"${QW[@]}" "$HOME/venvs/ltmain1013/bin/python" -I "$HOME/code/litertlm-convert/qwen3_gpuopt_work/tflite_ops.py" \
  "$G/$label.tflite" > "$G/$label.ops.txt" 2>&1
rc=$?
rm -f "$G/$label.tflite"
echo "### tflite_ops exit $rc -> $G/$label.ops.txt"
exit $rc
