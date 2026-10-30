#!/usr/bin/env python3
"""hold_eta — when a dashboard sitting expects to free its device, written into the device hold.

  python3 scripts/hold_eta.py history <device-key> [--before YYYY-MM-DD] [--json]
  python3 scripts/hold_eta.py replay <job log> <device-key> [--before YYYY-MM-DD] [--halves]
                                     [--skip CELLS]... [--history JSON] [--cells-dir DIR]

While a sitting of scripts/dashboard_job.py holds a device through the sibling lane's hold tools
(hold_cli.py's one-line JSON: pid, script, device, started), the job keeps three more keys in that
file (docs/dashboard-recurring-job-v1.md §10):

  expected_release   "YYYY-MM-DD HH:MM", local time: when the sitting expects to release the hold
  release_basis      what that time adds up: the stage running and its progress, then every stage
                     still to run with its minutes (the gate's block re-runs, the extra sessions)
  release_updated    "YYYY-MM-DD HH:MM:SS": when the job last wrote them

Why: on 2026-10-26 the Galaxy S26 was read as free early four times (the decision window three
times, a lane once): in the 09:40s and at 09:30, the end of the main matrix's round 3/3 taken for the
sitting's end, then twice at about 12:00, with the ONNX Runtime (20 min) and NPU (2 h 06 min)
sessions after it but not the gate's re-runs of four collapsed cells (09:27-10:22). The hold was
released at 12:47:58. The sitting knows its own stages: a waiter reads the hold (`queue_cli.py
list`), never adds them up.

How the time is made, from what the job log says as it is written (the job's own [timestamp]
lines and the runner's: `=== <launch> (HH:MM:SS)`, `run i/N`, `--- round k/N complete`, the
gate's lines):
- the plan: the runs the sitting makes in order (the anchor phase, the payload whole or in its
  storage halves, the extra sessions, a retake's profile pair), a file whose side build is missing
  left out; a `skipping` line takes a file out on the way;
- an Android run counts launches: each cells row owes its launches (an anchor row one block of
  its runs, any other row one launch per round), each at the length that launch took earlier in
  this sitting, else its median in the device's recent job logs, else the device's median launch;
- the gate: the runner names a cell it will re-run as soon as the cell's last round is over
  (`gate ahead:`) and all of them before the first re-run (`gate plan:`; android/bench/
  run_campaign.py), each GATE_COOLDOWN_S plus a block of the cell's runs; a cell still to finish
  its last round may add one, and the basis says so;
- any other run (the Mac and iPhone runners print no rounds) counts as a whole: its length in the
  device's recent logs, else the device's expected_hours (schedule.json) shared out;
- a stage that runs past its length is taken to end now: the time slips as it overruns;
- a device with a release_by (schedule.json, docs/dashboard-recurring-job-v1.md §11): a run not yet
  started whose end would pass it is not started (dashboard_job.attempt), so the time ends with the
  runs before it and the basis names the runs left for a later firing (Sitting.start_length is the
  length the job tests a run by).

The job writes the keys only into a hold it took itself (never a keeper's), replacing the file in
one step (os.replace: a reader sees the old hold or the new, never a part of one) and only while
it still names the job's pid. Every reader of these files (device_hold.py, queue_cli.py,
hold_cli.py, dashboard_job.check_holds, the lanes' drivers and gate scripts) reads them as JSON
by key or prints them whole: a key they do not know is ignored.
"""
import argparse
import collections
import datetime
import glob
import json
import os
import re
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from render_dashboard import load_cells  # noqa: E402

FIELDS = ("expected_release", "release_basis", "release_updated")
RELEASE_FMT = "%Y-%m-%d %H:%M"
# android/bench/run_campaign.py GATE_COOLDOWN: the wait before each block re-run
GATE_COOLDOWN_S = 180
DEFAULT_LAUNCH_S = 300.0   # no launch on record at all
DEFAULT_LEAD_S = 30.0      # a run's start to its first launch, none on record
MIN_SHARE_S = 600.0        # a whole run with no length on record gets at least this
PROFILE_S = 600.0          # a retake's profile pair, none on record (2026-10-20 S26: 2 min 54 s)
HISTORY_LOGS = 16          # the device's newest job logs read for lengths (a week's sitting among by-hand days)
HISTORY_KEEP = 5           # newest lengths per launch / run kept for the median
# when the job rewrites the hold besides its events (a run's start and end, a round, the gate):
WRITE_MOVED_S = 600        # the time moved this much since the last write
WRITE_EVERY_S = 1800       # or this long without a write

