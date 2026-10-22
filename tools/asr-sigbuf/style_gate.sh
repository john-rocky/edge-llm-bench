#!/bin/bash
# The litert-samples style gate (~/Downloads/meeting/style-sweep-tools/pre_pr_check.sh) on the change's
# branch, inside a Mac measurement window (it runs Python checks and a Gradle build). The gate's
# fixers may rewrite files: their diff is saved to .build/asr-sigbuf/style-gate.diff and the tracked
# files are put back, so the branch keeps the commit as it is (a fixer's change is applied by hand
# after reading the diff).
#
#   bash tools/asr-sigbuf/style_gate.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
B="$ROOT/.build/asr-sigbuf"
WT="${WT:-$HOME/code/litert-samples-asr-sigbuf-wt}"
MOD=samples/litert/speech_recognition
GATE="$HOME/Downloads/meeting/style-sweep-tools/pre_pr_check.sh"
[ -f "$GATE" ] || { echo "STYLE GATE: $GATE not found"; exit 0; }
git -C "$WT" checkout -q speech-recognition-tdt-separate-buffers || { echo "STYLE GATE: checkout failed"; exit 1; }
if [ -n "$(git -C "$WT" status --porcelain -- "$MOD" | grep -v '^??')" ]; then
  echo "STYLE GATE: tracked changes in $MOD before the gate; not run"; exit 1
fi
echo "STYLE GATE start $(date +%T) on $(git -C "$WT" rev-parse --short HEAD)"
zsh "$GATE" "$WT" "$MOD" > "$B/logs/style-gate.log" 2>&1
rc=$?
git -C "$WT" diff -- "$MOD" > "$B/style-gate.diff"
git -C "$WT" diff --stat -- "$MOD" | tail -8
git -C "$WT" checkout -q -- "$MOD"
echo "STYLE GATE end rc=$rc $(date +%T) (log $B/logs/style-gate.log, fixer diff $(wc -l < "$B/style-gate.diff" | tr -d ' ') lines, tracked files put back)"
grep -E '^=== |FAIL|PASS|BUILD_|^\^\^|TOOL DIFF' "$B/logs/style-gate.log" | head -40
exit 0
