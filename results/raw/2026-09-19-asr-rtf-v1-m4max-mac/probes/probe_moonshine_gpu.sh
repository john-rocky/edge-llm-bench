#!/bin/bash
# Moonshine GPU garbage after chunk 1: separate state-carry-over from int8-on-Metal numerics.
cd /Users/majimadaisuke/code/edge-llm-bench
R=$PWD/.build/asr-runner-1dadd00c; M=$PWD/.build/asr-models; SP=$1
S=$PWD/.build/asr-audio/librispeech-dev-clean-1272-82s.wav
U2=$PWD/evaldata/asr/librispeech-dev-clean-1272-82s/libri_1272_128104_0003.wav   # 9.9 s = 2-3 chunks
REF="$(python3 -c "import json;print(json.load(open('evaldata/asr/librispeech-dev-clean-1272-82s/manifest.json'))['stream']['reference'])")"
REF2="HE HAS GRAVE DOUBTS WHETHER SIR FREDERICK LEIGHTON'S WORK IS REALLY GREEK AFTER ALL AND CAN DISCOVER IN IT BUT LITTLE OF ROCKY ITHACA"
probe(){ tag=$1; audio=$2; ref=$3; model=$4; backend=$5; shift 5
  ( cd $R && DYLD_LIBRARY_PATH=$R gtimeout 300 ./asr_runner --model_name moonshine-tiny --metadata_path $R/model_metadata.json --model_path $model --cache_dir $M --backend $backend --audio_path $audio "$@" > $SP/probe/$tag.out 2> $SP/probe/$tag.err )
  st=$(grep "Starting speech" $SP/probe/$tag.err | sed -E 's/^I0000 00:00:([0-9.]+).*/\1/'); fi=$(grep "Finished speech" $SP/probe/$tag.err | sed -E 's/^I0000 00:00:([0-9.]+).*/\1/')
  python3 - "$SP/probe/$tag.out" "$ref" "$tag" "$st" "$fi" <<'PY'
import sys; sys.path.insert(0, "scripts")
from asr_rtf_mac import normalize, wer_counts
hyp = normalize(open(sys.argv[1]).read()); ref = normalize(sys.argv[2])
s,d,i,n = wer_counts(ref, hyp) if hyp else (0, len(ref), 0, len(ref))
proc = float(sys.argv[5]) - float(sys.argv[4])
print(f"{sys.argv[3]}: proc={proc:.3f}s WER={(s+d+i)/n:.3f} S/D/I={s}/{d}/{i} hyp={len(hyp)}")
print("    " + open(sys.argv[1]).read().strip()[:260].replace("\n", " "))
PY
}
I8=$M/moonshine-tiny.tflite
F32=$(ls ~/.cache/huggingface/hub/models--litert-community--moonshine-tiny/snapshots/*/moonshine_tiny_5s_f32.tflite | head -1)
echo "== 9.9 s utterance (2-3 chunks) =="
probe ms_i8_cpu_u2   $U2 "$REF2" $I8 cpu
probe ms_i8_gpu_u2   $U2 "$REF2" $I8 gpu
probe ms_i8_gpu_u2_b $U2 "$REF2" $I8 gpu
echo "== full stream, overlap 0 =="
probe ms_i8_gpu_ov0  $S "$REF" $I8 gpu --overlap_ratio 0
probe ms_i8_cpu_ov0  $S "$REF" $I8 cpu --overlap_ratio 0
echo "== full stream, f32 file =="
[ -n "$F32" ] && probe ms_f32_cpu $S "$REF" $F32 cpu
[ -n "$F32" ] && probe ms_f32_gpu $S "$REF" $F32 gpu
[ -n "$F32" ] && probe ms_f32_gpu_b $S "$REF" $F32 gpu
echo "== full stream, i8 gpu, 1 thread (does the CPU-side thread count matter?) =="
probe ms_i8_gpu_t1 $S "$REF" $I8 gpu --num_threads 1
