"""Cross-wire NeMo parakeet-tdt-0.6b-v3 and the litert-community tflite export to locate the stage
that loses text on a 5 s window.
usage: nemo_cross.py <model.nemo> <tflite> <wav>...
For each wav: (1) NeMo end-to-end transcript; (2) NeMo features -> tflite encoder -> tflite decoder
(python driver); (3) NeMo features -> NeMo encoder vs tflite encoder: per-frame cosine; (4) tflite
encoder output -> NeMo decoder/joint greedy; (5) NeMo encoder output -> tflite decoder driver."""
import sys, subprocess, numpy as np, torch, soundfile as sf
torch.set_num_threads(4)
import nemo.collections.asr as nemo_asr
from ai_edge_litert.interpreter import Interpreter
nemo_path, tflite, wavs = sys.argv[1], sys.argv[2], sys.argv[3:]
m = nemo_asr.models.ASRModel.restore_from(nemo_path, map_location="cpu"); m.eval()
it = Interpreter(model_path=tflite, num_threads=4)
enc_r = it.get_signature_runner("encode")

def tflite_decode(enc_out):  # enc_out [1,1024,63] numpy -> token ids (same loop as the engine)
    dec = it.get_signature_runner("decode"); dec1 = it.get_signature_runner("decode_1")
    e = enc_out.astype(np.float32); T = e.shape[2]; BLANK = 8192
    st1 = np.zeros((2,1,640), np.float32); st2 = np.zeros((2,1,640), np.float32)
    tokens = np.zeros((1,4), np.int32); tokens[0,0] = BLANK; tok_idx = 0; t = 0; out = []; n_inf = 4; steps = 0; same = 0; last = -1
    while t < T and steps < 3000:
        steps += 1
        if t == last:
            same += 1
            if same >= 10: t += 1; continue
        else: same = 0; last = t
        if n_inf > 1:
            r = dec(args_0=e, args_1=tokens, args_2=st1, args_3=st2); logits = r["output_0"][0, t, tok_idx]
        else:
            r = dec1(args_0=e, args_1=tokens, args_2=st1, args_3=st2); logits = r["output_0"][0, t, 0]
        tok = int(np.argmax(logits[:8193])); dur = int(np.argmax(logits[8193:8198]))
        if tok != BLANK:
            out.append(tok)
            if n_inf > 1:
                tok_idx += 1
                if tok_idx >= 4: st1, st2 = r["output_1"], r["output_2"]; n_inf = 1; tokens = np.zeros((1,1), np.int32); tok_idx = 0
            else: st1, st2 = r["output_1"], r["output_2"]
            tokens[0, tok_idx] = tok
        t += 1 if (dur == 0 and tok == BLANK) else dur
    return out

def nemo_decode(enc, enc_len):
    with torch.no_grad():
        hyps = m.decoding.rnnt_decoder_predictions_tensor(encoder_output=enc, encoded_lengths=enc_len, return_hypotheses=True)
    h = hyps[0] if isinstance(hyps, (list, tuple)) else hyps
    if isinstance(h, (list, tuple)): h = h[0]
    return getattr(h, "text", str(h)), getattr(h, "y_sequence", None)

for wav in wavs:
    name = wav.split("/")[-1]
    x, sr = sf.read(wav, dtype="float32"); sig = torch.tensor(x)[None]; ln = torch.tensor([len(x)])
    text_e2e = m.transcribe([wav], batch_size=1, verbose=False)[0]; text_e2e = getattr(text_e2e, "text", text_e2e)
    with torch.no_grad():
        feats, flen = m.preprocessor(input_signal=sig, length=ln)          # [1,128,T]
        nemo_enc, nemo_len = m.encoder(audio_signal=feats, length=flen)      # [1,1024,T/8]
    f500 = np.zeros((1,128,500), np.float32); n = min(feats.shape[2], 500); f500[0, :, :n] = feats[0, :, :n].numpy()
    tf_enc = enc_r(args_0=f500)["output_0"]                                  # [1,1024,63]
    T = min(tf_enc.shape[2], nemo_enc.shape[2])
    a = tf_enc[0, :, :T]; b = nemo_enc[0, :, :T].numpy()
    cos = (a*b).sum(0) / (np.linalg.norm(a, axis=0) * np.linalg.norm(b, axis=0) + 1e-9)
    toks_tf_tf = tflite_decode(tf_enc)
    text_nemo_from_tf, ids = nemo_decode(torch.tensor(tf_enc[:, :, :T]), torch.tensor([T]))
    ne = np.zeros((1,1024,63), np.float32); ne[0, :, :T] = b
    toks_tf_from_nemo = tflite_decode(ne)
    print(f"=== {name}")
    print(f"  NeMo end-to-end: {text_e2e!r}")
    print(f"  NeMo feats -> tflite enc+dec: {len(toks_tf_tf)} tokens {toks_tf_tf[:12]}")
    print(f"  encoder cosine (tflite vs NeMo, per frame): mean {cos.mean():.3f} min {cos.min():.3f} first8 {np.round(cos[:8],2)}")
    print(f"  tflite enc -> NeMo decoder: {text_nemo_from_tf!r} ({len(ids) if ids is not None else '?'} tokens)")
    print(f"  NeMo enc -> tflite decoder: {len(toks_tf_from_nemo)} tokens {toks_tf_from_nemo[:12]}")
