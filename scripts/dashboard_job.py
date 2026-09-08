#!/usr/bin/env python3
"""dashboard_job — one scheduled unit of the dashboard v1 recurring job.

  ./bench dashboard-job <device-key | auto> [--dry-run]
  python3 scripts/dashboard_job.py pixel8a --dry-run     # preflight + plan, no capture

Design: docs/dashboard-recurring-job-v1.md. Config: ops/dashboard-v1/schedule.json
(device keys, firing times, admission thresholds, retry policy). One invocation is
one sitting on one device. `auto` — what launchd runs every night at the times in
schedule.json "slots" — chooses the device: among the devices with no admitted
dashboard session since Monday 00:00 local, the attached, unheld ones (the iPhone
only inside its `auto_window` after `auto_idle_hours` without a record, the Mac only
while no heavy export pipeline runs), the one whose last admitted session is the
oldest (never measured = oldest; ties in schedule order). A candidate whose
preflight says busy or not ready is passed over for the next one; when every
pending device is busy the firing polls per "retry" and chooses again. Each
device is measured once a week; a firing with nothing pending exits 0 and leaves
no ledger line. The sitting itself does only what a careful operator did by hand
for the first pass, in this order:

  preflight   device attached / unlocked / not held by a sibling lane / no foreign
              engine process / storage floor / host runner idle
  hold        take the sibling lane's device hold for the run (hold_cli.py)
  phase A     ./bench matrix matrices/anchors.cells   -> <campaign>-anchor
  admission   the fresh anchor against the newest ADMITTED session's anchor on this
              device: short / collapse / thermal rules (schedule.json "admission")
  phase B     ./bench matrix <dashboard cells>        -> <campaign>   (or one run per
              storage half, rotating pushed model copies out between halves)
  close       SESSION.json in every campaign dir it created, a ledger line under
              logs/dashboard-job/, DASHBOARD.md re-rendered, hold released

Exit codes (ledger + launchd log):
  0 admitted and captured        3 busy — held, guarded, throttled, runner active
  4 aborted at admission         5 device not ready — absent, locked, no space, doctor FAIL
  6 whole-session timeout        2 configuration error
Busy and aborted sittings retry inside the firing's window per schedule.json
"retry"; one job instance per host (logs/dashboard-job/.job.lock) — a second
`auto` beside a running one exits 3 at once.

What the job never does: commit, push, edit a cells file, delete a raw record.
The one destructive step is deleting pushed MODEL COPIES on a storage-limited
phone between halves (the host HF cache is the source), together with their
engine caches and firstEver markers — the markers must go with the caches, or
the next run 1 rebuilds the cache unlabelled and pools as speed.
"""
import argparse
import csv
import datetime
import fcntl
import json
import os
import re
import statistics
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from render_dashboard import CSV_PLATFORM, REGIME, load_admission, load_cells  # noqa: E402

PY = sys.executable
SCHEDULE = os.path.join(ROOT, "ops", "dashboard-v1", "schedule.json")
LOG_DIR = os.path.join(ROOT, "logs", "dashboard-job")
SUMMARY_CSV = os.path.join(ROOT, "results", "summary", "device-runs.csv")
# a dashboard session's campaign (design §1): <date>-dashboard-v1-<device>[-<half>]-<plat>;
# the admission probe is <date>-dashboard-v1-<device>-anchor-<plat> and is not a session
DASHBOARD_CAMPAIGN = "-dashboard-v1-"
ANCHOR_CAMPAIGN_RE = r"-dashboard-v1-.*-anchor-"
# bench --platform name -> cells-file platform token (= campaign dir suffix)
PLATFORM_TOKEN = {"mac": "mac", "iphone": "ios", "android": "android"}
ANDROID_DEV_DIR = "/data/local/tmp/llmbench"
# the Mac runner's own guard, replicated so the job reports BUSY and polls
# instead of letting `bench matrix` fail once and give up the slot
MAC_HEAVY_RE = (r"coreai\.llm\.export|release/llm-benchmark |export_simple_template\.py|"
                r"scratchpad/export_[A-Za-z0-9_]*\.py|coreai-models/\.venv/bin/python|"
                r"coreai-build compile")

EXIT_OK, EXIT_CONFIG, EXIT_BUSY, EXIT_ABORTED, EXIT_DEVICE, EXIT_TIMEOUT = 0, 2, 3, 4, 5, 6
VERDICT_NAME = {EXIT_OK: "OK", EXIT_CONFIG: "CONFIG", EXIT_BUSY: "BUSY",
                EXIT_ABORTED: "ABORTED", EXIT_DEVICE: "DEVICE", EXIT_TIMEOUT: "TIMEOUT"}


class Busy(Exception):
    """Retry later inside the slot window (exit 3)."""


class NotReady(Exception):
    """Needs a human (exit 5)."""


# ---------------------------------------------------------------- utilities

_LOG = None


def log(msg):
    line = f"[{time.strftime('%F %T')}] {msg}"
    print(line, flush=True)
    if _LOG:
        _LOG.write(line + "\n")
        _LOG.flush()


