import json, sys, time, torch, whisper
torch.set_num_threads(2)
manifest, out, name = sys.argv[1], sys.argv[2], sys.argv[3]
m = whisper.load_model(name, device="cpu")
rows = [json.loads(l) for l in open(manifest)]
audio = proc = 0.0
with open(out, "w") as f:
    f.write(json.dumps({"type": "header", "model_name": f"openai-whisper-{name}-reference-cpu", "backend": "cpu", "num_threads": 2}) + "\n")
    for i, r in enumerate(rows):
        t0 = time.perf_counter()
        res = m.transcribe(r["path"], language="en", fp16=False, temperature=0.0, beam_size=None, best_of=None, condition_on_previous_text=False)
        dt = time.perf_counter() - t0
        audio += r["seconds_written"]; proc += dt
        f.write(json.dumps({"id": r["id"], "text": res["text"].strip(), "audio_seconds": r["seconds_written"], "processing_seconds": dt, "session_create_seconds": 0.0, "error": ""}, ensure_ascii=False) + "\n")
        if (i + 1) % 200 == 0:
            print(f"{i+1}/{len(rows)} rtfx {audio/proc:.1f}", file=sys.stderr, flush=True)
    f.write(json.dumps({"type": "footer", "utterances": len(rows), "total_audio_seconds": audio, "total_processing_seconds": proc, "peak_rss_bytes": 0}) + "\n")
