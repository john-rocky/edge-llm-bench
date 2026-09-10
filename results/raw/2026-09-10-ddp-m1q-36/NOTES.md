# 2026-09-10 — first Developer Device Platform (DDP) session of the Route B APK: Galaxy S26 `m1q-36`

Session `session-cc6509d5`, location `global`, project `litert-edge-portal`, submitted 11:05:21 JST
with `gcloud beta device-run sessions submit instrumentation … --async`, finished `PASSED` at
11:11:28 JST (job-000 / execution-000, one device). Console:
https://console.cloud.google.com/storage/browser/litert-edge-portal-devicerun/automation/sessions/session-cc6509d5/
The exact command and the transcript: `docs/ddp-integration.md`. Labels on the session:
`harness=edge-llm-bench, repo=litert-community--gemma-3-270m-it, device=m1q-36`.

Same APK pair as the local re-run two minutes earlier (`2026-09-10-ddp-apk-sm-s942q-gate2-android`):
engine `litertlm-android` 0.17.0, `engineArtifact` 28aa6bc4…2134 in every record; test APK with the
size-class gate. Arguments: `backend=cpu, runs=3, cooldown_s=60, campaign=2026-09-10-ddp-m1q-36`
plus the HF token (gated repo).

## The lab device and what it did

- `SM-S942U1` (US unlocked Galaxy S26; the local unit is the Japanese `SM-S942Q`), Android 16,
  security patch 2026-01-01 (local: 2026-06-05), SoC SM8850, USB-powered at 100 %, screen on,
  thermal status 0 before and after every run. The lab's clock is US Pacific (logcat `09-09 19:06`
  = 2026-09-10 02:06 UTC = 11:06 JST).
- Downloaded the 304 MB `gemma3-270m-it-q8.litertlm` from the Hub CDN itself in **87 s** (local
  Wi-Fi: 11 s); same sha256 757e9119…, same Hub commit 9d209327….
- Gate **PASS** (sub-1B bar: form 8/8, correct 5/8) with the same eight answers as the local unit
  and the Mac CLI.
- 3/3 runs: decode 48.37 / 48.07 / 48.41 tok/s, prefill 346 / 308 / 295 tok/s, TTFT 79 / 86 / 89 ms,
  44 tokens each, engine init 564 / 549 / 570 ms, resident median 702–703 MB, peak 858 MB.
- Instrumentation time 213.6 s (junit.xml `time='212.944'`); session wall ≈ 6 min including
  upload, device allocation and artifact collection.

## What this settles (all were "unverified" in the design doc until today)

The lab device has outbound internet (the Hub download worked with the token in the test options);
`--paths-to-pull` on the app's external files dir lands under
`execution-000/artifacts/sdcard/Android/data/<pkg>/files/…` with the same file names; `--location`
is `global`; a `--labels` dictionary is accepted; the CLI uploads local APK paths to
`gs://<project>-devicerun/automation/inputs/<stamp>/`. The full lab logcat (3.3 MB) was replaced by
`app-path-android/logcat-process.txt` (the test process's lines); `ddp-session/` keeps the
platform's own `junit.xml` (job and execution level) and `instrument.log`.

## Read beside the local S26 row

Two physical units, two rooms, the same binary and arguments: local 50.55 / 48.52 / 48.06 tok/s,
DDP 48.37 / 48.07 / 48.41 tok/s. Same shape; not a delta (devices drift 16–25 % between sittings,
and these are different units).