def sh(cmd, timeout=60, env=None, cwd=ROOT):
    """(rc, combined output) — never raises on a non-zero exit."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           env=env, cwd=cwd)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired as e:
        return 124, f"timeout after {timeout}s: {e}"
    except OSError as e:
        return 127, str(e)


def expand(p):
    return os.path.expanduser(p) if p else p


def pid_alive(pid):
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (ValueError, TypeError, OSError):
        return False
    return True


def read_hold(path):
    """None = no hold; {} = unowned legacy hold; dict = owned hold (sibling
    lane's device_hold.py format: {pid, script, device, started})."""
    path = expand(path)
    if not path or not os.path.exists(path):
        return None
    try:
        text = open(path).read().strip()
        return json.loads(text) if text else {}
    except (OSError, ValueError):
        return {}


def pgrep(pattern):
    rc, out = sh(["pgrep", "-fl", pattern])
    mine = {os.getpid(), os.getppid()}
    lines = [ln for ln in out.splitlines()
             if ln.strip() and int(ln.split()[0]) not in mine
             and "dashboard_job.py" not in ln]
    return lines


# ---------------------------------------------------------------- preflight

def check_holds(dev, dry):
    """A live foreign pid in any of the device's hold files = busy. An
    unowned zero-byte hold cannot be attributed and is treated as busy too
    (someone's driver wrote it; leaving it alone costs a slot, taking the
    phone costs a measurement — device-busy-is-probeable)."""
    for path in [dev.get("hold")] + list(dev.get("hold_also_check", [])):
        if not path:
            continue
        h = read_hold(path)
        if h is None:
            continue
        if not h:
            raise Busy(f"unowned hold present: {path}")
        if h.get("pid") not in (None, os.getpid()) and pid_alive(h.get("pid")):
            raise Busy(f"device held by pid {h.get('pid')} ({h.get('script')}) "
                       f"since {h.get('started')}: {path}")
        log(f"stale hold from pid {h.get('pid')} ({h.get('script')}) at {path} — "
            "not live; the acquire step will clear it" + (" [dry-run]" if dry else ""))


def adb_cmd(serial, *args):
    return ["adb", "-s", serial] + list(args)


def android_free_gb(serial):
    rc, out = sh(adb_cmd(serial, "shell", "df -k /data | tail -1"))
    parts = out.split()
    if rc != 0 or len(parts) < 4:
        return None
    try:
        return int(parts[3]) / 1e6  # KB -> GB
    except ValueError:
        return None


def android_state(serial):
    """adb's state word for the serial ('device', 'unauthorized', ...) or None."""
    rc, out = sh(["adb", "devices"])
    return next((ln.split()[1] for ln in out.splitlines()[1:]
                 if ln.strip() and ln.split()[0] == serial), None)


def iphone_attached(udid):
    rc, out = devicectl("list", "devices")
    row = next((ln for ln in out.splitlines() if udid in ln), None)
    return row is not None and ("available" in row or "connected" in row)


def mac_guard():
    """Busy when a Mac capture runs or a heavy pipeline would contend for
    unified memory (the runner's own guard, replicated so the job reports
    BUSY and polls instead of letting `bench matrix` fail once)."""
    if pgrep("bench_matrix_mac.sh") or pgrep("yardstick run"):
        raise Busy("a Mac capture is already running")
    rc, out = sh(["ps", "aux"])
    heavy = [ln for ln in out.splitlines() if re.search(MAC_HEAVY_RE, ln) and "grep" not in ln]
    if heavy:
        raise Busy(f"heavy pipeline running (unified-memory contention): {heavy[0][:120]}")


def preflight_android(dev, dry):
    serial = dev["serial"]
    state = android_state(serial)
    if state is None:
        raise NotReady(f"{serial} not visible to adb — plug it in")
    if state != "device":
        raise NotReady(f"{serial} adb state {state!r} — authorize USB debugging")
    for ln in pgrep("run_campaign.py|run_cell.py"):
        # run_cell.py names its phone (--serial); a campaign driver does not,
        # so an unattributed driver counts as busy (conservative)
        m = re.search(r"--serial\s+(\S+)", ln)
        if m and m.group(1) != serial:
            continue
        raise Busy(f"host driver running: {ln.strip()[:160]}")
    # the campaign lock (run_campaign.py takes it for real; this is a probe)
    lock_path = f"/tmp/edge-llm-bench-android-{serial}.lock"
    try:
        fh = open(lock_path, "w")
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fh, fcntl.LOCK_UN)
        fh.close()
    except OSError:
        raise Busy(f"campaign lock held: {lock_path}")
    check_holds(dev, dry)
    rc, out = sh(adb_cmd(serial, "shell", "ps -A | grep -E 'litert_lm|llama' | grep -v grep"))
    foreign = [ln for ln in out.splitlines() if ln.strip()]
    if foreign:
        raise Busy(f"foreign engine process on the phone: {foreign[0].strip()}")
    rc, out = sh(adb_cmd(serial, "shell", "dumpsys thermalservice | grep 'Thermal Status'"))
    m = re.search(r"Thermal Status: (\d+)", out)
    log(f"thermal status {m.group(1) if m else '?'} (the runner waits for 0 itself)")
    # a charge-throttle cap shows as scaling_max_freq far below cpuinfo_max_freq
    # (2026-09-05 Pixel 8a: 1065/1164 MHz caps under VIRTUAL-SKIN-CHARGE)
    rc, out = sh(adb_cmd(serial, "shell",
                         "for p in /sys/devices/system/cpu/cpufreq/policy*; do "
                         "echo $(cat $p/scaling_max_freq) $(cat $p/cpuinfo_max_freq); done"))
    capped = []
    for ln in out.splitlines():
        try:
            cur, mx = (int(x) for x in ln.split())
            if mx and cur < 0.6 * mx:
                capped.append(f"{cur // 1000}/{mx // 1000} MHz")
        except ValueError:
            continue
    if capped:
        raise Busy(f"CPU frequency capped (charge/thermal throttle): {', '.join(capped)}")
    free = android_free_gb(serial)
    log(f"free on /data: {free:.1f} GB" if free is not None else "free on /data: unknown")
    return {"free_gb": free}


