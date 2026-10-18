#!/usr/bin/env python3
"""autopilot — one Developer Device Platform lab unit's sitting by hand, end to end, in one command.

  ./bench autopilot --ddp <id> --project <p> --bucket gs://<b> [--cells FILE] [--runs N] [--suffix S]
                    [--dry-run] [--no-commit]
  ./bench autopilot --ddp akita-35 --dry-run --project <p> --bucket gs://<b>

Design: docs/dashboard-autopilot-v1.md section 10 (stage 5 of the autopilot). For a host with no phone
and no adb (a gLinux or gMac workstation): what the bench host's nightly job does for a lab unit, by the
job's own functions, then what follows a sitting there, in this order:

  1 sitting   scripts/dashboard_job.py ddp_slot: the doctor's DDP checks, the plan of `bench matrix
              --ddp --dry-run` within ops/autopilot/switch.json ddp_max_sessions (nothing is billed past
              it), `bench matrix <cells> --ddp <id>` billed to --project with its inputs in --bucket,
              SESSION.json, the job's ledger line and log (logs/dashboard-job/<date>-<key>.log)
  2 post      scripts/dashboard_post.py over the sitting's dir: the account name scrubbed,
              scripts/session_check.py, one local commit of the dir and results/summary rebuilt from the
              git index when it passes (REVIEW.md in the dir when it does not); the private page only
              where the switch's page_repo holds a build.py, else one line; the red segment's retakes and
              bisect requests; push and publish only as the switch says (committed: all off)
  3 table     scripts/render_dashboard.py -> DASHBOARD.md and .dashboard/ (local, gitignored)
  4 red       scripts/regression_watch.py --json --markdown: the team page's red points over the summary
  5 requests  logs/dashboard-job/retakes.json and bisect-requests.json: the pending ones, and each bisect
              request's scripts/engine_bisect.py command or why it has none
  then one screen: the sitting's verdict and campaign, the check, the commit, the summary's lines, the
  table, the red points, the requests and what a person does next (logs/autopilot/<campaign>/summary.txt,
  beside the post's output and the red points as JSON and markdown).

The lab unit: the schedule.json entry whose ddp_id is <id> (s26-ddp for m1q-36), else one made here from
android/ddp/devices.json: key <scheduleKey>-ddp (the product when the id has no schedule key),
identifier "<model> (DDP <id>)" as the summary's rows of the id name it (else the catalog's display:
the summary takes a unit's ro.product.model from its records, so an id with no row yet is a guess),
cells: --cells, else matrices/dashboard-ddp-v1-android-<scheduleKey>.cells when that file exists, else
matrices/ddp-first-run.cells. --runs N runs a copy of the cells file with runs=N on every row
(logs/autopilot/cells/; SESSION.json names the copy, the campaign's ddp/plan-<n>.json the runs).

Where this differs from the nightly job (each a wrapper here; scripts/dashboard_job.py is unchanged):
  - the switch's ddp_weekly is not read: it turns the bench host's nightly lab-unit slot on and off
    (false once a Googler runs the DDP set on their side); a run by hand is its own go, under the same
    ddp_max_sessions cap
  - --project / --bucket reach `bench matrix --ddp` as BENCH_DDP_PROJECT / BENCH_DDP_BUCKET (the job's
    plan and run pass neither)
  - a host without gtimeout (Linux): GNU timeout under that name, logs/autopilot/bin/gtimeout
  - --dry-run calls no network: the doctor's DDP checks run without `gcloud auth print-access-token`
    (it can refresh the token over the network; the run checks the sign-in before anything is billed),
    the plan reads the local Hugging Face cache only, and steps 2 and 3 print what they would do
  - --no-commit: the post's dry run over the sitting (the check, the message it would commit; nothing
    scrubbed, committed or written)

Exit codes: the sitting's when it is not 0 (scripts/dashboard_job.py: 2 config, 3 a sitting already
running on the key, 5 not ready or no record, 6 timeout); else the post's (0 committed, or nothing new;
1 held, or a step after the commit failed; 2 usage); a dry run 0.
"""
import argparse
import collections
import contextlib
import csv
import datetime
import io
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import dashboard_job as dj  # noqa: E402
import dashboard_post as dp  # noqa: E402
import regression_watch as rw  # noqa: E402

