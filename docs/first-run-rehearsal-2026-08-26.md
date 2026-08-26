# Fresh-clone rehearsal — 2026-08-26

Question answered: **how long from `git clone` to a first honest Mac number,
following only the README — and where does a first-time user stumble?**
Method: clone github.com/john-rocky/edge-llm-bench into a scratch dir on the
bench Mac and do only what the docs say. Every stumble below produced a fix
in the same session (commit referenced where applicable).

Caveat: the bench Mac is not a fresh machine — Xcode 27, xcodegen, brew
tools, and HF caches were already present. Two ambient-state leaks were
found *because* of that (stumbles 2 and 8); toolchain install time for a
truly fresh Mac comes on top of the timeline here.

## Timeline (measured)

| step | wall time |
|---|---|
| `git clone` (8.5 MB) | 1 s |
| `./bench release-watch` — works with zero setup | 2 s |
| `./bench matrix` naive attempts (stumbles 1-2) | ~2 min |
| build attempt without bootstrap (stumble 6) | fails in 1 s |
| `bootstrap.sh` (vendored engines, incl. cactus source build) | see below |
| `build_yardstick_mac.sh` (full flavor) | see below |
| first measured cell | see below |

## Stumbles, in the order a new user hits them

1. **README's example cells file has no mac cells.** `./bench matrix
   matrices/apple-warm-matrix.cells --platform mac` ran zero cells, then
   rebuilt the summary and LEADERBOARD from shipped raw and exited 0 —
   indistinguishable from a successful capture. Fixed: zero-matched runs now
   refuse loudly (exit 2).
2. **The runner silently used an out-of-repo yardstick.** Binary resolution
   defaulted to `~/bench-dd-mac`, so the fresh clone ran whatever stale
   binary another checkout had built — an unpinned harness under this
   clone's protocol. Fixed: `DD_MAC` defaults to `<repo>/.build/dd-mac`.
3. **No setup section existed.** README jumped from the loop commands to
   provenance; bootstrap was only mentioned inside a pin-bump runbook.
   Fixed: README Setup section + `./bench doctor`.
4. (variant of 2) Two checkouts on one machine shared one build dir — the
   same fix (repo-local `DD_MAC`) removes the collision.
5. **Nothing preflights.** A run died mid-capture on whatever was missing.
   Fixed: `./bench doctor` — every failure prints its fix command.
6. **Build without bootstrap fails opaquely** (xcodegen: "Invalid local
   package" x3, no hint). Fixed: `build_yardstick_mac.sh` now names the
   missing Vendored/ pieces and points at bootstrap.
7. **Bootstrap's default LiteRT-LM tag was v0.13.1** — three releases behind
   the published rows; a fresh clone vendored an engine the leaderboard does
   not use. Fixed: default = the lockfile's newest capture pin (v0.16.0),
   bumped together with the lock from now on.
8. **Bootstrap silently links the owner's patched coreai-models checkout**
   when present (`~/code/coreai-models-020-bench`). Correct for the owner's
   PLE captures, but it means the Core AI arm differs between this machine
   and a clean clone — the per-row engine stamp is what keeps that honest.
   Left as-is, documented here.
9. **The yardstick did not compile from a clean clone at all.** The build
   died at `MediaPipeRuntime.swift:132: extra argument 'maxNumTokens'`:
   upstream LiteRT-LM's Swift `benchmark()` computes maxNumTokens internally
   (both v0.13.1 and v0.16.0 — verified against pristine clones of each),
   and the parameter the harness passes existed only as an uncommitted edit
   inside a long-gone working `Vendored/` dir. The 2026-07-17 lesson ("two
   arms referenced APIs that exist only in unpushed local checkouts"),
   repeated. Fixed: the edit is now a committed patch
   (`ios/BenchmarkApp/patches/litert-lm-swift-benchmark-maxnumtokens.patch`)
   that bootstrap applies idempotently after cloning.

## Follow-ups landed with this rehearsal

- `./bench doctor` (preflight, per-lane, exact fix commands).
- Auto-gate: HOT / wide-spread captures quarantine + re-run once
  (`scripts/cell_gate.py`; mac + iPhone runners). Flagged retries stand,
  marked in `FLAGGED.txt`.
- Android lane binaries published as a GitHub release
  (`android-litert-lm-v0.16.0`) — the bazel+NDK build is no longer the entry
  fee for the Android lane.