def devicectl(*args, timeout=90):
    return sh(["xcrun", "devicectl"] + list(args), timeout=timeout)


def preflight_iphone(dev, dry):
    udid = dev["udid"]
    if not dev.get("app"):
        raise NotReady("schedule.json: iphone device needs an explicit \"app\" bundle id "
                       "(the runner's default is the retired app)")
    if not iphone_attached(udid):
        raise NotReady(f"{udid} not available to devicectl — connect + trust the phone")
    if pgrep("bench_matrix_iphone"):
        raise Busy("bench_matrix_iphone.sh is running")
    check_holds(dev, dry)
    rc, out = devicectl("device", "info", "lockState", "--device", udid)
    if rc != 0:
        raise NotReady(f"lockState query failed: {out.strip()[-200:]}")
    if "passcodeRequired: false" not in out:
        raise NotReady("phone is locked — a headless launch is refused until it is "
                       "unlocked (Auto-Lock Never for the session)")
    rc, out = devicectl("device", "info", "apps", "--device", udid, timeout=120)
    if rc == 0 and dev["app"] not in out:
        raise NotReady(f"{dev['app']} is not installed on the phone")
    if rc != 0:
        log("WARN could not list apps — install state unverified")
    log("storage: not probeable headlessly; a full container fails a cell with "
        "'No space left on device' (failed-runs-stay)")
    return {}


def preflight_mac(dev, dry):
    mac_guard()
    rc, out = sh([os.path.join(ROOT, "bench"), "doctor", "--platform", "mac"], timeout=120)
    if rc != 0:
        raise NotReady("bench doctor --platform mac FAILED:\n" + out)
    return {}


PREFLIGHT = {"android": preflight_android, "iphone": preflight_iphone, "mac": preflight_mac}


# ---------------------------------------------------------------- holds

def hold_acquire(schedule, dev):
    cli, path = expand(schedule.get("hold_cli")), expand(dev.get("hold"))
    if not path:
        return None
    if not cli or not os.path.exists(cli):
        log(f"WARN hold protocol not available on this host ({cli}); running without a hold")
        return None
    rc, out = sh([PY, cli, "acquire", path, "edge-llm-bench/scripts/dashboard_job.py",
                  str(os.getpid())])
    if rc != 0:
        raise Busy(f"hold refused: {out.strip()}")
    log(f"hold taken: {path}")
    return (cli, path)


def hold_release(h):
    if not h:
        return
    cli, path = h
    rc, out = sh([PY, cli, "release", path, str(os.getpid())])
    log(f"hold released: {path}" if rc == 0 else f"WARN hold release failed: {out.strip()}")


# ---------------------------------------------------------------- capture

def run_matrix(cells, platform, campaign, env, timeout_s, dry):
    cmd = ["gtimeout", "--kill-after=60", str(int(timeout_s)),
           os.path.join(ROOT, "bench"), "matrix", cells, "--platform", platform,
           "--campaign", campaign]
    log("$ " + " ".join(cmd) + "   env: " + " ".join(f"{k}={v!r}" for k, v in env.items()))
    if dry:
        return 0
    e = dict(os.environ)
    e.update(env)
    # the runners' progress lines (cells, rounds, gate verdicts) go to the job
    # log through a pipe; unbuffered, or they arrive in 8 KB chunks hours late
    # (first S26 run, 2026-09-08: round markers invisible until exit)
    e["PYTHONUNBUFFERED"] = "1"
    p = subprocess.run(cmd, env=e, cwd=ROOT, stdout=_LOG or None, stderr=subprocess.STDOUT)
    log(f"bench matrix exit {p.returncode}")
    return p.returncode


def device_env(dev):
    env = dict(dev.get("env", {}))
    if dev["platform"] == "android":
        env["BENCH_ANDROID_SERIAL"] = dev["serial"]
        env["BENCH_CPU_MASK"] = dev.get("cpu_mask", "f0")  # "" = unmasked (S26)
    elif dev["platform"] == "iphone":
        env["BENCH_UDID"] = dev["udid"]
        env["APP"] = dev["app"]
    return env


def campaign_rel(campaign, platform):
    return f"results/raw/{campaign}-{PLATFORM_TOKEN[platform]}"


# ---------------------------------------------------------------- admission

def load_rows(path=SUMMARY_CSV):
    if not os.path.exists(path):
        return []
    return list(csv.DictReader(open(path)))


def session_stats(rows, regime):
    """(median, n, thermal states) of one cell's rows in one session, on the
    same basis as arm_row: firstEver out, zero decode out, warm = coldRun
    False, cold = coldRun True."""
    want_cold = "True" if regime == "cold" else "False"
    vals, states = [], set()
    for r in rows:
        if r.get("first_ever") == "True" or r.get("cold_run") != want_cold:
            continue
        try:
            v = float(r["decode_tps"] or 0)
        except ValueError:
            continue
        if v <= 0:
            continue
        vals.append(v)
        states.add(r.get("thermal_initial") or "nominal")
    return (statistics.median(vals) if vals else None), len(vals), sorted(states)