FIRST_RUN_CELLS = "matrices/ddp-first-run.cells"
WEEKLY_CELLS = "matrices/dashboard-ddp-v1-android-{key}.cells"
OUT_REL = os.path.join("logs", "autopilot")
SIGN_IN = ["gcloud", "auth", "print-access-token"]
STEPS = "1 sitting -> 2 post (scrub, check, local commit) -> 3 table -> 4 red points -> 5 requests"


class Usage(Exception):
    """exit 2"""


def say(msg):
    dj.log("autopilot: " + msg)


def rel(p):
    return os.path.relpath(p, ROOT) if os.path.isabs(p) and p.startswith(ROOT + os.sep) else p


# ---------------------------------------------------------------- the lab unit

def catalog():
    with open(os.path.join(ROOT, "android", "ddp", "devices.json")) as fh:
        return {k: v for k, v in json.load(fh).items() if not k.startswith("_")}


def seen_identifier(ddp_id, rows):
    """The device string the summary gives this id's records, "<ro.product.model> (DDP <id>)" (the most
    rows), or None when no record of the id is in it."""
    seen = collections.Counter(r["device"] for r in rows if (r.get("device") or "").endswith(f" (DDP {ddp_id})"))
    return seen.most_common(1)[0][0] if seen else None


def lab_unit(ddp_id, cells=None):
    """(key, the schedule entry dashboard_job.ddp_sitting takes, notes) for a DDP catalog id."""
    units = catalog()
    if ddp_id not in units:
        raise Usage(f"--ddp {ddp_id}: not in android/ddp/devices.json ({', '.join(sorted(units))})")
    with open(os.path.join(ROOT, "ops", "dashboard-v1", "schedule.json")) as fh:
        devices = json.load(fh).get("devices", {})
    for key, dev in devices.items():
        if dev.get("platform") == "ddp" and dev.get("ddp_id") == ddp_id:
            return key, dict(dev, cells=cells or dev.get("cells")), [f"schedule.json entry {key}"]
    c = units[ddp_id]
    key = f"{c.get('scheduleKey') or c.get('product') or ddp_id}-ddp"
    if key in devices:
        key = f"{key}-{ddp_id}"
    ident = seen_identifier(ddp_id, dj.load_rows())
    notes = [f"no schedule.json entry for {ddp_id}: key {key} made here"]
    if not ident:
        ident = f"{c.get('display') or ddp_id} (DDP {ddp_id})"
        notes.append(f"identifier {ident!r} from devices.json's display (no record of {ddp_id} in the summary "
                     "yet; the records name the unit by its ro.product.model)")
    weekly = WEEKLY_CELLS.format(key=c.get("scheduleKey")) if c.get("scheduleKey") else None
    default = weekly if weekly and os.path.isfile(os.path.join(ROOT, weekly)) else FIRST_RUN_CELLS
    return key, {"platform": "ddp", "display": f"{c.get('display') or ddp_id} (DDP {ddp_id})", "identifier": ident,
                 "ddp_id": ddp_id, "cells": cells or default}, notes


def cells_arg(path):
    """--cells as the job runs it (`bench matrix <cells>` in the checkout): relative to the checkout."""
    p = os.path.abspath(path)
    if not os.path.isfile(p):
        raise Usage(f"--cells {path}: no such file")
    return os.path.relpath(p, ROOT) if p.startswith(ROOT + os.sep) else p


def with_runs(cells, n):
    """A copy of the cells file with runs=N on every row (logs/autopilot/cells/<name>-runs<N>.cells) -> its path."""
    src = os.path.join(ROOT, cells) if not os.path.isabs(cells) else cells
    out = []
    with open(src) as fh:
        for raw in fh:
            code, hash_, comment = raw.rstrip("\n").partition("#")
            toks = code.split()
            if toks:
                code = " ".join([t for t in toks if not t.startswith("runs=")] + [f"runs={n}"]) + (" " if hash_ else "")
            out.append(code + hash_ + comment + "\n")
    d = os.path.join(ROOT, OUT_REL, "cells")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{os.path.splitext(os.path.basename(src))[0]}-runs{n}.cells")
    with open(path, "w") as fh:
        fh.write(f"# {rel(src)} with runs={n} on every row (scripts/autopilot.py --runs)\n" + "".join(out))
    return rel(path)


