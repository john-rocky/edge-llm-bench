#!/bin/bash
# sess-iter.sh <num-iterations>: one billed DDP gpu session on pa3q-35, Gemma 4 E2B, every flag at the CLI default except --num-iterations.
S=<work>
V=<work>/.venv-nightly
M=/Users/USER/.cache/huggingface/hub/models--litert-community--gemma-4-E2B-it-litert-lm/snapshots/b3ca0d2f076785a8f4b2219ddbd2bdb99954eae1/gemma-4-E2B-it.litertlm
n="$1"; label="gemma-4-e2b-gpu-iter$n"
# --warmup-runs only sets how many leading iterations the CLI leaves out of the medians it prints (ddp.py _fetch_session_outputs);
# the binary's arguments come from _build_lm_benchmark_args and do not carry it. At 1 iteration the default (1) is refused, so pass 0.
wr=""; [ "$n" = 1 ] && wr=" --warmup-runs 0"
out="$S/sessions/$label.out"
RL_TAIL=400 "$S/tools/rl-iter.sh" "billed DDP session: Gemma 4 E2B gpu, --num-iterations $n (prefill 1024, decode 256, max 1280 at the defaults${wr:+;$wr for the printed medians only})" \
  "source $V/bin/activate && LITERT_GCP_PROJECT=litert-edge-portal litert benchmark '$M' --ddp --device pa3q-35 --gpu --num-iterations $n$wr" > "$out" 2>&1
rc=$(grep -o '^exit=[0-9]*' "$out" | tail -1 | cut -d= -f2)
sid=$(grep -o "session-[0-9a-f]\{8\}" "$out" | head -1)
name=$(grep -o "litert-cli-benchmark-[0-9a-f]\{8\}" "$out" | head -1)
printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M:%S')" "$label" "gpu" "$n" "${sid:-none}" "${name:-none}" "${rc:-?}" >> "$S/sessions/sessions-iter.tsv"
grep -v '^\.*$' "$out" | grep -v " [IWDV] [A-Za-z_.]* *: " | tail -12
