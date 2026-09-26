# 2026-09-24 vision-language response time, v1 — first cell, Mac leg

Task family definition: `docs/vl-response-v1.md`. Cells: `matrices/vl-response-v1.cells`
(`./bench matrix matrices/vl-response-v1.cells --platform mac --campaign 2026-09-24-vl-response-v1-m4max`,
session start 13:21:34 JST; the two Gemma 4 cells re-taken afterwards, see NOTES.md).
Numbers and findings: `NOTES.md` here. One JSONL per cell, one record per process
launch; the engine's stderr for every launch and the reply text are under `logs/`
(stored-report-rule; the SmolVLM2 GPU cell's launch 2 and 3 stderr logs — 350 KB each of the same Dawn (WebGPU) validation-error listing as launch 1 — are gzipped). `SKIPPED.txt` lists the rows whose bundle was not staged;
`FAILURES.txt` the cells whose launches failed (they stay in the table as FAIL rows).

## Host

Mac Studio M4 Max 128 GB (`Mac16,9`), macOS 27.0 (26A428), 16 cores. Session anchor
(`mlx-swift` Qwen3-0.6B-4bit short-chat, runs=3): warm 559.6 / 559.0 tok/s, cold 560.2,
thermal nominal — 2 % above the last five Mac sessions' band (527–550 warm; 539.9 on
2026-09-19), i.e. the machine was not throttled. The Mac was **shared** this afternoon:
another session ran Xcode builds (`swift-frontend` / `clang` / `xcodebuild` at 100 % on
3–4 cores) in bursts, a third drove Chrome (renderer bursts of 20–90 %), and the system's
`Storage` extension ran 20–90 % bursts throughout. Every launch samples foreign processes
≥ 20 % CPU before and after into `provenance.hostBefore/After.others`; NOTES.md lists them
per cell and says which cells were re-taken because of them. `pmset -g therm` reported no
CPU speed limit at any launch. A background download of this session's own (24 threads,
`Python:63%` at the first SmolVLM2 CPU launch) was paused for the rest of the pass.

## Instrument

Erratum (2026-09-26): the GPU arm ran on LiteRT's WebGPU accelerator, not on the Metal one.
Every launch of this leg, CPU and GPU arm alike, logs `Attempting to load GPU
accelerator(libLiteRtGpuAccelerator.dylib).` → `Attempting to load GPU
accelerator(libLiteRtWebGpuAccelerator.dylib).` → `RegisterAccelerator: ptr=…, name=GPU WebGPU` →
`Dynamically loaded GPU accelerator(libLiteRtWebGpuAccelerator.dylib) registered.` →
`RegisterAccelerator: ptr=…, name=CpuAccelerator`
(`logs/litert-lm_litert-community_gemma-4-E2B-it-litert-lm_vl-describe-catcouch-gen64_gpu_run2.stderr.log`
lines 61–66), and each GPU launch then logs `Selected adapter: Apple M4 Max, arch=metal-3,
vendor=apple, backend=Metal, adapterType=Integrated GPU` and `Initializing WebGPU-based API from
serialized data`: WebGPU through Dawn, with Metal as Dawn's backend. `GPU Metal` occurs in none of
the 24 launch logs and none of the CLI probe logs under `probes/`. LiteRT's `gpu_registry` keeps the
first library that registers, and on macOS it tries `libLiteRtWebGpuAccelerator.dylib` before
`libLiteRtMetalAccelerator.dylib` (`docs/vl-response-v1.md`, "The instrument"). The paragraph
below is wrong where it says the log registers `GPU Metal` from `libLiteRtMetalAccelerator.dylib`.
The GPU records' `engineArtifact` names `libLiteRtMetalAccelerator.dylib sha256:49df4fd5…`: that is
the hash of a file staged in the runner dir, not of the accelerator that computed. The one that
computed is `libLiteRtWebGpuAccelerator.dylib`, sha256
`e3a53a8f120f41a73b5069002c042efa7e2d6b700e5eb40ceca1a90557ef083b`, on `libwebgpu_dawn.dylib`
`309791ccd868de849d1eb331735f58d6769fcf901a7b4927481d15242f1a661e` (`SHA256SUMS` here). The
records stay as written; from 2026-09-26 the driver stamps the registered accelerator in
`conditions.gpuAccelerator`, and a GPU arm's `engineArtifact` lists the staged GPU dylibs as
`staged: …`. The Python-API probes behind NOTES finding 1's cosines (`probes/metal-bisect/`,
`ai_edge_litert` CompiledModel in `.build/lt-venv`, ai-edge-litert-nightly 2.3.0.dev20260923) are
on Metal: a registration check in the same venv on 2026-09-26 registers `GPU Metal` from the
wheel's own `libLiteRtMetalAccelerator.dylib` and logs `Initializing Metal-based API from graph`
(`probes/python-api-gpu-registration-2026-09-26.stderr.log`). That dylib (11,399,984 B, sha256
`096574cb…`) is a different build from the runner dir's `libLiteRtMetalAccelerator.dylib`
(16,535,552 B, `49df4fd5…`). The pip CLI 0.17.1 probes' logs name no accelerator.