# ---------------------------------------------------------------- the host

def gtimeout_note(dry):
    """The job runs `gtimeout` (GNU coreutils' name on macOS). Linux has GNU timeout as `timeout`: that
    file under the job's name, first on PATH -> a note, or None when gtimeout is there."""
    if shutil.which("gtimeout"):
        return None
    t = shutil.which("timeout")
    if not t:
        raise dj.NotReady("neither gtimeout nor timeout on PATH (GNU coreutils: brew install coreutils)")
    d = os.path.join(ROOT, OUT_REL, "bin")
    if not dry:
        os.makedirs(d, exist_ok=True)
        link = os.path.join(d, "gtimeout")
        if os.path.realpath(link) != os.path.realpath(t):
            if os.path.lexists(link):
                os.remove(link)
            os.symlink(t, link)
    os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
    return f"gtimeout: none on PATH; GNU timeout {t} under that name ({rel(d)}/gtimeout" + (
        ", linked by the run)" if dry else ")")


def doctor_offline():
    """dashboard_job.ddp_doctor for a dry run: scripts/doctor.py check_ddp in this process with its one
    network call left out. `gcloud auth print-access-token` is not run (its line says so); gcloud on the
    PATH, huggingface_hub and the 9 engine files are checked as the run checks them. Any other command
    the check would start reads as failed, never as passed."""
    import doctor
    started = []

    class NoNetwork:  # doctor's subprocess module during the check
        DEVNULL, PIPE, STDOUT = subprocess.DEVNULL, subprocess.PIPE, subprocess.STDOUT
        TimeoutExpired, CalledProcessError = subprocess.TimeoutExpired, subprocess.CalledProcessError

        @staticmethod
        def run(cmd, *a, **kw):
            started.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 0 if list(cmd) == SIGN_IN else 1)

    del doctor._RESULTS[:]
    real, doctor.subprocess = doctor.subprocess, NoNetwork
    try:
        doctor.check_ddp(True)
    finally:
        doctor.subprocess = real
    results = [(doctor.SKIP, n, "not checked in a dry run: gcloud auth print-access-token can refresh the token "
                                "over the network (the run checks it first)")
               if n == "gcloud sign-in" and SIGN_IN in started else (s, n, d) for s, n, d in doctor._RESULTS]
    out = "\n".join(f"{s:4}  {n}  {d}".rstrip() for s, n, d in results)
    return (1 if any(s == doctor.FAIL for s, _, _ in results) else 0), out


@contextlib.contextmanager
def job_overrides(dry, cap):
    """What this command changes in scripts/dashboard_job.py's lab-unit sitting, for one call of ddp_slot
    -> {"sitting": its (code, reason, dir, dirs), "error": a NotReady / ConfigError it raised, "handed": the
    (code, dirs) it would hand the post}: load_switch reads (True, the switch's cap): ddp_weekly is the bench
    host's nightly slot, not this command's; ddp_doctor is doctor_offline in a dry run; ddp_sitting is
    kept as it is, its result noted; post_sitting hands nothing over: the post is step 2 here."""
    kept = {}
    real = {n: getattr(dj, n) for n in ("load_switch", "ddp_doctor", "ddp_sitting", "post_sitting")}

    def sitting(*a, **kw):
        try:
            kept["sitting"] = real["ddp_sitting"](*a, **kw)
        except (dj.NotReady, dj.ConfigError) as e:
            kept["error"] = e
            raise
        return kept["sitting"]

    def hand_over(code, dirs, dry_run, extra=()):
        kept["handed"] = (code, list(dirs))
        return None

    dj.load_switch = lambda path=None: (True, cap)
    dj.ddp_sitting, dj.post_sitting = sitting, hand_over
    if dry:
        dj.ddp_doctor = doctor_offline
    try:
        yield kept
    finally:
        for n, f in real.items():
            setattr(dj, n, f)


class Tee(io.TextIOBase):
    """stdout to the terminal and to the given files (the job log, the step's own file)."""

    def __init__(self, *outs):
        self.outs = [o for o in outs if o]

    def write(self, s):
        for o in self.outs:
            o.write(s)
        return len(s)

    def flush(self):
        for o in self.outs:
            o.flush()


# ---------------------------------------------------------------- steps 2-5