JOB_LINE = re.compile(r"^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\] (.*)$")
RUN_START = re.compile(r"^\$ gtimeout --kill-after=\d+ \d+ \S*bench (matrix|profile) (\S+) ")
RUN_EXIT = re.compile(r"^bench (matrix|profile) exit (-?\d+)")
SKIP_FILE = re.compile(r"^skipping (\S+): side build not on the phone")
SKIP_HALF = re.compile(r" for (\S+) — skipping this half")
RELEASED = re.compile(r"^hold released")
LAUNCH = re.compile(r"^=== (\S+) (\S+) (\S+) \((\d\d):(\d\d):(\d\d)\)\s*$")
RUN_LINE = re.compile(r"^run \d+/(\d+)\b")
ROUND = re.compile(r"^--- round (\d+)/(\d+) complete")
GATE_AHEAD = re.compile(r"^gate ahead: (\S+ \S+ \S+) \(")
GATE_PLAN = re.compile(r"^gate plan: re-run (\d+) of \d+ payload cells[^:]*(?::\s*(.*))?$")
GATE_RERUN = re.compile(r"^gate: .* re-run once")


def launch_label(runtime, backend, model_id, task):
    """A cell as the Android runner's launch line names it (run_campaign.launch_label)."""
    return f"{runtime}{'/' + backend if backend else ''} {model_id} {task}"


def block_launches(runs):
    """How many of the cell's round launches a block of `runs` runs in one launch (an anchor row, a
    gate re-run) counts for when it has no length of its own on record: runs - 1. A round launch
    pays its own 120 s cooldown, thermal wait and engine setup; a block pays them once. 2026-10-26
    Galaxy S26: the gate's four re-runs (3 runs each) took 58 min after round 3/3, and 180 s plus
    two of each cell's round launches reads 64 min."""
    return max(runs - 1, 1)


def fmt_span(seconds):
    m = int(round(max(seconds, 0) / 60.0))
    return f"{m // 60}h{m % 60:02d}m" if m >= 60 else f"{m}m"


def _median(values):
    return statistics.median(values) if values else None


class Launch:
    __slots__ = ("label", "start", "runs", "end", "rerun", "before_gate")

    def __init__(self, label, start, runs, rerun):
        self.label, self.start, self.runs, self.rerun = label, start, runs, rerun
        self.end = None
        self.before_gate = False   # its end is the gate's start, not a launch's: no length

    @property
    def key(self):
        return (self.label, self.runs)


class Stage:
    """One run of the sitting: `bench matrix <cells>` (or a retake's `bench profile <cells>`)."""

    def __init__(self, kind, cells, tag, rows=None, expected=None):
        self.kind, self.cells, self.tag = kind, cells, tag
        self.rows = rows            # [(launch label, runs, anchor)] of an Android run, else None
        self.expected = expected    # seconds, a run counted whole
        self.start = self.end = self.rc = None
        self.skipped = False
        self.launches = []
        self.rounds = self.rounds_total = 0
        self.ahead = []             # cells the runner said the gate will re-run (`gate ahead:`)
        self.gate = None            # the labels the gate plan names; None = no plan line
        self.announced = 0          # re-runs the gate announced (`gate: ... re-run once`)
        self.announced_at = None
        self.in_gate = False

    @property
    def key(self):
        return f"{self.kind}|{self.cells}"

    def anchor_runs(self, label):
        for lbl, runs, anchor in self.rows or ():
            if anchor and lbl == label:
                return runs
        return None

    def runs_of(self, label):
        return next((runs for lbl, runs, _ in self.rows or () if lbl == label), 3)


