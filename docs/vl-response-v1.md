# Vision-language response time, v1 — the second non-LLM task family (2026-09-24)

Task id `vl-describe-catcouch-gen64`; cells `matrices/vl-response-v1.cells`;
driver `scripts/vl_response_mac.py` (dispatched by `scripts/bench_matrix_mac.sh`
for every `vl-*` row, so `./bench matrix matrices/vl-response-v1.cells --platform mac`
is the whole entry point). First capture:
`results/raw/2026-09-24-vl-response-v1-m4max-mac/` (NOTES.md there has the
numbers; this page is the definition).

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
(`vlTimeToFirstTokenSeconds` — image encoding + prefill, the number a chat UI
feels), prefill turn 1 (`vlPrefillTokens` = image tokens + prompt tokens,
`vlPrefillTokensPerSec`), decode turn 1 (`vlDecodeTokens`,
`vlDecodeTokensPerSec`) and the init phases. `vlFirstTokenHostSeconds` is the
host-side first-byte latency as a cross-check of the engine's TTFT.

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

Models: the HF cache (`hf download <repo> <file>`), or `.build/vl-models/<file>`
with an `HF_SHA256SUMS` file (`sha256  repo  file` lines from the Hub API) —
the driver refuses a local copy whose sha256 is not the Hub's, and stamps the
sha256 in every record either way. The repo's `litertlm_manifest.json` (HF
cache) supplies the recipe line of `model.quantization`.

## Protocol (stamped in every record's `conditions`)

| condition | value | note |
|---|---|---|
| `--backend` | `cpu` / `gpu` | arm identity: `litert-lm-cpu` and `litert-lm-gpu` never pool (as on Android and in asr-rtf-v1) |
| `--vision_backend` | = `--backend` | the CLI refuses an image without an explicit vision backend; the arm's backend runs the vision encoder too. A GPU arm whose vision encoder does not compile on Metal is a **FAIL row**, not a silent fallback to a CPU encoder |
| `--max_output_tokens` | 64 | budget in the task id |
| `--visual_token_budget` | engine default (-1) | the bundle's own image-token count |
| sampler | CLI defaults | repetition penalty 1.0, no presence / frequency penalty, no constraint; the sampler backend follows the engine's choice |
| `--benchmark` | on | makes the engine log BenchmarkInfo after the reply; the reply is still generated and printed in full |
| `--cache_dir` | `.build/vl-cache/<file>` | keeps the XNNPACK weight cache out of the HF snapshot dir |

Changing any one is a new task id, never a silent override (budget-mode-rule).

## Record shape

`schema/result.v1.json` with the `vl*` condition and metric keys added
2026-09-24. `runtime` is `litert-lm-cpu` / `litert-lm-gpu`. `model.quantization`
= the file name's word + the repo manifest's recipe line for that variant
(`_fixB` files inherit the base variant's line and say so). `provenance`
carries the image sha256, the manifest sha256, the model sha256, the exact
command, the host's load / thermal / foreign-process snapshot before and after,
and the stderr log path (`logs/<slug>_run<N>.stderr.log`; the reply in
`logs/<slug>_run<N>.stdout.txt`). A row whose bundle is not staged is
`SKIPPED … reason=model-file-not-staged` (driver exit 75), "not yet measured"
rather than a failure.

## Not covered in v1

- iPhone / Android legs: the same CLI builds for `android_arm64` (the asr-rtf-v1
  route); no released engine carries image flags on either platform yet.
- Other VL arms (MLX-VLM, llama.cpp mtmd, Core ML): the task is defined on the
  image + prompt + budget, so any arm that takes a JPEG and prints text can
  join; none is wired.
- Multi-image, higher `--visual_token_budget`, or the `int8` variants as a
  second recipe row.
- Bundles not staged at the first pass (InternVL3-1B, Qwen2-VL-2B: the Hub was
  throttled to ~0.2 MB/s that afternoon and no local copy matched the published
  sha256) — the rows are in the cells file and read SKIPPED until staged.
