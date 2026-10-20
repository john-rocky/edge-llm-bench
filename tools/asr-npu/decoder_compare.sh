#!/bin/bash
# The decoder-only run's reading (docs/asr-npu-v1.md), jq only (no Mac measurement window needed):
# per run the windows run and failed, the first failing window and its error, the tokens per window,
# and per window whether the token ids equal the reference run's (d-cpu-shared) in the same pass and
# window. Writes <REC>/d-compare.json and prints one line per run.
#
#   tools/asr-npu/decoder_compare.sh [REC]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REC="${1:-$ROOT/results/raw/2026-10-20-asr-npu-v1-s26-android}"
ref="$REC/d-cpu-shared.json"
[ -f "$ref" ] || { echo "no reference run ($ref)" >&2; exit 2; }
out="$REC/d-compare.json"
echo "[" > "$out.part"
first=1
for f in "$REC"/d-*.json; do
  case "$f" in *d-compare.json|*.probe-*.json) continue ;; esac
  row=$(jq -c --slurpfile ref "$ref" '
    . as $r
    | {tag: .tag, accelerator: .accelerator, tdt_buffers: .tdt_buffers, run_encode: .run_encode,
       load_ms: .load_ms, windows_run: .windows_run, windows_failed: .windows_failed,
       first_error: ([.windows[] | select(.error != null) | {pass, window, input, error}] | first),
       tokens_per_window: [.windows[] | (.tokens | length)],
       steps_per_window: [.windows[] | .decoder_steps],
       same_tokens_as_reference: [range(0; (.windows | length)) as $i
         | ($ref[0].windows[$i].tokens == .windows[$i].tokens)] | map(select(.)) | length}' "$f")
  [ $first = 1 ] || echo "," >> "$out.part"
  echo "$row" >> "$out.part"
  first=0
  echo "$row" | jq -r '"\(.tag): \(.accelerator) \(.tdt_buffers) run_encode=\(.run_encode) windows \(.windows_run) failed \(.windows_failed) same tokens as d-cpu-shared \(.same_tokens_as_reference)/\(.windows_run) tokens/window \(.tokens_per_window) first error \(.first_error)"'
done
echo "]" >> "$out.part"
jq . "$out.part" > "$out" && rm -f "$out.part"
