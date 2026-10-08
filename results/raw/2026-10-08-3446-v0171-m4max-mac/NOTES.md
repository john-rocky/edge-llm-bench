# LiteRT-LM #3446 — re-run of the endurance cell on the v0.17.1 macOS xcframework (2026-10-08)

Issue: https://github.com/google-ai-edge/LiteRT-LM/issues/3446 (phys_footprint retained per conversation create/destroy cycle; the original report was v0.16.0, 2026-09-01, `results/raw/2026-09-01-mac-litert-endurance-v0160/`).

## What ran

- Harness: this repo's yardstick (`yardstick flavor=full harness=2026-07-30-agreed-protocol-r4`), task `endurance-chat-30m`, `--context-tokens 2048` (budget rollover), `--litert-backend gpu`, one engine process, one 30-minute scripted chat, `phys_footprint` sampled after every turn — the same cell as the September report (`matrices/endurance-mac.cells`, gemma-4-E2B row).
- Engine: LiteRT-LM Swift package at tag v0.17.1 (commit 5e58e9a0), vendored with `LITERTLM_TAG=v0.17.1 ios/BenchmarkApp/scripts/bootstrap.sh`. Its `CLiteRTLM_mac` binary target is the release zip `CLiteRTLM_mac.xcframework.zip` sha256 `83efd536485c9d58fcd7fb7d4556ddb16ca46bb775b0449d08d9825c6836c1a4`; the dylib inside, `libCLiteRTLM_mac.dylib`, is sha256 `ece7f316cdcf0552caf7bbc1fc151fd4da068aa801caa5510c30440d66b1a585` (144,666,096 B). The v0.17.0 and v0.17.1 release zips are byte-identical (`assets.md`). `engine-pins.json` is the pin file the run was stamped with (`e2b_0171.jsonl` → `engineVersion` / `engineArtifact`).
- Bundle: `litert-community/gemma-4-E2B-it-litert-lm` `gemma-4-E2B-it.litertlm`, 2,588,147,712 B, Hub snapshot b3ca0d2f, sha256 `181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c`.
- Machine: Mac16,9 (Apple M4 Max, 128 GB), macOS 27.0 build 26A428 (the September run was build 26A5416b). GPU = WebGPU accelerator, adapter `Apple M4 Max … backend=Metal` (`e2b_0171.stderr.log`). The Mac was running two other GPU jobs during this session (load average 11.7 at 01:43 JST); decode median 151.06 tok/s.
- Command: `BENCH_ENGINE_PINS_FILE=<worktree>/ios/BenchmarkApp/Vendored/engine-pins.json yardstick run --runtime litert-lm --model-id litert-community/gemma-4-E2B-it-litert-lm --task endurance-chat-30m --runs 1 --context-tokens 2048 --litert-backend gpu --output e2b_0171.jsonl` (2026-10-08 01:44–02:14 JST).

## Files

- `e2b_0171.jsonl` — the schema-v1 session record (`endurance` object: 3,423 turns, 190 rollovers, elapsed 1800 s).
- `e2b_0171.turns.ndjson` — one line per turn: `footprintAfterTurnMB`, `rollover`, `rolloverReason`, tokens and rates.
- `e2b_0171.stderr.log` — the engine log (home directory redacted to `/Users/USER`).
- `attrib3446.py` — the attribution used in the issue: per-turn delta of `footprintAfterTurnMB`, split by the turn's `rollover` flag. `python3 attrib3446.py e2b_0171.turns.ndjson`.
- `attrib.txt` — its output for the September run (v0.16.0), this run (v0.17.1) and, for reference, the 2026-10-07 v0.18.0 run at a 4096 budget (`results/raw/2026-10-07-3444-v0180-m4max-mac/shape1.turns.ndjson`, where the conversation was replaced on the engine's error instead of on the budget).
- `bare.csv`, `bare_summary.txt`, `bareloop/` — a small Swift loop on the same engine (one engine, GPU, maxNumTokens 2048): 50 create/delete cycles without a turn, then 30 cycles of create + one short turn + delete, `phys_footprint` after each cycle.
- `assets.md` — the release-zip and dylib hashes.

## Result (attrib.txt)

| run | rollovers | Δ on rollover turns | mean | median | max | Δ on plain turns | first turn | last turn |
|---|---|---|---|---|---|---|---|---|
| v0.16.0 (2026-09-01) | 197 | +198.3 MB | +1.007 | +0.016 | +31.9 | −51.3 MB | 680.1 MB | 827.2 MB |
| v0.17.1 (this run) | 190 | +128.0 MB | +0.674 | +0.031 | +28.0 | −201.8 MB | 884.4 MB | 810.6 MB |

The v0.17.1 session total is below its first turn because of two single-turn drops on plain turns (−109.8 MB at turn 35, t = 17 s; −113.0 MB at turn 50, t = 27 s); from that minimum (686.9 MB) the footprint grows +123.7 MB over the remaining 29.5 minutes. Nothing in the engine log at those seconds names what was released.
