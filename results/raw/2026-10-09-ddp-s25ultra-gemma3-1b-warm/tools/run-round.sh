#!/bin/bash
# run-round.sh: three billed cpu sessions one after another via sess.sh; stop after two failures.
C="$HOME/code/edge-llm-bench/results/raw/2026-10-09-ddp-s25ultra-gemma3-1b-warm"
S="${SCRATCH:?set SCRATCH}"
P="$S/round.progress"
fails=0
for b in cpu cpu cpu; do
  echo "[$(TZ=Asia/Tokyo date '+%F %T')] START $b" >> "$P"
  out=$(SCRATCH="$S" VENV="$VENV" bash "$C/tools/sess.sh" "$b")
  line=$(tail -1 "$C/sessions.tsv")
  rc=$(echo "$line" | cut -f7); sid=$(echo "$line" | cut -f5); passed=$(echo "$line" | cut -f8 | cut -d= -f2)
  echo "[$(TZ=Asia/Tokyo date '+%F %T')] END $b sid=$sid rc=$rc passed=$passed out=$out" >> "$P"
  [ "$rc" = 0 ] && [ "$passed" -ge 1 ] || fails=$((fails+1))
  [ $fails -ge 2 ] && { echo "[$(TZ=Asia/Tokyo date '+%F %T')] STOP two failures" >> "$P"; exit 2; }
done
echo "[$(TZ=Asia/Tokyo date '+%F %T')] DONE fails=$fails" >> "$P"