def page_plan(sw):
    """The post's page step as it would read (dashboard_post.page_step's rule)."""
    repo = sw["page_repo"]
    if not repo:
        return "skipped: no page repo (switch page_repo)"
    if not os.path.isfile(os.path.join(repo, "build.py")):
        return f"skipped: no build.py in {repo}"
    return f"would build {repo}/build.py and run its four checks"


def post_step(dirs, dry_run, out_dir):
    """dashboard_post.main over the sitting's dirs, its output also in <out_dir>/post.txt -> (exit, the
    post's ledger row: check, bench_commit, summary_lines, page, note)."""
    row = {}
    real = dp.post

    def post_kept(top, dirs_, sw, args, row_, tmp):
        try:
            return real(top, dirs_, sw, args, row_, tmp)
        finally:
            row.update(row_)

    dp.post = post_kept
    try:
        with open(os.path.join(out_dir, "post.txt"), "w") as fh, contextlib.redirect_stdout(
                Tee(sys.stdout, fh, dj._LOG)):
            code = dp.main((["--dry-run"] if dry_run else []) + [os.path.join(ROOT, d) for d in dirs])
    finally:
        dp.post = real
    return code, row


def table_step(dry, campaign):
    """scripts/render_dashboard.py -> (its line, this campaign's cells on the table: [(arm, model, task,
    status, decode, n)])."""
    script = os.path.join(ROOT, "scripts", "render_dashboard.py")
    if dry:
        return "would render DASHBOARD.md and .dashboard/ (scripts/render_dashboard.py; local, gitignored)", []
    rc, out = dj.sh([sys.executable, script], timeout=300)
    line = (out.strip().splitlines() or ["(no output)"])[-1]
    if rc != 0:
        return f"render_dashboard.py exit {rc}: {line}", []
    devs = {r["device"] for r in dj.load_rows() if r["campaign"] == campaign}
    cells = []
    try:
        with open(os.path.join(ROOT, ".dashboard", "dashboard-v1.csv"), newline="") as fh:
            for r in csv.DictReader(fh):
                if r.get("device") in devs:
                    cells.append((r.get("arm"), r.get("model"), r.get("task"), (r.get("status") or "?").split(":")[0],
                                  r.get("decode_tps"), r.get("n")))
    except OSError:
        pass
    return line, cells


def red_step(dry, out_dir, campaign):
    """scripts/regression_watch.py over the summary (no --compare) -> (exit, its summary line, red lines,
    how many of them are this campaign's)."""
    cmd = [sys.executable, os.path.join(ROOT, "scripts", "regression_watch.py")]
    if not dry:
        cmd += ["--json", os.path.join(out_dir, "red.json"), "--markdown", os.path.join(out_dir, "red.md")]
    rc, out = dj.sh(cmd, timeout=600)
    lines = out.strip().splitlines()
    red = [ln.strip() for ln in lines if ln.lstrip().startswith("red ")]
    mine = sum(1 for ln in red if f"| {os.path.basename(campaign)} |" in ln) if campaign else 0
    head = next((ln for ln in lines if ln.startswith("regression:")), lines[-1] if lines else "(no output)")
    return rc, head, red, mine


def requests_step():
    """The pending retakes and bisect requests in logs/dashboard-job/ -> (lines, next-step lines)."""
    state = os.path.join(ROOT, "logs", "dashboard-job")
    tool = os.path.isfile(os.path.join(ROOT, rw.BISECT_TOOL))
    try:
        retakes = [e for e in rw.load_state(state, rw.RETAKES) if e.get("status") == "pending"]
        requests = [e for e in rw.load_state(state, rw.REQUESTS) if e.get("status") == "pending"]
    except rw.Config as e:
        return [f"state unreadable: {e}"], []
    lines = [f"retakes pending {len(retakes)}, bisect requests pending {len(requests)} "
             f"({rel(os.path.join(state, rw.RETAKES))}, {rel(os.path.join(state, rw.REQUESTS))})"]
    nxt = []
    for e in retakes:
        lines.append(f"  retake {e.get('id')}: {e.get('display') or e.get('device')} {e.get('model')} "
                     f"{e.get('backend')} {e.get('task')} (the attached phone's sitting: the bench host's job runs it)")
    for e in requests:
        lines.append(f"  bisect {e.get('id')}: {e.get('good')} -> {e.get('bad')}, {e.get('verdict')}, route "
                     f"{e.get('route')}" + (f"; draft {e.get('draft')}" if e.get("draft") else ""))
        if e.get("command"):
            nxt.append(f"bisect {e.get('id')}: {e['command']}" + ("" if tool else "  (needs the tool, below)"))
        else:
            nxt.append(f"bisect {e.get('id')}: no command ({e.get('why_no_command')})")
    if not tool:
        lines.append(f"  {rw.BISECT_TOOL} is not in this checkout: it comes after PR #4 (LiteRT-LM Android "
                     "builds from a git ref), with the bisect commit on top of it")
    return lines, nxt


