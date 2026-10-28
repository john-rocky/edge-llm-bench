# Dashboard v1 as a recurring job — cadence, device choice, rerun rules

Status: design + implemented job unit (2026-09-07); first end-to-end run on
the Galaxy S26 2026-09-08 (campaigns `2026-09-08-dashboard-v1-s26-*`); the
Core AI arm joined the cells file the same day (§8). The
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
./bench dashboard-job <m4max|s26|pixel8a|iphone17pro|iphone18pro> [--dry-run] [--once]   # that device, whatever the week
./bench dashboard                       # re-render DASHBOARD.md (local) any time
```

## 1. What one sitting does

One invocation of `scripts/dashboard_job.py` is one device, one sitting. It
does what the operator did by hand on 2026-09-05, in the same order, and
stops where a human is needed:

| step | what | on failure |
|---|---|---|
| choose (`auto` only) | the device to measure at this firing (§3): pending this week, attached, unheld, inside its window; oldest last-admitted first | a candidate whose preflight says busy or not ready is passed over for the next; every pending device busy → poll and choose again; nothing pending → exit 0 |
| preflight | device attached (adb / devicectl), iPhone unlocked (`devicectl device info lockState`), no sibling-lane hold with a live pid, no foreign `litert_lm*`/`llama*`/`ortgenai_run`/`model_benchmark` process on the phone, campaign lock free, no CPU-frequency cap (charge/thermal throttle), host runner idle (a `run_campaign.py` / `run_cell.py` driver on the host counts as this phone's unless it names another phone: `run_cell.py --serial` in argv, a campaign driver's `BENCH_ANDROID_SERIAL` in its environment), Mac heavy-pipeline guard, `bench doctor --platform mac`; free space on `/data`; on a phone, the side builds the cells files launch (rows with `engine-build=<tag>`: the tool under `engines/<tag>/`, `android/README.md` "Side builds") | busy → exit 3 and poll; not ready → exit 5, human; a cells file whose side build is missing is skipped by itself and the rest runs (exit 5 only when no file is left, §5) |
| hold | take the sibling lane's device hold (`hold_cli.py acquire`, owner pid = the job); from then on the hold also says when the sitting expects to release it, rewritten as the sitting moves (`expected_release`, §10) | refused → busy |
| reboot (opt-in) | on a phone whose entry carries `reboot_before`: when uptime exceeds `uptime_hours`, `adb reboot`, wait for `sys.boot_completed`, settle `settle_seconds`, `am kill-all`; uptime / MemAvailable / swap in use logged before and after (§3, the Pixel 8a memory finding) | not booted within `boot_timeout_seconds`, or the model directory unreadable (first unlock pending) → exit 5 |
| phase A | `./bench matrix matrices/anchors.cells --platform P --campaign <base>-anchor` | timeout → exit 6 |
| admission | the fresh primary anchor against the newest **admitted** session's anchor on the same device and the same engine build (§4) | not admitted → exit 4, retried once after a cooldown |
| phase B | `./bench matrix matrices/dashboard-text-v1.cells --platform P --campaign <base>` — or one run per storage half on a phone whose free space is below the whole set (§3) — then the device's extra files, one session each (§3, "Per-device extra files") | runner exit codes are recorded, never fatal: failed cells stay (`FAILURES.txt`) |
| close | `SESSION.json` in every campaign dir it created, one line in `logs/dashboard-job/ledger.tsv`, `DASHBOARD.md` re-rendered, hold released | — |
| post (exit 0 only) | after the ledger line, outside the hold: `scripts/dashboard_post.py <the dirs with SESSION.json>` (`docs/dashboard-autopilot-v1.md`) — session checker, local commit of the dirs + `results/summary` rebuilt from the git index, the private page and its checks, push / publish behind the switch | held or failed → `REVIEW.md` in the dirs, a line in `logs/dashboard-job/autopilot-ledger.tsv`; the sitting's exit code and ledger line stand |

Campaign names follow the first pass: `<date>-dashboard-v1-<device>[-<half>]-<platform>`
plus `<date>-dashboard-v1-<device>-anchor-<platform>` for the admission probe.
The anchor probe is its own short campaign on purpose: it costs one anchor
capture (a few minutes) and lets a contended or hot sitting be refused before
it spends two to four hours of device time producing rows that would have to
be thrown out.

The job never edits a cells file and never deletes a raw record. Since
2026-10-18 a sitting that exits 0 is committed by the post step
(`scripts/dashboard_post.py`, `docs/dashboard-autopilot-v1.md`) when every one
of its campaign dirs passes the session checker: one local commit of those dirs
and `results/summary` rebuilt from the git index, by path (other lanes' staged
and untracked files stay as they are). Pushing the bench, pushing the private
page and publishing it stay behind `ops/autopilot/switch.json` (all off). A
person is needed for a HOLD or a FAIL (the reasons are in each dir's
`REVIEW.md`) and for the switch. The only destructive step is the storage rotation on a phone
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
  (Pixel 8a, three halves) of device time — measured, §3 — under USB, phone
  unlocked, the iPhone's screen on (an Android phone's screen may be on or
  off; the runner reads and stamps it per launch); the phones are shared with
  the conversion lanes; and
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

The 2026-10-15 Android LiteRT-LM bump (v0.16.0 → v0.18.0, `android/engine-pins.json`
`android_pins`): on the Galaxy S26 the Gemma 4 E2B GPU protocol cell read 25.9 tok/s decode at
1024 / 256 on v0.16.0, while 0.18-era builds read 44–47 on the same phone and file
(`results/raw/2026-10-11-s26-gallery-vs-binary`). Its pass runs the weekly set's LiteRT-LM rows
(and the Gemma 4 E2B protocol rows) as slot cells files, `matrices/dashboard-0180-<device>-<slot>.cells`:
the session anchor row plus one or two rows byte-identical to their weekly source, each slot
estimated at 45 minutes or less from the previous weekly sitting's launch times. A keeper queues
for the phone and takes its hold, then runs
`python3 scripts/dashboard_job.py <device> --cells <slot file> --suffix 0180-<slot> --once --hold-held-by <keeper pid>`
inside it and releases the hold when the job ends, so every slot is an ordinary sitting:
preflight, the anchors phase, admission exactly as in the weekly job, SESSION.json and a ledger
line. The weekly sittings that follow run on the new pin. v0.18.0's `litert_lm_advanced_main`
prints `BenchmarkInfo:` on a glog line and an aggregated block (`Aggregated BenchmarkInfo`, the
median over the iterations) after the iterations; `android/bench/parsers.py` reads both forms
since 2026-10-15 and never takes a value from the aggregated block.

The 2026-10-19 llama.cpp bump (b8999 → b11721, owner decision that day: the comparison arms are measured
on their current release too) takes the same route with one cells file per platform,
`matrices/dashboard-llama-b11721-{mac,ios,android}.cells` (the session anchor row and the weekly set's ten
llama.cpp rows, byte-identical; the Pixel 8a skips the four 4B-class rows by their exclude-on), one
`dashboard_job.py <device> --cells <file> --suffix llama-b11721 --once` sitting per device. On Android the
session anchor is itself a llama.cpp row, so each phone's first sitting on b11721 is the build's first
session there (§4: no same-build reference; a hot start is refused).

A lane's coverage sitting takes the same route outside the weekly firings (2026-10-15, the Pixel 8a
ONNX Runtime GenAI cells, `results/raw/2026-10-15-dashboard-v1-pixel8a-ortgenai-*`). Each slot is a
cells file with the session anchor row and one or two payload rows, each byte-identical to its
source (`matrices/dashboard-ortgenai-v1-android-ort.cells` line 7 for the anchor,
`matrices/dashboard-ortgenai-v1.cells` for the payload), sized so that one hold lasts 45 minutes or
less. The lane's keeper queues first (`queue_cli.py enqueue`, then `wait`), takes the hold, pushes
the arm's runtime directory when the arm needs one, and runs
`BENCH_SITTING=1 python3 scripts/dashboard_job.py <device> --cells <slot file> --suffix <lane>-<slot> --once --hold-held-by <keeper pid>`
inside the hold; it releases the hold when the job ends and removes what it pushed. The job does
not set `BENCH_SITTING` itself; with it set, `run_cell` checks every launch against `android_pins`
and stops a build that is not the pin (`PIN MISMATCH before launch`). The job's `reboot_before`
runs as in a weekly sitting. Before it queues, the keeper reads the CPU clock ceilings only to log
them: on a phone that sessions use back to back, that reading is often another sitting's load
(three of the six keeper starts on 2026-10-15 read capped there, each while another sitting ran or
right after one), so a keeper that waits there for full clocks stays out of line. It waits inside
the hold instead: idle, one read a minute for up to 10 minutes against the cpu-cap-rule's 15 %
line, then it releases, waits 15 minutes and queues again. On 2026-10-15 the cap had lifted when
the hold came or one minute into it. The job's own preflight line (a ceiling under 0.6 × the
hardware maximum: busy, exit 3 under `--once`) still applies, and the preflight reads a host
`run_campaign.py` as a driver on this phone unless it names another one (`--serial` in
`run_cell.py`'s argv, or `BENCH_ANDROID_SERIAL` in the driver's environment, read since
2026-10-15): a by-hand driver without the variable makes every phone busy. On 2026-10-15 five such
holds took 27 to 40 minutes each (anchors phase 11.5–16.9 min, payload 15.2–25.8 min), and all
ten sessions were admitted.

A bundle replacement is re-measured the same way (2026-10-19): when a page row's file changes with no
engine bump, the moved rows run as cells files of the session anchor row and those rows byte for byte,
each an ordinary sitting through `scripts/dashboard_job.py <device> --cells <file> --suffix <name> --once`.
The Qwen3 0.6B LiteRT-LM rows that left `qwen3_0_6b_mixed_int4.litertlm` (its template drops the user
turn on LiteRT-LM v0.18.0, google-ai-edge/LiteRT-LM#3688) for `Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm`
run as `matrices/dashboard-q06-dynamic-android.cells` (Galaxy S26, Pixel 8a) and
`matrices/dashboard-q06-dynamic-ios.cells` (iPhone), `--suffix q06-dynamic`; the rows, the anchors and
the DDP slot's growth (16 jobs in 2 sessions to 20 in 3) are in docs/dashboard-cells-v1.md "Qwen3 0.6B
LiteRT-LM file (2026-10-19)".

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
   cells stand, §5). A device whose set is in parts (the Mac since
   2026-10-28, "The Mac set in two parts" below) is pending while one of its
   parts has no such session.
2. **Available now.** Attached (adb state `device`; `devicectl` lists the
   iPhone as available), no sibling-lane hold with a live pid (the same files
   preflight checks), and per device: the Mac only while no capture and no
   heavy export pipeline runs (the runner's own guard, replicated); the
   iPhone only inside `auto_window` (05:00–08:00 local, so only the 05:30
   firing) and only after `auto_idle_hours` (4) since its last record from
   the phone in the accumulation layer — the all-nominal sittings so far
   came after that much idle. Use of the phone by a sibling lane that leaves
   no record here is invisible beyond its hold file. An entry with
   `auto: false` is never a candidate (its report line reads `by-hand`): it
   is measured only by `./bench dashboard-job <key>`, by hand, in a window
   the owner offers. The iPhone 17 Pro is that entry since 2026-10-18 (the
   owner's daily phone, not a bench device; the bench iPhone is the 18 Pro).
3. **Oldest first.** Among the available pending devices, the one whose last
   admitted session is oldest; a device never measured is oldest of all;
   ties fall to `schedule.json` order (m4max, s26, pixel8a, iphone18pro;
   iphone17pro is `auto: false`). Two iPhone entries pending in the same 05:30
   window would be two candidates of one firing: one is chosen, and the other
   waits for a later 05:30 — a firing measures one device, and a second iPhone
   sitting beside a running one is refused at preflight (`bench_matrix_iphone`
   running = busy).

A pending retake (stage 3a, `docs/dashboard-autopilot-v1.md` §8: a red point of
the team page's regression rule that the post step found in a sitting, queued in
`logs/dashboard-job/retakes.json`) changes two of these steps: a device whose
weekly set is done is a candidate again while a retake of it is pending (that
firing runs the retake only), and among the available devices those with a
pending retake go first, then the oldest. A retake sitting is not a weekly
session: its `SESSION.json` names its retakes, and step 1 skips it (a by-hand
`--suffix -retake` sitting has no such field and counts as before). Whichever
way a device is chosen, by `auto` or by its key, its pending retakes run as one
sitting of their own before its weekly set (`--cells` and `--no-retake` take
none).

A lab unit on Google's Developer Device Platform (`schedule.json` platform `ddp`,
the entry `s26-ddp` since 2026-10-18, `docs/dashboard-autopilot-v1.md` §9) is no
candidate of these steps (its report line reads `ddp`): it uses no device of
this host, so after the firing's attached sitting (or at a firing with nothing
chosen) the job runs its sitting when it is due: `ops/autopilot/switch.json`
`ddp_weekly` true and no admitted session of the unit in the last
`interval_days` (6) — a rolling window, not the Monday week above.

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
what to plug in. One device per firing; one sitting per device
(`logs/dashboard-job/.job.lock.<device>` — a second run on a device that is
being measured exits 3 at once, while sittings on different devices run side
by side; `auto` holds `.choose.lock` for the seconds of its choice so two
autos never pick the same device). Until 2026-09-08 the lock was one per
host, which serialized independent devices for no measurement reason: a
phone sitting is adb traffic on the host while the Mac measures itself. What
two concurrent sittings share is only the derived files they regenerate at
their close (`results/summary/*`, `DASHBOARD.md`), and those are written
atomically (temp file + rename) and rebuilt from raw, so the last writer wins
without a torn file. `./bench dashboard-job auto --dry-run` prints the
decision with every device's state and the chosen device's plan.

The per-device conditions and cost, from the first pass (local time is the
bench host's):

| device | when it is a candidate | first-pass wall time | preconditions the job checks | sharing |
|---|---|---|---|---|
| Mac Studio (M4 Max) | any firing with no export pipeline running (the runner refuses while one runs; the job passes the Mac over until it is quiet) | 1 h 13 min (15 cells × 4 runs, 1 gate retry); v2 set 1 h 04 min (18 cells × 4 runs, 1 gate retry, 2026-09-08) | `bench doctor --platform mac` green, no yardstick running; Core AI bundles staged (advisory, `doctor` warns) | none (host); side by side with a phone sitting since 2026-09-08 (§3) |
| Galaxy S26 | any firing; USB, screen on or off (read and stamped per launch), unmasked (`BENCH_CPU_MASK=`) | 3 h 23 min (15 cells × 3 runs, one session) | attached, campaign lock free, no foreign engine process, no frequency cap, ≥28 GB free or it falls back to halves | hold `s2_npu_sweep/.device_hold` |
| Pixel 8a | any firing; USB, screen on or off (read and stamped per launch), `taskset f0` | 4 h 02 min as three sessions (a 1 h 41, b1 1 h 15, b2 1 h 06) + pushes | as S26; free space below 28 GB → halves with rotation | hold `.device_hold.pixel8a` (+ `.device_hold.<serial>`) |
| iPhone 17 Pro | never by `auto` (`auto: false` since 2026-10-18: the owner's daily phone, not a bench device); by hand, `./bench dashboard-job iphone17pro`, in a window the owner offers — plugged, unlocked (Auto-Lock Never), one hold at a time | 1 h 53 min for 12 cells with every cell HOT-retried; about 25 min more for the E4B cells | attached, `lockState` unlocked, app installed, no `bench_matrix_iphone` running | hold `community_accel_work/.iphone_hold` (+ `.device_hold.iphone`) |
| iPhone 18 Pro (entry since 2026-10-06; the bench iPhone, kept on USB) | the 05:30 firing only (`auto_window` 05:00–08:00), after ≥4 h without a record; unlocked (Auto-Lock Never) | no sitting yet | attached, `lockState` unlocked, app installed, no `bench_matrix_iphone` running; `udid` is the UDID `devicectl list devices` prints | hold `~/code/coreai/ondevice/.device_hold` (the iPhone lanes' lockfile) + the iPhone 17 Pro's two names |
| Galaxy S26 lab unit on the Developer Device Platform (`s26-ddp`, pool m1q-36 of SM-S942U1, since 2026-10-18) | never the firing's device: after its attached sitting (or a firing with none), while `ddp_weekly` is true in `ops/autopilot/switch.json`, at most once in `interval_days` (6) | 2026-10-16 by hand: 12 of its 16 jobs in 151 device-min, 92 min wall in three streams; first job sitting 2026-10-18: 42.9 min, 2 sessions (15.3 + 25.2 min), 193.0 device-min (ROUND5) | doctor.py `check_ddp` (gcloud signed in, huggingface_hub, the pinned engine files); the plan's Device Run sessions within `ddp_max_sessions`; no phone of this host listed or touched | none on the host; billed per device minute (about 200 a week) |

The Mac sitting holds the machine's measurement window for its whole length (2026-10-19): it flocks the lock
`schedule.json` names in `quiet_lock` (`~/code/coreai/_GPU_LOCK`) and writes the `timing` label every other lane's
heavy job waits on (`quiet_wait.py`, the guard hook); a lock another lane holds is busy (exit 3, the auto firing polls).
Before that the runner's name-based guard only refused to start, and an export from another lane ran on top of a
sitting on 2026-10-19 12:39.

Bench work goes last (user 2026-10-22; in the job since 2026-10-28): a free window that any other job wants is busy
the same way. With the flock taken, before writing its label, the sitting counts the jobs `quiet_rank.py` counts for
a window: a window waiter registered in `<lock>.waiters/<pid>` (`quiet_hold.py`), a job registered in
`<lock>.yield_waiters/<pid>` while it waits for a build slot, and the job a held `<lock>.yield_slots/<i>` names
(`quiet_yield.py`: a lane's build or export that runs outside the windows and stops while one is open). A
registration counts while its process lives, is not stopped, and started before the file was written. The Mac
priority of 2026-10-28 ranks the nightly dashboard last, so every such job counts, the other bench work's too. Any
one, and it lets the lock go untouched (its line, and the mtime the lanes' build gap reads). On 2026-10-28 a sitting
took the free window at 02:47 while lane builds ran outside the windows, and they stood stopped for its length. A
firing whose jobs want the window past its busy window (`retry.busy_window_minutes`) leaves the Mac to the next one.

On the Galaxy S26 and the Pixel 8a the job installs nothing on the phone: the flat engine build in
`/data/local/tmp/llmbench` is replaced by hand with `android/scripts/deploy_litert_lm_android.sh`,
which also resets the engine caches and markers.

Wall times are the span from the session's first to last record in
`results/summary/device-runs.csv` for the 2026-09-05 campaigns; the Android
figures include the first-time pushes, so steady-state sessions should be
somewhat shorter. Cooldowns dominate everywhere (300 s before every Gemma 4
and 4B cell). A phone sitting started at 02:00 is still running at 05:30;
launchd skips that firing, so on such a night the iPhone waits for the next
05:30 — with three phones and a Mac to fit into seven nights that is the
expected shape of a week, not a lost slot.

The wall times above are the short-chat set. Since 2026-10-06 every sitting
also measures the 1024 / 256 cells, which roughly doubles it; estimated
sitting length, hours (`docs/dashboard-cells-v1.md`, "Second task in the
weekly set", has the derivation): Mac Studio 3.8 (the added 51 minutes of
the 1K task measured; +1.0 for the ExecuTorch rows since 2026-10-08, "ExecuTorch
arm in the weekly set, Mac leg"; +0.6 for the ONNX Runtime rows since 2026-10-09, "ONNX Runtime
GenAI arm in the weekly set"), Galaxy S26 10.3 in three halves plus the ONNX Runtime session and,
since 2026-10-09, the NPU / GPU session (+2.1, "NPU and Android GPU rows in the weekly set";
11.5 with a gate retry per session),
Pixel 8a 11.1 (13.8 at the 2026-10-02 retry rate), iPhone 4.8 with every
cell HOT-retried (the iPhone 18 Pro 5.8 since 2026-10-09: +1.0 for the ONNX Runtime
rows, "ONNX Runtime GenAI arm in the weekly set"). `schedule.json` carries them as `expected_hours`, and
`timeout_hours` = 1.5 × the estimate — for a phone in storage halves, 1.5 ×
its longest half times three, because the job gives each half an equal share
of the timeout; an extra file's session (below) runs under its own
`timeout_hours` instead (S26: ONNX Runtime 1, NPU / GPU 4). The Mac's 3.8 was the whole set
as one sitting; since 2026-10-28 the set is two sittings, part b 3.1 and part a 2.5, each under
the 5 h timeout ("The Mac set in two parts", below).

Hold-file names differ between the sibling lanes (S26 `s2_npu_sweep/.device_hold`,
iPhone `community_accel_work/.iphone_hold` and `.device_hold.iphone`, Pixel 8a
`.device_hold.pixel8a` / `.device_hold.<serial>`, iPhone 18 Pro
`~/code/coreai/ondevice/.device_hold`), so each device checks every
name its lanes use (`hold_also_check`). The iPhone 18 Pro's lockfile is written
by its lanes with noclobber, as a JSON line with a keeper pid or as a plain text
line; the job reads a text line as an unowned hold and passes the phone over,
and it takes the hold (a JSON line, through `hold_cli.py`) only after
preflight found the file absent or its pid dead. That JSON line says
`"device": "S26"`: `hold_cli.py` labels a hold by its file name, and
`.device_hold` is the S26's original name — the path is what arbitrates. The Pixel 8a no longer checks the S26's
`.device_hold` (dropped 2026-09-08): one Pixel gate script used that name and
made the Pixel report busy whenever the S26 was in use; a Pixel gate script
that takes only the S26's name is now caught by the foreign-engine-process
check on the phone, not by the hold. The host-driver check had the same
shape on 2026-10-15: the job's own S26 sitting made the Pixel 8a report busy
for the whole sitting, because a `run_campaign.py` driver names its phone
only in its environment (the `bench` wrapper hands it `BENCH_ANDROID_SERIAL`
and `CAMPAIGN` there, not in argv). The preflight now reads that one
variable out of the driver's environment (`ps -E` on macOS, `/proc/<pid>/environ` on Linux; nothing else of it is
kept or logged), so the job's sittings on two phones run side by side; a
driver that names no phone either way still counts as busy.

Storage on phones is the binding constraint, not memory. The whole Android
set needs about 28 GB on the device (models plus LiteRT's XNNPACK/ML Drift
caches beside each bundle). The job compares free space with
`storage_gb_full` and, when short, runs the split files
(`dashboard-text-v1-android-{a,b1,b2}.cells`, each with the session anchor)
one after another; before each half whose floor (`min_free_gb`: on the
Pixel 8a the footprints measured at its first rotation on 2026-09-08 — a 15.4,
b1 10.0, b2 13.2 GB; on the S26 still the 18 / 10 / 13 estimates, to be
replaced when it first runs split) is not met it
deletes the *other* halves' pushed copies — models, the caches that share
their prefix, and their `firstEver` markers — never this half's own and
never a raw record. The job log carries, per half, the free space before and
after it ran and the on-device footprint of its copies with their caches;
that footprint is the measured floor.

Memory is the second constraint on the Pixel 8a, and it shows only after
hours of uptime. llama.cpp Gemma 4 E4B (Q4_K_M) declares about 8 GB of
buffers on the 7.5 GB phone (4.7 GB of weights plus a 2.6 GB CPU repack
buffer). On 2026-09-05 it read 5.0 tok/s on all three cold runs; on
2026-09-08 (4.5 h into the sitting) and 2026-09-09 (13 h of uptime, 1 GB of
swap in use, 2.5 GB of resident user apps) the first run read about 5 and
every later run 0.9-1.6, with the same engine, OS, recipe and thermal state;
nine minutes after a reboot plus `am kill-all` the same cell read 5.1 / 5.0 /
5.4. The mechanism is not measured (the records carry no page-fault
counter); the remedy is. A device entry may therefore carry `reboot_before`
(no entry does now; the Pixel 8a's did from 2026-09-09 to 2026-10-17 —
`uptime_hours` 2, `settle_seconds` 300 — and lost it because the phone has a
PIN: after an unattended reboot it stays RUNNING_LOCKED, the model directory
unreadable, until a person types the PIN, which cost a day each on
2026-10-15 and 2026-10-16): after the hold
is taken and before the anchor probe, a phone past the uptime limit is
rebooted, waited for, settled, and its background apps dropped, with the
memory figures logged before and after so every sitting adds a data point.
A dry run only reports. The S26 (more memory, no such reading) has no entry.
The driver now also drops an artifact's markers on any
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

The iPhone 18 Pro's app is a pin. The job installs nothing: a sitting measures whatever
build of `com.example.CoreMLLLMChat` is on the phone, and every record stamps that build's
engines (`engineVersion`). The pin is kept on the bench host in the main checkout at
`.build/dd-ios-pin/BenchmarkApp.app`, next to `PIN.txt`: the main binary's sha256 on its first
line, then where the build came from and when it went onto the phone. The bench lane replaces
both whenever it installs a new build. The pin of 2026-10-19 is a Release build from the side
tree `.build/dd-ios-0180-18pro/src` with LiteRT-LM v0.18.0 and llama.cpp b11721, signed with the
team profile of `com.example.CoreMLLLMChat` and its increased-memory-limit and
extended-virtual-addressing entitlements. A lane that installs its
own app under this bundle id shares the bench's data container (`Documents/`: models, results,
side-loaded files; `Library/Caches/`: the Hub cache, ONNX Runtime GenAI's cache; `tmp/`:
LiteRT-LM's cache). Such a lane takes
the iPhone hold through the queue, removes only the files it added, and puts the pin back
without uninstalling (an uninstall deletes the container's models). It checks the main binary
against `PIN.txt` before the install, and makes one throwaway launch after it: the first launch
after an install is killed by the scene-create watchdog.

From 2026-10-09 the pin was a Release build of bench `50ab482` (main binary sha256
`042df03a…`) with LiteRT-LM v0.16.0, llama.cpp b8999 and the ONNX Runtime GenAI 0.17.0
XCFramework. Its check on the phone
(`results/raw/2026-10-09-iphone18pro-pin-check-ios`, NOTES.md) found the two session anchors
within 1 % of the 2026-10-08 anchors, and one ONNX Runtime GenAI launch. The Core AI stock
bundles on the phone (Gemma 4 E2B, E4B) loaded neither with it nor with the build the Core AI
arm had measured them with: the app's specialization cache pointed at compiled Neural Engine
programs the phone no longer had (`No model at modelFilePath … existsInCache=0` in the device log).
The phone's first LiteRT-LM v0.18.0 records are from 2026-10-17.

What the job does about the two devices it cannot manage: the iPhone 15 is
never a bench device (no schedule entry, no way to select it); the Galaxy S26
must be attached by a person — while it is not, every firing reports it not
ready and measures the other pending devices; it is measured the first night
it is attached and free.

### Per-device extra files (2026-10-09)

A device entry may carry `extra_cells`: cells files measured on that device only (an arm that
is valid on one phone and not another). After the set — the whole file or the storage halves —
the job runs each as its own session, campaign `<base>-<tag>` with the tag the entry's `tag`, else
taken from the file name as for a half, under its own `timeout_hours` (default 1) and `min_free_gb`; the file starts with the
platform's session anchor row (as every half does), because §4 re-judges each payload session by the anchor
records inside its own campaign and a session without them is anchor-short, not admitted, and retried (in halves mode
the other halves' pushed copies are rotated out first, as between halves). An explicit `--cells`
retake never fans out into them. First use: the ONNX Runtime GenAI short-chat cells on the
Galaxy S26 (`docs/dashboard-cells-v1.md`, "ONNX Runtime GenAI arm in the weekly set").

Second use (2026-10-09, owner GO): `matrices/dashboard-npu-v1-android-s26-short.cells`, the session
anchor and the short-chat rows of the S26's NPU / GPU plan file (llama.cpp's Snapdragon side
build), as the session `-npu` after the ONNX Runtime one: about 2.1 h, `timeout_hours` 4
(`docs/dashboard-cells-v1.md`, "NPU and Android GPU rows in the weekly set", has the derivation).
Its 1K and protocol rows stay by-hand: on 2026-10-08 one such launch raised the battery up to
4.1 °C (1K) and 6.4 °C (llama-bench 1024/256) against at most 1.6 °C for a short-chat launch, and
the job has no battery-temperature stop — the runner waits up to 600 s for thermal status 0
before a launch, then runs. Its five GGUF files are the storage halves' own copies, so its
`min_free_gb` (7) is the room to push back the three a rotation between the halves can take
away (Qwen3 1.7B, Gemma 4 E2B, Qwen3 4B: 6.6 GB as the job counts space), not its 11.8 GB footprint: a floor above what
the halves leave free (13.9 GB after them on 2026-10-05) would rotate their LiteRT bundles and
caches out every week.

A cells file with side-build rows (`engine-build=<tag>`) needs that build on the phone
(`android/README.md`, "Side builds"; without it the runner stops each of those cells before its
launch). The preflight lists the tools those rows launch with one `ls` under `engines/<tag>/`;
a file whose build is missing gets no session and no rotation, the rest of the sitting runs,
the verdict stays the sitting's, and the ledger reason names the file. A `--cells` retake of
such a file alone is not ready (exit 5) before the hold is taken.

### The Mac set in two parts (2026-10-28)

The Mac's weekly set outgrew one sitting. Since 2026-10-19 it is 61 Mac cells (the four MLX
Gemma 4 PTQ rows joined that day), 31 of them with a 300 s cooldown before them. On 2026-10-28 the
02:00 firing took the window at 02:47, and `gtimeout` cut the payload after 300 min at 58 of the 61
cells (24 gate re-runs, 159.5 min of cooldowns): no session admitted, so `auto` takes the Mac again
the next night. The whole set had taken 232 and 224 min on 2026-10-19 (57 cells, 12 and 10 gate
re-runs), and the 2026-10-16 sitting was cut the same way (44 cells, 27 re-runs). A sitting of 4 to
5.5 h against a 5 h timeout fails on a noisy night, and it holds the Mac's window from the lanes
into the morning.

So the m4max entry of `schedule.json` carries `parts`, one sitting each, in this order:
`matrices/dashboard-text-v1-mac-b.cells` (Qwen3 4B and Gemma 4 E4B on every arm, then the ONNX
Runtime GenAI Qwen3 4B rows) and `matrices/dashboard-text-v1-mac-a.cells` (Qwen3 0.6B, Qwen3 1.7B
and Gemma 4 E2B on every arm, then the ONNX Runtime GenAI Qwen3 0.6B and 1.7B rows). They are the
parent file's Mac rows, byte for byte and in its order, and each starts with the session anchor
row, as every Android half does (§4 re-judges each payload on its own anchor records);
`scripts/dashboard_job_selftest.py` fails when a Mac row of the parent is in no part
(`parts_problem`). A part is an ordinary sitting: preflight, the window, the anchor phase and
admission, the payload, SESSION.json, the ledger line and the post. The campaign base names the
part, `<date>-dashboard-v1-m4max-<tag>` (anchor phase `<base>-anchor-mac`, payload `<base>-mac`,
`-r2` on an abort retry), and the payload's SESSION.json names the part's file in `cells` and its
tag in `part`. No number is pooled across the two sessions: each is admitted on its own anchor.

The week: a part is done when a session whose SESSION.json names its file was admitted since
Monday; a session of any other file (the whole set, a `--cells` sitting, a hand run without
SESSION.json) covers every part, as it covers a device without parts. The Mac is pending while a
part is, and its line in the `auto` report names the pending parts. A sitting, chosen by `auto` or
run by key, takes the first pending part in the list's order; when every part is done (a sitting
by hand) the part whose newest session is the oldest; `python3 scripts/dashboard_job.py m4max
--part <tag>` names one. `./bench dashboard-job m4max --dry-run` prints the part and why.

Part b goes first because part a holds the session anchor's model. Both parts measure the anchor
row (MLX Qwen3 0.6B short-chat), and the page shows a cell's newest admitted session, so with part
a last in the week the anchor cell comes from the session of that model's other arms. Every other
model has all its arms in one part: no cross-arm comparison spans the two sessions, except the
anchor cell between the week's two sittings, when it shows part b's number.

Lengths, from the 2026-10-28 m4max log: each cell's span that night (its start to the start of the
next cell's cooldown; the last started cell, ONNX Runtime GenAI Qwen3 4B CPU short-chat, to the
timeout, an upper bound), the three cells the night did not reach from the 2026-10-19 02:00 log,
each cell's own cooldown before it in the part's order (none before a part's first row), and that
night's preflight (1.3 min) and anchor phase (7.1 min, two gate re-runs). Part b: 186.7 min (3.1 h;
115 min of it cooldowns); part a: 149.8 min (2.5 h; 54.5 min of cooldowns). `expected_hours` is 3.1
and 2.5 per part and 3.1 for the device; `timeout_hours` stays 5, per sitting, 1.6 × the longer
part. The gate re-runs a cell once at most: with a re-run on every cell, part b would take about
4.1 h.

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
| collapse | median below `collapse_ratio` × the newest admitted session's anchor median on this device, same engine build | 0.5 | the cell gate's COLLAPSE bar: a contended device halves decode (measured 0.4–2.7 tok/s against 31 on 2026-09-05) |
| thermal | any anchor run started outside nominal → admitted only if the median is within `thermal_tolerance_pct` of the newest **all-nominal** admitted session's anchor on the same build | 5% | the iPhone 17 Pro rule (`devices/iphone-17-pro.md`): a plugged phone reports "fair" regardless of load; fair-at-full-speed is admissible, fair-with-throttling is not |
| first session | no earlier admitted session on this device, or none whose anchor ran this engine build | admitted, `reference: null` | a new device's first sessions establish its anchors; so do a build's |

The reference is matched on the engine build the anchor rows carry
(`engine_version` in `device-runs.csv` — the stamped witness, not the pin
registry): the newest admitted session on this device whose anchor ran the
same build. With no such session the sitting is the first session on that
build and is admitted with `reference: null`; a hot start then has no
all-nominal session to be measured against and is refused, as on a new
device — the retry, or the next firing that starts nominal, establishes
the build's baseline. Rows without a stamp (pre-v1) never match; a session
whose own anchor rows carry no stamp is judged against any build and its
reason says so. `SESSION.json` also keeps the build-blind choice, as
`reference_any_version`, so an excluded session can be read back. Why
(2026-09-13, Pixel 8a): another lane had run the llama.cpp anchor on
b10903 (55 tok/s) two days earlier; the sitting ran the pin b8999 (22–31
tok/s in every other Pixel session, 28.2 that day), read 0.513 against that
session and passed the collapse bar by 0.013, where the build-matched
reference reads 0.95. The phone is shared with lanes that run newer
builds, so the same pairing recurs; the fix is in the job, not in the rows.

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
| cell | HOT / SPREAD / DEAD / COLLAPSE (`scripts/cell_gate.py`; COLLAPSE = the slowest cold run under half the median, or the median under half the fastest — two slow runs beside one fast move the median itself, Pixel 8a 2026-09-09) | quarantine the capture (`.attempt1`, `device-jsonl-flagged/`), cool down, re-run **once**; a flagged retry stands with `FLAGGED.txt` and renders ⚠ | both captures | none |
| cell (retry) | LEVEL (`cell_gate.py --previous`, Android runner): the block re-run's median under half the median of the quarantined capture's un-collapsed runs — a uniformly slow re-run passes every within-capture test (Pixel 8a 2026-09-08: 1.3 / 0.9 / 1.3 after 5.2 / 5.3 / 2.5) | the retry stands with `FLAGGED.txt` and renders ⚠; never a third run | both captures | a targeted retake in a fresher window; on a phone with `reboot_before`, the next sitting reboots first |
| cell | SHORT (crash / timeout) | never retried in the session (failed-runs-stay) | record(s), `FAILURES.txt` | none |
| cell | DEGENERATE (the output is a repetition loop; `scripts/cell_gate.py`, added 2026-09-08 after a Core AI export decoded garbage at a fast rate) | flag only — a re-run reproduces it; the capture stays, `FLAGGED.txt` says the rate is not a measurement | the capture | read the sample; fix or retire the artifact, never quote the rate |
| session | anchor short / collapse / thermal (§4) | refuse the sitting (exit 4); retry **once** after `abort_retry_after_minutes` (collapse 30, thermal 60) | anchor campaign + `SESSION.json admitted:false` | none |
| session | whole-session timeout (`timeout_hours` per device) | exit 6; captured cells stand, missing cells keep last week's value in the table | records so far, `SESSION.json verdict:TIMEOUT` | look at the log |
| session | the phone stops accepting launches mid-session (two consecutive CoreDevice launch refusals with nothing pulled — a lost USB session, a locked phone, a device no longer listed; added 2026-09-09 after the first iPhone firing cycled 13 cells through their cooldowns) | the iPhone runner ends the session at once (`DEVICE_LOST.txt`); the job records verdict DEVICE (exit 5), admission stays the anchor's, captured cells stand, missing cells keep last week's value | records so far, `DEVICE_LOST.txt`, `SESSION.json verdict:DEVICE` | replug / unlock; re-run the missing cells by hand |
| session | a cells file's side build is not on the phone (rows with `engine-build=<tag>`; the preflight's `ls` of the tools they launch, §3 "Per-device extra files") | that file gets no session and no rotation; the rest of the sitting runs and keeps its verdict, the reason names the file; a `--cells` retake of that file alone exits 5 before the hold | ledger reason, sitting log | push the build (`android/README.md`, "Side builds"); a `--cells` retake of the file measures the week's rows, or the next weekly sitting does |
| firing | device busy (hold, lock, foreign process, guard, frequency cap) | `auto`: passed over for the next pending device; when every pending device is busy, poll every `busy_poll_minutes` (15) for `busy_window_minutes` (120), then exit 3. An explicit device: exit 3 after the same polling | ledger line only (device `auto` when none ran) | none — the next firing tries again, or `./bench dashboard-job <device>` by hand |
| firing | device not ready (absent, locked, no app, storage floor unmet, doctor FAIL) | `auto`: passed over for the firing, the other pending devices run; exit 5 only when nothing ran. An explicit device: exit 5, no retry | ledger line only | plug in / unlock / free storage; the next firing takes it, or run by hand |
| week | a cell SHORT in 3 consecutive weekly passes with the same failure | nothing automatic | the three campaigns | convert the row to `exclude=<slug>` in the cells file (the reason is the datum) |
| week | a cell ⚠ (flagged retry kept) in 2 consecutive passes | nothing automatic | — | a targeted retake — anchor + that cell as its own campaign in a cooler window: `--cells` with a file of the form the retake sitting generates (`logs/dashboard-job/retake-<date>-<device>.cells`: the platform's rows of `matrices/anchors.cells`, then the cell's row byte for byte) and `--suffix retake-<slug>` |
| week | a red point of the team page's regression rule (below −5 % against the cell's previous point, `scripts/regression_watch.py`) in the sitting just committed, the cell's newest | the post step queues a retake; the device's next sitting runs it first, as its own sitting over a generated cells file (`auto` takes the device for it at the next firing, its weekly set done or not); the retake's post judges it against the red point's previous point: red stays on another engine build → a bisect request and an issue draft (`docs/dashboard-autopilot-v1.md` §8) | the retake sitting's campaigns, `logs/dashboard-job/retakes.json`, `bisect-requests.json`, `regression-<date>-<slug>.md` | run a bisect request and post a draft (GO); read a retake that stays red on the same build |
| pin bump | `release-watch` shows drift | nothing automatic | — | bump + rebuild, then `./bench regress` per device (§2) |
| cells change | a recipe or model changes (e.g. the Qwen3 artifact question, Qwen3.5 / LFM2.5 go) | the changed rows are new cells; their first admitted session is their value | — | edit the cells file; the table shows the recipe per row |

Two rules the job enforces by *not* acting: a flagged or failed cell is
never averaged away or dropped, and a refused sitting is never partially
kept — the whole campaign is either admitted or shown as an attempt.

Decoded-text check (2026-10-06, text-check-rule in
`methodology/fairness-rules.md`): the job sets no `BENCH_TEXT_CHECK`, and the
Android runner now checks by default the decoded text of every
context-prompt launch — the weekly LiteRT-LM 1024 cells, which until then
ran unchecked. A launch whose reply is empty, off the task's subject or a
repetition loop is a failed run, not a slow one: both records, the stored text
(`*.decoded.txt`) and the log stay in raw, the launch is in `FAILURES.txt` and
so in `SESSION.json`, the text FAIL never triggers the gate's re-run (a re-run
reproduces it), and admission is untouched (the anchors are short-chat cells,
which store no decoded text). The summary's `text_check` column carries the
verdict and `arm_row` keeps the run out of every number, so a cell whose runs
all fail renders `— (text check failed: …)` in place of a rate, every week,
without an `exclude=`. Human step: read the stored text before the campaign
is committed.

Model bytes on the phone (correction, 2026-10-15): until 2026-10-15
`run_cell.push_verified` skipped the push when the phone's copy had the host
file's size, and the record's `model.sha256` was the host file's. The Hub
update of `litert-community/Qwen3-1.7B` on 2026-10-11 (commit 87603f0f,
LlmMetadata for litert-lm 0.18.0: a chat template with content parts,
weights unchanged) changed both files at the same byte size —
`Qwen3_1.7B.litertlm` 66064a4e… → 362ec1c9… (2,056,729,520 bytes),
`Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm` 2eeffef7… → 2a72330b…
(977,184,032 bytes) — so it never reached the Pixel 8a: the Qwen3 1.7B
records of its 2026-10-13 sitting and of the campaigns
`2026-10-15-dashboard-v1-pixel8a-0180-p3a-android` / `-p3b-android` name the
new sha but ran the copy pushed on 2026-09-05 (the phone's sha256sum on
2026-10-15: 66064a4e… and 2eeffef7…, the old files; deleted then, the later
campaigns pushed the new ones). The same day's
`qwen3_4b_mixed_int4.litertlm` update (f0794bc7… → 569fe029…) changed the size (2,659,057,664 → 2,659,053,760 bytes) and was
pushed; on the Galaxy S26 the 2026-10-11 sitting's rotation had deleted the
copies, and its 2026-10-14 sitting pushed all three new files (job log).
The template and the engine must match: on v0.16.0 the old template received
the prompt (Prefill Turn 1 = 19 tokens for short-chat, 1,338 for the 1024
task) and the new one did not (8 tokens for both tasks, the reply unrelated to
the question: the S26 2026-10-14 Qwen3 1.7B and 4B rows); on v0.18.0 the old
template drops it (8 tokens, the Pixel 8a `…-0180-p3a-android` rows). The
S26 2026-10-14 1024 rows fail the text check; short-chat rows carry no text
check.
Since 2026-10-15 `push_verified` compares sha256: the phone's sha is cached
in `<file>.sha256` (`<size> <mtime> <sha256>`, trusted while `stat` reads
that size and mtime, otherwise the phone hashes the file once), a copy with
other bytes is pushed again (its engine caches and firstEver markers go with
it), and `model.sha256` is the sha checked on the phone
(`provenance.modelShaSource: "device"`). Rotation and `deploy_litert_lm_android.sh
--reset-caches` delete the marker with the copy's other `<file>.*` files.

## 6. Outputs and where they live

| artifact | path | committed? |
|---|---|---|
| raw records, console logs, gate quarantine | `results/raw/<campaign>/` (unchanged layout) | yes: by the post step when every dir of the sitting passes the session checker, else by a person |
| session record | `results/raw/<campaign>/SESSION.json` (`schema: dashboard-job-session.v1`: device, cells, times, `admitted`, `verdict`, `reason`, anchor medians + engine build + reference (same build) + `reference_any_version` + ratio, runner exit, failures / flagged / skipped lines, cells expected vs with records, `part` on a device whose set is in parts) | yes, with the campaign |
| accumulation layer, leaderboard | `results/summary/*.csv` (regenerated by `bench matrix`), `LEADERBOARD.md` (local) | csv yes; leaderboard no |
| dashboard table | `DASHBOARD.md` + `.dashboard/dashboard-v1.{csv,json}` (`./bench dashboard`) | **no** — cross-runtime standings stay local; paste into the team channel |
| job log + ledger | `logs/dashboard-job/<date>-auto.log` (the firing's device choice), `<date>-<device>.log` (the sitting, and the post step's output), `logs/dashboard-job/ledger.tsv`, `logs/dashboard-job/autopilot-ledger.tsv` (one line per post) | no |
| regression response state | `logs/dashboard-job/retakes.json` (pending / done / expired / abandoned / superseded retakes, their verdicts), `bisect-requests.json` (requests: engine labels, row, verdict, route, command), `regression-<date>-<slug>.md` (issue drafts, EN + JA, never posted by the job), `retake-<date>-<device>.cells` (each retake sitting's generated cells file; its rows are also in the payload's `SESSION.json` `retake`) | no |

The commit subject is public text and must state what ran and what
reproduced, not a runtime-versus-runtime ordering, and someone reads
`FLAGGED.txt` / `FAILURES.txt` / `SESSION.json` before the numbers enter the
record. Until 2026-10-18 that was a person for every sitting; since then the
session checker (`scripts/session_check.py`, the points those people read,
`docs/session-check-v1.md`) reads them, and a sitting it passes whole is
committed by the post step with a generated one-line message of that kind
(`docs/dashboard-autopilot-v1.md`). A HOLD or a FAIL stays a person's step, as
before. Nothing is pushed while the switch is off.

The dashboard renderer (`scripts/render_dashboard.py`) is the display
surface's skeleton: the cells file is its authority (a cell with no rows
renders "not yet measured", an `exclude=` cell renders its reason), rows
keep cells-file order and columns are alphabetical (nothing is ranked),
the recipe sits next to every number, cold and warm are named per platform,
and a cell older than `stale_days` (10) carries "stale" so a missed slot is
visible in the table. Its numbers come from `arm_row` only.

## 7. Enabling the scheduler

Operator requirements before the first automated firing:

1. Phones attached over USB (an Android phone's screen may be on or off: the
   runner reads and stamps it per launch); the iPhone unlocked with Auto-Lock
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
6. The job runs in the checkout the LaunchAgent names (`cd __REPO__` in the
   template; `~/code/edge-llm-bench` on the bench host) and never pulls: a
   change to the cells files, `schedule.json` or the job's scripts reaches the
   job only once that checkout is updated (`git pull --rebase --autostash`
   there, after reading its uncommitted files — other lanes work in it). On
   2026-10-10 it was fourteen commits behind main, three of them changes to
   the weekly set.

The first automated week is a rehearsal: read each morning's ledger line
and `SESSION.json`, confirm the admission verdicts against the console logs,
and replace the storage floors in `schedule.json` with the per-half
footprints the job logs.

## 8. v2: the Core AI arm joins the job (2026-09-08)

Why the v1 job did not carry it:

- Reproducibility of the arm, not device time, was the blocker. v1 admitted
  only arms with a published artifact per model; Core AI had our own
  side-loaded exports, one of them staged, and the Gemma 4 bundles ran only
  on a patched engine. A weekly slot re-measuring rows that a third party
  cannot rebuild would have produced numbers the public harness cannot
  stand behind (`docs/dashboard-cells-v1.md`, "Core AI arm (v2)").
- The Mac had no protocol-identical path. The job's Mac sitting is one
  `bench matrix` over the cells file; the only Core AI entry point there
  was the external `llm-benchmark` wrapper with its own timing, which
  cannot produce a short-chat row. Putting it in the file would have made
  every Mac sitting write `SKIPPED core-ai … llm-benchmark-is-native-only`.
- Staging is a human step (side-loaded multi-GB folders over USB), and the
  job never stages anything: a not-staged row costs a review line every
  week for nothing.

What v2 changed, and why it fits the job without special-casing:

- The Qwen3 bundles are published (0.6B, 4B; the phone's 1.7B), and the
  Mac yardstick links `CoreAILM`, so the core-ai rows are ordinary cells:
  the same `bench matrix`, the same cell gate and quarantine, the same
  record and the same `arm_row` aggregation. `scripts/dashboard_job.py`
  did not change.
- Cost: three active cells more on the Mac and on the iPhone (the four
  Gemma 4 rows are `exclude=` and are not counted in `cells_expected`).
  Measured on the Mac: the first v2 sitting took 1 h 04 min for 18 cells
  (2026-09-08) against 1 h 13 min for v1's 15 on 2026-09-05 — each sitting
  had one gate retry, and the Core AI cells themselves cost under a minute
  each plus the 300 s cooldown before the 4B one. The iPhone adds a similar
  amount once its folders are staged.
- The first v2 sitting was also the first run side by side with a phone
  sitting (the per-device lock, §3). One cell was gate-flagged (LiteRT
  Gemma 4 E4B, one stalled warm run in each capture) during the minutes the
  Pixel 8a sitting pushed a 5 GB artifact over adb from this host; the same
  cell was clean on 2026-09-05. Not established as the cause — the note is in
  `docs/dashboard-cells-v1.md` — but if it recurs, the Mac guard should
  treat an active `adb push` as busy, or the phone job should pause pushes
  while a Mac capture runs.
- A missing bundle is a `SKIPPED` line (Mac) or a load failure (iPhone),
  never a refused sitting: admission is judged on the MLX anchor, so the
  arm cannot block a week. The morning review reads the line and stages
  the folder, or leaves the row "not yet measured".
- The bandwidth-utilization column in the rendered table normalizes each
  cell by its artifact's bytes and the device's cited ceiling, so an
  own-export arm is read next to published-artifact arms with the recipe
  in the number. Still no ranking: columns stay alphabetical.

### First automatic iPhone firing (2026-09-09, 05:30) — two gaps it exposed

The 05:30 `auto` firing took the iPhone 17 Pro as designed (pending, inside
its window, 4 h idle, `results/raw/2026-09-09-dashboard-v1-iphone17pro-*`).
The anchor probe started at thermal nominal and matched the newest
all-nominal session within 1.2 %, so the sitting was admitted; the phone
then reported `fair` (its charging quirk, §4) and, for one cell's retry at
06:06, `serious`, before reading nominal again at 06:37. The four cells that
completed reproduced their previous session's warm medians within 1.2 %
(the `serious` capture included), each carrying its HOT flag. At 06:42 the
phone stopped accepting launches (`CoreDeviceError 4016`: the trusted
connection and its power assertion were no longer assertable — a lost USB
session, not a phone-side crash) and stayed `unavailable` to `devicectl`
afterwards; the runner then spent 47 minutes cycling every remaining cell as
`SHORT 0` with its full cooldown, and the job closed the sitting as
COMPLETED / admitted with 4 of 17 expected cells recorded. Both behaviours
are the design working as written, and both are gaps:

- A device that has become unreachable should end the sitting at once
  (verdict DEVICE, captured cells stand) instead of paying every remaining
  cooldown; the signal is a run of launch failures with no records pulled.
  Done the same day (§5, `DEVICE_LOST.txt`): two consecutive launch
  refusals end the session; it cannot change a number, so it was not put
  to the owner first.
- A run that starts at `serious` or `critical` is marked and re-run once,
  never stopped. `fair` is this phone's charging label and the anchor rule
  handles it; `serious` is a real thermal escalation and the session should
  pause until nominal (or stop, if it does not return) rather than keep the
  numbers with a mark. Whether to stop or pause is an owner decision.

The `core-ai/qwen3-0.6b-4bit-gpu` cell failed with `not_in_catalog`: the
installed app predates the id (the Mac yardstick was rebuilt, the phone app
was not); the 1.7B / 4B Core AI cells fell inside the unreachable window.

## 9. Open items this design leaves to people

- Qwen3 artifact choice (open question 1 of the one-pager) is the LiteRT
  team's; until answered the rows run as they are, and the recipe shows per
  row.
- Qwen3.5 / LFM2.5 stay as disabled placeholders until the go signal;
  uncommenting them adds cells to the same slots (about +40% device time).
- iPhone MLX Gemma 4 E4B: the QAT OptiQ row stays `exclude=app-killed-at-model-load-sigkill`; since
  2026-10-19 the PTQ 4bit build is a second row (owner decision), and it loads on the iPhone 18 Pro
  (peak 5,139 MB, `results/raw/2026-10-19-dashboard-v1-iphone18pro-mlx-ptq-r3-ios/`).
- The second task (1024-prefill / 256-decode / ctx 2048) is scheduled since
  2026-10-06: every sitting measures `long-context-1024-gen256` beside
  `short-chat` (rows and reasons: `docs/dashboard-cells-v1.md`, "Second task
  in the weekly set"; estimated device time per sitting: §3). It roughly
  doubles a sitting; `expected_hours` / `timeout_hours` in `schedule.json`
  carry the estimate until the first sittings replace it.
- The iPhone 17 Pro is `auto: false` since 2026-10-18 (the owner's daily
  phone, not a bench device; the bench iPhone is the 18 Pro). Its entry stays
  for the by-hand route (`./bench dashboard-job iphone17pro` in a window the
  owner offers), its `udid` now the UDID `devicectl list devices` prints;
  until then the entry carried the CoreDevice identifier, which
  `iphone_attached` never matched (found 2026-10-06), so every 05:30 firing
  reported the phone "not available to devicectl", attached or not.
- Follow-ups found while building this: the iPhone runner has no per-device
  lock (the Android runner's `flock` pattern would close the gap the hold
  files only partly cover); the iPhone runner's default `APP` is the retired
  bundle id (the job refuses an iPhone slot without an explicit `app`, and the
  default should move); `devices/iphone-17-pro.md` cites an
  `ios_admissible_campaigns` helper that is not in `generate_charts.py` —
  the admission rule now lives in the job and `SESSION.json`; per-half
  storage floors are estimates until the first rotation measures them.

## 10. When the device frees up: the hold's release estimate (2026-10-26)

While a sitting holds a device with a hold it took itself, that hold file
carries three more keys beside `pid` / `script` / `device` / `started`
(`scripts/hold_eta.py`):

| key | what |
|---|---|
| `expected_release` | `YYYY-MM-DD HH:MM`, local time: when the sitting expects to release the hold |
| `release_basis` | what that time adds up: the run under way and its progress, then each run still to come with its minutes; it says when the gate may still add re-runs |
| `release_updated` | `YYYY-MM-DD HH:MM:SS`: when the job last wrote them |

Read them with `queue_cli.py list <hold file>` (the sibling lane's tool: the
holder line ends in `expected release …`, the basis under it) or `cat` the
hold. The job rewrites them at each run's start and end, each round, each
gate line, when the time moves 10 min, and at least every 30 min; it stops
writing before it releases the hold. A waiter still waits on the hold
(`queue_cli.py wait`), never on the clock: the time is an estimate.

Why: on 2026-10-26 the Galaxy S26 was read as free early four times: in the
09:40s and at 09:30 (the main matrix's round 3/3 taken for the sitting's
end), then twice at about 12:00 (with the ONNX Runtime and NPU sessions after
it, but not the gate's block re-runs of four collapsed cells, 09:27–10:22).
The hold was released at 12:47:58.

How the time is made: the job reads its own log while each run goes (the
runner's output goes there; `run_logged` lets the estimate read it every
`WATCH_POLL_S`, 30 s) against the sitting's plan (`sitting_runs`: the anchor
phase, the payload whole or in its storage halves, the extra files, a
retake's profile pair; a file whose side build is missing left out). An
Android run is counted launch by launch: each row of its cells file owes its
launches (an anchor row one block of its runs, any other row one launch per
round), each at the length it took earlier in this sitting, else its median
in the device's newest job logs, else the device's median launch. The gate's
re-runs come from the runner: since 2026-10-26 `android/bench/run_campaign.py`
prints `gate ahead: <cell> (<verdict>)` right after a cell's last round (its
verdict is final then) and `gate plan: re-run N of M payload cells …` before
the first re-run; each counts 180 s plus a block of the cell's runs (two of
its round launches when no block of it is on record). A Mac or iPhone run
(their runners print no rounds) is counted whole, from its length in the
logs, else from the device's `expected_hours`. A run past its length is taken
to end now, so the time slips as it overruns.

What it leaves out: a reboot before phase A (`reboot_before`: the first time
is written after it); the re-runs of cells still to finish their last round
(the basis says so); the weekly set after a retake sitting (named in the
retake's basis, but it takes a new hold); a keeper's hold (`--hold-held-by`:
the job never writes into a hold it did not take); the Mac's measurement
window (`quiet_lock`), which is not a device hold.

Safety: the job writes only while the hold names its own pid, and replaces
the file in one step (`os.replace` of a temp file in the same directory: a
reader sees the old hold or the new, never a part), on one line with the
hold's own keys first. Every reader of these files read them by key or
print them whole and ignore a key they do not know (checked 2026-10-26:
`device_hold.py`, `queue_cli.py`, `hold_cli.py read`, `check_holds`, the
lanes' drivers that `json.load` the hold, the iPhone gate scripts that read
its first line).

The 2026-10-26 S26 log replayed with the lengths of the logs before that day
(`scripts/testdata/hold-eta/`, `python3 scripts/hold_eta.py replay …`; the
selftest pins it), minutes from the release at 12:47:58:

| when | with the two gate lines | the log as it was |
|---|---|---|
| hold taken 02:00, anchor end 02:10 | −62, −70 | the same |
| main matrix round 1/3, 2/3 | −44, −45 | the same |
| round 3, as `gate ahead` names the 4 re-runs (08:03–09:22) | −31, −20, +1, +19 | — |
| main matrix round 3/3 | **+13** | −56 |
| the re-runs (09:22–09:44) | +13, +3, −1, −14 | −42, −37, −27, −19 |
| main matrix exit 10:22, ONNX Runtime exit 10:42 | +5, +6 | the same |
| NPU rounds 1–3 | +7, +2, −1 | the same |

Before round 3 the time is early by the gate's re-runs, which no line names
yet (58 min that day); the basis says they may come.
