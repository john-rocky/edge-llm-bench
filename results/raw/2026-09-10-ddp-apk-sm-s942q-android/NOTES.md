# 2026-09-10 — first local pass-through of the Route B APK (android/ddp-bench) on the Galaxy S26

Sitting: 2026-09-10 08:56–08:59 JST (records are stamped UTC: 2026-09-09T23:56–23:58Z). Device SM-S942Q
(m1q, SM8850, Android 16, patch 2026-06-05), USB-powered at 100 %, screen on, thermal status 0 before
and after every run, uptime 16 h, no other driver on the phone (no dashboard hold; `adb devices` = 1).
Engine: `litertlm-android` 0.17.0 AAR (sha256 28aa6bc4…2134, generated at build time). Model:
`litert-community/gemma-3-270m-it` `gemma3-270m-it-q8.litertlm` at Hub commit 9d209327…, sha256
757e9119…, 304 005 120 bytes, downloaded by the phone itself over Wi-Fi in 11 s.

Harness stamp `2026-09-android-ddp-apk-v1`, CPU backend, `short-chat`, 3 runs, 60 s cooldown, the
gate first. `am_instrument.txt` is the runner's transcript; `logcat-process.txt` the device log scoped
to the test process (the full 1.3 MB dump was dropped — unrelated device chatter is not a measurement);
one `.json` + `.log` per run and `gate_*.json` as written by the test.

## What happened

- A first invocation of `run_local.sh` aborted before installing anything (`EXTRA[@]: unbound
  variable` — macOS bash 3.2 treats an empty array as unbound under `set -u`); fixed in the runner,
  no record produced by that attempt.
- Gate: **FAIL 5/8** (threshold 6). Answers, greedy, 32-token cap: capital→"Paris" ✓, 2+3→"2" ✗,
  sky→"Blue" ✓, days in a week→"1" ✗, opposite of hot→"Cold" ✓, our planet→"Mars" ✗,
  thank-you in Spanish→"Gracias." ✓, 10 vs 100→"100" ✓. The JUnit test therefore failed by design
  (exit 1), and the three speed records were still written.
- Speed, 3/3 runs: decode 50.62 / 47.82 / 50.11 tok/s (engine-reported), prefill 377 / 300 / 334
  tok/s on the 20-token prompt, TTFT 73 / 87 / 80 ms, 44 generated tokens each (the model stopped at
  its own EOS under the 128 cap; the three replies are byte-identical), engine init 420 / 557 / 578 ms (engine-reported `initTimeInSecond`, which includes creating the conversation; `initialize()` alone took 210 / 279 / 289 ms wall),
  resident memory median 702–703 MB (instrumentation process, includes the ART runtime), peak 869 MB.
  No run was a cache build (`firstEver` absent: the gate's engine ran first).

## Cross-check: the three misses are the model's, not the APK's

`mac-cli-crosscheck.txt`: the official `litert-lm` CLI 0.17.0 (`uvx --from litert-lm==0.17.0`) on the
Mac, same artifact (sha256 verified), same greedy settings, answers all eight questions with exactly
the strings the APK produced on the phone — "Paris", "2", "Blue", "1", "Cold", "Mars", "Gracias.",
"100". So the APK's conversation path reproduces the reference implementation, and the gate's 6/8
threshold — fixed before any model ran — conflated *knowledge* (arithmetic, counting, a fact) with
*garbage detection*, which is what the gate is for (docs/ddp-integration.md). Whether the gate is
redefined as a coherence check or kept as is (and this model stays red) is an owner decision; the
threshold was not touched after seeing this data.

## Later the same day

The three speed records were renamed `*.json.gate-fail` (quarantined out of the summary) when the
rule "a gate-FAIL record never ranks" was adopted after the GPU sitting; their verdict was FAIL under
the original 6/8 bar. The same answers pass the size-class bar that replaced it, and the same numbers
are in `2026-09-10-ddp-apk-sm-s942q-gate2-android/` under that bar.