class Sitting:
    """A sitting's runs as its job log tells them, and what is left of them at a time.

    stages: the plan in order (plan_stages); a run the log starts that the plan does not name is
    added where it starts (a history log is read with no plan at all). lengths: history(). deadline:
    the device's release_by for this sitting (dashboard_job.release_deadline), or None."""

    def __init__(self, stages=(), lengths=None, deadline=None):
        self.stages = list(stages)
        self.hist = lengths or {"launches": {}, "stages": {}, "leads": {}}
        self.deadline = deadline
        self.current = None
        self.clock = None           # the newest time the log has said
        self.released = None
        self.events = 0             # parsed lines that move the estimate (a run, a round, the gate)

    # ------------------------------------------------------------ reading the log
    def _at(self, hh, mm, ss):
        """A launch line's HH:MM:SS on the day of the newest [timestamp] (a sitting crosses midnight)."""
        if self.clock is None:
            return None
        t = self.clock.replace(hour=hh, minute=mm, second=ss, microsecond=0)
        if t < self.clock - datetime.timedelta(hours=12):
            t += datetime.timedelta(days=1)
        elif t > self.clock + datetime.timedelta(hours=12):
            t -= datetime.timedelta(days=1)
        return t

    def _tick(self, t):
        if t is not None and (self.clock is None or t > self.clock):
            self.clock = t

    def observe(self, now):
        """The live reader's clock (HoldNote): lines without a time (a round's end, the gate's) are
        read as said at the newest of the log's times and `now`."""
        self._tick(now)

    def _close_launch(self, t, timed=True):
        """End the running launch at `t`; ended by a line with no time of its own (a round's end, the
        gate's), it has no length: its end is only known to the poll (or not at all in a replay)."""
        st = self.current
        if st and st.launches and st.launches[-1].end is None and t is not None:
            st.launches[-1].end = t
            if not timed:
                st.launches[-1].before_gate = True

    def feed(self, line):
        """Read one line of the job log -> True when it moved the sitting past a mark: a run's start
        or end, a round, the gate's plan or re-run, a skipped file, the release (a launch moves the
        estimate too, but is not a mark: the job rewrites the hold at marks)."""
        line = line.rstrip("\n")
        m = JOB_LINE.match(line)
        if m:
            try:
                t = datetime.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return False
            self._tick(t)
            return self._job_line(m.group(2), t)
        st = self.current
        if st is None:
            return False
        m = LAUNCH.match(line)
        if m:
            t = self._at(int(m.group(4)), int(m.group(5)), int(m.group(6)))
            if t is None:
                return False
            self._tick(t)
            self._close_launch(t)
            label = f"{m.group(1)} {m.group(2)} {m.group(3)}"
            if st.in_gate:
                runs, rerun = st.runs_of(label), True
            else:
                runs = st.anchor_runs(label)
                if runs and any(l.label == label and l.runs == runs for l in st.launches):
                    runs = None   # the anchor's block ran; another launch of it is a round's
                runs, rerun = (runs or 1), False
            st.launches.append(Launch(label, t, runs, rerun))
            return False
        m = RUN_LINE.match(line)
        if m and st.launches and st.launches[-1].end is None:
            st.launches[-1].runs = int(m.group(1))
            return False
        m = ROUND.match(line)
        if m:
            st.rounds, st.rounds_total = int(m.group(1)), int(m.group(2))
            if st.rounds == st.rounds_total:
                # the last round's last launch is over; the next line with a time is the gate's
                # first re-run or the run's exit, so its length is not a launch's
                self._close_launch(self.clock, timed=False)
            self.events += 1
            return True
        m = GATE_AHEAD.match(line)
        if m:
            st.ahead.append(m.group(1))
            self.events += 1
            return True
        m = GATE_PLAN.match(line)
        if m:
            names = [x.strip() for x in (m.group(2) or "").split(" | ") if x.strip()]
            st.gate = names if len(names) == int(m.group(1)) else [None] * int(m.group(1))
            st.in_gate = True
            self._close_launch(self.clock, timed=False)
            self.events += 1
            return True
        if GATE_RERUN.match(line):
            st.in_gate = True
            st.announced += 1
            st.announced_at = self.clock
            self._close_launch(self.clock, timed=False)
            self.events += 1
            return True
        return False

    def _job_line(self, msg, t):
        m = RUN_START.match(msg)
        if m:
            kind, cells = m.group(1), m.group(2)
            if self.current is not None:
                # a run that never said its exit (stopped, or a dry run's command line) is over
                self._close_launch(t, timed=False)
                self.current.end = t
                self.current = None
            st = next((s for s in self.stages if s.kind == kind and s.cells == cells
                       and s.start is None and not s.skipped), None)
            if st is None:
                # not in the plan (or no plan: a history log): the run is added where it starts
                st = Stage(kind, cells, os.path.basename(cells).replace(".cells", ""))
                idx = self.stages.index(self.current) + 1 if self.current in self.stages else len(self.stages)
                self.stages.insert(idx, st)
            st.start = t
            self.current = st
            self.events += 1
            return True
        m = RUN_EXIT.match(msg)
        if m and self.current is not None and self.current.kind == m.group(1):
            st = self.current
            self._close_launch(t)
            st.end, st.rc = t, int(m.group(2))
            self.current = None
            self.events += 1
            return True
        m = SKIP_FILE.match(msg) or SKIP_HALF.search(msg)
        if m:
            for s in self.stages:
                if s.cells == m.group(1) and s.start is None:
                    s.skipped = True
                    self.events += 1
                    return True
            return False
        if RELEASED.match(msg):
            self.released = t
            self.events += 1
            return True
        return False

    # ------------------------------------------------------------ lengths
    def own_lengths(self):
        """{(label, runs): [seconds]} of this sitting's finished launches (a gate start is no end)."""
        out = collections.defaultdict(list)
        for st in self.stages:
            for l in st.launches:
                if l.end is not None and not l.before_gate:
                    out[l.key].append((l.end - l.start).total_seconds())
        return out

    def _known(self, key, own):
        v = own.get(key)
        if v:
            return _median(v)
        v = self.hist["launches"].get(f"{key[0]}|{key[1]}")
        return _median(v[:HISTORY_KEEP]) if v else None

    def _typical(self, own):
        singles = [x for (lbl, runs), v in own.items() if runs == 1 for x in v]
        singles += [x for k, v in self.hist["launches"].items() if k.endswith("|1") for x in v[:HISTORY_KEEP]]
        return _median(singles) or DEFAULT_LAUNCH_S

    def length(self, key, own):
        """Seconds one launch of `key` = (label, runs) takes."""
        v = self._known(key, own)
        if v is not None:
            return v
        label, runs = key
        single = self._known((label, 1), own)
        if single is None:
            single = self._typical(own)
        return single if runs <= 1 else single * block_launches(runs)

    def _whole(self, st):
        v = self.hist["stages"].get(st.key)
        return _median(v[:3]) if v else st.expected

    def _lead(self, st):
        v = self.hist["leads"].get(st.key)
        return _median(v[:HISTORY_KEEP]) if v else DEFAULT_LEAD_S

    # ------------------------------------------------------------ the estimate
    def stage_left(self, st, now, own):
        """(seconds left in the run at `now`, its progress words, whether the gate is still uncounted)."""
        if st.rows is None:
            whole = self._whole(st) or MIN_SHARE_S
            if st.start is None:
                return whole, "", False
            gone = (now - st.start).total_seconds()
            return max(whole - gone, 0.0), f"{fmt_span(gone)} in", False
        owed = collections.Counter()
        for label, runs, anchor in st.rows:
            if anchor:
                owed[(label, runs)] += 1
            else:
                owed[(label, 1)] += runs
        done = collections.Counter(l.key for l in st.launches if not l.rerun)
        left = sum(max(n - done[key], 0) * self.length(key, own) for key, n in owed.items())
        cur = st.launches[-1] if st.launches else None
        if cur is not None and cur.end is None:
            left += max(self.length(cur.key, own) - (now - cur.start).total_seconds(), 0.0)
        payload = any(not anchor for _, _, anchor in st.rows)
        gate_open = False
        if st.gate is not None:
            started = sum(1 for l in st.launches if l.rerun)
            for label in st.gate[started:]:
                if label:
                    left += GATE_COOLDOWN_S + self.length((label, st.runs_of(label)), own)
                else:   # a plan line whose names did not parse: the device's median launch
                    left += GATE_COOLDOWN_S + self._typical(own) * block_launches(3)
            if st.announced > started and st.announced_at is not None:
                # the announced re-run is in its cooldown
                left -= min((now - st.announced_at).total_seconds(), GATE_COOLDOWN_S)
        elif st.in_gate:
            # a runner that names no plan: only the re-run it announced is counted
            started = sum(1 for l in st.launches if l.rerun)
            if st.announced > started and st.announced_at is not None:
                left += max(GATE_COOLDOWN_S - (now - st.announced_at).total_seconds(), 0.0) \
                    + self._typical(own) * block_launches(3)
        else:
            # the rounds still run: the re-runs the runner already named (`gate ahead:`), and the
            # cells still to finish their last round may add more
            for label in st.ahead:
                left += GATE_COOLDOWN_S + self.length((label, st.runs_of(label)), own)
            gate_open = payload   # until the plan line (seconds after the last round) names them all
        if st.start is None:
            left += self._lead(st)
        if st.start is None:
            words = ""
        elif st.in_gate:
            n = len(st.gate) if st.gate is not None else st.announced
            started = sum(1 for l in st.launches if l.rerun)
            words = (f"round {st.rounds}/{st.rounds_total} done, gate re-runs "
                     + (f"{started}/{n} started" if st.gate is not None else f"{started} so far, no plan line"))
        else:
            n = len([l for l in st.launches if not l.rerun])
            words = (f"round {st.rounds}/{st.rounds_total} done" if st.rounds
                     else f"{n} launch{'' if n == 1 else 'es'} in")
            if st.ahead:
                words += f", {len(st.ahead)} gate re-run{'s' if len(st.ahead) > 1 else ''} ahead"
        return max(left, 0.0), words, gate_open

    def start_length(self, st, own=None):
        """Seconds a run not yet started is taken to need when the job decides whether to start it before
        the device's release_by: its count (stage_left: the launches its rows owe, the lead) or, when
        longer, its newest whole length on record (history: the file's last run on this device that
        exited 0), which holds the gate's re-runs that run had; no line names a re-run before the run
        starts. The newest, not a median: a cells file grows (the S26's whole set took 3.3 h in
        September, 8.2 h on 2026-10-26), and a median of both is neither."""
        own = self.own_lengths() if own is None else own
        counted = self.stage_left(st, datetime.datetime.now(), own)[0] if st.start is None else 0.0
        newest = (self.hist["stages"].get(st.key) or [None])[0]
        return max(counted, newest or 0.0)

    def estimate(self, now):
        """(expected release datetime, basis) at `now`. With a deadline (release_by), a run not yet started
        counts its start_length, the length the job tests it by, and the walk ends at the first such run that
        would end past the deadline from the time the runs before it are taken to end: the job does not start
        that run nor any after it (dashboard_job.attempt), and the basis names them. A retake's profile pair
        goes with its matrix run, never alone."""
        own = self.own_lengths()
        total, parts, open_gates, cut = 0.0, [], [], []
        for st in self.stages:
            if st.skipped or st.end is not None:
                continue
            if cut:
                cut.append(st.tag)
                continue
            left, words, gate_open = self.stage_left(st, now, own)
            if self.deadline is not None and st.start is None:
                left = self.start_length(st, own)
                need = left + (0.0 if st.kind == "profile" else sum(
                    self.start_length(p, own) for p in self.stages
                    if p.kind == "profile" and p.cells == st.cells and p.start is None and not p.skipped))
                if st.kind != "profile" and now + datetime.timedelta(seconds=total + need) > self.deadline:
                    cut.append(st.tag)
                    continue
            total += left
            if gate_open:
                open_gates.append(st.tag)
            if st.start is not None:
                parts.append(f"{st.tag}: {words + ', ' if words else ''}~{fmt_span(left)} left")
            else:
                parts.append(f"{st.tag} ~{fmt_span(left)}")
        tail = (f"; release_by {self.deadline:%H:%M}: {', '.join(cut)} not started, left for a later firing"
                if cut else "")
        if not parts:
            return now, "nothing left to run" + tail
        basis = parts[0] + ("; then " + ", ".join(parts[1:]) if len(parts) > 1 else "")
        if open_gates:
            basis += (f" (+ any re-run the gate adds for a cell of {', '.join(open_gates)} still to finish "
                      f"its last round: {GATE_COOLDOWN_S // 60} min + a block of the cell's runs each)")
        return now + datetime.timedelta(seconds=total), basis + tail


