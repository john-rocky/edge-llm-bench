# Reply materials: the Linux first run of the DDP route (round 3, 2026-10-16)

For the session that writes the reply: the facts with their source, then two sentences as a proposal (EN and JA side by
side). Nothing here has been sent.

## Facts (each from the file named)

- What ran: the README section "Run the Android cells on a Developer Device Platform phone", as written, on a clean
  Ubuntu 24.04 machine (a Docker container, aarch64, on a Mac) with no adb and no phone, from a fresh clone of GitHub
  main (0efecb0) to a billed Device Run session on a lab Pixel 8a, catalog id `akita-35` — `K/LINUX_FIRST_RUN.md`
  "Result", "Environment".
- The session: `session-17997931`, one job (Qwen3-1.7B on the GPU, short chat, 2 runs), PASSED for the session, the
  job and the execution; 432 s from the command to the records; 2 records, LiteRT-LM v0.18.0 — `K/r2/session.md`.
- A second session after a driver fix: `session-b1179d6d`, PASSED, 360 s from the command to the records, nothing
  uploaded (all 12 inputs already in the bucket); the fix is commit 8e4ddad4 (the model is keyed by the sha256 of its
  bytes; huggingface_hub 2.2.0 names its cache file by another hash) — `K/r2b/session-b.md`, `K/LINUX_FIRST_RUN.md`
  finding 6.
- Command lines a person types, as the README prints them, on a machine that has python3 (with `python3-venv`), git,
  curl and gcloud: 9, or 10 with `./bench doctor --platform ddp` — `K/LINUX_FIRST_RUN.md` "Totals".
- Time: README step 1 took 7 s and the stretch from `git clone` to the records 457 s of command time (clone and engine
  files 7 s, selftest 17 s, dry run 1 s, the billed run 432 s), so 464 s, 7 min 44 s, in all; on the wall clock that
  stretch took 27 min 57 s, because two work rounds with probes and README fixes sat between the commands —
  `K/LINUX_FIRST_RUN.md` "Totals", table 2.
- README command lines that stopped on Linux: 0. Fixed on the way (same branch): the selftest step in README step 2,
  the `python3-venv` package named in step 1, the venv form of the `huggingface_hub` install in docs/OPERATIONS.md,
  `./bench doctor --platform ddp`, and the model key (above) — `K/LINUX_FIRST_RUN.md` "Result", "Findings".
- The quickstart: README section "Quickstart: the Android cells on a DDP lab phone" (8 bullets at the top of the
  README). Today it is on the branch `googler-first-run` only: push and merge wait for the GO. After the merge its
  URL is https://github.com/john-rocky/edge-llm-bench#quickstart-the-android-cells-on-a-ddp-lab-phone .

## Two sentences (proposal)

| | EN | JA |
|---|---|---|
| 1 | On a clean Ubuntu 24.04 machine with no adb and no phone, the README's DDP steps ran as written from a fresh clone to a passed Device Run session on a lab Pixel 8a (session-17997931): 9 command lines and under 8 minutes of command time, 7 of them the billed run. | adb も端末も無い素の Ubuntu 24.04 で、README の DDP の手順を書いてあるとおりに実行し、新しい clone から lab の Pixel 8a の Device Run session(session-17997931)が PASSED になるまで通りました。打つ command は 9 行、command の時間は 8 分弱で、そのうち 7 分が課金される run です。 |
| 2 | The short version is the quickstart at the top of the README, https://github.com/john-rocky/edge-llm-bench#quickstart-the-android-cells-on-a-ddp-lab-phone : the clone, the engine files, two checks and one billed command. | 手短な版は README 冒頭の quickstart です(https://github.com/john-rocky/edge-llm-bench#quickstart-the-android-cells-on-a-ddp-lab-phone ):clone、engine の file、確認 2 つ、課金される command 1 本です。 |

Sentence 2's link works once `googler-first-run` is merged into main; until then the section is on that branch only.
