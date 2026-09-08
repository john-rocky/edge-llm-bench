# Dashboard v1 as a recurring job — cadence, device choice, rerun rules

Status: design + implemented job unit (2026-09-07); first end-to-end run on
the Galaxy S26 2026-09-08 (campaigns `2026-09-08-dashboard-v1-s26-*`). The
scheduler is **enabled on the bench host since 2026-09-08** (owner decision):
`~/Library/LaunchAgents/com.edge-llm-bench.dashboard-v1.plist`, rendered from
`ops/dashboard-v1/com.edge-llm-bench.dashboard-v1.plist.template`; disable
with `launchctl bootout gui/$(id -u)/com.edge-llm-bench.dashboard-v1`. Since
the evening of 2026-09-08 the agent fires `auto` at 02:00 and 05:30 every
night and `auto` takes the first free device that has not been measured this
week (§3) instead of the weekday's fixed device. Every sitting can also be run
by hand with the same command the agent uses.

Companion pages: the cell set and its open questions
(`docs/dashboard-cells-v1.md`), the measurement rules
(`methodology/fairness-rules.md`), the strawman this replaces
(`methodology/continuous-benchmarking-proposal.md` §1–2), the operating
limits the first pass taught (`docs/OPERATIONS.md`, "Known limits").

```bash
./bench dashboard-job auto [--dry-run]            # the pending device whose last admitted session is oldest (§3)
./bench dashboard-job <m4max|s26|pixel8a|iphone17pro> [--dry-run] [--once]   # that device, whatever the week
./bench dashboard                       # re-render DASHBOARD.md (local) any time
```

## 1. What one sitting does

One invocation of `scripts/dashboard_job.py` is one device, one sitting. It
does what the operator did by hand on 2026-09-05, in the same order, and
stops where a human is needed:

| step | what | on failure |
|---|---|---|
| choose (`auto` only) | the device to measure at this firing (§3): pending this week, attached, unheld, inside its window; oldest last-admitted first | a candidate whose preflight says busy or not ready is passed over for the next; every pending device busy → poll and choose again; nothing pending → exit 0 |
| preflight | device attached (adb / devicectl), iPhone unlocked (`devicectl device info lockState`), no sibling-lane hold with a live pid, no foreign `litert_lm*`/`llama*` process on the phone, campaign lock free, no CPU-frequency cap (charge/thermal throttle), host runner idle, Mac heavy-pipeline guard, `bench doctor --platform mac`; free space on `/data` | busy → exit 3 and poll; not ready → exit 5, human |
| hold | take the sibling lane's device hold (`hold_cli.py acquire`, owner pid = the job) | refused → busy |
| phase A | `./bench matrix matrices/anchors.cells --platform P --campaign <base>-anchor` | timeout → exit 6 |
| admission | the fresh primary anchor against the newest **admitted** session's anchor on the same device (§4) | not admitted → exit 4, retried once after a cooldown |
| phase B | `./bench matrix matrices/dashboard-text-v1.cells --platform P --campaign <base>` — or one run per storage half on a phone whose free space is below the whole set (§3) | runner exit codes are recorded, never fatal: failed cells stay (`FAILURES.txt`) |
| close | `SESSION.json` in every campaign dir it created, one line in `logs/dashboard-job/ledger.tsv`, `DASHBOARD.md` re-rendered, hold released | — |

Campaign names follow the first pass: `<date>-dashboard-v1-<device>[-<half>]-<platform>`
plus `<date>-dashboard-v1-<device>-anchor-<platform>` for the admission probe.
The anchor probe is its own short campaign on purpose: it costs one anchor
capture (a few minutes) and lets a contended or hot sitting be refused before
it spends two to four hours of device time producing rows that would have to
be thrown out.

The job never commits, never pushes, never edits a cells file, never deletes
a raw record. The only destructive step is the storage rotation on a phone
(§3): pushed model copies are deleted between halves, together with their
engine caches and `firstEver` markers, and the host Hugging Face cache
re-pushes them next time.

## 2. Cadence

Default: **one full pass per device per week, taken by whichever device is
free first**: launchd fires `./bench dashboard-job auto` every night at 02:00
and 05:30, and each firing measures at most one device that has no admitted
session since Monday 00:00 local. Plus **a release-triggered pass** when an
engine pin is bumped.