# ---------------------------------------------------------------- one screen

def session_of(d):
    try:
        with open(os.path.join(ROOT, d, "SESSION.json")) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def summary_lines(path):
    try:
        with open(path, "rb") as fh:
            return fh.read().count(b"\n")
    except OSError:
        return None


def again(args, drop=("--dry-run",)):
    """This command without the flags in `drop`, for a next-step line."""
    out = ["./bench autopilot", f"--ddp {args.ddp}"]
    out += [f"--{k} {getattr(args, k)}" for k in ("project", "bucket", "cells", "runs", "suffix")
            if getattr(args, k) is not None]
    out += [f for f, on in (("--no-commit", args.no_commit), ("--dry-run", args.dry_run)) if on and f not in drop]
    return " ".join(out)


def held_rules(row):
    """The rules the post's check held on (its ledger note "held: <dirs> (rules: a, b); …"), [] when none."""
    note = row.get("note") or ""
    if "held: " not in note or "(rules: " not in note:
        return []
    return note.split("(rules: ", 1)[1].split(")", 1)[0].split(", ")


def post_lines(args, camp, post):
    """The check, commit, summary and page lines of the one screen, and the next steps they call for."""
    pcode, row = post
    rules = held_rules(row)
    checks = (row.get("check") or "").split()          # "<dir>=<verdict>" per dir
    verdicts = " ".join(c.split("=", 1)[-1] if len(checks) == 1 else c for c in checks)
    L = [f"check     {verdicts or '(not reached)'}" + (f" (rules: {', '.join(rules)})" if rules else "")]
    nxt = [f"{r}: {dp.ACTION.get(r, 'a person reviews it')}" for r in rules]
    if row.get("bench_commit"):
        L += [f"commit    {row['bench_commit'][:12]} on {dp.branch_of(ROOT) or '?'} (local), push: "
              f"{row.get('push_bench') or '?'}",
              f"summary   results/summary/device-runs.csv {row.get('summary_lines')} lines (the commit)",
              f"page      {row.get('page') or '?'}"]
        nxt.append(f"the commit is local: git show --stat {row['bench_commit'][:12]}")
    else:
        why = ("--no-commit: the post's dry run, nothing written" if args.no_commit
               else "held: a sitting is committed whole or not at all" if rules
               else (row.get("note") or "nothing new").split("; ")[0])
        n = summary_lines(os.path.join(ROOT, "results", "summary", "device-runs.csv"))
        L += [f"commit    none ({why})",
              f"summary   results/summary/device-runs.csv {n} lines on disk (bench matrix rebuilt it from this "
              "checkout's results/raw; not committed)"]
        if args.no_commit:
            nxt.append(f"the findings in full: python3 scripts/session_check.py {camp} --markdown <file>; "
                       f"commit once it passes: python3 scripts/dashboard_post.py {camp}")
        elif rules:
            nxt.append(f"read {camp}/REVIEW.md (each finding and what a person does), then post again: "
                       f"python3 scripts/dashboard_post.py {camp}")
        nxt.append("results/summary/ on disk holds this sitting's rows: `git checkout -- results/summary` gives "
                   "HEAD's back")
    red = [n for n in (row.get("note") or "").split("; ") if n.startswith("red: ")]
    if red:
        L.append(f"post red  {red[0][len('red: '):]}")
    if pcode not in (0, 1):
        nxt.append(f"the post exit {pcode}: read logs/autopilot/{os.path.basename(camp)}/post.txt")
    return L, nxt


