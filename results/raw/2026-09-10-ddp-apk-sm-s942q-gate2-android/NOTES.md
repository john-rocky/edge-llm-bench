# 2026-09-10 11:02–11:05 JST — Galaxy S26, the same APK pair with the size-class gate

Same device, power, screen and thermal state (0 before and after every run) as the first pass-through
two hours earlier (`2026-09-10-ddp-apk-sm-s942q-android/NOTES.md`); the model was already on the
device (verified sha256 sidecar, no download). Only the test APK changed: the gate now scores form on
every answer and applies the bar of the model's size class (sub-1B: form 8/8 and ≥3/8 correct). The
app APK — the engine — is byte-identical (`engineArtifact` 28aa6bc4…2134 in every record).

Gate: **PASS**, form 8/8, correct 5/8 — the same eight answers as two hours earlier. Speed, 3/3 runs:
decode 50.55 / 48.52 / 48.06 tok/s, prefill 340 / 303 / 279 tok/s, TTFT 79 / 87 / 92 ms, 44 tokens
each, resident median 698–700 MB. `am_instrument.txt` ends in `OK (1 test)`; exit 0.
