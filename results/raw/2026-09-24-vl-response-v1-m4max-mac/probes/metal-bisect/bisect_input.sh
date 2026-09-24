#!/usr/bin/env bash
# binary search over op index for the first prefix whose CPU-vs-Metal cosine < 0.999 (table fed as input)
cd /Users/majimadaisuke/code/edge-llm-bench-vltts-wt
S=/private/tmp/claude-501/-Users-majimadaisuke-code-edge-llm-bench-vltts-wt/51ea6b73-0d4d-4165-92d3-2b65bb0104fb/scratchpad
E=.build/lfm-export/unpacked/fold_visfp32/Section5_TFLiteModel_tf_lite_vision_encoder.tflite
probe(){ timeout 600 .build/lt-venv/bin/python $S/probe_prefix_input.py $E evaldata/vl/cc0-cat-couch-1024/cat_couch_1024.jpg $1 2>/dev/null | grep RESULT-INPUT; }
good(){ local line; line=$(probe $1); echo "$line" >> $S/bisect_input.log; echo "$line" >&2; local c; c=$(echo "$line" | awk '{print $4}'); [ -n "$c" ] && awk -v c="$c" 'BEGIN{exit !(c>=0.999)}'; }
lo=1; hi=628
good $hi && { echo "last op good"; exit; }
good $lo || { echo "op1 bad"; exit; }
while [ $((hi-lo)) -gt 1 ]; do mid=$(((lo+hi)/2)); if good $mid; then lo=$mid; else hi=$mid; fi; done
echo "FIRST_BAD=$hi LAST_GOOD=$lo"