Why first-free instead of a fixed weekday per device (the design until
2026-09-08): a device that was unplugged, held by a sibling lane, throttled
or locked on its weekday lost its whole week, and a device that was free on
Monday waited for Wednesday. With two firings a night every pending device
is tried again the next night, the week's order is whatever the devices
allow, and the ledger says which device ran when. What the weekday map
bought — one device per morning to review — is kept: one device per firing,
and a long phone sitting started at 02:00 absorbs the 05:30 firing (launchd
does not start a second instance while one runs).

Why weekly and not nightly:

- Freshness is the only thing cadence buys. A cell's number is always "the
  latest admitted session" (`render_leaderboard.arm_row`); sessions are never
  pooled, so running more often does not make a number more accurate, it
  makes it newer. Devices drift 16–25% between sittings, and every session
  carries its own anchor, so a weekly point per device is a usable drift
  series while a nightly one would mostly be a thermal-state series.
- Cost lands on phones and on people. A full pass is 1.2 h (Mac) to 4 h
  (Pixel 8a, three halves) of device time — measured, §3 — under USB, screen
  on, phone unlocked; the phones are shared with the conversion lanes; and
  every session produces a campaign dir somebody reviews and commits with a
  message that carries no cross-runtime ordering. One device per firing is
  a review load a person actually does.
- Upstream moves at roughly that rate. LiteRT-LM tags have arrived two to
  three weeks apart; a pin bump is a decision (`./bench release-watch`
  informs, a person decides), and the bumped arm gets its own
  release-triggered pass regardless of the weekly slot.

Release-triggered pass: after a pin bump and rebuild (OPERATIONS runbook
"an engine shipped a release"), run `./bench regress
matrices/dashboard-text-v1.cells --engine <arm> --version <v> --baseline
campaign:<previous admitted campaign of that device>` per device. That path
already exists; it produces the anchor-normalized verdicts and
`results/summary/history.csv`. The weekly slot that follows becomes the
first ordinary session on the new pin.

