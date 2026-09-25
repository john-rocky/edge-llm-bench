# 2026-09-25 — LiteRT-LM omni/asr on the iPhone 18 Pro: memory per session on Metal (one session per utterance)

Question (from the 2026-09-25 Omni ASR WER session on the Mac): the Metal path there grows
the process by ~26 MB per `AsrSession` for whisper-tiny and ~10 MB for parakeet when each
utterance gets its own session, while the CPU path stays flat and one reused session stays
flat — does the iPhone's Metal accelerator do the same? On a phone the answer decides how an
app must hold sessions, because the memory limit is a few GB away.

Instrument: `ios/AsrBench` (this repo; LiteRT-LM `main@66058c82`, `omni/asr` through the
`asr_runner` code path compiled as a static library, see
`../2026-09-25-asr-rtf-v1-iphone18pro-ios/PROVENANCE.md`) in its per-utterance mode
(`--manifest`): one `AsrEngine`, then for every utterance a new `FileAudioSource` +
`CreateSession` + the `ProcessNext`/`Flush` loop, the session destroyed before the next one
(the Omni eval runner's default pattern, `tools/omni-eval/omni_eval_runner.cc`). After each
session the app samples its own `phys_footprint` (what iOS's jetsam accounts) and
`resident_size` (`probes/*.sessions.ndjson`, one line per utterance with the text). Audio =
the first 300 lines of the Omni session's LibriSpeech test-clean manifest
(`probes/lstc300.manifest.tsv`, 14–35 s utterances, 5,576 s in total), engine defaults
(30 s window, overlap 0.4, `timestamp` merger, 4 threads), phone on USB.

## Result

| run | sessions | footprint after #1 → #10 → #100 → last | slope (MB/session, least squares) | end |
|---|---|---|---|---|
| whisper-tiny, Metal (`probes/sessions_whisper-tiny_gpu_lstc300.*`) | 107 of 300 | 363 → 600 → 3,177 → **3,365 MB** | **+28.6** | **killed** (`App terminated due to signal 9`) 169 s after the first session, with the footprint at 3.4 GB; every session up to the kill transcribed (0 empty texts) |
| whisper-tiny, CPU (`…_cpu_lstc300.*`) | 300 of 300 | 291 → 258 → 256 → **256 MB** | +0.01 | completed in 281 s (thermal `fair` → `serious` by the end — the phone was warm from the day's runs; the memory reading does not depend on it) |
| parakeet-tdt-0.6b-v3, Metal (`…parakeet-tdt-0.6b-v3_gpu_lstc300.*`) | 204 of 300 | 744 → 838 → 1,777 → **2,862 MB** | **+10.4** | **stalled**: session #205 (`7176-92135-0025`) started (its mel-filterbank line is the last engine output) and did not finish in 10 minutes with `resident_size` at 3.4 GB; killed by the driver (`SIGKILL`) at 18:54 JST, 347 s after the first session; every completed session transcribed (0 empty texts). `7176-92135-0025` is the very utterance on which the Mac Omni session's Metal run never returned (the cap-less TDT decode loop, `tools/omni-eval/tdt_decoder.max-symbols-per-step.patch`), so the stall is that decode loop reproducing on the phone, not a memory wall — the memory slope up to #204 stands on its own |

The Metal growth is linear from the first session for both models (whisper-tiny 363 MB after
#1, +28.6 MB each — the kill came at #107; parakeet 744 MB after #1, +10.4 MB each — the
run stopped at #205 on `7176-92135-0025`, the utterance whose TDT decode never returns on the
Mac's Metal path either — a separate defect, not the memory wall; extrapolated, the +10.4 MB
slope reaches 3.4 GB near session #260). The per-session slopes
match the Mac's (26 MB / 10 MB per session there).
`resident_size` stopped following the footprint around #90 (2,651 → 750 MB at #100) — the
system was already compressing / evicting pages, and the footprint (which counts the
compressed and the GPU-backed pages) kept climbing until jetsam. The CPU path processes
the same 300 utterances at a constant 256 MB. Text: the Metal sessions' transcripts differ
from the CPU's on about half of the utterances (54 of 107 identical), the same
Metal-vs-CPU text difference the stream cell shows (WER 0.351 vs 0.372); no empty texts.

## Reading

An app that creates one `AsrSession` per utterance on the iPhone's Metal path has about 100
utterances (whisper-tiny) or ~260 (parakeet, extrapolated) before the OS kills it; the same app on the CPU path, or (per the Mac probe) one
session reused across utterances, does not grow. Whether the leaked bytes are the decoder's
output buffers as `vmmap` shows on the Mac was not checked on the phone (no `vmmap`); the
per-session slope, the flat CPU control and the kill are the phone-side facts. Filing is the
Omni session's call (their Mac finding, their issue); this directory is the iPhone
reproduction.
