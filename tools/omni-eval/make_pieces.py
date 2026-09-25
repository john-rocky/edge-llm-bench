#!/usr/bin/env python3
"""Cut the 5-second windows of LibriSpeech test-clean utterance 4507-16021-0047
that reproduce the empty-window behaviour of LiteRT-LM's ASR path.

The utterance is 34.955 s of clean read speech (CC BY 4.0, LibriSpeech). Run on
each piece alone, `omni/asr:asr_runner` (and the OmniEngine path) returns no
text for c1, c2, c4 and c5 with parakeet-tdt-0.6b-v3 (i8 and f32 files), and
no text for c1 and c2 with whisper-tiny; openai-whisper `tiny` transcribes all
of them. Shifting the window start by 0.1-0.5 s changes the result.

Usage: make_pieces.py <utterance.wav 16 kHz mono> <out_dir>
"""
import pathlib
import sys

import numpy as np
import soundfile as sf


def main() -> int:
    src, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    x, sr = sf.read(src, dtype="float32")
    assert sr == 16000, sr
    for i in range(7):
        sf.write(out / f"4507-c{i}.wav", x[i * 5 * sr:(i + 1) * 5 * sr], sr, subtype="PCM_16")
    for s in [4.5, 4.9, 5.1, 5.25, 5.5, 6.0]:
        sf.write(out / f"4507-shift-{s}.wav", x[int(s * sr):int((s + 5) * sr)], sr, subtype="PCM_16")
    seg = x[5 * sr:10 * sr].copy()
    n = int(0.02 * sr)
    ramp = np.linspace(0, 1, n, dtype=np.float32)
    seg[:n] *= ramp
    seg[-n:] *= ramp[::-1]
    sf.write(out / "4507-c1-fade20ms.wav", seg, sr, subtype="PCM_16")
    print("wrote", len(list(out.glob("*.wav"))), "pieces to", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