Host-only checks (no device): `./bench release-watch` is already a one-shot
command and can ride the morning standup; an artifact-identity watch (sha256
of the pinned files on the Hub — the proposal's "alert on hash change even
when numbers look stable") is a follow-up, not built here.

Not in v1, deliberately: a nightly anchor-only heartbeat. It needs the
phones attached and unlocked every night for a drift point the weekly
session already provides; add it when the table needs a denser drift
series, not before.

## 3. Which device a firing measures

Firing times are in `ops/dashboard-v1/schedule.json` (`slots`: 02:00 and
05:30 local, both `auto`); the launchd template fires the same times. The
devices and their per-device conditions are `devices` in the same file.
`auto` (`resolve_device` in `scripts/dashboard_job.py`) decides in this order:

1. **Pending this week.** A device is pending when it has no admitted
   dashboard session since Monday 00:00 local. An admitted dashboard session
   is a `-dashboard-v1-` campaign that is not the anchor probe, with rows on
   the device's identifier in `results/summary/device-runs.csv`, whose
   `SESSION.json` does not say `admitted: false` (absent = admitted, as the
   renderer reads it); its time is its last record's. So a hand-run first
   pass counts, a refused sitting does not, an anchor probe alone does not,
   and a timed-out sitting whose anchor was admitted does (its captured
   cells stand, §5).
2. **Available now.** Attached (adb state `device`; `devicectl` lists the
   iPhone as available), no sibling-lane hold with a live pid (the same files
   preflight checks), and per device: the Mac only while no capture and no
   heavy export pipeline runs (the runner's own guard, replicated); the
   iPhone only inside `auto_window` (05:00–08:00 local, so only the 05:30
   firing) and only after `auto_idle_hours` (4) since its last record from
   the phone in the accumulation layer — the all-nominal sittings so far
   came after that much idle. Use of the phone by a sibling lane that leaves
   no record here is invisible beyond its hold file.
3. **Oldest first.** Among the available pending devices, the one whose last
   admitted session is oldest; a device never measured is oldest of all;
   ties fall to `schedule.json` order (m4max, s26, pixel8a, iphone17pro).

The chosen device then runs the full preflight (§1). Busy there (a driver,
the campaign lock, a foreign engine process, a frequency cap) passes it over
for the next candidate and reconsiders it at the next poll; not ready
(unauthorized, locked, no app, doctor FAIL) passes it over for the firing.
When every pending device is busy the firing waits `retry.busy_poll_minutes`
(15) and chooses again, for at most `retry.busy_window_minutes` (120). A
firing with nothing pending — every device measured this week, or only the
iPhone pending outside its window — exits 0 and leaves no ledger line; a
firing whose pending devices are all held or detached leaves one under
device `auto` (BUSY / DEVICE with the reasons) so the morning brief shows
what to plug in. One device per firing; one job instance per host
(`logs/dashboard-job/.job.lock`, a manual `auto` beside a running one exits
3). `./bench dashboard-job auto --dry-run` prints the decision with every
device's state and the chosen device's plan.

The per-device conditions and cost, from the first pass (local time is the
bench host's):

| device | when it is a candidate | first-pass wall time | preconditions the job checks | sharing |
|---|---|---|---|---|
| Mac Studio (M4 Max) | any firing with no export pipeline running (the runner refuses while one runs; the job passes the Mac over until it is quiet) | 1 h 13 min (15 cells × 4 runs, 1 gate retry) | `bench doctor --platform mac` green, no yardstick running | none (host) |
| Galaxy S26 | any firing; USB, screen on, unmasked (`BENCH_CPU_MASK=`) | 3 h 23 min (15 cells × 3 runs, one session) | attached, campaign lock free, no foreign engine process, no frequency cap, ≥28 GB free or it falls back to halves | hold `s2_npu_sweep/.device_hold` |
| Pixel 8a | any firing; USB, screen on, `taskset f0` | 4 h 02 min as three sessions (a 1 h 41, b1 1 h 15, b2 1 h 06) + pushes | as S26; free space below 28 GB → halves with rotation | hold `.device_hold.pixel8a` (+ `.device_hold.<serial>`) |
| iPhone 17 Pro | the 05:30 firing only, after ≥4 h without a record (the only all-nominal sittings so far); unlocked (Auto-Lock Never), plugged or charged | 1 h 53 min for 12 cells with every cell HOT-retried; about 25 min more for the E4B cells | attached, `lockState` unlocked, app installed, no `bench_matrix_iphone` running | hold `community_accel_work/.iphone_hold` (+ `.device_hold.iphone`) |

Wall times are the span from the session's first to last record in
`results/summary/device-runs.csv` for the 2026-09-05 campaigns; the Android
figures include the first-time pushes, so steady-state sessions should be
somewhat shorter. Cooldowns dominate everywhere (300 s before every Gemma 4
and 4B cell). A phone sitting started at 02:00 is still running at 05:30;
launchd skips that firing, so on such a night the iPhone waits for the next
05:30 — with three phones and a Mac to fit into seven nights that is the
expected shape of a week, not a lost slot.

Hold-file names differ between the sibling lanes (S26 `s2_npu_sweep/.device_hold`,
iPhone `community_accel_work/.iphone_hold` and `.device_hold.iphone`, Pixel 8a
`.device_hold.pixel8a` / `.device_hold.<serial>`), so each device checks every
name its lanes use (`hold_also_check`). The Pixel 8a no longer checks the S26's
`.device_hold` (dropped 2026-09-08): one Pixel gate script used that name and
made the Pixel report busy whenever the S26 was in use; a Pixel gate script
that takes only the S26's name is now caught by the foreign-engine-process
check on the phone, not by the hold.

Storage on phones is the binding constraint, not memory. The whole Android
set needs about 28 GB on the device (models plus LiteRT's XNNPACK/ML Drift
caches beside each bundle). The job compares free space with
`storage_gb_full` and, when short, runs the split files
(`dashboard-text-v1-android-{a,b1,b2}.cells`, each with the session anchor)
one after another; before each half whose floor (`min_free_gb`, estimates
to be replaced by measured values after the first rotation) is not met it
deletes the *other* halves' pushed copies — models, the caches that share
their prefix, and their `firstEver` markers — never this half's own and
never a raw record. The job log carries, per half, the free space before and
after it ran and the on-device footprint of its copies with their caches;
that footprint is the measured floor. The driver now also drops an artifact's markers on any
real re-push, because a marker that outlives its cache turns the next run 1
into an unlabelled cache build that would pool as speed (found on the Pixel
8a on 2026-09-07: 10 markers, 3 bundles; fixed in `run_cell.py`, proven by
selftest campaign B2). The iPhone's storage is not probeable headlessly; a
full container fails a cell with "No space left on device" and the row
stays as the datum.

The iPhone is the device that stays half manual: a headless launch needs
the phone unlocked, and an unlocked phone left overnight is either charging
(then it reports "fair" in a warm room and is admitted only through the
anchor rule, §4) or draining. The job passes over a locked phone (not ready)
and the morning brief shows it in the ledger; the operator decides whether
to unlock it for the next 05:30 firing or run it by hand.

What the job does about the two devices it cannot manage: the iPhone 15 is
never a bench device (no schedule entry, no way to select it); the Galaxy S26
must be attached by a person — while it is not, every firing reports it not
ready and measures the other pending devices; it is measured the first night
it is attached and free.

## 4. Session admission

A sitting is admitted or refused on its **primary anchor** — the platform's
non-LiteRT anchor in `matrices/anchors.cells` (MLX Qwen3-0.6B on Apple,
llama.cpp Qwen3-0.6B on Android), the same cell the dashboard file uses as
its `anchor=1` row. The LiteRT anchor is recorded alongside and does not
gate: it belongs to the engine most often under test and legitimately moves
with a pin bump. Basis: the session's warm median on Apple, cold median on
Android (Android v1 has no warm regime), cache-build runs excluded — the
same basis as `arm_row`. Thresholds live in `schedule.json` `admission`.

| rule | test | default | source |
|---|---|---|---|
| short | fewer than `min_anchor_runs` usable runs (crash, timeout, zero decode) | 2 | no-cherry-pick; the differ's n≥2 anchor rule |
| collapse | median below `collapse_ratio` × the newest admitted session's anchor median on this device | 0.5 | the cell gate's COLLAPSE bar: a contended device halves decode (measured 0.4–2.7 tok/s against 31 on 2026-09-05) |
| thermal | any anchor run started outside nominal → admitted only if the median is within `thermal_tolerance_pct` of the newest **all-nominal** admitted session's anchor | 5% | the iPhone 17 Pro rule (`devices/iphone-17-pro.md`): a plugged phone reports "fair" regardless of load; fair-at-full-speed is admissible, fair-with-throttling is not |
| first session | no earlier admitted session on this device | admitted, `reference: null` | a new device's first sessions establish its anchors |

The verdict, the anchor medians, the reference session and the ratio go to
`SESSION.json` (`"admitted": true/false`). `scripts/render_dashboard.py`
drops non-admitted campaigns *before* `arm_row` picks the latest session,
so a refused sitting never displaces the last admitted one in the table.
Campaigns without a `SESSION.json` (the first passes, hand-run sessions)
stay admitted, as they were. `LEADERBOARD.md` stays unfiltered; its rows
carry the thermal state per run.

Ordinary cross-session drift (up to 25%) is **not** a refusal: it is what
anchor normalization exists for, and the ratio is recorded as the drift
signal. The payload session's own anchor row (it runs first inside `bench
matrix`) is judged again post hoc with the same rules, so a contention that
began after the probe still marks that session `admitted: false`.

## 5. Failure and rerun rules, by layer

| layer | condition | automatic action | what stays on disk | human step |
|---|---|---|---|---|
| run | crash / hang / zero decode | the runner records it; `gtimeout` bounds a cell | record + console log | none |
| cell | HOT / SPREAD / DEAD / COLLAPSE (`scripts/cell_gate.py`) | quarantine the capture (`.attempt1`, `device-jsonl-flagged/`), cool down, re-run **once**; a flagged retry stands with `FLAGGED.txt` and renders ⚠ | both captures | none |
| cell | SHORT (crash / timeout) | never retried in the session (failed-runs-stay) | record(s), `FAILURES.txt` | none |
| session | anchor short / collapse / thermal (§4) | refuse the sitting (exit 4); retry **once** after `abort_retry_after_minutes` (collapse 30, thermal 60) | anchor campaign + `SESSION.json admitted:false` | none |
| session | whole-session timeout (`timeout_hours` per device) | exit 6; captured cells stand, missing cells keep last week's value in the table | records so far, `SESSION.json verdict:TIMEOUT` | look at the log |
| firing | device busy (hold, lock, foreign process, guard, frequency cap) | `auto`: passed over for the next pending device; when every pending device is busy, poll every `busy_poll_minutes` (15) for `busy_window_minutes` (120), then exit 3. An explicit device: exit 3 after the same polling | ledger line only (device `auto` when none ran) | none — the next firing tries again, or `./bench dashboard-job <device>` by hand |
| firing | device not ready (absent, locked, no app, storage floor unmet, doctor FAIL) | `auto`: passed over for the firing, the other pending devices run; exit 5 only when nothing ran. An explicit device: exit 5, no retry | ledger line only | plug in / unlock / free storage; the next firing takes it, or run by hand |
| week | a cell SHORT in 3 consecutive weekly passes with the same failure | nothing automatic | the three campaigns | convert the row to `exclude=<slug>` in the cells file (the reason is the datum) |
| week | a cell ⚠ (flagged retry kept) in 2 consecutive passes | nothing automatic in v1 | — | a targeted retake — anchor + that cell as its own campaign in a cooler window (the `--cells` override takes any file); automating the generated retake file is a follow-up |
| pin bump | `release-watch` shows drift | nothing automatic | — | bump + rebuild, then `./bench regress` per device (§2) |
| cells change | a recipe or model changes (e.g. the Qwen3 artifact question, Qwen3.5 / LFM2.5 go) | the changed rows are new cells; their first admitted session is their value | — | edit the cells file; the table shows the recipe per row |

Two rules the job enforces by *not* acting: a flagged or failed cell is
never averaged away or dropped, and a refused sitting is never partially
kept — the whole campaign is either admitted or shown as an attempt.

## 6. Outputs and where they live

| artifact | path | committed? |
|---|---|---|
| raw records, console logs, gate quarantine | `results/raw/<campaign>/` (unchanged layout) | yes, by a person |
| session record | `results/raw/<campaign>/SESSION.json` (`schema: dashboard-job-session.v1`: device, cells, times, `admitted`, `verdict`, `reason`, anchor medians + reference + ratio, runner exit, failures / flagged / skipped lines, cells expected vs with records) | yes, with the campaign |
| accumulation layer, leaderboard | `results/summary/*.csv` (regenerated by `bench matrix`), `LEADERBOARD.md` (local) | csv yes; leaderboard no |
| dashboard table | `DASHBOARD.md` + `.dashboard/dashboard-v1.{csv,json}` (`./bench dashboard`) | **no** — cross-runtime standings stay local; paste into the team channel |
| job log + ledger | `logs/dashboard-job/<date>-auto.log` (the firing's device choice), `<date>-<device>.log` (the sitting), `logs/dashboard-job/ledger.tsv` | no |

The commit is a human step on purpose: the commit subject is public text
and must state what ran and what reproduced, not a runtime-versus-runtime
ordering, and a person reads `FLAGGED.txt` / `FAILURES.txt` / `SESSION.json`
before the numbers enter the record. A templated local commit (no push) can
be added to the job later if the review load asks for it.

The dashboard renderer (`scripts/render_dashboard.py`) is the display
surface's skeleton: the cells file is its authority (a cell with no rows
renders "not yet measured", an `exclude=` cell renders its reason), rows
keep cells-file order and columns are alphabetical (nothing is ranked),
the recipe sits next to every number, cold and warm are named per platform,
and a cell older than `stale_days` (10) carries "stale" so a missed slot is
visible in the table. Its numbers come from `arm_row` only.

## 7. Enabling the scheduler

Operator requirements before the first automated firing:

1. Phones attached over USB, screen on; the iPhone unlocked with Auto-Lock
   Never for its window; the S26 plugged in (it is not attached today).
2. The Mac stays awake at the firing times (the bench host runs with sleep 0).
3. Sibling lanes keep using the device-hold protocol — the job takes the
   hold and refuses while another live pid holds it.
4. `./bench dashboard-job <device> --dry-run` for each device passes
   preflight (it prints the exact commands and env the sitting would run).
5. Load the LaunchAgent from the template (commands in its header). Disable
   with `launchctl bootout`. After changing the firing times in
   `schedule.json` and the template, re-render the plist and bootout +
   bootstrap it again — the loaded agent keeps its old times until then.

The first automated week is a rehearsal: read each morning's ledger line
and `SESSION.json`, confirm the admission verdicts against the console logs,
and replace the storage floors in `schedule.json` with the per-half
footprints the job logs.

## 8. Open items this design leaves to people

- Qwen3 artifact choice (open question 1 of the one-pager) is the LiteRT
  team's; until answered the rows run as they are, and the recipe shows per
  row.
- Qwen3.5 / LFM2.5 stay as disabled placeholders until the go signal;
  uncommenting them adds cells to the same slots (about +40% device time).
- iPhone MLX Gemma 4 E4B stays `exclude=app-killed-at-model-load-sigkill`
  unless the owner chooses the smaller PTQ build for that one row (open
  question 6).
- The second task (1024-prefill / 256-decode / ctx 2048) is not scheduled;
  adding it roughly doubles slot time and is open question 3.
- Follow-ups found while building this: the iPhone runner has no per-device
  lock (the Android runner's `flock` pattern would close the gap the hold
  files only partly cover); the iPhone runner's default `APP` is the retired
  bundle id (the job refuses an iPhone slot without an explicit `app`, and the
  default should move); `devices/iphone-17-pro.md` cites an
  `ios_admissible_campaigns` helper that is not in `generate_charts.py` —
  the admission rule now lives in the job and `SESSION.json`; per-half
  storage floors are estimates until the first rotation measures them.