def anchor_cells(schedule, platform):
    plat = PLATFORM_TOKEN[platform]
    cells = [c for c in load_cells(os.path.join(ROOT, schedule["anchors"]))
             if c["platform"] == plat and c["anchor"] and not c["exclude"]]
    # the primary anchor is a non-litert arm (the engine most often under
    # test); its runtime's own anchor is recorded alongside, not gating
    cells.sort(key=lambda c: c["runtime"] == "litert-lm")
    return cells


def admit(schedule, dev, campaign_rel_path, platform):
    """Compare this session's primary anchor with the newest admitted
    session's on the same device. Returns (admitted, reason, details)."""
    adm = schedule.get("admission", {})
    min_runs = int(adm.get("min_anchor_runs", 2))
    collapse = float(adm.get("collapse_ratio", 0.5))
    tol = float(adm.get("thermal_tolerance_pct", 5.0)) / 100.0
    rows = load_rows()
    admitted_map = load_admission()
    plat = CSV_PLATFORM[PLATFORM_TOKEN[platform]]
    regime = REGIME[PLATFORM_TOKEN[platform]]
    ident = dev["identifier"]
    details = {"regime": regime, "anchors": []}
    anchors = anchor_cells(schedule, platform)
    if not anchors:
        return True, "no anchor cell defined for this platform", details
    primary = anchors[0]
    for c in anchors:
        mine = [r for r in rows if r["campaign"] == campaign_rel_path and r["device"] == ident
                and r["runtime"] == c["arm"] and r["model_id"] == c["model_id"]
                and r["task"] == c["task"]]
        med, n, states = session_stats(mine, regime)
        # reference: newest admitted earlier session with this cell; and the
        # newest one whose anchor runs all started nominal (thermal rule)
        by_camp = {}
        for r in rows:
            if (r["platform"] == plat and r["device"] == ident and r["runtime"] == c["arm"]
                    and r["model_id"] == c["model_id"] and r["task"] == c["task"]
                    and r["campaign"] != campaign_rel_path
                    and admitted_map.get(r["campaign"], True)):
                by_camp.setdefault(r["campaign"], []).append(r)
        ref = ref_nominal = None
        for camp in sorted(by_camp, key=lambda k: max(x["timestamp"] or "" for x in by_camp[k]),
                           reverse=True):
            rmed, rn, rstates = session_stats(by_camp[camp], regime)
            if rmed is None or rn < min_runs:
                continue
            if ref is None:
                ref = {"campaign": camp, "median": rmed, "n": rn, "thermal": rstates}
            if ref_nominal is None and all(s in ("nominal", "") for s in rstates):
                ref_nominal = {"campaign": camp, "median": rmed, "n": rn}
            if ref and ref_nominal:
                break
        details["anchors"].append({"cell": f"{c['arm']} {c['model_id']} {c['task']}",
                                   "primary": c is primary, "median": med, "n": n,
                                   "thermal": states, "reference": ref,
                                   "reference_nominal": ref_nominal,
                                   "ratio": (med / ref["median"]) if med and ref else None})
    p = details["anchors"][0]
    if p["median"] is None or p["n"] < min_runs:
        return False, "anchor-short", details
    if p["reference"] and p["median"] < collapse * p["reference"]["median"]:
        return False, "anchor-collapse", details
    hot = [s for s in p["thermal"] if s not in ("nominal", "")]
    if hot:
        rn = p["reference_nominal"]
        if rn and abs(p["median"] / rn["median"] - 1) <= tol:
            return True, (f"non-nominal start ({','.join(hot)}) admitted: anchor within "
                          f"{tol*100:.0f}% of the newest all-nominal session"), details
        return False, "anchor-thermal", details
    return True, "anchor nominal" + (f", ratio {p['ratio']:.3f} vs reference" if p["ratio"] else
                                     ", first session on this device"), details


# ---------------------------------------------------------------- storage rotation

def android_models_of(cells_file):
    """On-device basenames the driver pushes for a cells file."""
    out = set()
    for c in load_cells(os.path.join(ROOT, cells_file)):
        if c["platform"] != "android" or c["exclude"]:
            continue
        f = c["opts"].get("file")
        if f and not os.path.exists(os.path.expanduser(f)):
            out.add(f"{c['model_id'].replace('/', '_')}_{f}")
    return out


def android_rotate(serial, previous_files, next_file, dry):
    """Delete pushed model copies of earlier halves that the next half does
    not use — with their engine caches (same prefix, same dir) AND their
    firstEver markers. Raw records are never touched; the host HF cache
    re-pushes the file next time."""
    keep = android_models_of(next_file)
    drop = set()
    for f in previous_files:
        drop |= android_models_of(f)
    drop -= keep
    for base in sorted(drop):
        cmd = (f"rm -f {ANDROID_DEV_DIR}/models/{base} {ANDROID_DEV_DIR}/models/{base}_* "
               f"{ANDROID_DEV_DIR}/models/{base}.* {ANDROID_DEV_DIR}/markers/{base}.*.cachebuilt")
        log(("[dry-run] " if dry else "") + f"adb shell {cmd}")
        if not dry:
            sh(adb_cmd(serial, "shell", cmd), timeout=120)
    return sorted(drop)


