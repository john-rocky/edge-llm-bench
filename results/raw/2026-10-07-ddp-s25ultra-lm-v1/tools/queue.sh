#!/bin/bash
# queue.sh: the remaining sessions, one at a time. A session without metrics.pb is retried once;
# stops after two failures in a row or when the retry budget (2) is spent and another failure comes.
S=/private/tmp/claude-501/-Users-USER-code-edge-llm-bench/5f1069b5-75f5-48a0-8cf8-e569a9902f1e/scratchpad
H=$HOME/.cache/huggingface/hub
TSV=$S/sessions/sessions.tsv
Q=$S/sessions/queue.log
# wait for the session already in flight (line 2 of the tsv)
until [ "$(wc -l < "$TSV" | tr -d ' ')" -ge 2 ]; do /bin/sleep 10; done
ok_last() { # did the last tsv line leave a metrics.pb
  local sid backend
  sid=$(tail -1 "$TSV" | cut -f5); backend=$(tail -1 "$TSV" | cut -f3)
  [ -s "$HOME/.cache/litert-cli/ddp/$sid/$backend-pa3q-35/metrics.pb" ]
}
fails=0; retries=0
if ok_last; then echo "in-flight session ok" >> "$Q"; else fails=1; echo "in-flight session left no metrics.pb (not retried by the queue)" >> "$Q"; fi
while IFS='|' read -r label backend path; do
  attempt=1
  while :; do
    "$S/tools/sess.sh" "$label" "$backend" "$path" "$attempt" > /dev/null 2>&1
    if ok_last; then fails=0; echo "$(TZ=Asia/Tokyo date +%H:%M:%S) OK $label $backend a$attempt $(tail -1 "$TSV" | cut -f5)" >> "$Q"; break; fi
    fails=$((fails+1)); echo "$(TZ=Asia/Tokyo date +%H:%M:%S) NO-RESULT $label $backend a$attempt $(tail -1 "$TSV" | cut -f5)" >> "$Q"
    if [ "$fails" -ge 2 ]; then echo "STOP: two failures in a row" >> "$Q"; exit 2; fi
    if [ "$attempt" -ge 2 ] || [ "$retries" -ge 2 ]; then echo "no retry left for $label $backend" >> "$Q"; break; fi
    retries=$((retries+1)); attempt=2
  done
done <<LIST
qwen3-0.6b|cpu|$H/models--litert-community--Qwen3-0.6B/snapshots/a3c5d805ae362dff7f580bc25f2dfb9a5a7eaa76/qwen3_0_6b_mixed_int4.litertlm
gemma-4-e2b|cpu|$H/models--litert-community--gemma-4-E2B-it-litert-lm/snapshots/b3ca0d2f076785a8f4b2219ddbd2bdb99954eae1/gemma-4-E2B-it.litertlm
gemma-4-e2b|gpu|$H/models--litert-community--gemma-4-E2B-it-litert-lm/snapshots/b3ca0d2f076785a8f4b2219ddbd2bdb99954eae1/gemma-4-E2B-it.litertlm
qwen3-4b|cpu|$H/models--litert-community--Qwen3-4B/snapshots/84cc5a35c9c65cd18fcd65bb1f3a7d77a4acfe6e/qwen3_4b_mixed_int4.litertlm
qwen3-4b|gpu|$H/models--litert-community--Qwen3-4B/snapshots/84cc5a35c9c65cd18fcd65bb1f3a7d77a4acfe6e/qwen3_4b_mixed_int4.litertlm
gemma-4-e4b|cpu|$H/models--litert-community--gemma-4-E4B-it-litert-lm/snapshots/2eee7ac325f20eb8c9ac1d0e972f7c84663062da/gemma-4-E4B-it.litertlm
gemma-4-e4b|gpu|$H/models--litert-community--gemma-4-E4B-it-litert-lm/snapshots/2eee7ac325f20eb8c9ac1d0e972f7c84663062da/gemma-4-E4B-it.litertlm
LIST
echo "QUEUE DONE" >> "$Q"
