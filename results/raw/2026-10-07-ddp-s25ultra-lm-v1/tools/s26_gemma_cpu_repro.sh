#!/bin/bash
# s26_gemma_cpu_repro.sh: on the Galaxy S26, under the shared hold, run the DDP sessions' benchmark binary
# (gs://litert/binaries/latest, sha256 adac974b...) on the Gemma 4 cpu bundles: first the DDP flags
# (prefill 1024, max_num_tokens 1280) to see the same failure, then other token settings to find one that runs.
# Works/does-not-work only; no rate from this script is a measurement (one iteration, phone state not controlled).
set -u
S=/private/tmp/claude-501/-Users-USER-code-edge-llm-bench/5f1069b5-75f5-48a0-8cf8-e569a9902f1e/scratchpad
CA=/Users/USER/code/litertlm-convert/community_accel_work
L="$CA/s2_npu_sweep/.device_hold"
NAME=edge-llm-bench/ddp-s25ultra-gemma-cpu-repro
SUP=ddp-s25ultra-lm
SERIAL=RFGL80R6A6H
DEV=/data/local/tmp/ddp-lm-latest-repro
OUT="$S/s26-repro"; mkdir -p "$OUT"
A() { adb -s "$SERIAL" "$@"; }
say() { echo "[$(TZ=Asia/Tokyo date '+%F %T')] $*" | tee -a "$OUT/steps.log"; }

rel="$S/.s26_repro_release"; rm -f "$rel"
( start=$(date +%s); while [ ! -f "$rel" ] && [ $(( $(date +%s) - start )) -lt 14400 ]; do sleep 5; done ) &
kp=$!
python3 "$CA/queue_cli.py" enqueue "$L" "$NAME" "$SUP" 25 >/dev/null
say "QUEUED keeper $kp: $(python3 "$CA/queue_cli.py" list "$L" | tr '\n' ' ' | cut -c1-300)"
if ! python3 "$CA/queue_cli.py" wait "$L" "$NAME" "$kp" --timeout 10800 --poll 5 >> "$OUT/steps.log" 2>&1; then
  python3 "$CA/queue_cli.py" dequeue "$L" "$NAME" >/dev/null; touch "$rel"; say "HOLD_GAVE_UP (3 h in the queue)"; exit 3
fi
say "HOLD_TAKEN: $(head -c 300 "$L")"
release() { A shell "rm -rf $DEV" >/dev/null 2>&1; python3 "$CA/hold_cli.py" release "$L" "$kp" >/dev/null; touch "$rel"; say "HOLD_RELEASED: hold now $( [ -f "$L" ] && head -c 200 "$L" || echo free); device dir removed"; }
trap release EXIT

# preflight under the hold
[ "$(A get-state 2>/dev/null)" = "device" ] || { say "PREFLIGHT no adb device"; exit 4; }
host=$(pgrep -fl "run_campaign.py|run_cell.py" | grep -v grep | head -2)
[ -z "$host" ] || { say "PREFLIGHT host driver running: $host"; exit 4; }
eng=$(A shell "ps -A -o NAME | grep -E 'litert_lm|llama' | head -3" | tr -d '\r')
[ -z "$eng" ] || { say "PREFLIGHT foreign engine on the phone: $eng"; exit 4; }
say "PREFLIGHT ok: battery $(A shell dumpsys battery | grep -E 'temperature' | tr -d '\r ' ), free $(A shell df -h /data/local/tmp | tail -1 | awk '{print $4}' | tr -d '\r')"

A shell "mkdir -p $DEV" || exit 5
for f in litert_lm_advanced_main libGemmaModelConstraintProvider.so libLiteRtDispatch_GoogleTensor.so libLiteRtDispatch_MediaTek.so libLiteRtDispatch_Qualcomm.so libLiteRtOpenClAccelerator.so libLiteRtTopKOpenClSampler.so; do
  A push "$S/lm-latest/$f" "$DEV/$f" >/dev/null 2>&1 || { say "push failed: $f"; exit 5; }
done
A shell "chmod 755 $DEV/litert_lm_advanced_main; cd $DEV && sha256sum litert_lm_advanced_main" | tr -d '\r' | tee -a "$OUT/steps.log"
A shell "cd $DEV && LD_LIBRARY_PATH=$DEV ./litert_lm_advanced_main --helpfull 2>&1" > "$OUT/helpfull.txt" 2>&1
say "helpfull lines: $(wc -l < "$OUT/helpfull.txt" | tr -d ' ')"

