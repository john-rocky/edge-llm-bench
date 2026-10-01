# 2026-10-01 vision-language response time, v1 — Mac leg, the two rows not staged on 2026-09-24

Task family definition: `docs/vl-response-v1.md`. Cells: the anchor row and the four
InternVL3-1B / Qwen2-VL-2B `mac` rows of `matrices/vl-response-v1.cells`, copied verbatim and in
that file's order into a session cells file (`session_provenance.txt`), run as
`./bench matrix <that file> --platform mac --campaign 2026-10-01-vl-response-v1-m4max`
(session start 19:24:48 JST, last launch 19:29:04 JST). Numbers and findings: `NOTES.md` here.
One JSONL per cell, one record per process launch; the engine's stderr and the reply for every
launch under `logs/` (stored-report-rule). `FAILURES.txt` names the one cell whose launches
failed (it stays in the table as a FAIL row); `SKIPPED.txt` is empty (both bundles staged).
`probes/qwen2vl-gpu-warmcache/` holds two extra launches behind NOTES finding 3 (not a cell).

These rows complete the Mac leg of 2026-09-24 (`results/raw/2026-09-24-vl-response-v1-m4max-mac/`,
where both models were SKIPPED: bundle not staged). Same instrument, image, prompt, budget,
flags, arm identity, run count, cooldowns and driver as that leg; the differences are the date,
the checkout (`~/code/edge-llm-bench`, main at `d14b6fe`, instead of the vltts worktree) and a
fresh `--cache_dir` for these two bundles (they had never run on this Mac).

## Host

Mac Studio M4 Max 128 GB (`Mac16,9`), macOS 27.0 (26A428), 16 cores. Session anchor
(`mlx-swift` Qwen3-0.6B-4bit short-chat, runs=3, same yardstick build as 2026-09-24 —
`engineVersion` 60bd0d78, model revision 73e3e38d): cold 558.7, warm 544.4 / 560.9 tok/s
(warm median 552.6), thermal nominal. Against the 2026-09-24 VL leg's anchor (warm 559.6 / 559.0)
that is 0.988, and 0.981 against the reference the dashboard job's admission uses for this Mac
(563.2, `results/raw/2026-09-24-tts-rtf-v1-m4max-mac`) — the machine was not throttled.
Before the pass a home-directory `bfs` scan of another session held one core at 70–75 % for
about a minute; the pass started after it ended (19:24:42). Every launch samples foreign
processes ≥ 20 % CPU before and after into `provenance.hostBefore/After.others`; NOTES.md lists
them per cell. `pmset -g therm` reported no CPU speed limit at any launch.

## Instrument

LiteRT-LM `main` at `1dadd00c2a2363f275e713cfebab5fa9b96c6226`, `litert_lm_advanced_main`, the
same staged runner dir as 2026-09-24: `~/code/edge-llm-bench-vltts-wt/.build/litert-lm-advanced-main-1dadd00c/`
copied to this checkout's `.build/litert-lm-advanced-main-1dadd00c/` (the driver's default
`VL_RUNNER_DIR`); its `SHA256SUMS` equals the 2026-09-24 campaign's `SHA256SUMS` byte for byte and
`shasum -c` passes on all 8 files after the copy (`SHA256SUMS` here). Binary sha256
`afb0af84…ed5a1f`. Build recipe: `docs/vl-response-v1.md`, "The instrument"; it was not rebuilt.

GPU arm = LiteRT's WebGPU accelerator through Dawn on Metal, as on 2026-09-24: every launch log
registers `GPU WebGPU` from `libLiteRtWebGpuAccelerator.dylib` and no `GPU Metal`; the records
say so in `conditions.gpuAccelerator`, and a GPU record's `engineArtifact` lists the staged GPU
dylibs as `staged: …` (driver behaviour since 2026-09-26).

## Models (sha256 in every record's `model.sha256`; `hfRevision`)

| repo | file | sha256 (= the Hub's LFS sha256, checked 2026-10-01 19:1x JST) | bytes | where it came from | revision |
|---|---|---|---|---|---|
| `litert-community/InternVL3-1B` | `InternVL3-1B.litertlm` | `7cf87c35cf364d04bd2e6f957e3a0366830ad0b46eca3dd81e0000891fd1284a` | 737,314,160 | HF cache, downloaded 2026-09-26 for the S26 leg | `1750633f` (= the Hub's current `main`) |
| `litert-community/Qwen2-VL-2B` | `Qwen2-VL-2B.litertlm` | `cf481776bcb16fe539a38c924a67fc213bb5ee55e6fa600729f060e64849066b` | 1,783,424,544 | same | `5a03c859` (= the Hub's current `main`) |

The same bytes as the S26 leg's rows (`results/raw/2026-09-26-vl-response-v1-s26-android/PROVENANCE.md`,
"Models"). Recipe lines in `model.quantization` come from each snapshot's `litertlm_manifest.json`.

## Fixture and command

As on 2026-09-24 (that leg's PROVENANCE.md, "Fixture" and "Command"): `evaldata/vl/cc0-cat-couch-1024/cat_couch_1024.jpg`
(sha256 `cca087e6…a7be59`, verified by the driver before every cell), prompt
`Describe this image in one sentence.`, one image, `--max_output_tokens 64`:

```
litert_lm_advanced_main --backend=<cpu|gpu> --vision_backend=<same> --model_path=<file> \
  --input_prompt="Describe this image in one sentence. [image:<repo>/evaldata/vl/cc0-cat-couch-1024/cat_couch_1024.jpg]" \
  --benchmark --max_output_tokens=64 --cache_dir=<repo>/.build/vl-cache/<model>_<file>
```

3 launches per cell, 5 s between launches, 30 s before the InternVL3-1B cells and 60 s before the
Qwen2-VL-2B cells (`cooldown=60` in the cells row), as on 2026-09-24. The exact line of each
launch is in its record's `provenance.command`. Paths in the stored records and logs carry
`USER` in place of the Mac account name.
