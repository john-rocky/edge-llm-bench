#!/usr/bin/env bash
# r18_repack.sh STEP - round r18's metadata-only re-pack of the Qwen3 0.6B dynamic INT4 file, with the
# litertlm-convert team_repack_20261012 tools (read only), each step through quiet_wait.py (no model runs here,
# but the unpack / pack moves ~700 MB on the shared Mac).
#   identity   --identity self-test on IN (the 2026-08-05 file, Hub 8414150f) and on CUR (the current file,
#              Hub a3c5d805, HF cache blob); the reports' evidence holds both LlmMetadataProto.pbtext
#   describe   litert-lm 0.18.0 describe of IN and CUR (header read only)
#   repack F   IN + NEW.pbtext -> OUT, --expect-changed F (comma list of top-level LlmMetadata fields)
#   describe-out  describe of OUT
# Paths: CAND = ~/.cache/edge-llm-bench/litert-candidates (outside every repo). Nothing is overwritten.
set -uo pipefail
CAND=$HOME/.cache/edge-llm-bench/litert-candidates
T=$HOME/code/litertlm-convert/team_repack_20261012/tools
IN=$CAND/in/Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm
CUR=$CAND/cur/Qwen3-0.6B_dynamic_wi4b32_afp32.a3c5d805.litertlm  # APFS clone of the HF cache blob 03e7da1e… (a symlink resolves to a suffix-less blob name, which the tool refuses)
OUT=$CAND/out/Qwen3-0.6B_dynamic_wi4b32_afp32.r0805meta018.litertlm
NEW=$CAND/meta/NEW.LlmMetadataProto.pbtext
QW=(python3 "$HOME/code/standup/tools/quiet/quiet_wait.py" --max-wait 1800 --)
PY=(uv run --no-project --with litert-lm==0.18.0 python -I)

case "${1:-}" in
  identity)
    mkdir -p "$CAND/identity"
    if [ ! -e "$CAND/identity/in.identity.report.json" ]; then
      "${QW[@]}" "${PY[@]}" "$T/repack_metadata.py" "$IN" "$CAND/identity/in.identity.litertlm" \
        --identity --report "$CAND/identity/in.identity.report.json"
      echo "### in identity exit $?"
    fi
    "${QW[@]}" "${PY[@]}" "$T/repack_metadata.py" "$CUR" "$CAND/identity/cur.identity.litertlm" \
      --identity --report "$CAND/identity/cur.identity.report.json"
    echo "### cur identity exit $?"
    ;;
  describe)
    mkdir -p "$CAND/describe"
    "${QW[@]}" bash "$T/describe.sh" "$IN" "$CAND/describe/in_0180.txt" > /dev/null; echo "### describe in exit $?"
    "${QW[@]}" bash "$T/describe.sh" "$CUR" "$CAND/describe/cur_0180.txt" > /dev/null; echo "### describe cur exit $?"
    ;;
  repack)
    [ -n "${2:-}" ] || { echo "usage: $0 repack FIELD[,FIELD...]" >&2; exit 2; }
    [ -f "$NEW" ] || { echo "missing $NEW" >&2; exit 2; }
    mkdir -p "$CAND/out"
    "${QW[@]}" "${PY[@]}" "$T/repack_metadata.py" "$IN" "$OUT" --pbtext "$NEW" \
      --report "$CAND/out/r0805meta018.report.json" --expect-changed "$2"
    echo "### repack exit $?"
    ;;
  describe-out)
    "${QW[@]}" bash "$T/describe.sh" "$OUT" "$CAND/describe/out_0180.txt" > /dev/null; echo "### describe out exit $?"
    ;;
  repack-diag)
    # the supervisor's 2x2 (13:5x): diagnostic file (c) = CUR's graph + IN's LlmMetadata (the 2026-08-05 template),
    # for one iPhone GPU engine-build launch only; never on the Hub or the page
    mkdir -p "$CAND/diag"
    "${QW[@]}" "${PY[@]}" "$T/repack_metadata.py" "$CUR" "$CAND/diag/Qwen3-0.6B_dynamic_wi4b32_afp32.r0921meta0805.litertlm" \
      --pbtext "$CAND/identity/in.identity.report.evidence/original.LlmMetadataProto.pbtext" \
      --report "$CAND/diag/r0921meta0805.report.json" --expect-changed jinja_prompt_template
    echo "### repack-diag exit $?"
    ;;
  *) echo "usage: $0 identity|describe|repack FIELDS|describe-out|repack-diag" >&2; exit 2 ;;
esac