def android_footprint_gb(serial, cells_file):
    """On-device size of one half's pushed copies with the caches beside them
    (same globs as android_rotate): the free space that half needs on a phone
    holding none of it — the measured value for schedule.json min_free_gb."""
    total_kb = 0
    for base in sorted(android_models_of(cells_file)):
        rc, out = sh(adb_cmd(serial, "shell",
                             f"du -k {ANDROID_DEV_DIR}/models/{base} {ANDROID_DEV_DIR}/models/{base}_* "
                             f"{ANDROID_DEV_DIR}/models/{base}.* 2>/dev/null | cut -f1"), timeout=120)
        for ln in out.splitlines():
            try:
                total_kb += int(ln.strip())
            except ValueError:
                continue
    return total_kb / 1e6


# ---------------------------------------------------------------- session record

def read_lines(path):
    return [ln.rstrip("\n") for ln in open(path)] if os.path.exists(path) else []


def campaign_notes(rel_path):
    d = os.path.join(ROOT, rel_path)
    notes = {}
    for name in ("FAILURES.txt", "FLAGGED.txt", "SKIPPED.txt", "THERMAL_GATE.txt"):
        lines = read_lines(os.path.join(d, name)) + read_lines(os.path.join(d, "app-path-android", name))
        if lines:
            notes[name.split(".")[0].lower()] = lines
    return notes


def cells_with_records(rel_path, cells_file, platform, ident):
    plat = PLATFORM_TOKEN[platform]
    want = {(c["arm"], c["model_id"], c["task"]) for c in load_cells(os.path.join(ROOT, cells_file))
            if c["platform"] == plat and not c["exclude"]}
    have = set()
    for r in load_rows():
        if r["campaign"] == rel_path and r["device"] == ident:
            have.add((r["runtime"], r["model_id"], r["task"]))
    return len(want), len(want & have)


def write_session(rel_path, payload):
    d = os.path.join(ROOT, rel_path)
    if not os.path.isdir(d):
        return
    payload = dict(payload, schema="dashboard-job-session.v1", job="dashboard-v1")
    with open(os.path.join(d, "SESSION.json"), "w") as fh:
        json.dump(payload, fh, indent=1, default=str)
    log(f"wrote {rel_path}/SESSION.json (admitted={payload.get('admitted')}, "
        f"verdict={payload.get('verdict')})")


def ledger(row):
    os.makedirs(LOG_DIR, exist_ok=True)
    path = os.path.join(LOG_DIR, "ledger.tsv")
    new = not os.path.exists(path)
    with open(path, "a") as fh:
        if new:
            fh.write("started\tended\tdevice\tcampaign\tverdict\treason\texit\tminutes\tattempt\n")
        fh.write("\t".join(str(row.get(k, "")) for k in
                           ("started", "ended", "device", "campaign", "verdict", "reason",
                            "exit", "minutes", "attempt")) + "\n")


# ---------------------------------------------------------------- one attempt

