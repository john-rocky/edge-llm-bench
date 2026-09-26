# Vision-language response time, v1 — the second non-LLM task family (2026-09-24)

Task id `vl-describe-catcouch-gen64`; cells `matrices/vl-response-v1.cells`;
driver `scripts/vl_response_mac.py` (dispatched by `scripts/bench_matrix_mac.sh`
for every `vl-*` row, so `./bench matrix matrices/vl-response-v1.cells --platform mac`
is the whole entry point). First capture:
`results/raw/2026-09-24-vl-response-v1-m4max-mac/` (NOTES.md there has the
numbers; this page is the definition). Android leg: `scripts/vl_response_android.py`,
first capture `results/raw/2026-09-26-vl-response-v1-s26-android/` (section
"Android leg" below).

## What is measured

**Response seconds per image** (`vlResponseSeconds`) = wall clock from the
engine's request marker (the log line that opens the single-turn conversation,
after the engine and its caches are up) to the last byte of the reply on
stdout. It is what one image costs an app: image preprocessing + vision encoder
+ prefill of the image tokens and the prompt + decoding the reply up to the
budget or the end-of-turn token. Model load is excluded and reported separately
(`loadTimeSeconds`). Each run is a fresh process (`coldRun: true`); three runs
per cell; the engine's XNNPACK weight cache lives under `.build/vl-cache/<file>/`
and is warm from run 2 (the load column shows it; the response column does not
depend on it).

Beside the headline the record carries the engine's own clocks from
`--benchmark` (BenchmarkInfo, logged after the reply): time to first token
(`vlTimeToFirstTokenSeconds` — prefill of the image + prompt tokens up to the
first sampled token; the vision encoder runs before it and is **not** in it),
the vision encoder's own clock (`vlMarkDurationsMS.vision_executor`, recorded
from 2026-09-26; earlier records carry it in their stderr log), prefill turn 1
(`vlPrefillTokens` = image tokens + prompt tokens, `vlPrefillTokensPerSec`),
decode turn 1 (`vlDecodeTokens`, `vlDecodeTokensPerSec`) and the init phases.
The response seconds contain all three stages: on the Galaxy S26,
`vision_executor` + prefill + decode came to the response seconds minus
8–26 ms in every passing launch. `vlFirstTokenHostSeconds` is the host-side
latency from the request marker to the first reply byte; like the response
seconds it includes the vision encoder.

**Text check.** A rate whose reply nobody read is not a measurement
(benchmark-mode-needs-a-text-check): every record carries the reply and
`vlTextCheck` — the manifest's keyword rule (any of `cat` / `kitten` / `feline`
in the reply, case-insensitive). It is a coherence gate, not a caption-quality
score: a model that names the animal passes; a stream of `!` or end-of-text
tokens fails and its rate is "throughput only". `Invalid decode` lines in the
engine log void the run as well (`vlInvalidDecodeLines`).

## The request

`evaldata/vl/cc0-cat-couch-1024/`: one photograph — Erik-Jan Leusink,
"Cat resting on a couch", CC0 1.0 via Wikimedia Commons — resized to 1024 × 682
JPEG (quality 85) so the repo carries 325 KB, sha256-pinned in `manifest.json`
with the Commons page, the original's sha1 / sha256 and the license URL. The
engine resizes it to each model's fixed vision input (SigLIP 512 × 512 → 64 or
256 tokens, InternViT 448 × 448 → 256, …), so the bytes handed over are the
same for every arm and the token count is the model's (it is in
`vlPrefillTokens`). Prompt: `Describe this image in one sentence.`; one image;
`--max_output_tokens 64` (the budget is in the task id: budget-mode-rule).

## The instrument

