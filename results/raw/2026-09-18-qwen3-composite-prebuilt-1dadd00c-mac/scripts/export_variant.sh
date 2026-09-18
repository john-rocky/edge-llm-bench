#!/bin/zsh
# Bisect helper: export Qwen3 with the requested 11-flag set MINUS the flags named in DROP,
# to find which composite produces the WGSL shader failures on the OSS 0.17.0 WebGPU path.
#
# Usage: DROP="use_sdpa_composite" ./export_variant.sh Qwen/Qwen3-0.6B out/v_nosdpa
#        DROP="…" EXTRA="--use_rope_composite=True" ./export_variant.sh …   (append flags)
#        DROP="use_sdpa_composite use_qkv_norm_rope_composite" ./export_variant.sh ...
# Flags not in DROP are passed exactly as in export_qwen3_gpuopt.sh.
set -euo pipefail
MODEL=${1:?HF model id}
OUT=${2:?output dir}
DROP=${DROP:-}
EXTRA=${EXTRA:-}   # extra flags to append, e.g. EXTRA="--use_rope_composite=True"
VENV=${VENV:-$HOME/venvs/ltmain0910}
PY=$VENV/bin/python
export HF_HUB_DISABLE_XET=1
mkdir -p "$OUT"
cd "$(dirname "$0")"

ALL=(
  --quantization_recipe=dynamic_wi4b32_afp32
  --enable_gpu_dynamic_prefill=True
  --enable_gpu_dynamic_cache=True
  --apply_gpu_composites=True
  --fuse_gate_up=True
  --fuse_qkv=True
  --use_qkv_norm_rope_composite=True
  --use_swiglu_composite=True
  --use_sdpa_composite=True
  --use_bool_mask=True
  --bundle_litert_lm=True
  --prefill_lengths=1024
  --cache_length=32768
)
ARGS=()
for a in "${ALL[@]}"; do
  keep=1
  for d in ${=DROP}; do
    [[ "$a" == "--${d}="* ]] && keep=0
  done
  (( keep )) && ARGS+=("$a")
done
for e in ${=EXTRA}; do ARGS+=("$e"); done
echo "DROP = [$DROP]  EXTRA = [$EXTRA]"
echo "ARGS = ${ARGS[*]}"
$PY -c 'import litert_torch; print("litert_torch.__file__ =", litert_torch.__file__)' 2>/dev/null | grep -v '^W0'
time $PY -m litert_torch.generative.export_hf --model="$MODEL" --output_dir="$OUT" "${ARGS[@]}"
ls -la "$OUT"
shasum -a 256 "$OUT"/*.litertlm
