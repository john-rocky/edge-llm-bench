"""Drive the parakeet 5s stateful tflite the way omni/asr/tdt_decoder.cc does.
usage: tdt_drive.py <model.tflite> <features.f32 [128*500, layout m*500+f]> [--cap N]
prints the token id sequence (and per-step trace with --trace)."""
import sys, numpy as np
from ai_edge_litert.interpreter import Interpreter
model, feat = sys.argv[1], sys.argv[2]
cap = int(sys.argv[sys.argv.index("--cap")+1]) if "--cap" in sys.argv else 0
trace = "--trace" in sys.argv
x = np.fromfile(feat, dtype=np.float32).reshape(1, 128, 500)
it = Interpreter(model_path=model, num_threads=4)
enc = it.get_signature_runner("encode"); dec = it.get_signature_runner("decode"); dec1 = it.get_signature_runner("decode_1")
e = enc(args_0=x)["output_0"]                       # [1,1024,63]
T = e.shape[2]; BLANK = 8192; NTOK = 8193; NDUR = 5
st1 = np.zeros((2,1,640), np.float32); st2 = np.zeros((2,1,640), np.float32)
tokens = np.zeros((1,4), np.int32); tokens[0,0] = BLANK
tok_idx = 0; t = 0; out = []; n_inf = 4; steps = 0; same = 0; last_t = -1
while t < T:
    steps += 1
    if cap and t == last_t:
        same += 1
        if same >= cap: t += 1; continue
    else: same = 0; last_t = t
    if n_inf > 1:
        r = dec(args_0=e, args_1=tokens, args_2=st1, args_3=st2)
        logits = r["output_0"][0, t, tok_idx]      # 8198
        out_st = (r["output_1"], r["output_2"])
    else:
        r = dec1(args_0=e, args_1=tokens, args_2=st1, args_3=st2)
        logits = r["output_0"][0, t, 0]
        out_st = (r["output_1"], r["output_2"])
    tok = int(np.argmax(logits[:NTOK])); dur = int(np.argmax(logits[NTOK:NTOK+NDUR]))
    if trace: print(f"t={t} tok={tok} dur={dur} n={n_inf} idx={tok_idx} blank={logits[BLANK]:.2f} max={logits[:NTOK].max():.2f}")
    if tok != BLANK:
        out.append((t, tok))
        if n_inf > 1:
            tok_idx += 1
            if tok_idx >= 4:
                # switch to stateful: states = outputs of the stateless decode
                st1, st2 = out_st
                n_inf = 1; tokens = np.zeros((1,1), np.int32); tok_idx = 0
        else:
            st1, st2 = out_st   # commit on emission
        tokens[0, tok_idx] = tok
    t += 1 if (dur == 0 and tok == BLANK) else dur
    if steps > 5000: print("STEP CAP"); break
print("tokens:", [k for _, k in out])
print("n_tokens", len(out), "steps", steps)
