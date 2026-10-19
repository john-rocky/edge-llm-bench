#!/usr/bin/env bash
# r18_probe.sh LABEL BUNDLE - litertlm-convert team_repack_20261012/tools/run_all.sh (read only) on an APFS clone of
# BUNDLE in CAND/probe/LABEL/bundle/: describe (0.18.0 CLI), probe_one.py D A B C E (0.18.0 python API, CPU, one
# process per condition, each through quiet_wait.py), control_017.sh (0.17.0 CLI), SUMMARY.md in
# CAND/probe/LABEL/run_all/. The engine writes its .xnnpack_cache next to the bundle: the clone dir is removed at
# the end (the README's trap), the run_all dir is kept.
set -uo pipefail
[ $# -eq 2 ] || { echo "usage: $0 LABEL BUNDLE" >&2; exit 2; }
label=$1; src=$2
P=$HOME/.cache/edge-llm-bench/litert-candidates/probe/$label
[ -e "$P" ] && { echo "refusing: $P exists" >&2; exit 2; }
mkdir -p "$P/bundle"
cp -c "$src" "$P/bundle/$(basename "$src")" || exit 1
bash "$HOME/code/litertlm-convert/team_repack_20261012/tools/run_all.sh" "$P/bundle/$(basename "$src")" "$P/run_all"
rc=$?
ls -la "$P/bundle" > "$P/run_all/bundle_dir_at_end.txt"
rm -rf "$P/bundle"
echo "### run_all exit $rc -> $P/run_all/SUMMARY.md"
exit $rc