LiteRT-LM `main` at `1dadd00c2a2363f275e713cfebab5fa9b96c6226` (Fengwu Yao, 2026-09-17
15:50 -0700, "Update dependencies of litert_lm") — the same worktree as the asr-rtf-v1
runner (`~/code/litert-lm-1dadd00c-wt`, detached). Build:
`bazelisk build //runtime/engine:litert_lm_advanced_main`, bazel 7.6.1 (`.bazelversion`
via bazelisk 9.2.0), Xcode 27.0 (27A266a), `.bazelrc` defaults (`-c opt`, macOS config),
12:41–12:44 JST, 5,384 actions; the first link failed on the LFS pointer files under
`prebuilt/macos_arm64/` (`ld: unknown file type … libGemmaModelConstraintProvider.dylib`),
fixed by `git lfs pull origin --include="prebuilt/macos_arm64/*"` and a relink (3 actions).
The binary links `@rpath/libGemmaModelConstraintProvider.dylib` and loads the accelerator
dylibs at runtime (`DYLD_LIBRARY_PATH` = the staged dir; the log registers
`GPU Metal` from `libLiteRtMetalAccelerator.dylib`, `GPU WebGPU`, and the XNNPACK CPU
accelerator). Between `1dadd00c` and `origin/main` (`55691e61`, 2026-09-23) the CLI /
lib / vision executor changed in two commits (`c72fd7d8` explicit signature selection,
`cb13f1b4` median benchmark metrics over iterations) — neither touches the single-image
path measured here. Staged dir `.build/litert-lm-advanced-main-1dadd00c/` (`SHA256SUMS`
copied to this campaign's `SHA256SUMS`).

The released macOS binaries carry no image flags (`litert_lm_main.macos_arm64` of the
v0.17.x releases: four flags; the GitHub releases ship only the two xcframework zips), so
this is a bump for measurement; `environment.lock.json`'s v0.16.0 pin for the yardstick's
text cells is untouched (bump-engine-for-comparison). Every record stamps
`engineVersion: main@1dadd00c` and the binary's sha256 in `engineArtifact`.

## Models (sha256 in every record's `model.sha256`; `hfRevision`)

| repo | file | sha256 (= the Hub's LFS sha256) | where it came from |
|---|---|---|---|
| `litert-community/SmolVLM2-500M` | `SmolVLM2-500M.litertlm` | `b808b328…60ad0` | local archive copy (`/Volumes/HD-SGDA/…/tokenizer_parity_20260830/fixed/`), sha256 verified against the Hub API before use (`hfRevision: local`) |
| `litert-community/LFM2.5-VL-450M` | `LFM2.5-VL-450M_int4_fixB.litertlm` | `6854cd96…bf6033` | local archive copy (`…/lfm25vl_work/out_fixb/`), verified the same way |
| `litert-community/LFM2.5-VL-1.6B` | `LFM2.5-VL-1.6B_int4_fixB.litertlm` | `79ca9db8…bd565c` | local archive copy (`…/lfm25vl_work/out_fixb/`), verified the same way |
| `litert-community/gemma-4-E2B-it-litert-lm` | `gemma-4-E2B-it.litertlm` | `18193810…9a63c` | HF cache snapshot `b3ca0d2f` (the dashboard's file) |
| `litert-community/InternVL3-1B` | `InternVL3-1B.litertlm` | — | **not staged**: the Hub was throttled to 0.2 MB/s from this host all afternoon and no local copy matched the published sha256 (four archived copies are earlier exports) — SKIPPED |
| `litert-community/Qwen2-VL-2B` | `Qwen2-VL-2B.litertlm` | — | not staged, same reason — SKIPPED |

The `HF_SHA256SUMS` used for the verification (`sha256  repo  file` from
`https://huggingface.co/api/models/<repo>?blobs=true`) is reproduced in this dir. The
repo manifests (`litertlm_manifest.json`, the recipe lines in `model.quantization`) were
fetched from the Hub on 2026-09-24 (snapshots `dad030b6` SmolVLM2, `be196f4f` LFM 450M,
`9f4ac757` LFM 1.6B).

## Fixture

`evaldata/vl/cc0-cat-couch-1024/cat_couch_1024.jpg` (sha256 `cca087e6…a7be59`, 1024 × 682,
325,221 bytes): Erik-Jan Leusink, "Cat resting on a couch (Unsplash)", CC0 1.0 via
Wikimedia Commons (`File:Cat_resting_on_a_couch_(Unsplash).jpg`; original 4272 × 2848,
sha1 `9716b459…847cd`, sha256 `bf266236…cef9b`), resized with macOS `sips -Z 1024`,
JPEG quality 85. Prompt `Describe this image in one sentence.`, one image,
`--max_output_tokens 64`. The driver verifies the image sha256 against the manifest
before every cell.

## Command (per launch; the exact line is in each record's `provenance.command`)

```
litert_lm_advanced_main --backend=<cpu|gpu> --vision_backend=<same> --model_path=<file> \
  --input_prompt="Describe this image in one sentence. [image:<repo>/evaldata/vl/cc0-cat-couch-1024/cat_couch_1024.jpg]" \
  --benchmark --max_output_tokens=64 --cache_dir=<repo>/.build/vl-cache/<file>
```
