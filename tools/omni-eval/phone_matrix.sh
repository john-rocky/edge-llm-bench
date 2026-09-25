#!/system/bin/sh
P=/data/local/tmp/edge-llm-bench/omni
O=$P/runs/2026-09-25-librispeech-s26
mkdir -p $O
cd $P
cool() {
  # wait (max 15 min) for the battery to drop to 36 C, like the 09-19 harness
  i=0
  while [ $i -lt 90 ]; do
    t=$(dumpsys battery | grep -m1 temperature | tr -dc '0-9')
    [ "$t" -le 360 ] && break
    sleep 10; i=$((i+1))
  done
  echo "cooldown waited $((i*10))s, batt=$t" >> $O/progress.log
}
for set in clean other; do
  for m in parakeet-tdt-0.6b-v3 whisper-tiny; do
    tag=$m-$set-cpu
    if grep -q '"type":"footer"' $O/$tag.jsonl 2>/dev/null; then echo "SKIP $tag" >> $O/progress.log; continue; fi
    cool
    echo "START $tag $(date +%H:%M:%S) batt=$(dumpsys battery | grep -m1 temperature | tr -dc '0-9') therm=$(dumpsys thermalservice 2>/dev/null | grep -m1 'Thermal Status' | tr -dc '0-9')" >> $O/progress.log
    ./bin/omni_eval_runner --model_name=$m --cache_dir=$P/models --backend=cpu --num_threads=4 --manifest=$P/sets/librispeech-test-$set/manifest-android.tsv --output=$O/$tag.jsonl 2> $O/$tag.stderr.log
    echo "END $tag rc=$? $(date +%H:%M:%S) batt=$(dumpsys battery | grep -m1 temperature | tr -dc '0-9') therm=$(dumpsys thermalservice 2>/dev/null | grep -m1 'Thermal Status' | tr -dc '0-9') $(tail -n 1 $O/$tag.jsonl | cut -c1-200)" >> $O/progress.log
  done
done
echo "PHONE MATRIX DONE $(date +%H:%M:%S)" >> $O/progress.log
