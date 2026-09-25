import sys, torch
torch.set_num_threads(4)
import nemo.collections.asr as nemo_asr
m = nemo_asr.models.ASRModel.restore_from("/Users/majimadaisuke/.cache/nemo-models/parakeet-tdt-0.6b-v3.nemo", map_location="cpu"); m.eval()
out = m.transcribe(sys.argv[1:], batch_size=1, verbose=False)
for f, h in zip(sys.argv[1:], out):
    print("NEMO", f.split("/")[-1], "->", repr(getattr(h, "text", h))[:160], flush=True)
