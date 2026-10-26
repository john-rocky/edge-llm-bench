#!/bin/bash
# Per log: cache loads tried / failed / loaded per call, the error location, the call's wall time, and the program cache size after the process.
O=$1
for f in "$O"/*-p[12].log; do
  awk -v name="$(basename "$f" .log)" '
    /^CALL_BEGIN/ {call=$3}
    /Initializing .* from serialized data/ {try[call]++}
    /Deserialization failed/ {fail[call]++}
    /Initialized InferenceContext from serialized data/ {ok[call]++}
    /inference_context\.(cc|mm):[0-9]+/ {loc=$0}
    /^CALL_END/ {for (i=1;i<=NF;i++) if ($i ~ /^wall_s=/) w[$3]=$i}
    /mldrift_program_cache\.bin/ {size=$5}
    END {for (c in w) printf "%-28s %-7s tried %2d failed %2d loaded %2d  %s\n", name, c, try[c], fail[c], ok[c], w[c]; printf "%-28s program cache after the process: %s bytes; error at %s\n", name, size, loc}' "$f"
done