def attempt(schedule, key, dev, attempt_no, args):
    platform = dev["platform"]
    date = datetime.date.today().isoformat()
    base = f"{date}-dashboard-v1-{key}" + (f"-r{attempt_no}" if attempt_no > 1 else "")
    env = device_env(dev)
    dry = args.dry_run
    started = time.strftime("%F %T")
    log(f"=== slot {key} ({dev['display']}, {platform}) attempt {attempt_no} campaign base {base}"
        + (" [dry-run]" if dry else ""))

    info = PREFLIGHT[platform](dev, dry)      # raises Busy / NotReady
    log("preflight ok")
    if dry:
        log("plan:")
    hold = None if dry else hold_acquire(schedule, dev)
    created = []
    try:
        # --- phase A: the session anchor as its own short campaign
        anchor_camp = f"{base}-anchor"
        anchor_rel = campaign_rel(anchor_camp, platform)
        rc = run_matrix(schedule["anchors"], platform, anchor_camp, env, 45 * 60, dry)
        if dry:
            log(f"  admission would read {anchor_rel} against the newest admitted session")
        else:
            created.append(anchor_rel)
            if rc == 124:
                write_session(anchor_rel, {"campaign": anchor_rel, "phase": "anchor",
                                           "admitted": False, "verdict": "TIMEOUT",
                                           "reason": "anchor phase timed out",
                                           "device_key": key, "started": started,
                                           "ended": time.strftime("%F %T")})
                return EXIT_TIMEOUT, "anchor phase timed out", anchor_rel
            admitted, reason, details = admit(schedule, dev, anchor_rel, platform)
            write_session(anchor_rel, {"campaign": anchor_rel, "phase": "anchor",
                                       "cells": schedule["anchors"], "device_key": key,
                                       "device_display": dev["display"],
                                       "device_identifier": dev["identifier"],
                                       "platform": platform, "attempt": attempt_no,
                                       "started": started, "ended": time.strftime("%F %T"),
                                       "admitted": admitted,
                                       "verdict": "ADMITTED" if admitted else "ABORTED",
                                       "reason": reason, "anchor": details,
                                       "runner_exit": rc, **campaign_notes(anchor_rel)})
            log(f"admission: {'ADMITTED' if admitted else 'ABORTED'} — {reason}")
            if not admitted:
                return EXIT_ABORTED, reason, anchor_rel

        # --- phase B: the payload, whole or in storage halves
        halves = None
        if platform == "android" and dev.get("split"):
            free = info.get("free_gb")
            if free is not None and free < float(dev.get("storage_gb_full", 0)):
                halves = dev["split"]
                log(f"free {free:.1f} GB < {dev['storage_gb_full']} GB for the whole set — "
                    f"running {len(halves)} halves with model rotation")
        plan = ([(h["cells"], float(h.get("min_free_gb", 0))) for h in halves]
                if halves else [(args.cells or schedule["cells"], 0.0)])
        timeout_s = float(dev.get("timeout_hours", 6)) * 3600 / len(plan)
        worst = EXIT_OK
        previous = []
        last_rel = None
        for cells_file, floor in plan:
            camp = base
            if halves:
                tag = re.sub(r"^.*-android-|\.cells$", "", os.path.basename(cells_file))
                camp = f"{base}-{tag}"
                free = android_free_gb(dev["serial"]) if not dry else info.get("free_gb")
                log(f"free before {tag}: {free:.1f} GB (floor {floor:g} GB)" if free is not None
                    else f"free before {tag}: unknown (floor {floor:g} GB)")
                if free is None or free < floor:
                    # rotate out every OTHER half's copies (last week's leftover
                    # half included), never this half's own
                    others = [h["cells"] for h in halves if h["cells"] != cells_file]
                    dropped = android_rotate(dev["serial"], others, cells_file, dry)
                    free = android_free_gb(dev["serial"]) if not dry else free
                    log(f"rotated out {len(dropped)} pushed copies; free now "
                        f"{free:.1f} GB" if free is not None else "rotated; free unknown")
                if free is not None and free < floor and not dry:
                    log(f"still {free:.1f} GB < floor {floor} GB for {cells_file} — "
                        "skipping this half (needs a human look at the device storage)")
                    worst = max(worst, EXIT_DEVICE)
                    continue
            rel_path = campaign_rel(camp, platform)
            rc = run_matrix(cells_file, platform, camp, env, timeout_s, dry)
            previous.append(cells_file)
            last_rel = rel_path
            if dry:
                continue
            if halves:
                # the measured storage floors (design §3, §7): what this half
                # consumed this sitting, and what its copies occupy on the phone
                # with their caches — the latter is what min_free_gb should carry
                after = android_free_gb(dev["serial"])
                foot = android_footprint_gb(dev["serial"], cells_file)
                used = (f"{free - after:.1f} GB" if free is not None and after is not None
                        else "unknown")
                log(f"free after {tag}: {after:.1f} GB" if after is not None
                    else f"free after {tag}: unknown")
                log(f"{tag} used {used} this sitting; on-device footprint of {tag}: {foot:.1f} GB "
                    "(models + caches — the measured floor for min_free_gb)")
            created.append(rel_path)
            expected, have = cells_with_records(rel_path, cells_file, platform, dev["identifier"])
            # the payload session runs its own anchor row first; re-judge it
            # so a contention that began after phase A is not admitted blindly
            own_ok, own_reason, own_details = admit(schedule, dev, rel_path, platform)
            verdict = "TIMEOUT" if rc == 124 else "COMPLETED"
            write_session(rel_path, {"campaign": rel_path, "phase": "payload",
                                     "cells": cells_file, "device_key": key,
                                     "device_display": dev["display"],
                                     "device_identifier": dev["identifier"],
                                     "platform": platform, "attempt": attempt_no,
                                     "started": started, "ended": time.strftime("%F %T"),
                                     "admitted": bool(own_ok), "verdict": verdict,
                                     "reason": own_reason, "anchor": own_details,
                                     "anchor_phase": anchor_rel, "runner_exit": rc,
                                     "cells_expected": expected, "cells_with_records": have,
                                     **campaign_notes(rel_path)})
            if rc == 124:
                worst = max(worst, EXIT_TIMEOUT)
            elif not own_ok:
                worst = max(worst, EXIT_ABORTED)
        if not dry:
            rc = sh([PY, os.path.join(ROOT, "scripts", "render_dashboard.py")], timeout=300)[0]
            log(f"render_dashboard exit {rc}")
        return worst, ("ok" if worst == EXIT_OK else VERDICT_NAME[worst].lower()), last_rel
    finally:
        hold_release(hold)


# ---------------------------------------------------------------- auto: which device now

def parse_ts(text):
    """Accumulation-layer timestamp (UTC, 'Z') -> aware local datetime, or None."""
    if not text:
        return None
    try:
        if text.endswith("Z"):
            dt = datetime.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        else:
            dt = datetime.datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        return None
    return dt.astimezone()


