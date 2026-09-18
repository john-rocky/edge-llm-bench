#!/bin/zsh
# 2026-09-18 control for the prefill-SDPA flag: the SAME 11-flag command as the published p1024 files, exported from litert-torch
# main 1e2d37f (2026-09-17, one commit before 731ef0a = the level of the PyPI nightly 0.10.0.dev20260917). Why: the 12-flag
# exports (731ef0a) differ from the published files (6d4c622) not only by the prefill composite but also by a handful of
# SUB/SLICE/CONCATENATION ops in both signatures (exporter drift: in-graph param_tensor update-length handling). At 731ef0a
# the plain --use_sdpa_composite already emits the prefill composite, so the flag-only control has to come from 1e2d37f:
# 11 flags there = no prefill composite + the same exporter drift as the 12-flag files. The worktree ~/code/litert-torch-0918-wt
# (editable install of ~/venvs/ltmain0918) is checked out to 1e2d37f for the two exports and back to 731ef0a afterwards.
# Usage: (nohup ./chain_p1024_11flags_1e2d37f.sh > logs/chain_p1024_11flags_1e2d37f_driver.txt 2>&1 &)
set -u
cd "$(dirname "$0")"
export VENV=$HOME/venvs/ltmain0918
export HF_HUB_DISABLE_XET=1
WT=$HOME/code/litert-torch-0918-wt
PB=$HOME/code/litert-lm-0170-metal/models/qwen3/LlmMetadataProto.pbtext
OV="--litert_lm_llm_metadata_override=$PB"
restore() { git -C $WT checkout -q --detach 731ef0a; echo "=== worktree restored to $(git -C $WT rev-parse --short HEAD)"; }
trap restore EXIT
echo "=== chain_p1024_11flags_1e2d37f start $(date '+%Y-%m-%d %H:%M:%S')  load=$(uptime | sed 's/.*load averages: //')"
git -C $WT checkout -q --detach 1e2d37f || { echo "ABORT: checkout failed"; exit 4; }
echo "worktree HEAD = $(git -C $WT rev-parse HEAD)  status: $(git -C $WT status --short | wc -l | tr -d ' ') dirty files"
$VENV/bin/python - <<'PYEOF' 2>/dev/null | grep -v '^W0'
import litert_torch, subprocess, os
root = os.path.dirname(os.path.dirname(litert_torch.__file__))
print("litert_torch.__file__ =", litert_torch.__file__)
print("git HEAD =", subprocess.check_output(["git", "-C", root, "rev-parse", "HEAD"]).decode().strip())
PYEOF
run() { local name=$1 model=$2 drop=$3 extra=$4
  echo "=== export $name  $(date '+%Y-%m-%d %H:%M:%S')  DROP=[$drop] EXTRA=[$extra]  load=$(uptime | sed 's/.*load averages: //')"
  echo "### CMD: DROP=\"$drop\" EXTRA=\"$extra\" VENV=$VENV ./export_variant.sh $model out/$name"
  DROP="$drop" EXTRA="$extra" ./export_variant.sh "$model" "out/$name" > "logs/export_$name.log" 2>&1
  echo "   exit $?  $(shasum -a 256 out/$name/model.litertlm 2>/dev/null | cut -c1-64)  $(stat -f %z out/$name/model.litertlm 2>/dev/null) bytes  $(date '+%H:%M:%S')"
  $VENV/bin/python tflite_ops.py "out/$name/model.litertlm" > "logs/ops_$name.txt" 2>&1
  echo "   ops inventory logs/ops_$name.txt: $(grep -E '^== subgraph [01]:' logs/ops_$name.txt | tr '\n' ' ')"
  grep -E 'STABLEHLO_COMPOSITE:odml\.(sdpa_transposed|qkv_norm_rope|swiglu|cache_update|runtime_bmm)' "logs/ops_$name.txt" | head -12
}
run p1024_06b_11flags_1e2d37f Qwen/Qwen3-0.6B "enable_gpu_dynamic_prefill" "$OV"
run p1024_4b_11flags_1e2d37f  Qwen/Qwen3-4B   "enable_gpu_dynamic_prefill" "$OV"
echo "=== DONE $(date '+%Y-%m-%d %H:%M:%S')"
