#!/bin/zsh
# 2026-09-18: Fengwu (Chat "HF Model GPU optimization", 07:5x JST): "There is a new prebuilt checked in, feel free to use it,
# we shall have new prefill performance, and we need use_sdpa_composite_for_prefill flag when doing the export."
# Re-export the two published 11-flag recipes (FINDINGS §13: his 09-11 command = the 11 flags minus
# --enable_gpu_dynamic_prefill, plus the LlmMetadata override) with --use_sdpa_composite_for_prefill=True appended.
# Exporter: litert-torch main 731ef0a (2026-09-17) = worktree ~/code/litert-torch-0918-wt, venv ~/venvs/ltmain0918
# (the lane's lt094dev pins in venv_requirements.txt + `pip install --no-deps -e ~/code/litert-torch-0918-wt`, so the only
# component that moves against the p1024 files is litert-torch: 6d4c622 -> 731ef0a). The flag itself is Fengwu's 9f8a33f
# (2026-08-31, "Optimize sdpa op."); the exporter CL the fused FA2 prefill kernel needs is 75370b9 (2026-09-15, "Skip query
# head packing when using SDPA composite."), neither of which the 09-08 checkout behind the p1024 files had.
# Usage: (nohup ./chain_p1024_12flags.sh > logs/chain_p1024_12flags_driver.txt 2>&1 &)
#   completion = the "=== DONE" line + out/p1024_{06b,4b}_12flags/model.litertlm + logs/ops_p1024_*_12flags.txt
set -u
cd "$(dirname "$0")"
export VENV=$HOME/venvs/ltmain0918
export HF_HUB_DISABLE_XET=1
PB=$HOME/code/litert-lm-0170-metal/models/qwen3/LlmMetadataProto.pbtext
OV="--litert_lm_llm_metadata_override=$PB"
echo "=== chain_p1024_12flags start $(date '+%Y-%m-%d %H:%M:%S')  load=$(uptime | sed 's/.*load averages: //')"
shasum -a 256 "$PB"
$VENV/bin/python - <<'PYEOF' 2>/dev/null | grep -v '^W0'
import litert_torch, subprocess, os
print("litert_torch.__file__ =", litert_torch.__file__)
print("litert_torch.__version__ =", getattr(litert_torch, "__version__", "?"))
root = os.path.dirname(os.path.dirname(litert_torch.__file__))
print("git HEAD =", subprocess.check_output(["git", "-C", root, "rev-parse", "HEAD"]).decode().strip())
print("git status --short =", subprocess.check_output(["git", "-C", root, "status", "--short"]).decode().strip() or "(clean)")
PYEOF
$VENV/bin/pip freeze 2>/dev/null | grep -i -E 'litert|ai-edge|^torch|transformers' | sed 's/^/pin: /'
run() { local name=$1 model=$2 drop=$3 extra=$4
  echo "=== export $name  $(date '+%Y-%m-%d %H:%M:%S')  DROP=[$drop] EXTRA=[$extra]  load=$(uptime | sed 's/.*load averages: //')"
  echo "### CMD: DROP=\"$drop\" EXTRA=\"$extra\" VENV=$VENV ./export_variant.sh $model out/$name"
  DROP="$drop" EXTRA="$extra" ./export_variant.sh "$model" "out/$name" > "logs/export_$name.log" 2>&1
  echo "   exit $?  $(shasum -a 256 out/$name/model.litertlm 2>/dev/null | cut -c1-64)  $(stat -f %z out/$name/model.litertlm 2>/dev/null) bytes  $(date '+%H:%M:%S')"
  grep -E 'Qwen3 model patch applied|real' "logs/export_$name.log" | cut -c1-160
  $VENV/bin/python tflite_ops.py "out/$name/model.litertlm" > "logs/ops_$name.txt" 2>&1
  echo "   ops inventory logs/ops_$name.txt: $(grep -E '^== subgraph [01]:' logs/ops_$name.txt | tr '\n' ' ')"
  grep -E 'STABLEHLO_COMPOSITE:odml\.(sdpa_transposed|qkv_norm_rope|swiglu|cache_update|runtime_bmm)' "logs/ops_$name.txt" | head -12
}
run p1024_06b_12flags Qwen/Qwen3-0.6B "enable_gpu_dynamic_prefill" "$OV --use_sdpa_composite_for_prefill=True"
run p1024_4b_12flags  Qwen/Qwen3-4B   "enable_gpu_dynamic_prefill" "$OV --use_sdpa_composite_for_prefill=True"
echo "=== DONE $(date '+%Y-%m-%d %H:%M:%S')"