LiteRT-LM's own CLI `//runtime/engine:litert_lm_advanced_main` — the C++
engine behind the Kotlin / Swift / Python `litert-lm` surfaces — with the
image in the prompt as `[image:<path>]`, built from `main` at `1dadd00c`
(2026-09-17): the same worktree as the asr-rtf-v1 runner. The released macOS
binaries (`litert_lm_main.macos_arm64`) carry only the four basic flags and no
image path, so this is a bump for measurement; the pin in
`environment.lock.json` (v0.16.0 Swift package for the yardstick's text cells)
is untouched (bump-engine-for-comparison). `engineVersion: main@1dadd00c`.

Build and stage (Mac, ~3 min with the asr-rtf-v1 worktree's bazel cache; the
first build of a clean worktree is longer):

```bash
cd ~/code/litert-lm-1dadd00c-wt                     # git worktree add --detach … 1dadd00c
git lfs pull origin --include="prebuilt/macos_arm64/*"   # the link needs the real dylibs, not LFS pointers
bazelisk build //runtime/engine:litert_lm_advanced_main
D=<repo>/.build/litert-lm-advanced-main-1dadd00c && mkdir -p $D
cp bazel-bin/runtime/engine/litert_lm_advanced_main prebuilt/macos_arm64/*.dylib $D/
echo "main@1dadd00c" > $D/ENGINE_VERSION && (cd $D && shasum -a 256 litert_lm_advanced_main *.dylib > SHA256SUMS)
```

The GPU arm's accelerator is the first library LiteRT's `gpu_registry` manages
to register, not a flag: on macOS it dlopens `libLiteRtGpuAccelerator.dylib`,
`libLiteRtWebGpuAccelerator.dylib`, `libLiteRtOpenClAccelerator.dylib`,
`libLiteRtMetalAccelerator.dylib` in that order from the runner dir and stops at
the first that registers (`litert/runtime/accelerators/gpu_registry.cc` at LiteRT
`0da36b31`, the `LITERT_REF` of `1dadd00c`). The stage above copies all of
`prebuilt/macos_arm64/`, which has no `libLiteRtGpuAccelerator.dylib`, so every
2026-09-24 launch logs `Attempting to load GPU accelerator(libLiteRtGpuAccelerator.dylib).`
→ `Attempting to load GPU accelerator(libLiteRtWebGpuAccelerator.dylib).` →
`RegisterAccelerator: … name=GPU WebGPU`: the Mac GPU arm ran on the WebGPU
accelerator (Dawn, adapter backend Metal), and the registry never reached
`libLiteRtMetalAccelerator.dylib`. The asr-rtf-v1 run dir staged the same Metal
dylib and no WebGPU one, and its logs register `GPU Metal` after the WebGPU
attempt. Records from 2026-09-26 on
name the registered accelerator in `conditions.gpuAccelerator`; a GPU arm's
`engineArtifact` lists the staged GPU dylibs as `staged: …`.

Models: the HF cache (`hf download <repo> <file>`), or `.build/vl-models/<file>`
with an `HF_SHA256SUMS` file (`sha256  repo  file` lines from the Hub API) —
the driver refuses a local copy whose sha256 is not the Hub's, and stamps the
sha256 in every record either way. The repo's `litertlm_manifest.json` (HF
cache) supplies the recipe line of `model.quantization`.

## Protocol (stamped in every record's `conditions`)

| condition | value | note |
|---|---|---|
| `--backend` | `cpu` / `gpu` | arm identity: `litert-lm-cpu` and `litert-lm-gpu` never pool (as on Android and in asr-rtf-v1) |
| `--vision_backend` | = `--backend` | the CLI refuses an image without an explicit vision backend; the arm's backend runs the vision encoder too. A GPU arm whose vision encoder does not compile on the GPU (the Mac CLI's WebGPU-on-Metal path, OpenCL) is a **FAIL row**, not a silent fallback to a CPU encoder |
| `--max_output_tokens` | 64 | budget in the task id |
| `--visual_token_budget` | engine default (-1) | the bundle's own image-token count |
| sampler | CLI defaults | repetition penalty 1.0, no presence / frequency penalty, no constraint; the sampler backend follows the engine's choice |
| `--benchmark` | on | makes the engine log BenchmarkInfo after the reply; the reply is still generated and printed in full |
| `--cache_dir` | `.build/vl-cache/<file>` | keeps the XNNPACK weight cache out of the HF snapshot dir |

Changing any one is a new task id, never a silent override (budget-mode-rule).

## Record shape

