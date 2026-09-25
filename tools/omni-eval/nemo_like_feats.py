"""NeMo-style FilterbankFeatures for parakeet (preemph 0.97, n_fft 512, win 400 Hann symmetric,
hop 160, center/reflect, power 2, slaney mel 128 bins 0-8000 Hz, log(x + 2^-24), per-feature
normalization with unbiased std + 1e-5), written in the engine's layout [128, 500] (m*500+f).
usage: nemo_like_feats.py <in.wav> <out.f32>"""
import sys, numpy as np, soundfile as sf, torch, librosa
wav, out = sys.argv[1], sys.argv[2]
x, sr = sf.read(wav, dtype="float32"); assert sr == 16000
x = torch.tensor(x)
x = torch.cat([x[:1], x[1:] - 0.97 * x[:-1]])
win = torch.hann_window(400, periodic=False)
st = torch.stft(x, n_fft=512, hop_length=160, win_length=400, window=win, center=True, pad_mode="reflect", return_complex=True)
mag = (st.abs() ** 2).numpy()                       # [257, T]
fb = librosa.filters.mel(sr=16000, n_fft=512, n_mels=128, fmin=0.0, fmax=8000.0, norm="slaney", htk=False)
logmel = np.log(fb @ mag + 2.0 ** -24)              # [128, T]
T = logmel.shape[1]
mean = logmel.mean(axis=1, keepdims=True); std = logmel.std(axis=1, ddof=1, keepdims=True)
feats = (logmel - mean) / (std + 1e-5)
outp = np.zeros((128, 500), np.float32); n = min(T, 500); outp[:, :n] = feats[:, :n]
outp.tofile(out)
print(f"{wav.split('/')[-1]}: T={T} -> 500, mean {feats.mean():.3f} std {feats.std():.3f} min {feats.min():.2f} max {feats.max():.2f}")
