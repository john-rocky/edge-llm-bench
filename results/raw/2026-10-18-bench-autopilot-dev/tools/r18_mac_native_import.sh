#!/usr/bin/env bash
# r18_mac_native_import.sh - the supervisor's ask (2026-10-19 14:5x): the Mac sitting's two native-benchmark rows into
# MAIN/results/raw/2026-10-19-dashboard-v1-m4max-q06cand-mac/app-path-native/ as schema-v1 records, the form of
# 2026-10-06-dashboard-v1-m4max-protocol1024-mac/NOTES.md (scripts/import_native_benchmark.py --schema-v1, --like = the same
# model's short-chat record of this campaign, --launch-times = the runner's CELL line in UTC), then NOTES.md beside them.
# Run through quiet_wait.py (a python call while another lane's window is open is refused). Nothing else is written.
set -uo pipefail
cd "$HOME/code/edge-llm-bench" || exit 1
D=results/raw/2026-10-19-dashboard-v1-m4max-q06cand-mac
[ -e "$D/app-path-native" ] && { echo "refusing: $D/app-path-native exists"; exit 2; }
[ -e "$D/NOTES.md" ] && { echo "refusing: $D/NOTES.md exists"; exit 2; }
INSTR="litert-lm native benchmark() via yardstick --litert-native-benchmark"
imp() {   # $1 = cell stem, $2 = model id, $3 = launch time (UTC)
  python3 scripts/import_native_benchmark.py --schema-v1 "$D/$1_native-benchmark-1024x256_ctx2048.jsonl" \
    --out "$D/app-path-native" --like "$D/$1_short-chat.jsonl" --model-id "$2" --launch-times "$3" \
    --instrument "$INSTR" --device Mac16,9
}
imp litert-lm_litert-community_Qwen3-0_6B_dynamic_wi4b32_afp32 litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32 2026-10-19T05:34:27Z || exit 1
imp litert-lm_litert-community_Qwen3-0_6B_dynamic_wi4b32_afp32_r0805meta018 litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32_r0805meta018 2026-10-19T05:35:03Z || exit 1
when=$(date '+%Y-%m-%d %H:%M JST')
cat > "$D/NOTES.md" <<EOF
# 2026-10-19-dashboard-v1-m4max-q06cand-mac — notes

One dashboard-job sitting on the Mac Studio M4 Max (\`Mac16,9\`, macOS 27.0 26A428), 2026-10-19 14:30:35–14:47:44 JST, cells
\`matrices/q06-candidate-mac.cells\`: the current Qwen3 0.6B dynamic INT4 file (\`litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32\`,
Hub a3c5d805) beside the local candidate \`litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32_r0805meta018\` (the same file's
2026-08-05 graph with the current LlmMetadata, sha256 \`e6bf25c0cf7e1a09d19fc6ad716072bb5b8ac96a0eca75075a69f7ce8c1a8f91\`,
side-loaded; \`docs/dashboard-cells-v1.md\` "Qwen3 0.6B candidate (2026-10-19)"). Yardstick \`.build/dd-mac-q06cand\` (sha256
\`735120b9…\`, LiteRT-LM v0.18.0, \`DD_MAC\` set for this sitting). Anchor phase \`2026-10-19-dashboard-v1-m4max-q06cand-anchor-mac\`
admitted (ratio 1.004).

The two \`native-benchmark-1024x256\` rows: the Mac runner writes no schema-v1 record for them. \`<cell>.jsonl\` holds the
\`YARDSTICK_NATIVE_OK\` lines (the stored report): one launch per row with \`--runs 4\` = four \`benchmark()\` calls in one
process, run 1 cold (\`cold=1\`). \`app-path-native/\` holds the same lines as schema-v1 records, written by
\`scripts/import_native_benchmark.py --schema-v1\` after the sitting ($when): \`timestamp\` = the launch's start from the
runner's \`CELL\` line (current file 14:34:27 JST = 2026-10-19T05:34:27Z, candidate 14:35:03 JST = 2026-10-19T05:35:03Z);
\`device\`, \`engineVersion\` / \`engineArtifact\` and \`model\` copied from the same model's GPU short-chat record of this
campaign (\`--like <cell>_short-chat.jsonl\`, \`--model-id\` = that record's id: the Mac CLI's native line names no model);
\`--device Mac16,9\`; \`--instrument "$INSTR"\`.
No \`--first-ever\`: the GPU program caches in \`\$TMPDIR\` (\`<file>_<mtime>_<size>_mldrift_program_cache.bin\`, the native
path's cacheDir) were not written during either native launch: the current file's is from 06:22:02 (an earlier sitting),
the candidate's was last written at 14:33:46 (its 1K cell's first run, the first use of prefill_1024) and not after.
\`SESSION.json\`'s \`cells_with_records\` (9 of 11: the two native rows had no record yet) was written before the import.
EOF
ls "$D/app-path-native"
echo "NOTES.md written"
