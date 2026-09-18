# 2026-09-19 ASR real-time factor, v1 — first cell, Mac leg

Task family definition: `docs/asr-rtf-v1.md`. Cells: `matrices/asr-rtf-v1.cells`
(`./bench matrix matrices/asr-rtf-v1.cells --platform mac --campaign 2026-09-19-asr-rtf-v1-m4max`,
session start 06:27:30 JST). Numbers and findings: `NOTES.md` here. One JSONL per
cell, one record per process launch; the runner's stderr for every launch is under
`logs/` (stored-report-rule).

## Host

Mac Studio M4 Max 128 GB (`Mac16,9`), macOS 27.0 (26A428), 16 cores. Session anchor
(`mlx-swift` Qwen3-0.6B-4bit short-chat, runs=3): warm median 539.9 tok/s, cold 565.4,
thermal nominal — inside the band of the last five Mac sessions (527–550 warm;
`2026-09-18-dashboard-longctx-v1-m4max-mac` 527.2, `2026-09-14-…-anchor` 535.2,
`2026-09-10-…-retake4b` 549.7). Foreign processes above 20 % CPU are sampled before and
after every launch into the record (`provenance.hostBefore/After.others`): a Chrome
renderer (23–86 %) during several launches, `syspolicyd` / `spotlightknowledged` /
`mediaanalysisd` (macOS indexing the freshly written WAVs) on a few — listed per run in
NOTES.md. `pmset -g therm` reported no CPU speed limit throughout. Another Claude
session (the Qwen3-TTS usage-recipe lane) confirmed by message at 06:16 that its Mac
timing runs had ended at 06:12; it ran non-timing work (an ASR round-trip check, a
phone measurement over adb) during this session.

## Instrument

LiteRT-LM `main` at `1dadd00c2a2363f275e713cfebab5fa9b96c6226` (Fengwu Yao, 2026-09-17
15:50 -0700, "Update dependencies of litert_lm") — the commit whose prebuilt Metal
accelerator the 2026-09-18 Qwen3 session identified; worktree
`~/code/litert-lm-1dadd00c-wt` (detached, LFS skipped except the macOS Metal dylib).
`omni/asr` is unchanged between `1dadd00c` and `origin/main` on 2026-09-19 (`be31cc65`);
the only later commit under `omni/` is `506da4b6` (`AsyncStageScheduler::Stop` waits
for its pool — the runner uses the synchronous `ProcessNextChunk` loop, not the async
scheduler). No released tag carries the four-model engine: v0.17.0 / v0.17.1 have
`6343fd39` (ASR on GPU) but not `c9b1ba54` / `007e7c76` / `12fae71e`. PR #3658 (TTS/ASR
capability protos) and PR #3672 (Kotlin ASR API) were both OPEN on 2026-09-19.

Build: `bazel build //omni/asr:asr_runner` in that worktree, bazel 7.6.1 (bazelisk,
`.bazelversion`), Xcode 27.0 (27A266a), `.bazelrc` defaults (`-c opt`, macOS config),
06:16:24–06:19:38 JST, 5,112 actions, exit 0 (`logs/bazel_asr_runner.log`). Statically
linked against LiteRT (`otool -L`: system frameworks only, Metal among them); the GPU
accelerator is loaded dynamically from the run dir.

Run dir `.build/asr-runner-1dadd00c/` (repo-local, git-ignored; `SHA256SUMS` copied here):

| file | sha256 | identity |
|---|---|---|
| `asr_runner` | `19625a2fc6f41c34eb770fb0d332a75cd2cc36d3a0bf10188c0609a66c3f0e3a` | 17,368,136 B, Mach-O arm64, this build |
| `libLiteRtMetalAccelerator.dylib` | `49df4fd58976d981bdb338a7fe8b6ad26424cacbc632d135b6f79b4eb6ee0ed9` | LiteRT-LM `main` LFS object at `1dadd00c` (`prebuilt/macos_arm64/`), 16,535,552 B — the same dylib the 2026-09-18 session measured |
| `libLiteRtTopKMetalSampler.dylib` | `a60e9a6e09a13fdbc4aa35df6fce1a7c2c75e9763b9c1072349f32f087b3f8a0` | v0.17.0 release; present for the Qwen3-ASR LM decoder's GPU sampler, not needed by the three `.tflite` models |
| `model_metadata.json` | `960747e5fe316e25fc1cfca378377c2131c763d92996b590ae5e524b5e5e6be1` | `omni/asr/model_metadata.json` at `1dadd00c` (copy: `model_metadata.json` here) |