# ---------------------------------------------------------------- history and the plan

def history(log_dir, key, before=None, n=HISTORY_LOGS):
    """Lengths from the device's newest job logs (logs/dashboard-job/<date>-<key>.log, at most n,
    dated before `before` when given) -> {"launches": {"<label>|<runs>": [s, ...]},
    "stages": {"<kind>|<cells>": [s, ...]}, "leads": {...}}, newest first. Only runs that exited 0
    count; a launch whose end is the gate's start does not."""
    out = {"launches": collections.defaultdict(list), "stages": collections.defaultdict(list),
           "leads": collections.defaultdict(list)}
    paths = sorted(glob.glob(os.path.join(log_dir, f"*-{key}.log")), reverse=True)
    if before:
        paths = [p for p in paths if os.path.basename(p)[:10] < before]
    for path in paths[:n]:
        s = Sitting()
        try:
            with open(path, errors="replace") as fh:
                for ln in fh:
                    s.feed(ln)
        except OSError:
            continue
        for st in reversed(s.stages):     # newest first within the file too
            if st.end is None or st.rc != 0 or st.start is None:
                continue
            out["stages"][st.key].append((st.end - st.start).total_seconds())
            if st.launches:
                out["leads"][st.key].append((st.launches[0].start - st.start).total_seconds())
            for l in reversed(st.launches):
                if l.end is not None and not l.before_gate:
                    out["launches"][f"{l.label}|{l.runs}"].append((l.end - l.start).total_seconds())
    return {k: dict(v) for k, v in out.items()}


