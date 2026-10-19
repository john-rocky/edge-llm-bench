#!/usr/bin/env bash
# r18_mac_smoke.sh OUTDIR - one short-chat launch (runs=1) per file x backend on the Mac with the r18 yardstick
# (.build/dd-mac-q06cand), inside one quiet_hold window: the current file (catalog dynamic_wi4b32_afp32, the hub cache)
# and the candidate (dynamic_wi4b32_afp32_r0805meta018, side-loaded first by r18_step7.sh mac-stage), GPU then CPU.
# A wiring and prompt-token check, not a measurement: the records go to OUTDIR, never into results/raw.
set -uo pipefail
[ $# -eq 1 ] || { echo "usage: $0 OUTDIR" >&2; exit 2; }
O=$1; mkdir -p "$O"
M=$HOME/code/edge-llm-bench
YS=$M/.build/dd-mac-q06cand/Build/Products/Release/yardstick
export BENCH_ENGINE_PINS_FILE=$M/ios/BenchmarkApp/Vendored/engine-pins.json
cat > "$O/smoke.sh" <<EOF
set -uo pipefail
for be in gpu cpu; do
  for id in litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32 litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32_r0805meta018; do
    tag=\$(echo "\${id##*/}_\$be" | tr '/.' '__')
    echo "smoke \$tag start \$(date '+%T')"
    gtimeout 900 "$YS" run --runtime litert-lm --model-id "\$id" --task short-chat --runs 1 --litert-backend "\$be" \
      --output "$O/\$tag.jsonl" > "$O/\$tag.console.txt" 2>&1
    echo "smoke \$tag rc=\$? \$(date '+%T')"
    sleep 20
  done
done
EOF
python3 "$HOME/code/standup/tools/quiet/quiet_hold.py" r18-q06cand-mac-smoke -- bash "$O/smoke.sh"