Every launch: `cd <run dir> && DYLD_LIBRARY_PATH=<run dir> ./asr_runner --model_name <name>
--metadata_path model_metadata.json --model_path <file> --cache_dir .build/asr-models
--backend cpu|gpu --num_threads 4 --overlap_ratio 0.4 --text_merger_type timestamp
--audio_path .build/asr-audio/librispeech-dev-clean-1272-82s.wav` (the exact line is in
each record's `provenance.command`). The GPU rows' logs read `RegisterAccelerator …
name=GPU Metal`, `delegate_metal.mm:89 Created a Metal device`, `Metal Residency Set
successfully initialized`; the CPU rows `Created TensorFlow Lite XNNPACK delegate for CPU`.

## Models (litert-community, the file `model_metadata.json` names for each model)

| model_name | HF revision | file | bytes | sha256 |
|---|---|---|---|---|
| `moonshine-tiny` | `4d0fd016df005c889aaa738b4765ede92736424f` (lastModified 2026-09-05) | `moonshine_tiny_5s_i8.tflite` | 51,936,896 | `97abdeea122d579229091659c24c59d988c6419d453a200f6471241a53b9a9b9` |
| `whisper-tiny` | `d92f0ee1d4316ab0099add38d67ac5f2cc31c8fd` (2026-05-03) | `whisper_tiny_30s_i8.tflite` | 41,116,288 | `6748ac565a228c4a00b18d11ea1e2fd7cead3db6fba94e3f0bf35756b13ba4a9` |
| `parakeet-tdt-0.6b-v3` | `50dae0cb8c7b39dda477966eff7150cd7fe206ae` (2026-08-26) | `parakeet_tdt_0.6b_v3_5s_i8_stateful.tflite` | 614,261,072 | `334745b8bc7fd372b1c213516f0b6338bb827b1a2abb3e77ad35fe6fea5cd16b` |
| `qwen3-asr-0.6b` | `80384dfbad4a6cd0c698892395c4664fd122c081` (2026-09-03) | `qwen3_asr_0.6b_5s_i8.litertlm` | 959,627,232 | `d4444d51f0c08142f57e16097673150f3ea02900a00b29a58a41f6e7578db251` |

Tokenizers (the runner reads `<cache_dir>/<model_name>_tokenizer.json`; pre-staged from
the base repos so no launch had to `curl`): `moonshine-ai/moonshine-tiny`
`390624ed…` `6579793438bc4fbafffacf699169ff53e3769c5a0a0f5e71cdee8853e8130deb`;
`openai/whisper-tiny` `169d4a43…` `27fc476bfe7f17299480be2273fc0608e4d5a99aba2ab5dec5374b4482d1a566`;
`nvidia/parakeet-tdt-0.6b-v3` `541d1f99…` `bd321b096832a3f270bd3b2a88823957920f1a5c5ada71114a26ea729d0cbe91`.
Qwen3-ASR's tokenizer is inside the `.litertlm`.

Recipes (quant-label-rule): the moonshine card documents the `i8` file as "f32 encoder +
dynamic-range int8 decoder"; the whisper / parakeet / Qwen3-ASR cards are front-matter only
(104 / 31 / 104 bytes), so those rows say "i8 per the file name" and nothing more. The f32
files (and the per-SoC `_MediaTek_*` / `_Qualcomm_*` variants) are the NPU AOT source and
were not run.

## Audio

`evaldata/asr/librispeech-dev-clean-1272-82s/manifest.json` (ten LibriSpeech dev-clean
utterances of speaker 1272, 82.335 s, sha256 per file, reference text per file). Stream
built by the driver in manifest order, no inserted silence:
`.build/asr-audio/librispeech-dev-clean-1272-82s.wav`, 1,317,359 frames, sha256
`052852e6cfea…` (full value in every record's `provenance.audioStreamSha256`).