def screen(args, key, unit, code, kept, post, table, red, reqs):
    """The one screen -> its lines."""
    dry = args.dry_run
    sitting = kept.get("sitting") or ()
    camp = sitting[2] if len(sitting) > 2 else None
    s = session_of(camp) if camp and not dry else {}
    reason = sitting[1] if sitting else str(kept.get("error") or "")
    L = [f"=== autopilot: {unit['display']}, key {key}" + (" [dry-run: nothing billed, nothing written]" if dry else ""),
         f"sitting   {dj.VERDICT_NAME.get(code, str(code))}" + (f" ({reason})" if reason and reason != "ok" else "")
         + (f" — {camp}" if camp else "")]
    nxt = []
    d = s.get("ddp") or {}
    if d:
        L.append(f"          Device Run sessions {', '.join(d.get('sessions') or []) or 'none'}; {d.get('jobs')} jobs "
                 f"{d.get('results') or ''}, {d.get('device_minutes')} device-min; {s.get('cells_with_records')} of "
                 f"{s.get('cells_expected')} cells with records")
    if code != dj.EXIT_OK:
        log_hint = f"logs/dashboard-job/{datetime.date.today().isoformat()}-{key}.log"
        if "holds a sitting already" in reason:
            nxt.append(f"a second sitting today takes a suffix: {again(args, ())} --suffix r2")
        elif code == dj.EXIT_TIMEOUT:
            nxt.append(f"read {log_hint}: a session still running on DDP is resumed with android/ddp/run_ddp.py "
                       "--resume <operation> (ddp/operation-create-<n>.json in the campaign dir)")
        else:
            nxt.append(f"fix what the reason says (the job log: {log_hint}), then run the same command again")
    if dry:
        sw = dp.load_switch(os.path.join(ROOT, dp.SWITCH_REL))
        L += ["post      would run scripts/dashboard_post.py over the dir: the scrub, scripts/session_check.py, "
              "a local commit of the dir + results/summary from the git index when it passes",
              f"          page {page_plan(sw)}; push_bench / push_page / publish "
              + " / ".join("on" if sw[k] else "off" for k in dp.SWITCH_KEYS)]
    elif post is not None:
        lines, more = post_lines(args, camp, post)
        L += lines
        nxt += more
    if table is not None:
        line, cells = table
        L.append(f"table     {line}")
        if cells:
            by = collections.Counter(c[3] for c in cells)
            L.append("          this unit's cells: " + ", ".join(f"{k} {v}" for k, v in sorted(by.items())))
            for arm, model, task, status, dec, n in cells[:4]:
                L.append(f"          {arm} {model} {task}: {status}" + (f", decode {dec} tok/s (n={n})" if dec else ""))
    if red is not None:
        rc, head, lines, mine = red
        L += [f"red       {head}" + ("" if rc == 0 else f" (exit {rc})"),
              f"          {len(lines)} red points, {mine} of them this sitting's"
              + ("" if mine else " (a lab unit's rows make no series of the page's rule)")]
    if reqs is not None:
        lines, more = reqs
        L.append(f"requests  {lines[0]}")
        L += [f"          {ln.strip()}" for ln in lines[1:]]
        nxt += more
    if dry and code == dj.EXIT_OK:
        billed = args.project or "run_ddp.py's default project"
        nxt.insert(0, f"the run, billed to {billed}: {again(args)}")
    if camp and not dry:
        L.append(f"log       logs/dashboard-job/{datetime.date.today().isoformat()}-{key}.log; "
                 f"{OUT_REL}/{os.path.basename(camp)}/ (summary.txt, post.txt, red.json, red.md)")
    L += [f"next      {n}" for n in (nxt or ["nothing: the sitting is committed and nothing is pending"])]
    return L


# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ddp", required=True, metavar="DEVICE_ID", help="a DDP catalog id (android/ddp/devices.json)")
    ap.add_argument("--project", help="the Cloud project the sessions are billed to (default: run_ddp.py's)")
    ap.add_argument("--bucket", help="gs://<bucket> for the inputs and session outputs (default: run_ddp.py's)")
    ap.add_argument("--cells", help="the cells file (default: the lab unit's weekly file, else "
                                    f"{FIRST_RUN_CELLS})")
    ap.add_argument("--runs", type=int, help="runs= of every row (a copy of the cells file under logs/autopilot/)")
    ap.add_argument("--suffix", help="campaign-name suffix for a second sitting the same day")
    ap.add_argument("--dry-run", action="store_true", help="every step's plan; no network, nothing billed")
    ap.add_argument("--no-commit", action="store_true", help="the sitting and the check; nothing committed")
    args = ap.parse_args(argv)
    if args.runs is not None and args.runs < 1:
        ap.error("--runs: 1 or more")
    try:
        key, unit, notes = lab_unit(args.ddp, cells_arg(args.cells) if args.cells else None)
        if args.runs is not None:
            unit["cells"] = with_runs(unit["cells"], args.runs)
        on, cap = dj.load_switch()
    except (Usage, dj.ConfigError, OSError, ValueError) as e:
        print(f"autopilot: {e}", file=sys.stderr)
        return dj.EXIT_CONFIG
    if not args.dry_run:
        other = dj.device_lock(key)
        if other:
            print(f"autopilot: a sitting is already running on {key} (pid {other}); exit {dj.EXIT_BUSY}")
            return dj.EXIT_BUSY
        dj.open_log(key)
    try:
        return run(args, key, unit, notes, on, cap)
    finally:
        dj._unlock(f".job.lock.{key}")


def run(args, key, unit, notes, on, cap):
    dry = args.dry_run
    for k, v in (("BENCH_DDP_PROJECT", args.project), ("BENCH_DDP_BUCKET", args.bucket)):
        if v:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)
    say(f"lab unit {unit['display']}, key {key}, cells {unit['cells']}, project "
        f"{args.project or '(run_ddp.py default)'}, bucket {args.bucket or '(run_ddp.py default)'}"
        + (" [dry-run: no network, nothing billed]" if dry else ""))
    say(f"steps: {STEPS}")
    for n in notes:
        say(n)
    say(f"switch: ddp_max_sessions {cap} caps the plan (ops/autopilot/switch.json); its ddp_weekly ({str(on).lower()}) "
        "is the bench host's nightly slot, not read by a run by hand")
    try:
        note = gtimeout_note(dry)
    except dj.NotReady as e:
        print(f"autopilot: {e}", file=sys.stderr)
        return dj.EXIT_DEVICE
    if note:
        say(note)
    if not dry:
        say(f"the run's output: logs/dashboard-job/{datetime.date.today().isoformat()}-{key}.log")
    ns = argparse.Namespace(dry_run=dry, post_page_out=None, no_page_commit=False)
    with job_overrides(dry, cap) as kept:
        code = dj.ddp_slot({"devices": {key: unit}}, key, unit, ns, cells=unit["cells"], suffix=args.suffix)
    sitting = kept.get("sitting") or ()
    camp = sitting[2] if len(sitting) > 2 else None
    out_dir = None
    if camp and not dry:
        out_dir = os.path.join(ROOT, OUT_REL, os.path.basename(camp))
        os.makedirs(out_dir, exist_ok=True)
    post = table = red = reqs = None
    handed = kept.get("handed") or (code, [])
    if dry:
        say("2 post: printed in the summary below (the dir does not exist in a dry run)")
    elif code == dj.EXIT_OK and handed[1]:
        say(f"2 post: scripts/dashboard_post.py {' '.join(handed[1])}" + (" --dry-run (--no-commit)" if args.no_commit else ""))
        post = post_step(handed[1], args.no_commit, out_dir)
    if code == dj.EXIT_OK:
        say("3 table: scripts/render_dashboard.py")
        table = table_step(dry, camp)
        say("4 red: scripts/regression_watch.py" + ("" if dry else " --json --markdown"))
        red = red_step(dry, out_dir, camp if not dry else None)
    say("5 requests: logs/dashboard-job/retakes.json, bisect-requests.json")
    reqs = requests_step()
    lines = screen(args, key, unit, code, kept, post, table, red, reqs)
    text = "\n".join(lines) + "\n"
    print("\n" + text, end="", flush=True)
    if dj._LOG:
        dj._LOG.write("\n" + text)
        dj._LOG.flush()
    if out_dir:
        with open(os.path.join(out_dir, "summary.txt"), "w") as fh:
            fh.write(time.strftime("%F %T %Z") + "\n" + text)
    if code != dj.EXIT_OK or dry:
        return code
    return post[0] if post else dj.EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