def stage_rows(cells_path, platform_token, key):
    """[(launch label, runs, anchor)] of an Android cells file as the runner runs it on device `key`:
    its android rows minus exclude= / manual=1 rows and the rows exclude-on= names for the device."""
    rows = []
    for c in load_cells(cells_path):
        if c["platform"] != platform_token or c["exclude"] or (key and key in c["exclude_on"]):
            continue
        rows.append((launch_label(c["runtime"], c["opts"].get("backend"), c["model_id"], c["task"]),
                     int(c["opts"].get("runs", "3")), c["anchor"]))
    return rows


def _launches(cells_path, platform_token, key):
    try:
        return sum(runs for _, runs, _ in stage_rows(cells_path, platform_token, key))
    except (OSError, ValueError, KeyError):
        return 0


def plan_stages(runs, dev, key, lengths, root=ROOT, platform_token="android", budget_s=None):
    """The Stage list for runs = [(kind, cells, tag)] (dashboard_job.sitting_runs). An Android run is
    counted by launches (its cells rows). Any other is counted whole: its median length in the logs;
    else, in the weekly set (budget_s = the device's expected_hours), an even share of what the runs
    counted otherwise leave of it; else its rows' runs at DEFAULT_LAUNCH_S each. A retake's profile
    pair: the median of the pairs on record, else PROFILE_S."""
    stages = []
    for kind, cells, tag in runs:
        rows = None
        if platform_token == "android" and kind == "matrix":
            try:
                rows = stage_rows(os.path.join(root, cells), "android", key)
            except (OSError, ValueError, KeyError):
                rows = None
        stages.append(Stage(kind, cells, tag, rows=rows))
    profiles = [x for k, v in lengths["stages"].items() if k.startswith("profile|") for x in v[:HISTORY_KEEP]]
    whole = [s for s in stages if s.rows is None]
    for s in whole:
        if s.kind == "profile":
            s.expected = _median(lengths["stages"].get(s.key, [])[:3]) or _median(profiles) or PROFILE_S
        else:
            s.expected = _median(lengths["stages"].get(s.key, [])[:3])
    unknown = [s for s in whole if s.expected is None]
    if unknown and budget_s:
        # the runs counted by launch and the runs with a length on record take their part first
        counted = Sitting(stages, lengths)
        spent = sum(counted.stage_left(s, datetime.datetime.now(), {})[0] for s in stages if s.rows is not None)
        spent += sum(s.expected for s in whole if s.expected is not None)
        for s in unknown:
            s.expected = max((budget_s - spent) / len(unknown), MIN_SHARE_S)
    for s in unknown:
        if s.expected is None:
            s.expected = max(_launches(os.path.join(root, s.cells), platform_token, key) * DEFAULT_LAUNCH_S,
                             MIN_SHARE_S)
    return stages


