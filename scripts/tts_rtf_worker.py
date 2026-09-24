#!/usr/bin/env python3
"""One TTS synthesis in a fresh process (the worker behind scripts/tts_rtf_mac.py).

Runs the public Qwen3-TTS LiteRT reference pipeline — `qwen3_tts_pipeline.py`
from john-rocky/litert-samples `compiled_model_api/text_to_speech_lm/python`
at a pinned commit (TTS_PIPELINE_DIR/COMMIT) — inside the pinned venv, exactly
as the sample's `synthesize.py` would (same constructor, same `synthesize()`
defaults: sampling top-k 50, temperature 0.9, repetition penalty 1.05,
max 512 frames; only the seed is fixed so launches are comparable), and
writes a JSON with the timings the pipeline itself reports plus the wall
clock around load and synthesis. Nothing here touches the model code.

  tts_rtf_worker.py --pipeline-dir DIR --model-dir DIR --text "..." --seed 1 \
      --threads 8 --out-wav X.wav --out-json X.json
"""
import argparse
import importlib.util
import json
import os
import sys
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pipeline-dir", required=True)
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--text", required=True)
    ap.add_argument("--language", default="english")
    ap.add_argument("--talker-file", default="talker_int4.tflite")
    ap.add_argument("--speaker", default=None, help="x-vector .npy (default: <model-dir>/voices/demo_speaker.npy)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--greedy", action="store_true")
    ap.add_argument("--threads", type=int, default=8, help="the sample's --threads default (talker/codec); MTP stays at the pipeline's 1")
    ap.add_argument("--out-wav", required=True)
    ap.add_argument("--out-json", required=True)
    args = ap.parse_args()

    import numpy as np
    import soundfile
    import ai_edge_litert

    spec = importlib.util.spec_from_file_location(
        "qwen3_tts_pipeline", os.path.join(args.pipeline_dir, "qwen3_tts_pipeline.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    t_load0 = time.monotonic()
    pipeline = mod.Qwen3TtsPipeline(args.model_dir, talker_file=args.talker_file,
                                    num_threads=args.threads)
    load_s = time.monotonic() - t_load0
    speaker_path = args.speaker or os.path.join(args.model_dir, "voices", "demo_speaker.npy")
    speaker = np.load(speaker_path)

    t0 = time.monotonic()
    result = pipeline.synthesize(args.text, speaker, language=args.language,
                                 do_sample=not args.greedy, seed=args.seed)
    synth_s = time.monotonic() - t0
    soundfile.write(args.out_wav, result.waveform, result.sample_rate, subtype="PCM_16")  # 24 kHz PCM16: the repo keeps the audio (~0.5 MB per 10 s)
    audio_s = len(result.waveform) / result.sample_rate
    out = {
        "loadSeconds": round(load_s, 3),
        "synthesisSeconds": round(synth_s, 3),
        "audioSeconds": round(audio_s, 3),
        "numFrames": int(result.num_frames),
        "sampleRate": int(result.sample_rate),
        "prefillSeconds": round(result.prefill_seconds, 3),
        "talkerSeconds": round(result.talker_seconds, 3),
        "mtpSeconds": round(result.mtp_seconds, 3),
        "codecSeconds": round(result.codec_seconds, 3),
        "pipelineRTF": round(result.rtf, 4),
        "peakAbs": float(np.max(np.abs(result.waveform))) if len(result.waveform) else 0.0,
        "rmsDbfs": (20 * float(np.log10(np.sqrt(np.mean(result.waveform.astype(np.float64) ** 2)) + 1e-12))
                    if len(result.waveform) else None),
        "aiEdgeLitertVersion": getattr(ai_edge_litert, "__version__", "unknown"),
        "python": sys.version.split()[0],
        "speakerFile": os.path.relpath(speaker_path, args.model_dir),
        "talkerFile": args.talker_file,
        "seed": None if args.greedy else args.seed,
        "doSample": not args.greedy,
        "threads": args.threads,
    }
    json.dump(out, open(args.out_json, "w"), indent=1)
    print(json.dumps(out))


if __name__ == "__main__":
    main()
