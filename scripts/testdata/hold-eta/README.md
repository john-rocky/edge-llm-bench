# hold-eta fixtures (scripts/dashboard_job_selftest.py, `hold_estimate_cases`)

The 2026-10-26 Galaxy S26 dashboard sitting, for the hold's release estimate
(`scripts/hold_eta.py`, docs/dashboard-recurring-job-v1.md §10). Its hold was
released at 12:47:58; that morning it was read as free at 09:40, 09:30 and
12:00.

- `2026-10-26-s26-job-log.txt` (not `.log`: the repo ignores `*.log`):
  `logs/dashboard-job/2026-10-26-s26.log` from its first
  line to `=== done`, cut to the lines the estimate reads: the job's
  `[timestamp]` lines, the runner's launch lines (`=== <label> (HH:MM:SS)`),
  `run i/N` (cut after `i/N`), `--- round k/N complete`, the gate's lines.
  The account name is `USER`. Seven lines were not in the log; they are what
  `android/bench/run_campaign.py` prints since 2026-10-26, made from the
  log's own gate lines: a `gate ahead:` line after the round-3 launch of each
  of the four cells the gate re-ran that day (with the verdict its `gate:`
  line gave), and the `gate plan:` line after each run's
  `--- round 3/3 complete` (the main run's names those four cells in the order
  they were re-run; the ONNX Runtime and NPU runs re-ran none).
- `matrices/*.cells`: the `android` rows of the four cells files that sitting
  ran, as they were on 2026-10-26 (unchanged since 2026-10-19).
- `history-s26-before-2026-10-26.json`: the lengths the estimate reads from the
  S26's job logs before that day,
  `python3 scripts/hold_eta.py history s26 --before 2026-10-26 --json`
  on the bench host (the logs are not in the repo).

Replay by hand:

    python3 scripts/hold_eta.py replay scripts/testdata/hold-eta/2026-10-26-s26-job-log.txt s26 \
      --history scripts/testdata/hold-eta/history-s26-before-2026-10-26.json --cells-dir scripts/testdata/hold-eta

## 2026-11-02: the gate's deadline (`gate_deadline_cases`)

The 2026-11-02 Galaxy S26 sitting under release_by 08:00 (design §11): a and
b1 ran, b1 finished its last round at 07:45, the gate re-ran two collapsed
cells to 08:07, and the hold was released at 08:07:52.

- `2026-11-02-s26-job-log.txt`: `logs/dashboard-job/2026-11-02-s26.log`
  cut the same way, from its first line to b1's `--- round 3/3 complete`;
  the job's `hold release estimate` lines are cut to their mark, and the
  post step's lines are left out. Then the tail the runner and the job print
  under `BENCH_GATE_DEADLINE` (07:58), made from that night's times: the
  `gate plan:` line, the short-chat re-run as it ran (07:48:16, its three
  runs), the long-context re-run deferred at 07:53:04 (`re-run deferred: ~19
  min would end 08:12:19`: three times its longest launch that morning, 245 s,
  with the cooldowns), the run's exit at 07:53:14 and the job's closing
  lines to `hold released` at 07:53:16. The account name is `USER`.
- `matrices/dashboard-text-v1-android-{a,b1,b2}.cells`: the `android` rows of
  the S26's storage halves (unchanged since 2026-10-07).
- `history-s26-before-2026-11-02.json`:
  `python3 scripts/hold_eta.py history s26 --before 2026-11-02 --json` on the
  bench host; it carries the `rounds` lengths (a run's rounds apart from its
  gate re-runs).

    python3 scripts/hold_eta.py replay scripts/testdata/hold-eta/2026-11-02-s26-job-log.txt s26 \
      --history scripts/testdata/hold-eta/history-s26-before-2026-11-02.json --cells-dir scripts/testdata/hold-eta \
      --halves --deadline "2026-11-02 08:00"
