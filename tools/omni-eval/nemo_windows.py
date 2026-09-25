"""How often does the ORIGINAL parakeet-tdt-0.6b-v3 (NeMo) return nothing for a standalone 5 s
window cut the way the engine cuts (5 s windows, 3 s hop)? Takes N test-clean utterances of
10-20 s, cuts every window, transcribes each alone, and counts empties / word coverage."""
import sys, json, numpy as np, soundfile as sf, torch, os, tempfile
torch.set_num_threads(4)
import nemo.collections.asr as nemo_asr
manifest, n_utts = sys.argv[1], int(sys.argv[2])
rows = [json.loads(l) for l in open(manifest)]
rows = [r for r in rows if 10.0 <= r["seconds_written"] < 20.0][:n_utts]
m = nemo_asr.models.ASRModel.restore_from("/Users/majimadaisuke/.cache/nemo-models/parakeet-tdt-0.6b-v3.nemo", map_location="cpu"); m.eval()
tmp = tempfile.mkdtemp(); files = []; meta = []
for r in rows:
    x, sr = sf.read(r["path"], dtype="float32")
    start = 0
    while start < len(x):
        seg = x[start:start + 5 * sr]
        if len(seg) < sr: break
        p = os.path.join(tmp, f"{r['id']}_{start//sr*1000:06d}.wav"); sf.write(p, seg, sr, subtype="PCM_16")
        files.append(p); meta.append((r["id"], start / sr, len(seg) / sr)); start += 3 * sr
out = m.transcribe(files, batch_size=8, verbose=False)
texts = [getattr(h, "text", h) for h in out]
empties = sum(1 for t in texts if not t.strip())
words = sum(len(t.split()) for t in texts)
print(f"utterances {len(rows)}, windows {len(files)}, empty windows {empties} ({100*empties/len(files):.1f}%), words emitted {words}")
first = [i for i, mt in enumerate(meta) if mt[1] == 0.0]
print(f"  first windows: {len(first)}, empty {sum(1 for i in first if not texts[i].strip())}")
later = [i for i, mt in enumerate(meta) if mt[1] > 0.0]
print(f"  later windows: {len(later)}, empty {sum(1 for i in later if not texts[i].strip())}")
with open(sys.argv[3], "w") as f:
    for (uid, st, dur), t in zip(meta, texts):
        f.write(json.dumps({"id": uid, "start": st, "dur": dur, "text": t}) + "\n")