# ---------------------------------------------------------------- the hold file

def note_hold(path, pid, fields):
    """Write `fields` into the hold at `path` while it names `pid` -> True when written. The file is
    replaced whole in one step (a temp file in the same directory, then os.replace), its own keys
    first and in their order, on one line as hold_cli.py writes it; a hold that is gone, is not a
    JSON object or names another pid is left as it is."""
    try:
        with open(path) as fh:
            cur = json.loads(fh.read().strip() or "null")
    except (OSError, ValueError):
        return False
    if not isinstance(cur, dict):
        return False
    try:
        if int(cur.get("pid")) != int(pid):
            return False
    except (TypeError, ValueError):
        return False
    new = {k: v for k, v in cur.items() if k not in FIELDS}
    new.update(fields)
    tmp = os.path.join(os.path.dirname(path) or ".", f".hold-eta-{os.getpid()}.tmp")
    try:
        with open(tmp, "w") as fh:
            json.dump(new, fh)
        os.replace(tmp, path)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False
    return True


class HoldNote:
    """The live side: read the job log from `offset` as it grows and keep the estimate in the hold.
    `warn` takes one line for the job log (dashboard_job.log); nothing here raises into the sitting."""

    def __init__(self, hold_path, pid, sitting, log_path, offset, warn=print, then=None):
        self.path, self.pid, self.sitting = hold_path, pid, sitting
        self.log_path, self.offset, self.warn = log_path, offset, warn
        self.then = then              # a words tail: what follows this hold (a retake sitting's weekly set)
        self.partial = b""            # a line the runner has not finished writing
        self.last = None              # (time written, expected release, events seen)
        self.off = False

    def _read(self, now):
        """Feed the log's complete new lines (bytes from `offset`: a read can end inside a line, or
        inside a character)."""
        self.sitting.observe(now)
        try:
            with open(self.log_path, "rb") as fh:
                fh.seek(self.offset)
                chunk = fh.read()
        except OSError:
            return
        self.offset += len(chunk)
        lines = (self.partial + chunk).split(b"\n")
        self.partial = lines.pop()
        for ln in lines:
            self.sitting.feed(ln.decode("utf-8", errors="replace"))

    def update(self, now=None, force=False):
        """Read the new log lines and rewrite the hold when the sitting moved (a run, a round, the
        gate), the time moved WRITE_MOVED_S, or WRITE_EVERY_S passed -> the (release, basis) written,
        or None."""
        if self.off:
            return None
        try:
            now = now or datetime.datetime.now()
            self._read(now)
            eta, basis = self.sitting.estimate(now)
            if self.then:
                basis += f"; {self.then}"
            last = self.last
            due = (force or last is None or self.sitting.events != last[2]
                   or abs((eta - last[1]).total_seconds()) >= WRITE_MOVED_S
                   or (now - last[0]).total_seconds() >= WRITE_EVERY_S)
            if not due:
                return None
            fields = {"expected_release": eta.strftime(RELEASE_FMT), "release_basis": basis,
                      "release_updated": now.strftime("%Y-%m-%d %H:%M:%S")}
            if not note_hold(self.path, self.pid, fields):
                self.warn(f"WARN hold release estimate not written: {self.path} is gone or not this "
                          f"pid's ({self.pid}); no more estimates this sitting")
                self.off = True
                return None
            self.last = (now, eta, self.sitting.events)
            self.warn(f"hold release estimate: {fields['expected_release']} ({basis})")
            return eta, basis
        except Exception as e:  # noqa: BLE001 — the estimate never stops a sitting
            self.warn(f"WARN hold release estimate off for this sitting: {type(e).__name__}: {e}")
            self.off = True
            return None

    def stop(self):
        """No write after this (the job calls it before it releases the hold)."""
        self.off = True