def week_start(now):
    """Monday 00:00 local of the week `now` falls in."""
    monday = now - datetime.timedelta(days=now.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def device_sessions(schedule, rows, admitted):
    """key -> [(ended, campaign)] of the device's admitted dashboard sessions,
    newest first. A session is a `-dashboard-v1-` campaign that is not the
    anchor probe, matched on the device's identifier and platform, whose
    SESSION.json does not say admitted:false (absent = admitted, as in
    render_dashboard); its time is its last record's. Hand-run first passes
    count the same way as the job's own sittings."""
    out = {}
    for key, dev in schedule.get("devices", {}).items():
        plat = CSV_PLATFORM[PLATFORM_TOKEN[dev["platform"]]]
        ended = {}
        for r in rows:
            camp = r["campaign"]
            if (DASHBOARD_CAMPAIGN not in camp or re.search(ANCHOR_CAMPAIGN_RE, camp)
                    or r["platform"] != plat or r["device"] != dev["identifier"]
                    or not admitted.get(camp, True)):
                continue
            t = parse_ts(r["timestamp"])
            if t and (camp not in ended or t > ended[camp]):
                ended[camp] = t
        out[key] = sorted(((t, c) for c, t in ended.items()), reverse=True)
    return out


def newest_record(rows, dev):
    """When this device last produced a record in any campaign (its idle
    clock). Use by a sibling lane that leaves no record here is invisible
    beyond its hold file."""
    plat = CSV_PLATFORM[PLATFORM_TOKEN[dev["platform"]]]
    best = None
    for r in rows:
        if r["platform"] == plat and r["device"] == dev["identifier"]:
            t = parse_ts(r["timestamp"])
            if t and (best is None or t > best):
                best = t
    return best


def outside_window(dev, now):
    """'' when `now` is inside the device's auto_window ("HH:MM-HH:MM", local,
    end exclusive), else why not. No window = always."""
    w = dev.get("auto_window")
    if not w:
        return ""
    lo, hi = w.split("-")
    h1, m1 = (int(x) for x in lo.split(":"))
    h2, m2 = (int(x) for x in hi.split(":"))
    t = now.hour * 60 + now.minute
    if h1 * 60 + m1 <= t < h2 * 60 + m2:
        return ""
    return f"outside its window {w}"


def resolve_device(schedule, key, exclude=None, now=None, rows=None, admitted=None):
    """(key, dev, report). An explicit key resolves as given (report []).

    `auto`: the device to measure at this firing — among the devices with no
    admitted dashboard session since Monday 00:00 local, the attached, unheld
    ones (the iPhone only inside its auto_window after auto_idle_hours without a
    record; the Mac only while no heavy pipeline runs), ordered by the age of
    their last admitted session, oldest first (never measured = oldest; ties
    in schedule order). `exclude` maps keys already tried this firing to
    (state, detail). The report has one dict per device — key, state (done /
    candidate / busy / not-ready / waiting), detail, last — for the log."""
    devices = schedule.get("devices", {})
    if key != "auto":
        dev = devices.get(key)
        if not dev:
            raise SystemExit(f"unknown device key {key!r}; known: {sorted(devices)}")
        return key, dev, []
    now = now or datetime.datetime.now().astimezone()
    rows = load_rows() if rows is None else rows
    admitted = load_admission() if admitted is None else admitted
    exclude = exclude or {}
    sessions = device_sessions(schedule, rows, admitted)
    monday = week_start(now)
    report, ranked = [], []
    for i, (k, dev) in enumerate(devices.items()):
        last = sessions[k][0] if sessions[k] else None
        entry = {"key": k, "last": last[0] if last else None, "state": "candidate",
                 "detail": (f"last admitted {last[0]:%F %H:%M}" if last else "never measured")}
        report.append(entry)
        if last and last[0] >= monday:
            entry.update(state="done", detail=f"admitted {last[0]:%F %H:%M} {last[1]}")
            continue
        if k in exclude:
            entry.update(state=exclude[k][0], detail=exclude[k][1])
            continue
        why = outside_window(dev, now)
        if not why and dev.get("auto_idle_hours"):
            used = newest_record(rows, dev)
            age_h = (now - used).total_seconds() / 3600 if used else None
            if age_h is not None and age_h < float(dev["auto_idle_hours"]):
                why = f"last record {age_h:.1f} h ago, needs {dev['auto_idle_hours']} h idle"
        if why:
            entry.update(state="waiting", detail=f"{why}; {entry['detail']}")
            continue
        try:
            check_holds(dev, dry=True)
            if dev["platform"] == "mac":
                mac_guard()
        except Busy as e:
            entry.update(state="busy", detail=f"{e}; {entry['detail']}")
            continue
        if dev["platform"] == "android":
            state = android_state(dev["serial"])
            if state != "device":
                entry.update(state="not-ready", detail=(
                    "not visible to adb" if state is None else f"adb state {state!r}")
                    + f"; {entry['detail']}")
                continue
        elif dev["platform"] == "iphone" and not iphone_attached(dev["udid"]):
            entry.update(state="not-ready", detail=f"not available to devicectl; {entry['detail']}")
            continue
        ranked.append(((1, last[0].timestamp(), i) if last else (0, 0, i), k))
    if not ranked:
        return None, None, report
    chosen = min(ranked)[1]
    return chosen, devices[chosen], report


def log_report(now, report, chosen):
    log(f"auto @ {now:%F %H:%M} (week of Mon {week_start(now):%F}):")
    for e in report:
        log(f"  {e['key']:<12} {e['state']:<10} {e['detail']}")
    log(f"  -> {chosen}" if chosen else "  -> no device to measure now")


# ---------------------------------------------------------------- main

_JOB_LOCK = None


def job_lock():
    """One job instance per host. A second `auto` beside a running one (a
    manual run next to the launchd firing) would otherwise race it for a
    device between the choice and the hold."""
    global _JOB_LOCK
    os.makedirs(LOG_DIR, exist_ok=True)
    fh = open(os.path.join(LOG_DIR, ".job.lock"), "a+")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.seek(0)
        return fh.read().strip() or "?"
    fh.seek(0)
    fh.truncate()
    fh.write(str(os.getpid()))
    fh.flush()
    _JOB_LOCK = fh
    return None


def open_log(name):
    global _LOG
    if _LOG:
        _LOG.close()
    os.makedirs(LOG_DIR, exist_ok=True)
    _LOG = open(os.path.join(LOG_DIR, f"{datetime.date.today().isoformat()}-{name}.log"), "a")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("device", help="device key from schedule.json, or 'auto' (the pending "
                                   "device whose last admitted session is oldest)")
    ap.add_argument("--schedule", default=SCHEDULE)
    ap.add_argument("--cells", help="override the cells file (single-file mode)")
    ap.add_argument("--dry-run", action="store_true",
                    help="preflight and print the plan; take no hold, capture nothing")
    ap.add_argument("--once", action="store_true",
                    help="no busy polling / abort retry — one attempt")
    args = ap.parse_args()

    try:
        schedule = json.load(open(args.schedule))
    except (OSError, ValueError) as e:
        print(f"schedule unreadable: {e}", file=sys.stderr)
        return EXIT_CONFIG
    auto = args.device == "auto"
    key, dev, _ = resolve_device(schedule, args.device)
    if not args.dry_run:
        other = job_lock()
        if other:
            print(f"another dashboard_job is running (pid {other}); exit {EXIT_BUSY}")
            return EXIT_BUSY
    open_log("auto" if auto else key)

    retry = schedule.get("retry", {})
    poll = float(retry.get("busy_poll_minutes", 15)) * 60
    window = float(retry.get("busy_window_minutes", 120)) * 60
    max_attempts = int(retry.get("max_attempts_per_slot", 2))
    abort_wait = retry.get("abort_retry_after_minutes", {})
    t0 = time.time()
    attempt_no, code, reason, camp = 1, EXIT_CONFIG, "", ""
    started = time.strftime("%F %T")
    tried = {}        # auto: key -> (state, detail) for devices passed over this firing
    pinned = False    # auto: an abort retry stays on the device it aborted on
    while True:
        if auto and not pinned:
            now = datetime.datetime.now().astimezone()
            key, dev, report = resolve_device(schedule, "auto", exclude=tried, now=now)
            log_report(now, report, key)
            if not key:
                busy = [e["key"] for e in report if e["state"] == "busy"]
                notready = [e for e in report if e["state"] == "not-ready"]
                if busy and not (args.once or args.dry_run) and time.time() - t0 + poll <= window:
                    log(f"pending devices busy ({', '.join(busy)}) — choosing again in "
                        f"{poll/60:.0f} min")
                    time.sleep(poll)
                    tried = {k: v for k, v in tried.items() if v[0] != "busy"}
                    continue
                if notready:
                    code, reason = EXIT_DEVICE, "; ".join(f"{e['key']}: {e['detail']}" for e in notready)
                elif busy:
                    code, reason = EXIT_BUSY, "busy: " + ", ".join(busy)
                else:
                    code, reason = EXIT_OK, "nothing pending this week"
                break
            open_log(key)
            log(f"auto chose {key} (the decision is in {datetime.date.today().isoformat()}-auto.log)")
        try:
            code, reason, camp = attempt(schedule, key, dev, attempt_no, args)
        except Busy as e:
            code, reason = EXIT_BUSY, str(e)
            log(f"BUSY: {e}")
        except NotReady as e:
            code, reason = EXIT_DEVICE, str(e)
            log(f"DEVICE: {e}")
        if auto and not pinned and code in (EXIT_BUSY, EXIT_DEVICE):
            # pass over this device now; a busy one is reconsidered after the poll
            tried[key] = ("busy" if code == EXIT_BUSY else "not-ready", reason)
            open_log("auto")
            continue
        if args.dry_run or args.once or code in (EXIT_OK, EXIT_DEVICE, EXIT_TIMEOUT, EXIT_CONFIG):
            break
        if code == EXIT_BUSY:
            if time.time() - t0 + poll > window:
                log("busy window exhausted — giving up this slot")
                break
            log(f"retrying in {poll/60:.0f} min")
            time.sleep(poll)
            continue
        if code == EXIT_ABORTED:
            if attempt_no >= max_attempts:
                log("max attempts reached — giving up this slot")
                break
            wait = float(abort_wait.get(reason, 30)) * 60
            log(f"aborted ({reason}) — retrying once in {wait/60:.0f} min")
            time.sleep(wait)
            attempt_no += 1
            pinned = True
            continue
        break
    ended = time.strftime("%F %T")
    # a firing that found nothing pending is the normal nightly case: log only
    if not args.dry_run and not (auto and not key and code == EXIT_OK):
        ledger({"started": started, "ended": ended, "device": key or "auto", "campaign": camp or "",
                "verdict": VERDICT_NAME.get(code, str(code)), "reason": reason,
                "exit": code, "minutes": round((time.time() - t0) / 60, 1),
                "attempt": attempt_no})
    log(f"=== done: {VERDICT_NAME.get(code, code)} ({reason}) exit {code}")
    return code


if __name__ == "__main__":
    sys.exit(main())