stage() {  # stage <file> <sha256> <local path>: copy the bundle into $DEV from a copy already on the phone, else push it
  local file="$1" want="$2" localp="$3" src got
  src=$(A shell "find /data/local/tmp -maxdepth 4 -name '$file' -not -path '$DEV/*' 2>/dev/null | head -1" | tr -d '\r')
  if [ -n "$src" ]; then A shell "cp '$src' $DEV/$file"; say "staged $file from $src (copy on the phone)"; else
    A push "$localp" "$DEV/$file" >/dev/null 2>&1; say "staged $file by adb push"; fi
  got=$(A shell "sha256sum $DEV/$file" | awk '{print $1}' | tr -d '\r')
  if [ "$got" != "$want" ]; then
    say "sha256 of the phone's copy differs ($got); pushing the Hub file"; A push "$localp" "$DEV/$file" >/dev/null 2>&1
    got=$(A shell "sha256sum $DEV/$file" | awk '{print $1}' | tr -d '\r')
  fi
  [ "$got" = "$want" ] && say "sha256 ok $file $got" || { say "sha256 MISMATCH $file $got"; return 1; }
}

run() {  # run <tag> <file> <flags...>: one process, caches removed first, one iteration
  local tag="$1" file="$2"; shift 2
  local t0; t0=$(A shell "date '+%m-%d %H:%M:%S.000'" | tr -d '\r')
  A shell "cd $DEV && rm -f ./*.xnnpack_cache* ./*_mldrift_*cache*.bin && touch $file && LD_LIBRARY_PATH=$DEV ./litert_lm_advanced_main --backend=cpu --model_path=$DEV/$file --benchmark=true --benchmark_decode_tokens=256 --report_peak_memory_footprint=true --num_iterations=1 $* ; echo rc=\$?" > "$OUT/$tag.stdout.txt" 2>&1
  A logcat -d -T "$t0" > "$OUT/$tag.logcat.txt" 2>/dev/null
  local src="$OUT/$tag.stdout.txt"; grep -q "BenchmarkInfo" "$src" || src="$OUT/$tag.logcat.txt"
  say "RUN $tag [$*] $(grep -o 'rc=[0-9]*' "$OUT/$tag.stdout.txt" | tail -1)" \
      "prefill=$(grep -o 'Prefill Speed: [0-9.]*' "$src" | head -1 | awk '{print $3}')" \
      "decode=$(grep -o 'Decode Speed: [0-9.]*' "$src" | head -1 | awk '{print $3}')" \
      "no_prefill_turns=$(grep -c 'No prefill turns recorded' "$src")" \
      "update_slice_fail=$(grep -c 'DYNAMIC_UPDATE_SLICE) failed to prepare' "$src")" \
      "temp=$(A shell dumpsys battery | grep temperature | tr -d '\r ' )"
  sleep 20
}

H=$HOME/.cache/huggingface/hub
E2B=gemma-4-E2B-it.litertlm; E4B=gemma-4-E4B-it.litertlm
if stage "$E2B" 181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c "$H/models--litert-community--gemma-4-E2B-it-litert-lm/snapshots/b3ca0d2f076785a8f4b2219ddbd2bdb99954eae1/$E2B"; then
  run e2b-p1024-n1280 "$E2B" --benchmark_prefill_tokens=1024 --max_num_tokens=1280
  run e2b-p1024-n2048 "$E2B" --benchmark_prefill_tokens=1024 --max_num_tokens=2048
  run e2b-p1024-n1281 "$E2B" --benchmark_prefill_tokens=1024 --max_num_tokens=1281
  run e2b-p1024-n1536 "$E2B" --benchmark_prefill_tokens=1024 --max_num_tokens=1536
  run e2b-p1024-n4096 "$E2B" --benchmark_prefill_tokens=1024 --max_num_tokens=4096
  run e2b-p512-n1280  "$E2B" --benchmark_prefill_tokens=512  --max_num_tokens=1280
  run e2b-p128-n1280  "$E2B" --benchmark_prefill_tokens=128  --max_num_tokens=1280
  A shell "rm -f $DEV/$E2B $DEV/*.xnnpack_cache*"
fi
if stage "$E4B" 0b2a8980ce155fd97673d8e820b4d29d9c7d99b8fa6806f425d969b145bd52e0 "$H/models--litert-community--gemma-4-E4B-it-litert-lm/snapshots/2eee7ac325f20eb8c9ac1d0e972f7c84663062da/$E4B"; then
  run e4b-p1024-n1280 "$E4B" --benchmark_prefill_tokens=1024 --max_num_tokens=1280
  run e4b-p1024-n2048 "$E4B" --benchmark_prefill_tokens=1024 --max_num_tokens=2048
  A shell "rm -f $DEV/$E4B $DEV/*.xnnpack_cache*"
fi
say "DONE"
