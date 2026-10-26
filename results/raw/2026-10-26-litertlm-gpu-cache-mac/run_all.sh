#!/bin/bash
# Mac (M4 Max) GPU program-cache check, Qwen3.5-0.8B_int8.litertlm (sha256 25447e25…), three litert-lm-api builds.
# Per build: an empty cache dir, process 1 = one call (writes the cache), process 2 = two calls (reads it).
set -u
S="${1:?work dir holding venv-<build> (uv venv + pip install litert-lm-api==<build>)}"
M="${2:?path to Qwen3.5-0.8B_int8.litertlm (sha256 25447e2550082aed6145bbc755ec4da5d535f98f6a0c386865fdae2ccb88aed1)}"
OUT=$S/out-$(date +%m%d-%H%M)
mkdir -p "$OUT"
export TF_CPP_MIN_LOG_LEVEL=0 GLOG_minloglevel=0
for v in 0.18.0 0.18.1 0.19.0.dev20261022; do
  C=$S/cache-$v; rm -rf "$C"; mkdir -p "$C"
  for p in 1 2; do
    n=$p
    echo "### $v p$p calls=$n $(date '+%F %T')" | tee -a "$OUT/runlog.txt"
    /usr/bin/time -l "$S/venv-$v/bin/python" "$S/run_one.py" "$M" "$C" $n "$v-p$p" > "$OUT/$v-p$p.log" 2>&1
    echo "exit $?" >> "$OUT/$v-p$p.log"
    ls -laT "$C" >> "$OUT/$v-p$p.log"
  done
done
echo "DONE $(date '+%F %T') $OUT" | tee -a "$OUT/runlog.txt"