# ---------------------------------------------------------------- command line

# schedule.json platform -> cells-file platform token (dashboard_job.PLATFORM_TOKEN)
REPLAY_TOKEN = {"mac": "mac", "iphone": "ios", "android": "android"}


def _schedule(path):
    with open(path) as fh:
        return json.load(fh)


def _replay_runs(schedule, dev, halves, skip):
    runs = [("matrix", schedule["anchors"], "anchor")]
    files = [(h["cells"], re.sub(r"^.*-android-|\.cells$", "", os.path.basename(h["cells"])))
             for h in dev.get("split", [])] if halves else [(schedule["cells"], "set")]
    for e in dev.get("extra_cells", []):
        files.append((e["cells"], e.get("tag") or re.sub(r"^.*-android-|\.cells$", "", os.path.basename(e["cells"]))))
    runs += [("matrix", f, t) for f, t in files if f not in skip]
    return runs


def replay(log_path, key, schedule, lengths, halves=False, skip=(), cells_root=ROOT):
    """Feed a sitting's job log line by line -> [(time, the line that moved it, release, basis)], and
    the time its hold was released (None if the log never says)."""
    dev = schedule["devices"][key]
    sitting = None
    rows = []
    with open(log_path, errors="replace") as fh:
        lines = fh.readlines()
    for ln in lines:
        m = JOB_LINE.match(ln.rstrip("\n"))
        if sitting is None:
            if m and m.group(2).startswith("hold taken"):
                stages = plan_stages(_replay_runs(schedule, dev, halves, skip), dev, key, lengths, root=cells_root,
                                     platform_token=REPLAY_TOKEN.get(dev.get("platform"), dev.get("platform")),
                                     budget_s=float(dev.get("expected_hours") or 0) * 3600 or None)
                sitting = Sitting(stages, lengths)
                sitting.feed(ln)
                eta, basis = sitting.estimate(sitting.clock)
                rows.append((sitting.clock, "hold taken", eta, basis))
            continue
        if sitting.feed(ln):
            if sitting.released:
                break
            eta, basis = sitting.estimate(sitting.clock)
            rows.append((sitting.clock, ln.strip()[:90], eta, basis))
    return rows, (sitting.released if sitting else None)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("history", help="the lengths the estimate reads from the device's job logs")
    h.add_argument("key")
    h.add_argument("--before", help="only logs dated before YYYY-MM-DD")
    h.add_argument("--log-dir", default=os.path.join(ROOT, "logs", "dashboard-job"))
    h.add_argument("--json", action="store_true")
    r = sub.add_parser("replay", help="the estimate after each line of a sitting's log that moves it")
    r.add_argument("log")
    r.add_argument("key")
    r.add_argument("--schedule", default=os.path.join(ROOT, "ops", "dashboard-v1", "schedule.json"))
    r.add_argument("--before", help="history from logs dated before YYYY-MM-DD (default: the log's date)")
    r.add_argument("--log-dir", default=os.path.join(ROOT, "logs", "dashboard-job"))
    r.add_argument("--history", help="a history JSON (`history --json`) instead of the logs")
    r.add_argument("--halves", action="store_true", help="the sitting ran the storage halves")
    r.add_argument("--skip", action="append", default=[], help="a cells file the sitting skipped")
    r.add_argument("--cells-dir", default=ROOT, help="where the cells files' paths resolve")
    args = ap.parse_args(argv)
    if args.cmd == "history":
        lengths = history(args.log_dir, args.key, before=args.before)
        if args.json:
            print(json.dumps(lengths, indent=1, sort_keys=True))
        else:
            for kind in ("stages", "leads", "launches"):
                for k, v in sorted(lengths[kind].items()):
                    print(f"{kind:8} {k}: median {fmt_span(_median(v[:HISTORY_KEEP]))} of {len(v)}")
        return 0
    before = args.before or os.path.basename(args.log)[:10]
    if args.history:
        with open(args.history) as fh:
            lengths = json.load(fh)
    else:
        lengths = history(args.log_dir, args.key, before=before)
    rows, released = replay(args.log, args.key, _schedule(args.schedule), lengths, halves=args.halves,
                            skip=args.skip, cells_root=args.cells_dir)
    for t, what, eta, basis in rows:
        off = f"{(eta - released).total_seconds() / 60:+.0f} min" if released else "?"
        print(f"{t:%H:%M:%S}  release {eta:%H:%M} ({off})  {what}\n          {basis}")
    print(f"hold released: {released:%Y-%m-%d %H:%M:%S}" if released else "hold released: not in the log")
    return 0


if __name__ == "__main__":
    sys.exit(main())
