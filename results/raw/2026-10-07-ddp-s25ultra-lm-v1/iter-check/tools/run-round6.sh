#!/bin/bash
# run-round6.sh: four billed sessions in order gpu, cpu, gpu, cpu via sess-aligned.sh; stop after two failures.
S=/private/tmp/claude-501/-Users-USER-code-edge-llm-bench/d21f53ca-5923-4da1-b5fc-7e34ecbf7034/scratchpad/r5
fails=0
for b in gpu cpu gpu cpu; do
  echo "[$(TZ=Asia/Tokyo date '+%F %T')] START $b" >> "$S/round6.progress"
  bash "$S/tools/sess-aligned.sh" "$b" > "$S/round6.$b.$(date +%s).out" 2>&1
  line=$(tail -1 "$S/sessions/sessions-aligned.tsv")
  rc=$(echo "$line" | cut -f7); sid=$(echo "$line" | cut -f5)
  passed=$(grep -c "finished: PASSED" "$S/sessions/gemma-4-e2b-$b-iter1-max4096.out")
  echo "[$(TZ=Asia/Tokyo date '+%F %T')] END $b sid=$sid rc=$rc passed=$passed" >> "$S/round6.progress"
  [ "$rc" = 0 ] && [ "$passed" -ge 1 ] || fails=$((fails+1))
  [ $fails -ge 2 ] && { echo "[$(TZ=Asia/Tokyo date '+%F %T')] STOP two failures" >> "$S/round6.progress"; exit 2; }
done
echo "[$(TZ=Asia/Tokyo date '+%F %T')] DONE" >> "$S/round6.progress"