`schema/result.v1.json` with the `vl*` condition and metric keys added
2026-09-24 (`vlMarkDurationsMS` and `conditions.gpuAccelerator` 2026-09-26). `runtime` is `litert-lm-cpu` /
`litert-lm-gpu`. `model.quantization` = the file name's word + the repo manifest's recipe line for that variant
(`_fixB` files inherit the base variant's line and say so). `provenance`
carries the image sha256, the manifest sha256, the model sha256, the exact
command, the host's load / thermal / foreign-process snapshot before and after,
and the stderr log path (`logs/<slug>_run<N>.stderr.log`; the reply in
`logs/<slug>_run<N>.stdout.txt`). A row whose bundle is not staged is
`SKIPPED … reason=model-file-not-staged` (driver exit 75), "not yet measured"
rather than a failure.

## Android leg (2026-09-26)

The same CLI at the same commit, built with the NDK (r28, `ANDROID_NDK_HOME`;
~2 min in the Mac build's worktree), plus the GPU accelerator `.so` files from
`prebuilt/android_arm64/` (LFS; `libLiteRtGpuAccelerator.so` is the OpenCL path
the log names `LiteRT GPU`):

```bash
cd ~/code/litert-lm-1dadd00c-wt
git lfs pull origin --include="prebuilt/android_arm64/*"
ANDROID_NDK_HOME=~/Library/Android/sdk/ndk/28.2.13676358 bazelisk build --config=android_arm64 \
  --enable_platform_specific_config //runtime/engine:litert_lm_advanced_main
D=<repo>/.build/litert-lm-advanced-main-1dadd00c-android && mkdir -p $D
cp bazel-bin/runtime/engine/litert_lm_advanced_main prebuilt/android_arm64/*.so $D/
printf 'main@1dadd00c\n<commit date + subject; build command; bazel / NDK versions; build date>\n' > $D/ENGINE_VERSION
(cd $D && shasum -a 256 litert_lm_advanced_main *.so > SHA256SUMS)
```

Line 1 of `ENGINE_VERSION` is stamped as `engineVersion`; line 2 goes into
`engineArtifact` beside the binary's and every `.so`'s sha256.

`BENCH_ANDROID_SERIAL=<serial> scripts/vl_response_android.py
matrices/vl-response-v1.cells --campaign <date>-vl-response-v1-s26` is its own
mini-runner, like `scripts/asr_rtf_android.py`. It reads the `android` `vl-*`
rows, pushes the CLI, the `.so` files, the image and the bundles to
`/data/local/tmp/edge-llm-bench/vl/`, re-hashes each bundle and the image on the
phone, and writes the Mac record shape into `results/raw/<campaign>-android/`
(JSONL per cell, `logs/`, `runlog.txt`, `FAILURES.txt`, `SKIPPED.txt`,
`session_provenance.txt`). `--only <model substring>`, `--backend cpu|gpu` and
`--runs N` serve smokes and re-takes; a smoke goes to a `local-*` campaign
(gitignored).

**Session anchor and admission.** Right before the payload, run the android rows
of the anchor cells and judge the sitting with the dashboard's rule:

```bash
./bench matrix matrices/anchors.cells --platform android --campaign <date>-vl-response-v1-s26-anchor
python3 - <<'EOF'   # admit() reads results/summary/device-runs.csv, which bench matrix just rebuilt
import json, sys; sys.path.insert(0, "scripts")
from dashboard_job import admit
s = json.load(open("ops/dashboard-v1/schedule.json"))
print(admit(s, s["devices"]["s26"], "results/raw/<date>-vl-response-v1-s26-anchor-android", "android"))
EOF
```

`admit()` returns `(admitted, reason, details)`. Write it as `SESSION.json` into
the anchor dir (phase `anchor`, verdict `ADMITTED` / `ABORTED`) and into the
payload dir (phase `payload`); the 2026-09-26 pair is the template. The
dashboard job stops a sitting whose anchor is not admitted; do the same. The
summary that `bench matrix` rebuilt on disk is not the one to commit: rebuild it
from the git index (CLAUDE.md).

**Protocol.** 45 s between launches and 90 s between cells; a cells-file
`cooldown=` overrides the latter (60 on the three largest bundles). Before every
launch the driver waits for thermal status 0 and a battery temperature ≤ 36.0 °C
(15 s polls, 600 s at most, then it launches and records the state). These are
the asr-rtf-v1 phone protocol values, where 5 s between launches let the S26's
CPU cells drift +12–27 %. Clocks: `adb shell` hands over the phone process's
stdout and stderr as two streams, so the response and first-byte clocks are
host arrival times of the request marker and of the reply bytes (adb jitter, no
offset); load and total wall are phone-clock differences (`$EPOCHREALTIME`
before exec, the absl timestamp of the marker). Peak memory is `VmHWM`, polled
through adb every 0.5 s (host memory only; the OpenCL arm's GPU heap is not in
it).

**Screen state.** Before and after every launch the driver reads
`mWakefulness` and `stay_on_while_plugged_in` into `provenance.deviceBefore/After`
and stamps `conditions.screen` from the reading: `on-usb` only when the phone is
`Awake`, otherwise `off-usb (mWakefulness=…)`. The first capture predates that
stamp: its records say `on-usb`, while the phone was `Dozing` for all 36
launches (NOTES.md there).

Records: `results/raw/<campaign>-android/`, anchor records under
`results/raw/<campaign>-anchor-android/app-path-android/`. First capture
`results/raw/2026-09-26-vl-response-v1-s26-android/` (Galaxy S26, 12 cells;
NOTES.md there: SmolVLM2 produces text on OpenCL, both LFM2.5-VL GPU rows stop
at the same `RESIZE_BILINEAR` compile error as on the Mac, InternVL3-1B's GPU row
stops on `BROADCAST_TO` / `GATHER_ND`, and TTFT excludes the vision encoder).

## Not covered in v1

- iPhone leg: not wired; no released engine carries image flags on iOS yet.
- Other VL arms (MLX-VLM, llama.cpp mtmd, Core ML): the task is defined on the
  image + prompt + budget, so any arm that takes a JPEG and prints text can
  join; none is wired.
- Multi-image, higher `--visual_token_budget`, or the `int8` variants as a
  second recipe row.
- InternVL3-1B and Qwen2-VL-2B on the Mac: not staged at the first pass (the
  Hub was throttled to ~0.2 MB/s that afternoon and no local copy matched the
  published sha256). Both were downloaded on 2026-09-26 for the Android leg;
  the Mac rows wait for their own sitting.
