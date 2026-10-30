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
oldest (never measured = oldest; ties in schedule order); an entry with `auto: false`
is never chosen (by hand only: `./bench dashboard-job <key>`). A candidate whose
preflight says busy or not ready is passed over for the next one; when every
pending device is busy the firing polls per "retry" and chooses again. Each
device is measured once a week; a firing with nothing pending exits 0 and leaves
no ledger line. A device whose weekly set is in parts (schedule.json "parts": the
Mac since 2026-10-28, whose whole set outgrew one sitting's timeout) takes one
firing per part: a sitting runs one part, the first in the week's order with no
admitted session since Monday, and the week is done when every part has one (a
session whose SESSION.json names another cells file — the whole set, a --cells
file, a hand run — covers every part, as it covers a device without parts);
--part TAG runs a given part by hand. A device without parts is done for the week when every run
of its weekly plan has an admitted session since Monday: the set (its file, or each of its storage
halves) and each extra file; a session counts for the file its SESSION.json names, a hand run with
no SESSION.json for the whole plan, a --cells file (a slot, a coverage run) for none of it. A device
with a release_by (schedule.json, "HH:MM" local; docs/dashboard-recurring-job-v1.md §11) gives its
hold back by the first such time after the firing began: before the hold, the anchor phase and the
first payload run must be expected to end by then (else the device is passed over this firing, as
TooLate; the whole set gives way to the storage halves when only they fit); before each later run,
a run expected to end past it is not started, and the sitting closes with the runs it finished. The
runs left over run at a later firing of the week; a run under way is never stopped. --release-by
HH:MM|none sets or lifts it for one invocation. The sitting itself does only what a careful
operator did by hand for the first pass, in this order:

  preflight   device attached / unlocked / not held by a sibling lane / no foreign
              engine process / storage floor / host runner idle / the side builds the
              cells files launch are on the phone (a file whose build is missing is
              skipped by itself, the others run)
  hold        take the sibling lane's device hold for the run (hold_cli.py), and keep in it when
              the sitting expects to release it, rewritten as the sitting moves (expected_release,
              release_basis: scripts/hold_eta.py, docs/dashboard-recurring-job-v1.md §10)
  phase A     ./bench matrix matrices/anchors.cells   -> <campaign>-anchor
  admission   the fresh anchor against the newest ADMITTED session's anchor on this
              device that ran the same engine build (none: first session on that
              build): short / collapse / thermal rules (schedule.json "admission")
  phase B     ./bench matrix <dashboard cells>        -> <campaign>   (or one run per
              storage half, rotating pushed model copies out between halves; or the
              sitting's part, <campaign> = <date>-dashboard-v1-<device>-<part tag>)
  close       SESSION.json in every campaign dir it created, a ledger line under
              logs/dashboard-job/, DASHBOARD.md re-rendered, hold released

Exit codes (ledger + launchd log):
  0 admitted and captured        3 busy — held, guarded, throttled, runner active
  4 aborted at admission         5 device not ready — absent, locked, no space, doctor FAIL
  6 whole-session timeout        2 configuration error
Busy and aborted sittings retry inside the firing's window per schedule.json
"retry"; one sitting per device (logs/dashboard-job/.job.lock.<device>): sittings
on different devices run side by side, a second run on a device already being
measured exits 3 at once, and `auto` holds .choose.lock while it picks so two
autos never pick the same device.

--hold-held-by <pid> (one device, never `auto`): the device hold is already taken by that live
pid (a keeper script that queued for the phone through the sibling lane's queue); the job
checks that the hold file names it, neither acquires nor releases the hold, and stops with
exit 2 when the pid is dead or the hold names another pid.

After the ledger line, outside the hold, a sitting that exits 0 is handed to
scripts/dashboard_post.py (docs/dashboard-autopilot-v1.md): it commits the sitting's
campaign dirs locally when every one passes scripts/session_check.py, rebuilds
results/summary from the git index into the same commit and the private page from
that commit, and pushes or publishes only what ops/autopilot/switch.json turns on;
its exit code never changes the sitting's. A dry run prints that command only, and so does
--no-post (a sitting by hand whose commit and push wait for a person's review: the person runs
the printed command after it).

Before a device's weekly set, its pending retakes (logs/dashboard-job/retakes.json: a red point of
the team page's rule that the post step found in a sitting, scripts/regression_watch.py) run as
one sitting of their own (docs/dashboard-autopilot-v1.md §8): the platform's rows of the anchors
file and each retake's row byte for byte in logs/dashboard-job/retake-<date>-<device>.cells,
campaign suffix retake-<slug>, the same preflight, hold, admission and close, its own ledger line
and post; an android native-benchmark retake row adds `./bench profile`'s pair in the same
campaign. `auto` takes a device whose weekly set is done when a retake of it is pending, and a
device with a pending retake before the others; the week counts weekly sets only (a retake
sitting's SESSION.json names its retakes). --cells (a run by hand) and --no-retake take none.

A Developer Device Platform lab unit (schedule.json platform "ddp", docs/dashboard-autopilot-v1.md
§9) has no device on this host, so `auto` never takes it as the firing's one device: after the
attached device's sitting (or at a firing with none) each lab unit whose weekly sitting is due runs
one (`ddp: …` lines in the auto log): ops/autopilot/switch.json ddp_weekly on, the checks `bench
doctor --platform ddp` requires (scripts/doctor.py check_ddp alone: no phone of this host is listed or
touched), the plan of `bench matrix --ddp --dry-run` within the switch's ddp_max_sessions (nothing is
billed past it), then `bench matrix <cells> --ddp <id>`. No hold, no reboot, no anchor
phase: SESSION.json is admitted when the sitting wrote records (each run carries its cap marks and
the text check), then the ledger line and the post as any sitting. At most once in its entry's
interval_days (6): an admitted session of the unit in the last 6 days, or a sitting in them that
ran Device Run sessions and was not admitted, means not due (not the attached devices' Monday week:
a Sunday-night sitting is not repeated at Monday 02:00). --no-ddp skips it; `dashboard_job.py <its
key>` runs it by hand.
What the job never does: edit a cells file, delete a raw record.
The one destructive step is deleting pushed MODEL COPIES on a storage-limited
phone between halves (the host HF cache is the source), together with their
engine caches and firstEver markers — the markers must go with the caches, or
the next run 1 rebuilds the cache unlabelled and pools as speed.
"""
import argparse
import collections
import csv
import datetime
import fcntl
import glob
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
import hold_eta  # noqa: E402
import regression_watch  # noqa: E402

PY = sys.executable
SCHEDULE = os.path.join(ROOT, "ops", "dashboard-v1", "schedule.json")
# the step after a sitting that exits 0 (docs/dashboard-autopilot-v1.md): check, commit, page
POST = os.path.join(ROOT, "scripts", "dashboard_post.py")
POST_TIMEOUT_S = 3600
# --no-post: the post command is printed, never run (main() sets it)
NO_POST = False
# a retake's per-op profile pair (`./bench profile`, android/bench/run_profile.py): control + twin
PROFILE_TIMEOUT_S = 3600
LOG_DIR = os.path.join(ROOT, "logs", "dashboard-job")
SUMMARY_CSV = os.path.join(ROOT, "results", "summary", "device-runs.csv")
# a dashboard session's campaign (design §1): <date>-dashboard-v1-<device>[-<half>]-<plat>;
# the admission probe is <date>-dashboard-v1-<device>-anchor-<plat> and is not a session
DASHBOARD_CAMPAIGN = "-dashboard-v1-"
ANCHOR_CAMPAIGN_RE = r"-dashboard-v1-.*-anchor-"
# bench --platform name -> cells-file platform token (= campaign dir suffix); a DDP lab unit runs the
# android rows (bench matrix --ddp writes <campaign>-android)
PLATFORM_TOKEN = {"mac": "mac", "iphone": "ios", "android": "android", "ddp": "android"}
ANDROID_DEV_DIR = "/data/local/tmp/llmbench"
# the Mac runner's own guard (scripts/bench_matrix_mac.sh heavy_guard), replicated so the
# job reports BUSY and polls instead of letting `bench matrix` fail once and give up the
# slot. Every pattern is anchored at the program the process runs: its argv[0] (the coreai
# venv's python, llm-benchmark, coreai-build), or the module / script a python argv[0]
# runs. Unanchored, a name anywhere in an argv matched: on 2026-10-08 two coding-agent CLI
# sessions' argv (their prompt text) named coreai-models/.venv/bin/python, and this guard
# read an idle Mac as busy while the runner's did the same.
MAC_HEAVY_PROGRAM_RE = re.compile(
    r"^[^ ]*(coreai-models/\.venv/bin/python|release/llm-benchmark( |$)|coreai-build compile)")
MAC_HEAVY_PYTHON_RE = re.compile(
    r"^[^ ]*[Pp]ython[0-9.]*( [^ ]+)* (-m coreai\.llm\.export|[^ ]*export_simple_template\.py|"
    r"[^ ]*scratchpad/export_[A-Za-z0-9_]*\.py|[^ ]*scripts/(convert|verify_lock)\.py|-m executorch\.extension\.llm\.export|"
    r"[^ ]*export_gemma4\.py|[^ ]*scripts/executorch/(export_|run_gemma4_export))")


def mac_heavy_command(command):
    """True when a live process whose argv (joined by spaces) is `command` is a heavy Mac
    pipeline by the runner's rule above: a Core AI export / benchmark / compile, or an
    ExecuTorch export, anchored at the program — never a name inside another process's
    arguments."""
    return bool(MAC_HEAVY_PROGRAM_RE.search(command) or MAC_HEAVY_PYTHON_RE.search(command))

EXIT_OK, EXIT_CONFIG, EXIT_BUSY, EXIT_ABORTED, EXIT_DEVICE, EXIT_TIMEOUT = 0, 2, 3, 4, 5, 6
VERDICT_NAME = {EXIT_OK: "OK", EXIT_CONFIG: "CONFIG", EXIT_BUSY: "BUSY",
                EXIT_ABORTED: "ABORTED", EXIT_DEVICE: "DEVICE", EXIT_TIMEOUT: "TIMEOUT"}


class Busy(Exception):
    """Retry later inside the slot window (exit 3)."""


class NotReady(Exception):
    """Needs a human (exit 5)."""


class ConfigError(Exception):
    """The invocation cannot run as given (exit 2)."""


class TooLate(Exception):
    """The sitting's first runs would end past the device's release_by: nothing started, no hold taken;
    `auto` passes the device over for this firing, a device by key exits 3."""


# --hold-held-by: the pid that took the device hold for this sitting (None = the job takes it)
HOLD_KEEPER = None


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
    """Live processes whose command line matches pattern. A line that does not
    start with a pid is the continuation of a multi-line argv and is skipped;
    so is the agent CLI itself (its argv carries the prompt text, and a prompt
    that names run_cell.py is not run_cell.py running — a live Claude session
    crashed this probe with ValueError on 2026-09-13)."""
    rc, out = sh(["pgrep", "-fl", pattern])
    rc2, ids = sh(["pgrep", "-f", pattern])
    # the pids pgrep matched: a record of the -fl output starts with one of them, once; any other
    # line that starts with a number is argv text (2026-10-19: a Claude session's prompt argument
    # carried a line "3 asset ...", read as pid 3's command and reported as a host driver)
    pids = {p for p in ids.split() if p.isdigit()}
    mine = {os.getpid(), os.getppid()}
    lines = []
    for ln in out.splitlines():
        parts = ln.split(None, 2)
        if len(parts) < 2 or not parts[0].isdigit() or parts[0] not in pids:
            continue
        pids.discard(parts[0])
        if int(parts[0]) in mine or "dashboard_job.py" in ln:
            continue
        if os.path.basename(parts[1]) == "claude":
            continue
        lines.append(ln)
    return lines


def driver_env(pid, var):
    """One variable of a live process's environment (`/proc/<pid>/environ` on Linux, `ps -E` on
    macOS), or None when the process is gone or does not set it. Only that variable is taken;
    nothing else of the environment is kept or logged (it carries the shell's secrets)."""
    if os.path.isdir("/proc"):
        try:
            with open(f"/proc/{pid}/environ", "rb") as fh:
                for item in fh.read().split(b"\0"):
                    if item.startswith(var.encode() + b"="):
                        return item.split(b"=", 1)[1].decode(errors="replace") or None
        except OSError:
            pass
        return None
    rc, out = sh(["ps", "-E", "-o", "command=", "-p", str(pid)])
    if rc != 0:
        return None
    m = re.search(r"(?:^|\s)" + re.escape(var) + r"=(\S+)", out)
    return m.group(1) if m else None


def driver_serial(pid):
    """The phone a host campaign driver drives, read from its environment: the bench
    wrapper hands run_campaign.py its phone (BENCH_ANDROID_SERIAL) and campaign (CAMPAIGN)
    through the environment, not argv. None when the process is gone or names no phone."""
    return driver_env(pid, "BENCH_ANDROID_SERIAL")


def other_phones_held(dev):
    """The keys of the other schedule devices whose live holds sit in this device's sibling hold
    files (the lanes' .iphone_hold names its phone)."""
    mine = device_key_of(dev)
    keys = set()
    for path in dev.get("hold_also_check", []):
        h = read_hold(path)
        if not h or not pid_alive(h.get("pid")):
            continue
        other = KNOWN_DEVICES.get(str(h.get("device") or "").strip().lower())
        if other is not None and mine is not None and other != mine:
            keys.add(other)
    return keys


def iphone_runner_busy(udid, dev):
    """Why a live iPhone runner (scripts/bench_matrix_iphone.sh) makes this phone busy, or None.
    A runner whose environment names its phone (BENCH_UDID, the job's run_matrix env, or DEV) is
    read by that name: another schedule phone's runner shares only the host (2026-10-19 12:36: the
    17 Pro's AA lane's runner held the 18 Pro's job at exit 3); this phone's, or an unknown id, is
    busy. macOS shows another session's environment as empty: such runners are explained only up to
    the number of other phones holding a live sibling lock (other_phones_held), one each; any runner
    left over may be this phone's and is busy."""
    mine = device_key_of(dev) or KNOWN_DEVICES.get(udid.lower())
    unnamed = []
    for ln in pgrep("bench_matrix_iphone"):
        pid = ln.split(None, 1)[0]
        try:
            named = driver_env(int(pid), "BENCH_UDID") or driver_env(int(pid), "DEV")
        except ValueError:
            named = None
        if not named:
            unnamed.append(pid)
            continue
        other = KNOWN_DEVICES.get(named.strip().lower())
        if other is not None and mine is not None and other != mine:
            log(f"bench_matrix_iphone.sh pid {pid}: its environment names {other} — another phone's runner")
            continue
        return f"bench_matrix_iphone.sh is running (pid {pid}, device {named})"
    if unnamed:
        held = other_phones_held(dev)
        if len(unnamed) <= len(held):
            log(f"bench_matrix_iphone.sh pid(s) {', '.join(unnamed)}: environment unreadable; the live sibling "
                f"hold(s) name {', '.join(sorted(held))} — taken as those phones' runners")
            return None
        return (f"bench_matrix_iphone.sh is running (pid {', '.join(unnamed)}, phone unknown; "
                f"{len(held)} other phone(s) hold a sibling lock)")
    return None


# ---------------------------------------------------------------- preflight

# every name a hold file may use for a schedule device -> its key (register_devices, from the
# schedule the run loaded); device_key_of maps a device entry back to its key the same way
KNOWN_DEVICES = {}


def register_devices(schedule):
    KNOWN_DEVICES.clear()
    for key, d in (schedule.get("devices") or {}).items():
        for name in (key, d.get("display"), d.get("identifier"), d.get("serial"), d.get("udid"), d.get("coredevice")):
            if name:
                KNOWN_DEVICES[str(name).strip().lower()] = key


def device_key_of(dev):
    for name in (dev.get("key"), dev.get("identifier"), dev.get("serial"), dev.get("udid"), dev.get("coredevice"), dev.get("display")):
        if name and str(name).strip().lower() in KNOWN_DEVICES:
            return KNOWN_DEVICES[str(name).strip().lower()]
    return None


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
        other, mine = KNOWN_DEVICES.get(str(h.get("device") or "").strip().lower()), device_key_of(dev)
        # only a sibling file: the device's own hold file is this phone's whatever its device field
        # says (hold_cli.py writes "S26" into every hold it takes, the iPhone 18 Pro's too)
        if path != dev.get("hold") and other is not None and mine is not None and other != mine:
            # the sibling lanes' .iphone_hold serves two phones and names its phone (memory
            # device-busy-is-probeable): a hold that names another device of the schedule is not
            # this sitting's business (2026-10-19 12:3x: the 17 Pro's AA lane held it while the
            # 18 Pro was free); a device string the schedule does not know stays busy
            log(f"hold at {path} names another device ({h.get('device')} = {other}, pid {h.get('pid')}, "
                f"{h.get('script')}): not this phone's")
            continue
        if HOLD_KEEPER is not None and same_pid(h.get("pid"), HOLD_KEEPER):
            log(f"hold kept by keeper pid {HOLD_KEEPER} at {path} — the sitting's own")
            continue
        if h.get("pid") not in (None, os.getpid()) and pid_alive(h.get("pid")):
            raise Busy(f"device held by pid {h.get('pid')} ({h.get('script')}) "
                       f"since {h.get('started')}: {path}")
        log(f"stale hold from pid {h.get('pid')} ({h.get('script')}) at {path} — "
            "not live; the acquire step will clear it" + (" [dry-run]" if dry else ""))


def same_pid(a, b):
    try:
        return int(a) == int(b)
    except (TypeError, ValueError):
        return False


def keeper_hold_problem(dev, pid):
    """--hold-held-by <pid>: why that pid's hold cannot stand for the job's own, or None.
    The pid must be alive and the device's hold file (schedule.json "hold") must name it."""
    if not pid_alive(pid):
        return f"keeper pid {pid} is not alive"
    path = dev.get("hold")
    if not path:
        return "this device has no hold file in schedule.json"
    h = read_hold(path)
    if h is None:
        return f"no hold at {expand(path)} (the keeper must hold it before the job starts)"
    if not same_pid(h.get("pid"), pid):
        return (f"the hold at {expand(path)} belongs to pid {h.get('pid')} ({h.get('script')}), "
                f"not to {pid}")
    return None


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


def android_uptime_hours(serial):
    rc, out = sh(adb_cmd(serial, "shell", "cat /proc/uptime"))
    try:
        return float(out.split()[0]) / 3600
    except (ValueError, IndexError):
        return None


def android_memory_gb(serial):
    """(MemAvailable, swap in use) in GB from /proc/meminfo, or (None, None)."""
    rc, out = sh(adb_cmd(serial, "shell", "cat /proc/meminfo"))
    kv = {}
    for ln in out.splitlines():
        parts = ln.replace(":", " ").split()
        if len(parts) >= 2 and parts[1].isdigit():
            kv[parts[0]] = int(parts[1])
    try:
        return kv["MemAvailable"] / 1e6, (kv["SwapTotal"] - kv["SwapFree"]) / 1e6
    except KeyError:
        return None, None


def _gb(x):
    return "?" if x is None else f"{x:.2f}"


def android_reboot_if_stale(dev, dry):
    """Opt-in per device (`reboot_before` in schedule.json): reboot the phone
    before the sitting when its uptime exceeds `uptime_hours`, wait for
    sys.boot_completed, settle `settle_seconds`, drop background apps
    (`am kill-all`), and log uptime / MemAvailable / swap in use before and
    after, so each sitting adds a data point. Basis, Pixel 8a 2026-09-09:
    llama.cpp Gemma 4 E4B (about 8 GB of buffers on a 7.5 GB phone) read 4.9
    then 1.6 / 1.4 tok/s at 13 h uptime with 1 GB of swap in use, and 5.1 /
    5.0 / 5.4 nine minutes after a reboot — same engine, OS, recipe, thermal
    state. Called after the hold is taken, so no sibling lane starts on the
    phone across the reboot. Returns True when it rebooted; a dry run only
    reports."""
    cfg = dev.get("reboot_before")
    if not cfg:
        return False
    serial = dev["serial"]
    limit = float(cfg.get("uptime_hours", 2))
    up = android_uptime_hours(serial)
    avail, swap = android_memory_gb(serial)
    log(f"uptime {_gb(up)} h, MemAvailable {_gb(avail)} GB, swap in use {_gb(swap)} GB "
        f"(reboot_before: uptime over {limit:g} h)")
    if up is None or up <= limit:
        log("no reboot: uptime within the limit" if up is not None else "no reboot: uptime unreadable")
        return False
    settle = int(cfg.get("settle_seconds", 300))
    if dry:
        log(f"would reboot the phone (uptime {up:.1f} h > {limit:g} h), wait for boot, "
            f"settle {settle} s, am kill-all [dry-run]")
        return False
    log(f"rebooting the phone: uptime {up:.1f} h > {limit:g} h")
    sh(adb_cmd(serial, "reboot"), timeout=30)
    time.sleep(float(cfg.get("reboot_grace_seconds", 10)))
    deadline = time.time() + float(cfg.get("boot_timeout_seconds", 300))
    booted = False
    while time.time() < deadline:
        rc, out = sh(adb_cmd(serial, "shell", "getprop sys.boot_completed"), timeout=20)
        if rc == 0 and out.strip() == "1":
            booted = True
            break
        time.sleep(5)
    if not booted:
        raise NotReady(f"{serial} did not finish booting within "
                       f"{cfg.get('boot_timeout_seconds', 300)} s of the reboot — look at the phone")
    log(f"boot completed; settling {settle} s")
    time.sleep(settle)
    if cfg.get("kill_background", True):
        sh(adb_cmd(serial, "shell", "am kill-all"))
        log("am kill-all: background processes dropped")
    # a phone waiting for its first unlock hides credential-encrypted storage;
    # the model directory must be readable before a cell runs
    rc, out = sh(adb_cmd(serial, "shell", f"ls {ANDROID_DEV_DIR}/models | head -1"))
    if rc != 0 or not out.strip():
        raise NotReady(f"{serial}: {ANDROID_DEV_DIR}/models unreadable after the reboot "
                       "(first unlock pending?) — unlock the phone once")
    rc, out = sh(adb_cmd(serial, "shell", "dumpsys power | grep -m1 mWakefulness="))
    if "Awake" not in out:
        sh(adb_cmd(serial, "shell", "input keyevent KEYCODE_WAKEUP"))
        log("screen woken after the reboot (KEYCODE_WAKEUP)")
    up2 = android_uptime_hours(serial)
    avail2, swap2 = android_memory_gb(serial)
    log(f"after reboot: uptime {_gb(up2)} h, MemAvailable {_gb(avail2)} GB, swap in use {_gb(swap2)} GB")
    return True


def iphone_attached(udid):
    rc, out = devicectl("list", "devices")
    row = next((ln for ln in out.splitlines() if udid in ln), None)
    return row is not None and ("available" in row or "connected" in row)


def mac_guard():
    """Busy when a Mac capture runs or a heavy pipeline would contend for
    unified memory (the runner's own guard, replicated so the job reports
    BUSY and polls instead of letting `bench matrix` fail once)."""
    # ortgenai_mac.py: the ONNX Runtime GenAI cells' own driver, run by the matrix runner or by hand
    if pgrep("bench_matrix_mac.sh") or pgrep("yardstick run") or pgrep("scripts/ortgenai_mac.py"):
        raise Busy("a Mac capture is already running")
    rc, out = sh(["ps", "-Awwo", "command="])  # argv only, one line per process
    heavy = [ln.strip() for ln in out.splitlines()
             if mac_heavy_command(ln.strip()) and "grep" not in ln]
    if heavy:
        raise Busy(f"heavy pipeline running (unified-memory contention): {heavy[0][:120]}")


def side_build_tools(cells_file):
    """On-device paths of the tools a cells file's side-build rows launch (engine-build=<tag>,
    android/README.md "Side builds"), laid out as android/bench/run_cell.py looks for them:
    llama.cpp's release asset keeps its tools in <dev dir>/engines/<tag>/bin/ (llama-bench for a
    native-benchmark task, llama-cli otherwise), LiteRT-LM's NPU build sits flat in
    <dev dir>/engines/<tag>/. Excluded rows launch nothing; a file that is not there is left
    to `bench matrix` to report, as before."""
    path = os.path.join(ROOT, cells_file)
    if not os.path.exists(path):
        return []
    tools = set()
    for c in load_cells(path):
        tag = c["opts"].get("engine-build")
        if c["platform"] != "android" or c["exclude"] or not tag:
            continue
        build = f"{ANDROID_DEV_DIR}/engines/{tag}"
        if c["runtime"] == "litert-lm":
            # a cpu / gpu build's short-chat row launches its litert_lm_main (run_cell.py
            # engine_command); every other LiteRT-LM side-build row its advanced_main
            short = c["opts"].get("backend") in ("cpu", "gpu") and c["task"] == "short-chat" \
                and not c["opts"].get("context-tokens")
            tools.add(f"{build}/{'litert_lm_main' if short else 'litert_lm_advanced_main'}")
        else:
            tool = "llama-bench" if c["task"].startswith("native-benchmark-") else "llama-cli"
            tools.add(f"{build}/bin/{tool}")
    return sorted(tools)


def android_side_builds_missing(serial, cells_files):
    """cells file -> the side-build tools it launches that are not on the phone (one `ls` for
    all of them). run_cell.py stops each such cell before its launch (observed_engine), so the
    job skips that file as a whole and runs the others."""
    tools = {f: side_build_tools(f) for f in cells_files}
    wanted = sorted({t for ts in tools.values() for t in ts})
    if not wanted:
        return {}
    rc, out = sh(adb_cmd(serial, "shell", "ls " + " ".join(wanted) + " 2>/dev/null"))
    present = set(out.split())
    return {f: [t for t in ts if t not in present] for f, ts in tools.items()
            if any(t not in present for t in ts)}


def preflight_android(dev, dry, cells_files=()):
    serial = dev["serial"]
    state = android_state(serial)
    if state is None:
        raise NotReady(f"{serial} not visible to adb — plug it in")
    if state != "device":
        raise NotReady(f"{serial} adb state {state!r} — authorize USB debugging")
    for ln in pgrep("run_campaign.py|run_cell.py"):
        # run_cell.py names its phone in argv (--serial); a campaign driver names it only
        # in its environment (driver_serial), so the job's own sitting on another phone
        # made this phone report busy (2026-10-15, Pixel 8a during an S26 sitting). A
        # driver that names no phone either way counts as busy (conservative).
        m = re.search(r"--serial\s+(\S+)", ln)
        other = m.group(1) if m else driver_serial(int(ln.split(None, 1)[0]))
        if other and other != serial:
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
    # the engines the Android rows run: LiteRT-LM, llama.cpp, ONNX Runtime GenAI (ortgenai_run,
    # model_benchmark in /data/local/tmp/llmbench/ortgenai/)
    rc, out = sh(adb_cmd(serial, "shell", "ps -A | grep -E 'litert_lm|llama|ortgenai_run|model_benchmark' | grep -v grep"))
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
    # a side build that is not on the phone (android/README.md, "Side builds") costs only the
    # files that launch it: phase B skips them and runs the rest; with nothing left to run the
    # device is not ready
    missing = android_side_builds_missing(serial, cells_files)
    for f, tools in missing.items():
        log(f"side build not on the phone for {f}: {', '.join(tools)} — that file is skipped")
    if cells_files and all(f in missing for f in cells_files):
        raise NotReady("side build not on the phone for " + ", ".join(cells_files)
                       + " — push it first (android/README.md, 'Side builds')")
    return {"free_gb": free, "side_build_missing": missing}


def devicectl(*args, timeout=90):
    return sh(["xcrun", "devicectl"] + list(args), timeout=timeout)


def preflight_iphone(dev, dry, cells_files=()):
    udid = dev["udid"]
    if not dev.get("app"):
        raise NotReady("schedule.json: iphone device needs an explicit \"app\" bundle id "
                       "(the runner's default is the retired app)")
    if not iphone_attached(udid):
        raise NotReady(f"{udid} not available to devicectl — connect + trust the phone")
    busy = iphone_runner_busy(udid, dev)
    if busy:
        raise Busy(busy)
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


def preflight_mac(dev, dry, cells_files=()):
    mac_guard()
    rc, out = sh([os.path.join(ROOT, "bench"), "doctor", "--platform", "mac"], timeout=120)
    if rc != 0:
        raise NotReady("bench doctor --platform mac FAILED:\n" + out)
    return {}


# each takes (device entry, dry run, the cells files phase B may run); only the Android
# preflight reads the files (their side builds)
PREFLIGHT = {"android": preflight_android, "iphone": preflight_iphone, "mac": preflight_mac}


# a part's tag names its campaigns (<date>-dashboard-v1-<key>-<tag>-<plat>): these would read as an anchor
# probe, a retake, a stopped sitting's quarantine or a lab unit's dir to the job and the session checker
PART_TAG_RE = re.compile(r"^[a-z][a-z0-9]{0,7}$")
PART_TAG_RESERVED = ("anchor", "retake", "stopped", "ddp")


def device_parts(dev):
    """The device's weekly set in parts, one part per sitting, in the week's order (schedule.json
    "parts": [{"tag", "cells", "expected_hours"}]), or [] for the whole set in one sitting."""
    return list(dev.get("parts") or [])


def check_parts(schedule):
    """ValueError when a device's "parts" cannot run: each part needs a tag (PART_TAG_RE, not one of
    PART_TAG_RESERVED, unique: it names the campaigns) and a cells file, and a part is the sitting's
    one payload file, so no storage halves (split) or extra files (extra_cells) beside parts."""
    for key, dev in (schedule.get("devices") or {}).items():
        parts = device_parts(dev)
        if not parts:
            continue
        tags = [p.get("tag") if isinstance(p, dict) else None for p in parts]
        bad = [t for t, p in zip(tags, parts) if not isinstance(p, dict) or not p.get("cells")
               or not PART_TAG_RE.match(t or "") or t in PART_TAG_RESERVED]
        if bad or len(set(tags)) != len(tags):
            raise ValueError(f"devices.{key}.parts: every part needs a cells file and a unique tag of "
                             f"{PART_TAG_RE.pattern}, not {'/'.join(PART_TAG_RESERVED)} (got {tags})")
        if dev.get("split") or dev.get("extra_cells"):
            raise ValueError(f"devices.{key}: parts with split or extra_cells (a part is the sitting's one "
                             "payload file)")


RELEASE_BY_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def check_release_by(schedule):
    """ValueError when a device's release_by is not "HH:MM" (local, 24 h)."""
    for key, dev in (schedule.get("devices") or {}).items():
        v = dev.get("release_by")
        if v is not None and not RELEASE_BY_RE.match(str(v)):
            raise ValueError(f"devices.{key}.release_by: \"HH:MM\" local time, not {v!r}")


def release_deadline(dev, start, override=None):
    """When a sitting of `dev` in an invocation begun at `start` (naive local time) gives its hold back: the
    first release_by (schedule.json "HH:MM", local) after `start`, so a firing's busy polls, its abort
    retry and its retake sitting keep that morning's time; --release-by (`override`) "HH:MM" replaces it,
    "none" lifts it. None when neither sets one."""
    text = dev.get("release_by") if override is None else override
    if not text or str(text).lower() == "none":
        return None
    m = RELEASE_BY_RE.match(str(text))
    t = start.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
    return t if t > start else t + datetime.timedelta(days=1)


def part_budget(dev, part):
    """A sitting's expected length in seconds for the hold's release estimate: the part's
    expected_hours, else the device's; None when neither is set."""
    return float((part or {}).get("expected_hours") or dev.get("expected_hours") or 0) * 3600 or None


def parts_problem(schedule, dev):
    """None when the device's parts hold its platform's rows of the weekly set (schedule.json "cells"),
    else what is off. Each part's first row of the platform is the set's session anchor row (anchor=1:
    each part is a session of its own, re-judged on its own anchor records, §4), each part's other rows
    are rows of the set in the set's order, and together they are the set's rows but that anchor, each
    once. Rows compare as written, comments and blank lines aside. A row added to the set and to no part
    would never run in the weekly job: scripts/dashboard_job_selftest.py holds schedule.json to this."""
    token = PLATFORM_TOKEN[dev["platform"]]

    def rows(path):
        with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
            lines = [ln.split("#", 1)[0].strip() for ln in fh]
        return [ln for ln in lines if ln.split(" ", 1)[0] == token]
    try:
        whole = rows(schedule["cells"])
        anchor = next(r for r in whole if "anchor=1" in r.split())
        bodies = []
        for p in device_parts(dev):
            own = rows(p["cells"])
            if not own or own[0] != anchor:
                return (f"part {p['tag']} ({p['cells']}): its first {token} row is not the set's session "
                        "anchor row")
            rest = iter(whole)
            if not all(r in rest for r in own[1:]):
                return (f"part {p['tag']} ({p['cells']}): a {token} row that is not in {schedule['cells']}, "
                        "or out of its order")
            bodies += own[1:]
    except (OSError, StopIteration, KeyError) as e:
        return f"parts unreadable: {type(e).__name__}: {e}"
    want = [r for r in whole if r != anchor]
    if sorted(bodies) == sorted(want):
        return None
    missing = [r for r in want if r not in bodies]
    twice = len(bodies) - len(set(bodies))
    return (f"the parts hold {len(bodies)} {token} rows besides the anchor, the set {len(want)}"
            + (f"; in no part: {missing[0]!r}" + (f" and {len(missing) - 1} more" if len(missing) > 1 else "")
               if missing else "")
            + (f"; {twice} in two parts" if twice else ""))


def phase_b_files(schedule, dev, cells_override, left=None):
    """The cells files phase B may run: an explicit --cells file alone (a targeted retake), or
    the whole set and the device's storage halves (the free space decides which) followed by
    its extra files; with `left` (sitting_left: earlier sittings this week ran the rest), only the
    runs it names."""
    if cells_override:
        return [cells_override]
    if left is None:
        return ([schedule["cells"]] + [h["cells"] for h in dev.get("split", [])]
                + [e["cells"] for e in dev.get("extra_cells", [])])
    rest = ([] if left["set"] is None else list(left["set"]) if isinstance(left["set"], list)
            else [schedule["cells"]] + [h["cells"] for h in dev.get("split", [])])
    return rest + [e["cells"] for e in dev.get("extra_cells", []) if e["cells"] in left["extras"]]


def phase_b_halves(dev, args, info):
    """The storage halves phase B runs (schedule.json "split"), or None for the whole set: halves when
    the phone's free space (preflight's free_gb) is under storage_gb_full, or when the whole set would end
    past the device's release_by and the halves fit (info window_halves: window_plan); the halves still to
    run this week when earlier sittings ran the others (args.week_left, sitting_left), and none when they
    ran the set; never for an explicit --cells file (single-file mode, a targeted retake: design §5)."""
    if dev["platform"] == "android" and dev.get("split") and not args.cells:
        left = getattr(args, "week_left", None)
        if left is not None and left["set"] != "whole":
            return [h for h in dev["split"] if h["cells"] in (left["set"] or [])] or None
        free = info.get("free_gb")
        if (free is not None and free < float(dev.get("storage_gb_full", 0))) or info.get("window_halves"):
            return dev["split"]
    return None


def phase_b_plan(schedule, dev, args, halves):
    """(the payload files with their storage floors in order, the extra files' entries by file):
    the halves or the whole set (an explicit --cells file alone; the sitting's part, args.part_entry,
    on a device whose set is in parts; none when this week's sittings ran the set, args.week_left), then
    the device's extra_cells files (an arm measured on this device only) still to run this week, none
    for --cells."""
    part = getattr(args, "part_entry", None)
    left = None if args.cells else getattr(args, "week_left", None)
    if halves:
        plan = [(h["cells"], float(h.get("min_free_gb", 0))) for h in halves]
    elif left is not None and left["set"] != "whole":
        plan = []
    else:
        plan = [(args.cells or (part["cells"] if part else schedule["cells"]), 0.0)]
    extras = {} if args.cells else {e["cells"]: e for e in dev.get("extra_cells", [])
                                    if left is None or e["cells"] in left["extras"]}
    return plan, extras


def run_tag(cells_file, extras):
    """A storage half's or an extra file's campaign tag: the extra entry's "tag", else the file name's
    tail (dashboard-text-v1-android-b1.cells -> b1)."""
    return ((extras[cells_file].get("tag") if cells_file in extras else None)
            or re.sub(r"^.*-android-|\.cells$", "", os.path.basename(cells_file)))


def sitting_runs(schedule, dev, args, info):
    """The runs a sitting makes once it holds the device, in order, for the hold's release estimate
    (scripts/hold_eta.py) -> [(kind, cells file, tag)]: the anchor phase, then phase B's files as
    phase B picks them (the storage halves when the phone is short of space, then the extra files),
    less a file whose side build preflight found missing, a retake file followed by its profile pair."""
    runs = [("matrix", schedule["anchors"], "anchor")]
    halves = phase_b_halves(dev, args, info)
    plan, extras = phase_b_plan(schedule, dev, args, halves)
    for cells_file in [f for f, _ in plan] + list(extras):
        if cells_file in info.get("side_build_missing", {}):
            continue
        if halves or cells_file in extras:
            tag = run_tag(cells_file, extras)
        elif args.cells:
            tag = os.path.basename(cells_file).replace(".cells", "")
        else:
            part = getattr(args, "part_entry", None)
            tag = part["tag"] if part else "set"
        runs.append(("matrix", cells_file, tag))
        if getattr(args, "profile", False) and dev["platform"] == "android":
            runs.append(("profile", cells_file, "profile"))
    return runs


def release_estimate(schedule, key, dev, args, info, hold, dry, deadline=None):
    """The sitting's hold release estimate (scripts/hold_eta.py, docs/dashboard-recurring-job-v1.md
    §10) -> a hold_eta.HoldNote that keeps expected_release / release_basis / release_updated in the
    hold as the sitting moves, or None. The job writes only into a hold it took itself, never a
    keeper's (--hold-held-by); a dry run logs what the hold would read and writes nothing. A retake
    sitting the weekly set follows says so in the basis (that set takes a new hold). With the device's
    release_by (`deadline`, §11) the time ends with the runs expected to end by then. Nothing here
    stops a sitting: a failure is one WARN line and no estimate."""
    try:
        now = datetime.datetime.now()
        lengths = hold_eta.history(LOG_DIR, key)
        token = PLATFORM_TOKEN[dev["platform"]]
        # the device's expected_hours is the weekly set's (a part's, on a device whose set is in parts):
        # a --cells sitting (a retake) is not shared it
        budget = part_budget(dev, getattr(args, "part_entry", None))
        stages = hold_eta.plan_stages(sitting_runs(schedule, dev, args, info), dev, key, lengths,
                                      platform_token=token, budget_s=None if args.cells else budget)
        sitting = hold_eta.Sitting(stages, lengths, deadline=deadline)
        then = None
        if getattr(args, "weekly_follows", False):
            wargs = argparse.Namespace(**dict(vars(args), cells=None, profile=False))
            wargs.part_entry = sitting_part(schedule, key, dev, wargs)[0]
            wargs.week_left = sitting_left(schedule, key, dev, wargs)
            weekly = hold_eta.Sitting(hold_eta.plan_stages(sitting_runs(schedule, dev, wargs, info), dev, key,
                                                           lengths, platform_token=token,
                                                           budget_s=part_budget(dev, wargs.part_entry)), lengths,
                                      deadline=deadline)
            # from when this sitting is expected to end: the weekly set's runs meet release_by from there
            mine, _ = sitting.estimate(now)
            weta, _ = weekly.estimate(mine)
            then = (f"then the weekly set as its own sitting (a new hold), "
                    f"~{hold_eta.fmt_span((weta - mine).total_seconds())}")
        if dry or not hold or not _LOG:
            if dry:
                eta, basis = sitting.estimate(now)
                log(f"  the hold would read expected_release {eta.strftime(hold_eta.RELEASE_FMT)} "
                    f"({basis}{'; ' + then if then else ''}) [dry-run]")
            return None
        _LOG.flush()
        note = hold_eta.HoldNote(hold[1], os.getpid(), sitting, _LOG.name, os.path.getsize(_LOG.name),
                                 warn=log, then=then)
        note.update(force=True)
        return note
    except Exception as e:  # noqa: BLE001 — the estimate never stops a sitting
        log(f"WARN hold release estimate off for this sitting: {type(e).__name__}: {e}")
        return None


def run_start_test(sitting, cells_file, at, profile=False):
    """(seconds the run of `cells_file` is taken to need, the time it would end) when it starts at `at`, for
    the release_by test: hold_eta.Sitting.start_length of its stage (the launches its rows owe, or its newest
    whole length on record when longer: the gate's re-runs are inside a run, counted, never a cut point),
    with the retake profile pair that follows it; (None, None) when the sitting has no such stage."""
    st = next((s for s in sitting.stages if s.kind == "matrix" and s.cells == cells_file
               and s.start is None and not s.skipped), None)
    if st is None:
        return None, None
    own = sitting.own_lengths()
    need = sitting.start_length(st, own)
    if profile:
        need += sum(sitting.start_length(p, own) for p in sitting.stages
                    if p.kind == "profile" and p.cells == cells_file and p.start is None)
    return need, at + datetime.timedelta(seconds=need)


def window_plan(schedule, key, dev, args, info, deadline, now=None):
    """Before the hold, a sitting of a device with a release_by (`deadline`, release_deadline) -> the
    hold_eta.Sitting of its runs, which the cut between runs reads where the hold's own estimate is not
    kept (a dry run, a failed estimate). The whole set gives way to the storage halves (info window_halves)
    when it would end past the deadline after the anchor phase and the device has halves: the same rows,
    one session each, so a sitting can stop between them. TooLate when the anchor phase and the first
    payload run would not end by then: no hold, nothing runs (docs/dashboard-recurring-job-v1.md §11)."""
    now = now or datetime.datetime.now()
    lengths = hold_eta.history(LOG_DIR, key)
    budget = None if args.cells else part_budget(dev, getattr(args, "part_entry", None))

    def sitting():
        return hold_eta.Sitting(hold_eta.plan_stages(sitting_runs(schedule, dev, args, info), dev, key, lengths,
                                                     platform_token=PLATFORM_TOKEN[dev["platform"]], budget_s=budget),
                                lengths, deadline=deadline)

    def first_of(s):
        return next((st for st in s.stages[1:] if st.kind == "matrix"), None)
    s = sitting()
    anchor_s = s.start_length(s.stages[0])
    after_anchor = now + datetime.timedelta(seconds=anchor_s)
    first = first_of(s)
    if (first is not None and first.cells == schedule["cells"]
            and phase_b_halves(dev, args, dict(info, window_halves=True))):
        need, end = run_start_test(s, first.cells, after_anchor)
        if end > deadline:
            info["window_halves"] = True
            log(f"release_by {deadline:%F %H:%M}: the whole set (~{hold_eta.fmt_span(need)}) would end "
                f"{end:%H:%M} after the anchor phase — running its storage halves instead (the same rows, one "
                "session each, so the sitting can stop between them)")
            s = sitting()
            first = first_of(s)
    if first is None:
        return s
    need, end = run_start_test(s, first.cells, after_anchor,
                               profile=getattr(args, "profile", False) and dev["platform"] == "android")
    if end > deadline:
        raise TooLate(f"release_by {deadline:%F %H:%M}: the anchor phase (~{hold_eta.fmt_span(anchor_s)}) and "
                      f"{first.tag} (~{hold_eta.fmt_span(need)}) would end {end:%H:%M}; nothing started")
    log(f"release_by {deadline:%F %H:%M}: the anchor phase and {first.tag} (~{hold_eta.fmt_span(need)}) are "
        f"expected to end {end:%H:%M}; a later run expected to end past release_by is not started")
    return s


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


QUIET_SCHEDULED = re.compile(r"\d+\s+(?:adopted|thaw)\s+(\d+)")  # a scheduler's slot line names its root


def quiet_lock_others(path):
    """What the other jobs want of the Mac window at `path` -> a reason, or None when nothing.
    Counted as quiet_rank.py counts the jobs a window waits for (~/code/standup/tools/quiet:
    window_blockers): a quiet_hold.py window waiter registered in `<lock>.waiters/<pid>`
    (hold_waiters), a quiet_yield.py job registered in `<lock>.yield_waiters/<pid>` while it waits for
    a build slot (waiting_jobs), and the job a held `<lock>.yield_slots/<i>` names (running_jobs): the
    pid its line starts with, or the root of a scheduler's `<pid> adopted|thaw <root>` line. quiet_yield
    jobs are the lanes' builds and exports that run outside the windows and stop while one is open.
    A registration counts while its process lives, is not stopped (SIGSTOP from outside: it cannot take
    its turn) and started before the file was written (else the pid was reused); a slot's job counts
    stopped too (it keeps the slot); the lock line's holder and this process's ancestors never count.
    Every such job counts: the user's Mac priority (~/code/standup/state/mac-priority.txt, 2026-10-28)
    ranks the nightly dashboard last, with the other bench work (bench goes last, user 2026-10-22), so
    the job reads no ranks, and it lets the bench-rank jobs go first too, where quiet_hold orders them by
    waiting time. quiet_rank's scan for quiet_yield waiters from before the registry (2026-10-28 09:05)
    is left out. 2026-10-28 02:47: a sitting took the free window while lane builds ran outside the
    windows, and they stood stopped for its length."""
    rc, out = sh(["ps", "-A", "-o", "pid=,ppid=,stat=,lstart="], env=dict(os.environ, LC_ALL="C"))
    procs = {}                                  # pid -> (ppid, state, start); {} when ps fails
    for ln in out.splitlines() if rc == 0 else []:
        f = ln.split()
        try:
            procs[int(f[0])] = (int(f[1]), f[2],
                                time.mktime(time.strptime(" ".join(f[3:8]), "%a %b %d %H:%M:%S %Y")))
        except (IndexError, ValueError):
            continue
    skip, pid = {os.getpid()}, os.getpid()
    while pid in procs and procs[pid][0] > 1 and procs[pid][0] not in skip:
        pid = procs[pid][0]
        skip.add(pid)
    skip.add(os.getppid())

    def alive(pid):
        if not procs:
            return pid_alive(pid)
        return pid in procs and not procs[pid][1].startswith("Z")

    def registered(directory, holder=None):
        out = []
        try:
            names = sorted(os.listdir(directory))
        except OSError:
            return out
        for name in names:
            f = os.path.join(directory, name)
            try:
                written, text = os.stat(f).st_mtime, open(f, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            pid = int(name) if name.isdigit() else None
            if (pid is None or pid in skip or pid == holder or not alive(pid)
                    or (procs and (procs[pid][1].startswith("T") or procs[pid][2] > written + 1))):
                continue
            out.append((pid, text.strip()))
        return out

    running, sdir = [], path + ".yield_slots"
    try:
        slots = sorted(os.listdir(sdir), key=lambda s: (len(s), s))
    except OSError:
        slots = []
    for name in slots:
        try:
            sfd = os.open(os.path.join(sdir, name), os.O_RDONLY)
        except OSError:
            continue
        try:
            try:
                fcntl.flock(sfd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(sfd, fcntl.LOCK_UN)
                line = ""
            except BlockingIOError:
                line = os.read(sfd, 4096).decode("utf-8", "replace")
        except OSError:
            line = ""
        finally:
            os.close(sfd)
        m = QUIET_SCHEDULED.match(line) or re.match(r"(\d+)", line)
        if m and int(m.group(1)) not in skip and alive(int(m.group(1))):
            running.append((int(m.group(1)), f"slot {name}: {line.strip()}"))
    busy = {pid for pid, _ in running}
    slot_waiters = [(pid, text) for pid, text in registered(path + ".yield_waiters") if pid not in busy]
    try:
        m = re.search(r"\bpid\s+(\d+)", open(path, encoding="utf-8", errors="replace").read())
    except OSError:
        m = None
    window_waiters = registered(path + ".waiters", int(m.group(1)) if m else None)
    why = [f"{len(jobs)} job(s) {what} (pid {jobs[0][0]}: {jobs[0][1][:80]})"
           for jobs, what in ((window_waiters, "waiting for the window"),
                              (slot_waiters, "waiting for a build slot"), (running, "holding a build slot"))
           if jobs]
    return "; ".join(why) or None


def quiet_lock_take(dev, label):
    """The Mac measurement window for a sitting: flock the lock file schedule.json names in
    "quiet_lock" (the machine's ~/code/coreai/_GPU_LOCK: every other lane's heavy job waits on it
    through quiet_wait.py and the guard hook) and write the `timing` label the others read. None
    when the device names no lock. A lock another process holds = Busy (the job's busy retry), and
    so is a free one other jobs want (quiet_lock_others): counted with the flock taken, so no lane
    window opens between the count and the take, then let go untouched (its line, and the mtime
    quiet_hold.py's build gap reads).
    2026-10-19 12:39: an export from another lane ran on top of a Mac sitting because the sitting
    held no lock; the runner's name-based guard only refuses to start."""
    path = expand(dev.get("quiet_lock"))
    if not path:
        return None
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        try:
            holder = open(path, encoding="utf-8", errors="replace").read().strip()[:160]
        except OSError:
            holder = "?"
        os.close(fd)
        raise Busy(f"the Mac measurement window is held by another lane: {holder or path}")
    try:
        others = quiet_lock_others(path)
        if others:
            raise Busy(f"the Mac measurement window goes to the other jobs first (bench goes last): {others}")
    except BaseException:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
        raise
    line = f"dashboard-job {label} timing pid {os.getpid()} since {time.strftime('%Y-%m-%dT%H:%M:%S%z')}"
    os.ftruncate(fd, 0)
    os.lseek(fd, 0, 0)
    os.write(fd, line.encode())
    os.fsync(fd)
    log(f"quiet window taken: {path} ({line})")
    return (fd, path)


def quiet_lock_release(q):
    if not q:
        return
    fd, path = q
    try:
        os.ftruncate(fd, 0)
        os.fsync(fd)
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
        log(f"quiet window released: {path}")
    except OSError as e:
        log(f"WARN quiet window release failed: {e}")


# ---------------------------------------------------------------- capture

# how often a running `bench matrix` / `bench profile` lets the hold's release estimate read the log
WATCH_POLL_S = 30


def run_logged(cmd, env, watch=None):
    """Run cmd with its output in the job log -> its exit code. With `watch` (the hold's release
    estimate, hold_eta.HoldNote) the estimate reads the log every WATCH_POLL_S while it runs; the
    command, its output and its exit code are the same either way."""
    if watch is None:
        return subprocess.run(cmd, env=env, cwd=ROOT, stdout=_LOG or None, stderr=subprocess.STDOUT).returncode
    with subprocess.Popen(cmd, env=env, cwd=ROOT, stdout=_LOG or None, stderr=subprocess.STDOUT) as p:
        try:
            while True:
                try:
                    return p.wait(timeout=WATCH_POLL_S)
                except subprocess.TimeoutExpired:
                    watch.update()
        except BaseException:
            p.kill()   # as subprocess.run does on any interruption
            raise


def run_matrix(cells, platform, campaign, env, timeout_s, dry, ddp=None, watch=None):
    # a lab unit (ddp = its catalog id): the android rows as Device Run sessions, android/ddp/run_ddp.py
    target = ["--ddp", ddp] if ddp else ["--platform", platform]
    cmd = ["gtimeout", "--kill-after=60", str(int(timeout_s)),
           os.path.join(ROOT, "bench"), "matrix", cells] + target + ["--campaign", campaign]
    log("$ " + " ".join(cmd) + "   env: " + " ".join(f"{k}={v!r}" for k, v in env.items()))
    if dry:
        return 0
    e = dict(os.environ)
    e.update(env)
    # the runners' progress lines (cells, rounds, gate verdicts) go to the job
    # log through a pipe; unbuffered, or they arrive in 8 KB chunks hours late
    # (first S26 run, 2026-09-08: round markers invisible until exit)
    e["PYTHONUNBUFFERED"] = "1"
    rc = run_logged(cmd, e, watch)
    log(f"bench matrix exit {rc}")
    if watch is not None:
        watch.update()
    return rc


def run_profile(cells, campaign, env, timeout_s, dry, watch=None):
    """A retake's per-op profile (docs/dashboard-autopilot-v1.md §8): `./bench profile <cells>
    --campaign <campaign>` writes, per android litert-lm native-benchmark row of the file, a control
    run and its --enable_profiling twin into <campaign>-android/profiles/ (android/bench/run_profile.py,
    docs/profiling-subcommand-design.md); the control's record is an ordinary speed run of the same
    sitting, the profiled twin's never is; the file's other rows are listed in profiles/SKIPPED.txt."""
    cmd = ["gtimeout", "--kill-after=60", str(int(timeout_s)),
           os.path.join(ROOT, "bench"), "profile", cells, "--campaign", campaign]
    log("$ " + " ".join(cmd) + "   env: " + " ".join(f"{k}={v!r}" for k, v in env.items()))
    if dry:
        return 0
    e = dict(os.environ)
    e.update(env)
    e["PYTHONUNBUFFERED"] = "1"
    rc = run_logged(cmd, e, watch)
    log(f"bench profile exit {rc}")
    if watch is not None:
        watch.update()
    return rc


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


def engine_version_of(rows):
    """The engine build stamped on a session's rows of one cell (the witness,
    which may differ from the pin registry); None when no row carries one.
    One session runs one cell on one build; if rows ever disagree, the build
    most of them carry."""
    counts = collections.Counter(r.get("engine_version") or "" for r in rows)
    counts.pop("", None)
    return counts.most_common(1)[0][0] if counts else None


def reference_note(p):
    """Tail of an admission reason: what the primary anchor was judged against."""
    engine = p["engine_version"]
    if p["ratio"]:
        return f"ratio {p['ratio']:.3f} vs reference" + (
            f" ({engine})" if engine else " (anchor rows unstamped: reference of any build)")
    if p["reference_any_version"]:
        ran = p["reference_any_version"]["engine_version"] or "unstamped rows"
        return (f"first session with engine version {engine} on this device "
                f"(newest admitted session ran {ran})")
    return "first session on this device"


def admit(schedule, dev, campaign_rel_path, platform):
    """Compare this session's primary anchor with the newest admitted
    session's on the same device whose anchor ran the same engine build.
    Returns (admitted, reason, details)."""
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
        engine = engine_version_of(mine)
        # candidates: every admitted earlier session with this cell on this
        # device, newest first
        by_camp = {}
        for r in rows:
            if (r["platform"] == plat and r["device"] == ident and r["runtime"] == c["arm"]
                    and r["model_id"] == c["model_id"] and r["task"] == c["task"]
                    and r["campaign"] != campaign_rel_path
                    and admitted_map.get(r["campaign"], True)):
                by_camp.setdefault(r["campaign"], []).append(r)
        newest_first = sorted(by_camp, key=lambda k: max(x["timestamp"] or "" for x in by_camp[k]),
                              reverse=True)

        def usable(camp):
            rmed, rn, rstates = session_stats(by_camp[camp], regime)
            if rmed is None or rn < min_runs:
                return None
            return {"campaign": camp, "median": rmed, "n": rn, "thermal": rstates,
                    "engine_version": engine_version_of(by_camp[camp])}

        # The reference must have run the anchor on the same engine build as
        # this session (the stamped witness, not the pin): on 2026-09-13 the
        # Pixel 8a's newest admitted session had run the llama.cpp anchor on
        # b10903 (55 tok/s) while the sitting ran the pin b8999 (22-31 in every
        # other Pixel session), and the collapse bar passed at 0.513 by luck.
        # No admitted session on this build = first session on it. The session
        # the build-blind rule would have taken stays in the record as
        # reference_any_version, so the exclusion can be read back. Rows with
        # no stamp (pre-v1) never match; a session whose own anchor rows carry
        # no stamp is judged against any build, and its reason says so.
        ref = ref_nominal = ref_any = None
        for camp in newest_first:
            cand = usable(camp)
            if cand is None:
                continue
            if ref_any is None:
                ref_any = cand
            if engine is not None and cand["engine_version"] != engine:
                continue
            if ref is None:
                ref = cand
            if ref_nominal is None and all(s in ("nominal", "") for s in cand["thermal"]):
                ref_nominal = cand
            if ref and ref_nominal:
                break
        details["anchors"].append({"cell": f"{c['arm']} {c['model_id']} {c['task']}",
                                   "primary": c is primary, "median": med, "n": n,
                                   "thermal": states, "engine_version": engine,
                                   "reference": ref, "reference_nominal": ref_nominal,
                                   "reference_any_version": ref_any,
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
                          f"{tol*100:.0f}% of the newest all-nominal session on this build"), details
        return False, "anchor-thermal", details
    return True, "anchor nominal, " + reference_note(p), details


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


def cells_with_records(rel_path, cells_file, platform, ident, key=None):
    """(cells the device was to run, cells with a record): the file's rows of the platform minus its
    exclude= rows and, given the device key, the rows exclude-on= names for that device (the runner
    skips those with a CELL_SKIP line and no record; counting them read every Pixel 8a sitting of a
    file with 4B-class rows as partial, 2026-10-19)."""
    plat = PLATFORM_TOKEN[platform]
    want = {(c["arm"], c["model_id"], c["task"]) for c in load_cells(os.path.join(ROOT, cells_file))
            if c["platform"] == plat and not c["exclude"] and not (key and key in c["exclude_on"])}
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


def post_args(args, dirs):
    """The post's options a run by hand passes through: --post-page-out DIR -> --page-out
    DIR/<the sitting's last campaign> (the post builds into an empty or new dir), --no-page-commit."""
    out = []
    if getattr(args, "post_page_out", None) and dirs:
        out += ["--page-out", os.path.join(os.path.abspath(os.path.expanduser(args.post_page_out)),
                                           os.path.basename(dirs[-1]))]
    if getattr(args, "no_page_commit", False):
        out.append("--no-page-commit")
    return out


def post_sitting(code, dirs, dry, extra=()):
    """Hand a sitting that exited 0 to scripts/dashboard_post.py over the campaign dirs it wrote
    SESSION.json in (docs/dashboard-autopilot-v1.md) -> the command, or None when there is
    nothing to hand over (another exit code, no dir). A dry run prints the command and runs
    nothing. The post's output goes to this job log; its exit code, a HOLD or a failure is one
    line here and its own ledger line (logs/dashboard-job/autopilot-ledger.tsv), never the
    sitting's exit code or ledger line. `extra`: post_args."""
    if code != EXIT_OK or not dirs:
        return None
    cmd = [PY, POST] + list(extra) + list(dirs)
    log("post: $ " + " ".join(cmd) + ("   [dry-run: printed, not run]" if dry else
                                      "   [--no-post: printed, not run; a person runs it after review]"
                                      if NO_POST else ""))
    if dry or NO_POST:
        return cmd
    try:
        p = subprocess.run(cmd, cwd=ROOT, stdout=_LOG or None, stderr=subprocess.STDOUT,
                           timeout=POST_TIMEOUT_S, env=dict(os.environ, PYTHONUNBUFFERED="1"))
        rc = p.returncode
    except subprocess.TimeoutExpired:
        rc = 124
    except OSError as e:
        log(f"post did not start: {e}")
        rc = 127
    what = {0: "committed, or nothing new", 1: "held, or a step after the commit failed", 2: "usage",
            124: f"killed after {POST_TIMEOUT_S} s"}.get(rc, "?")
    log(f"post exit {rc} ({what}; logs/dashboard-job/autopilot-ledger.tsv) — the sitting's exit "
        f"{code} stands")
    return cmd


# ---------------------------------------------------------------- one attempt

def attempt(schedule, key, dev, attempt_no, args):
    """One sitting -> (exit code, reason, the last campaign dir, the campaign dirs it wrote
    SESSION.json in — a dry run: the ones it would; what main() hands to the post step)."""
    platform = dev["platform"]
    date = datetime.date.today().isoformat()
    suffix = ("-" + args.suffix.strip("-")) if args.suffix else ""   # always one leading dash
    # a device whose weekly set is in parts runs one part per sitting, named in its campaigns
    part, part_why = sitting_part(schedule, key, dev, args)
    # the weekly plan's runs that earlier sittings this week left (a sitting stopped at release_by, §11)
    left = sitting_left(schedule, key, dev, args)
    args = argparse.Namespace(**dict(vars(args), part_entry=part, week_left=left))
    stem = f"{date}-dashboard-v1-{key}" + (f"-{part['tag']}" if part else "") + suffix
    n = attempt_no
    # a weekly sitting never runs in a campaign an earlier sitting of the day ran in (its anchor phase's
    # dir is on disk): admit() would pool both sittings' anchor rows (memory
    # stopped-sitting-needs-a-new-campaign-name); the next -r<n> is free
    while not args.cells and os.path.isdir(os.path.join(ROOT, campaign_rel(
            stem + (f"-r{n}" if n > 1 else "") + "-anchor", platform))):
        n += 1
    base = stem + (f"-r{n}" if n > 1 else "")
    env = device_env(dev)
    dry = args.dry_run
    started = time.strftime("%F %T")
    log(f"=== slot {key} ({dev['display']}, {platform}) attempt {attempt_no} campaign base {base}"
        + (" [dry-run]" if dry else ""))
    if n != attempt_no:
        log(f"campaign base {base}: {campaign_rel(stem + (f'-r{attempt_no}' if attempt_no > 1 else '') + '-anchor', platform)}"
            " is on disk from an earlier sitting today")
    if part:
        log(f"part {part['tag']} of the week's parts {'/'.join(p['tag'] for p in device_parts(dev))}: "
            f"{part['cells']}, expected {part.get('expected_hours', '?')} h ({part_why})")
        problem = parts_problem(schedule, dev)
        if problem:
            log(f"WARN the parts and {schedule['cells']} differ, the weekly job misses what no part holds: "
                f"{problem}")
    if left is not None:
        log(f"the week's plan: {', '.join(left_tags(dev, left))} left by this week's earlier sittings — "
            "this sitting runs those")
    # the device's release_by: the hold is given back by then (§11); never into a keeper's hold
    deadline = None if HOLD_KEEPER is not None else release_deadline(
        dev, getattr(args, "started_at", None) or datetime.datetime.now(), getattr(args, "release_by", None))

    if HOLD_KEEPER is not None:
        # judged before the preflight, in a dry run too: the preflight's hold check reads
        # the keeper's hold as the sitting's own only once it is known to be the keeper's
        problem = keeper_hold_problem(dev, HOLD_KEEPER)
        if problem:
            raise ConfigError(f"--hold-held-by {HOLD_KEEPER}: {problem}")
        log(f"--hold-held-by {HOLD_KEEPER}: the keeper holds {expand(dev.get('hold'))}")
    files = phase_b_files(schedule, dev, args.cells or (part["cells"] if part else None), left)
    info = PREFLIGHT[platform](dev, dry, files)  # raises Busy / NotReady
    log("preflight ok")
    # before the hold: the anchor phase and the first payload run must end by release_by (TooLate)
    fit = window_plan(schedule, key, dev, args, info, deadline) if deadline is not None else None
    if dry:
        log("plan:")
    if HOLD_KEEPER is not None:
        hold = None
        log(f"hold kept by keeper pid {HOLD_KEEPER} (not acquired / not released by the job)"
            + (" [dry-run]" if dry else ""))
    else:
        hold = None if dry else hold_acquire(schedule, dev)
    created = []
    planned = []    # a dry run: the campaign dirs the sitting would create

    def sitting_dirs():
        return (list(planned) if dry else
                [d for d in created if os.path.exists(os.path.join(ROOT, d, "SESSION.json"))])
    qlock = None
    eta = None
    try:
        # the Mac measurement window for the whole sitting (schedule "quiet_lock"; Busy when held)
        qlock = None if dry else quiet_lock_take(dev, f"{key} {base}")
        # a phone past its uptime limit is rebooted here, under the hold
        # (reboot_before, opt-in per device; §3) — then the state a reboot
        # changes is read again
        if platform == "android" and android_reboot_if_stale(dev, dry):
            info["free_gb"] = android_free_gb(dev["serial"])
            log(f"free on /data: {info['free_gb']:.1f} GB" if info["free_gb"] is not None
                else "free on /data: unknown")
        # when the hold is expected back, in the hold itself, rewritten as the sitting moves (§10)
        eta = release_estimate(schedule, key, dev, args, info, hold, dry, deadline)
        # a dry run's clock for the release_by test: each run taken to end when it is expected to
        clock = (datetime.datetime.now() + datetime.timedelta(seconds=fit.start_length(fit.stages[0]))
                 if fit is not None and dry else None)
        # --- phase A: the session anchor as its own short campaign
        anchor_camp = f"{base}-anchor"
        anchor_rel = campaign_rel(anchor_camp, platform)
        rc = run_matrix(schedule["anchors"], platform, anchor_camp, env, 45 * 60, dry, watch=eta)
        if dry:
            planned.append(anchor_rel)
            log(f"  admission would read {anchor_rel} against the newest admitted session "
                "on the same engine build")
        else:
            created.append(anchor_rel)
            if rc == 124:
                write_session(anchor_rel, {"campaign": anchor_rel, "phase": "anchor",
                                           "admitted": False, "verdict": "TIMEOUT",
                                           "reason": "anchor phase timed out",
                                           "device_key": key, "started": started,
                                           "ended": time.strftime("%F %T")})
                return EXIT_TIMEOUT, "anchor phase timed out", anchor_rel, sitting_dirs()
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
                return EXIT_ABORTED, reason, anchor_rel, sitting_dirs()

        # --- phase B: the payload, whole or in storage halves
        # an explicit --cells file is single-file mode (a targeted retake, design
        # §5): it names its own rows and never fans out into the storage halves
        halves = phase_b_halves(dev, args, info)
        if halves:
            free = info.get("free_gb")
            if left is not None and left["set"] != "whole":
                log(f"running the halves this week's earlier sittings left ({', '.join(run_tag(h['cells'], {}) for h in halves)}), "
                    "with model rotation")
            elif free is not None and free < float(dev.get("storage_gb_full", 0)):
                log(f"free {free:.1f} GB < {dev['storage_gb_full']} GB for the whole set — "
                    f"running {len(halves)} halves with model rotation")
            else:
                log(f"running {len(halves)} halves with model rotation: the whole set would end past release_by")
        # per-device extra files (schedule.json "extra_cells": an arm measured on
        # this device only, e.g. the ONNX Runtime GenAI cells on the Galaxy S26):
        # each runs after the set as its own tagged session with its own timeout
        # (the tag: the entry's "tag", else from the file name as for a half);
        # an explicit --cells retake never fans out into them
        plan, extras = phase_b_plan(schedule, dev, args, halves)
        timeout_s = float(dev.get("timeout_hours", 6)) * 3600 / max(len(plan), 1)
        plan += [(f, float(e.get("min_free_gb", 0))) for f, e in extras.items()]
        worst = EXIT_OK
        previous = []
        last_rel = None
        no_build = []
        cut = []        # the runs release_by left for a later firing (§11)

        def tag_of(cells_file):
            if halves or cells_file in extras:
                return run_tag(cells_file, extras)
            return part["tag"] if part else ("set" if cells_file == schedule["cells"]
                                             else os.path.basename(cells_file).replace(".cells", ""))
        for i, (cells_file, floor) in enumerate(plan):
            camp = base
            if halves or cells_file in extras:
                tag = run_tag(cells_file, extras)
                camp = f"{base}-{tag}"
            if cells_file in info.get("side_build_missing", {}):
                # preflight found its side build missing: no session, no rotation for it; the
                # verdict stays the sitting's, the reason names the file (ledger)
                log(f"skipping {cells_file}: side build not on the phone "
                    f"({', '.join(info['side_build_missing'][cells_file])}; android/README.md, "
                    "'Side builds')")
                no_build.append(os.path.basename(cells_file))
                continue
            if deadline is not None:
                # release_by (§11): a run expected to end past it is not started, nor any after it;
                # the run under way was never stopped. The hold's own estimate has read this sitting's
                # launches; a dry run's clock is the plan's
                at = clock if dry else datetime.datetime.now()
                need, end = run_start_test(eta.sitting if eta is not None else fit, cells_file, at,
                                           profile=getattr(args, "profile", False) and platform == "android")
                if need is None and eta is not None:
                    need, end = run_start_test(fit, cells_file, at,
                                               profile=getattr(args, "profile", False) and platform == "android")
                if need is None:
                    log(f"WARN release_by: no estimate of {cells_file}; it runs")
                elif end > deadline:
                    cut = [tag_of(f) for f, _ in plan[i:]]
                    log(f"release_by {deadline:%F %H:%M}: {tag_of(cells_file)} (~{hold_eta.fmt_span(need)}) "
                        f"would end {end:%H:%M} — not started; the sitting closes with the runs it finished "
                        f"and gives the hold back; left for a later firing this week: {', '.join(cut)}"
                        + (" [dry-run]" if dry else ""))
                    break
                elif dry:
                    clock = end
            if halves:
                free = android_free_gb(dev["serial"]) if not dry else info.get("free_gb")
                log(f"free before {tag}: {free:.1f} GB (floor {floor:g} GB)" if free is not None
                    else f"free before {tag}: unknown (floor {floor:g} GB)")
                if free is None or free < floor:
                    # rotate out every OTHER half's copies (last week's leftover
                    # half included), never this half's own: every half of the device, also
                    # those an earlier sitting this week ran (args.week_left)
                    others = [h["cells"] for h in dev["split"] if h["cells"] != cells_file]
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
            session_timeout = (float(extras[cells_file].get("timeout_hours", 1)) * 3600
                               if cells_file in extras else timeout_s)
            rc = run_matrix(cells_file, platform, camp, env, session_timeout, dry, watch=eta)
            prof_rc = None
            if getattr(args, "profile", False) and platform == "android" and rc != 124:
                # a retake's native-benchmark row: the per-op pair in the same campaign, under the hold
                prof_rc = run_profile(cells_file, camp, env, PROFILE_TIMEOUT_S, dry, watch=eta)
            previous.append(cells_file)
            last_rel = rel_path
            if dry:
                planned.append(rel_path)
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
            expected, have = cells_with_records(rel_path, cells_file, platform, dev["identifier"], key)
            # the payload session runs its own anchor row first; re-judge it
            # so a contention that began after phase A is not admitted blindly
            own_ok, own_reason, own_details = admit(schedule, dev, rel_path, platform)
            verdict = "TIMEOUT" if rc == 124 else "COMPLETED"
            # the iPhone runner ends a session whose phone stopped accepting
            # launches (two refusals in a row) and says so in DEVICE_LOST.txt:
            # the verdict is DEVICE, the captured cells stand, admission is
            # still the anchor's (design §5; the 2026-09-09 05:30 firing)
            lost = read_lines(os.path.join(ROOT, rel_path, "DEVICE_LOST.txt"))
            if lost:
                verdict = "DEVICE"
                log(f"device lost mid-session: {lost[-1]}")
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
                                     **({"device_lost": lost} if lost else {}),
                                     **({"part": part["tag"]} if part else {}),
                                     **({"release_by": deadline.strftime("%Y-%m-%d %H:%M")}
                                        if deadline is not None else {}),
                                     **({"retake": args.retake} if getattr(args, "retake", None) else {}),
                                     **({"profile": {"exit": prof_rc, "dir": f"{rel_path}/profiles"}}
                                        if prof_rc is not None else {}),
                                     **campaign_notes(rel_path)})
            if rc == 124:
                worst = max(worst, EXIT_TIMEOUT)
            elif lost:
                worst = max(worst, EXIT_DEVICE)
            elif not own_ok:
                worst = max(worst, EXIT_ABORTED)
        if not dry:
            rc = sh([PY, os.path.join(ROOT, "scripts", "render_dashboard.py")], timeout=300)[0]
            log(f"render_dashboard exit {rc}")
        reason = "ok" if worst == EXIT_OK else VERDICT_NAME[worst].lower()
        if no_build:
            reason += "; skipped, side build not on the phone: " + ", ".join(no_build)
        if cut:
            why = f"release_by {deadline:%H:%M}: not started, left for a later firing this week: {', '.join(cut)}"
            if last_rel is None:
                # the anchor phase ran and no payload run fits after it (it overran its estimate):
                # nothing measured, no post; the device is tried again at a later firing
                return EXIT_BUSY, f"{why} (no payload run fits after the anchor phase)", anchor_rel, sitting_dirs()
            reason += f"; {why}"
        return worst, reason, last_rel, sitting_dirs()
    finally:
        if eta is not None:
            eta.stop()   # no estimate written after this: the hold goes next
        quiet_lock_release(qlock)
        if HOLD_KEEPER is not None:
            log(f"hold kept by keeper pid {HOLD_KEEPER} (not acquired / not released by the job)")
        hold_release(hold)


def retake_sitting(schedule, key, dev, args, weekly_follows=False):
    """The device's pending retakes as one sitting before its weekly set (docs/dashboard-autopilot-v1.md
    §8) -> its exit code, or None when it has none. The cells file is generated per sitting
    (regression_watch.retake_cells_text: the platform's anchor rows, then each retake's row byte for
    byte), the sitting is attempt() with that file and the suffix retake-<slug> (its own campaign, a
    single-file sitting), and it closes as a sitting does: its ledger line, then the post step, which
    judges it (the red segment). Exit 0 marks the retakes done with the payload campaign; another
    exit counts an attempt (abandoned after regression_watch.RETAKE_MAX_ATTEMPTS). A dry run writes
    the generated cells file its plan names and changes no retake state. weekly_follows: the weekly
    set runs after it (its hold's release estimate says so: that set takes a new hold)."""
    date = datetime.date.today().isoformat()
    try:
        gone = []
        entries = regression_watch.pending_retakes(LOG_DIR, key, write=not args.dry_run, root=ROOT, gone=gone)
        for rid, why in gone:
            log(f"retake {rid} superseded: {why} (the cell's row changed after it was queued; not run)")
        if not entries:
            return None
        path, slug, rows = regression_watch.write_retake_cells(ROOT, LOG_DIR, schedule["anchors"],
                                                               PLATFORM_TOKEN[dev["platform"]], key, entries, date)
    except (regression_watch.Config, OSError, ValueError, KeyError) as e:
        # the retake state is the autopilot's, never a reason to skip the weekly set
        log(f"WARN retake state unusable, no retake this sitting: {e}")
        return None
    rel = os.path.relpath(path, ROOT)
    ids = [e["id"] for e in entries]
    profile, why = regression_watch.profile_plan(dev["platform"], entries)
    rargs = argparse.Namespace(**dict(vars(args), cells=rel, suffix=f"retake-{slug}", profile=profile,
                                      retake={"ids": ids, "cells_file": rel, "rows": rows},
                                      weekly_follows=weekly_follows))
    log(f"=== retake: {len(ids)} pending for {key} ({', '.join(ids)}): one sitting over {rel} before the "
        "weekly set" + (" [dry-run]" if args.dry_run else ""))
    log(f"retake profile: {why}")
    t0, started = time.time(), time.strftime("%F %T")
    code, reason, camp, sitting = EXIT_CONFIG, "", "", []
    try:
        code, reason, camp, sitting = attempt(schedule, key, dev, 1, rargs)
    except Busy as e:
        code, reason = EXIT_BUSY, str(e)
        log(f"BUSY: {e}")
    except NotReady as e:
        code, reason = EXIT_DEVICE, str(e)
        log(f"DEVICE: {e}")
    except ConfigError as e:
        code, reason = EXIT_CONFIG, str(e)
        log(f"CONFIG: {e}")
    if not args.dry_run:
        try:
            regression_watch.finish_retakes(LOG_DIR, ids, code, reason, camp or "", cells_file=rel,
                                            suffix=rargs.suffix)
        except (regression_watch.Config, OSError) as e:
            log(f"WARN retake state not updated ({e}): the retakes stay as they were")
        ledger({"started": started, "ended": time.strftime("%F %T"), "device": key, "campaign": camp or "",
                "verdict": VERDICT_NAME.get(code, str(code)), "reason": f"retake {', '.join(ids)}: {reason}",
                "exit": code, "minutes": round((time.time() - t0) / 60, 1), "attempt": 1})
    log(f"=== retake done: {VERDICT_NAME.get(code, code)} ({reason}) exit {code}")
    post_sitting(code, sitting, args.dry_run, post_args(args, sitting))
    return code


# ---------------------------------------------------------------- DDP lab units (docs/dashboard-autopilot-v1.md §9)

# the autopilot's switch: ddp_weekly turns the lab-unit slot on (user 2026-10-16: no per-session GO;
# off when a Googler runs the weekly DDP set on their side), ddp_max_sessions caps the Device Run
# sessions one sitting may start (the plan's count, read before any is billed)
SWITCH = os.path.join(ROOT, "ops", "autopilot", "switch.json")
DDP_REASON = "ddp lab unit: no session anchor; each run carries its cap marks and the text check"
# a lab unit's sitting is due when no admitted session of it ended in this many days before the firing
# (schedule.json interval_days overrides): a rolling window, not the attached devices' Monday week, so a
# Sunday-night sitting is not repeated by the Monday 02:00 firing (supervisor, 2026-10-18 r5)
DDP_INTERVAL_DAYS = 6


def load_switch(path=None):
    """(ddp_weekly, ddp_max_sessions) of the switch (default SWITCH): only true turns the slot on; the
    cap is a whole number >= 0 (absent or anything else: 0, no session); no file = off. ConfigError
    when it does not parse."""
    path = path or SWITCH
    try:
        with open(path) as fh:
            raw = json.load(fh)
    except FileNotFoundError:
        raw = {}
    except (OSError, ValueError) as e:
        raise ConfigError(f"switch unreadable: {path}: {e}")
    if not isinstance(raw, dict):
        raise ConfigError(f"switch is not a JSON object: {path}")
    cap = raw.get("ddp_max_sessions")
    cap = cap if isinstance(cap, int) and not isinstance(cap, bool) and cap >= 0 else 0
    return raw.get("ddp_weekly") is True, cap


def one_line(text, n=400):
    """A reason for the ledger (one TSV field): whitespace runs to one space, the last n characters."""
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else "…" + text[-(n - 1):]


def log_tail(n=3):
    """The last lines of this sitting's log (a runner prints into it through the pipe), for a reason."""
    if not _LOG:
        return ""
    try:
        with open(_LOG.name, errors="replace") as fh:
            lines = [ln.strip() for ln in fh if ln.strip()]
    except OSError:
        return ""
    return one_line(" | ".join(lines[-n:]))


def ddp_doctor():
    """(rc, output) of the checks `bench doctor --platform ddp` makes required, alone (scripts/doctor.py
    check_ddp): gcloud on PATH and signed in (its exit code only, the token is never read),
    huggingface_hub, the pinned engine files (BENCH_ANDROID_BIN_DIR, else android/bin). Not the whole
    doctor: it also lists `adb devices` and `xcrun devicectl list devices`, and with one Android phone
    attached runs `adb -s <serial> shell sha256sum …` on it, which a lab unit's sitting must not do to a
    phone another sitting may be measuring."""
    code = ("import sys; sys.path.insert(0, sys.argv[1]); import doctor; doctor.check_ddp(True); "
            "[print(f'{s:4}  {n}  {d}'.rstrip()) for s, n, d in doctor._RESULTS]; "
            "sys.exit(1 if any(s == doctor.FAIL for s, _, _ in doctor._RESULTS) else 0)")
    return sh([PY, "-c", code, os.path.join(ROOT, "scripts")], timeout=180)


def ddp_plan(cells, ddp_id, campaign):
    """The plan `bench matrix <cells> --ddp <id> --dry-run` prints (android/ddp/run_ddp.py: no gcloud,
    no network, the models looked up in the local HF cache only) -> {jobs, sessions, skipped, cells:
    (arm, model id, task) per job, skips, upload_objects, upload_bytes, uncached, device_minutes (run_ddp's
    own estimate), engine}; ConfigError with the output's tail when it prints no summary."""
    rc, out = sh([os.path.join(ROOT, "bench"), "matrix", cells, "--ddp", ddp_id, "--campaign", campaign,
                  "--dry-run"], timeout=900)
    plan, summary, upload = {"cells": [], "skips": []}, None, {}
    for ln in out.splitlines():
        if not ln.startswith("{"):
            continue
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        if "job" in d:
            plan["cells"].append(tuple(d["cell"].split()[:3]))
        elif "skip" in d:
            plan["skips"].append(f"{d['skip']}: {d.get('reason')}"
                                 + (f" (exclude-on {d['excludeOn']})" if d.get("excludeOn") else ""))
        elif "uploadCandidates" in d:
            upload = d
        elif "summary" in d:
            summary = d["summary"]
    if rc != 0 or summary is None:
        raise ConfigError(f"the DDP plan (bench matrix {cells} --ddp {ddp_id} --dry-run) exit {rc}: "
                          + one_line(" | ".join(out.strip().splitlines()[-4:])))
    plan.update(jobs=summary.get("jobs", 0), sessions=summary.get("sessions", 0),
                skipped=summary.get("skipped", 0), device_minutes=summary.get("deviceMinutes"),
                engine=summary.get("engine"), upload_objects=len(upload.get("uploadCandidates") or []),
                upload_bytes=upload.get("uploadBytes") or 0, uncached=upload.get("uncached") or [])
    return plan


def ddp_time(text):
    """A Device Run API time ("2026-10-16T09:27:28.344Z", up to nanoseconds) -> aware datetime, or None."""
    m = re.match(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(\.\d+)?Z$", text or "")
    if not m:
        return None
    return datetime.datetime.fromisoformat(m.group(1) + (m.group(2) or ".0")[:7] + "+00:00")


def ddp_facts(rel):
    """The Device Run sessions a lab unit's campaign dir pulled (ddp/session-<n>.json, else the response
    in ddp/operation-<n>.json, as run_ddp.py reads them back) -> {sessions: [ids], jobs, device_minutes:
    the executions' start -> end summed, results: {resultType: jobs}}."""
    found = {}
    for p in glob.glob(os.path.join(ROOT, rel, "ddp", "*.json")):
        m = re.fullmatch(r"(session|operation)-(\d+)\.json", os.path.basename(p))
        if m:
            found.setdefault(int(m.group(2)), {})[m.group(1)] = p
    sessions, jobs, secs, results = [], 0, 0.0, collections.Counter()
    for n in sorted(found):
        doc = {}
        for kind in ("session", "operation"):
            try:
                with open(found[n][kind]) as fh:
                    d = json.load(fh)
            except (KeyError, OSError, ValueError):
                continue
            d = (d.get("response") or {}) if kind == "operation" and isinstance(d, dict) else d
            if isinstance(d, dict) and "sessionReport" in d:
                doc = d
                break
        if not doc:
            continue
        sessions.append((doc.get("name") or "").rsplit("/", 1)[-1] or f"session {n}")
        for j in (doc.get("sessionReport") or {}).get("jobReports") or []:
            jobs += 1
            results[(j.get("result") or {}).get("resultType") or "?"] += 1
            for e in j.get("executionReports") or []:
                a, b = ddp_time(e.get("startTime")), ddp_time(e.get("endTime"))
                if a and b:
                    secs += (b - a).total_seconds()
    return {"sessions": sessions, "jobs": jobs, "device_minutes": round(secs / 60, 1), "results": dict(results)}


def ddp_window(dev, now):
    """(days, start) of a lab unit's window at `now`: its interval_days (DDP_INTERVAL_DAYS), and now
    minus that many days."""
    days = float(dev.get("interval_days", DDP_INTERVAL_DAYS))
    return days, now - datetime.timedelta(days=days)


def ddp_tried(key, monday, root=None):
    """The newest sitting of lab unit `key` started since `monday` (the window's start, ddp_window) that
    ran Device Run sessions and was not admitted (its SESSION.json) -> (dir name, verdict, reason), or
    None: one billed attempt a window, the next waits for a person."""
    best = None
    for f in glob.glob(os.path.join(root or ROOT, "results", "raw", f"*-dashboard-v1-{key}-*", "SESSION.json")):
        try:
            with open(f) as fh:
                s = json.load(fh)
            t = datetime.datetime.strptime(s.get("started") or "", "%Y-%m-%d %H:%M:%S").astimezone()
        except (OSError, ValueError, AttributeError):
            continue
        if s.get("admitted", True) or not (s.get("ddp") or {}).get("sessions") or t < monday:
            continue
        if best is None or t > best[0]:
            best = (t, os.path.basename(os.path.dirname(f)), s.get("verdict"), s.get("reason"))
    return best[1:] if best else None


def ddp_due(key, dev, now, sessions, switch_on, tried):
    """(due, why) of a lab unit's sitting at this firing (`sessions`: device_sessions of the unit, newest
    first; `tried`: ddp_tried over the same window). Not due: by hand only, the switch off, an admitted
    session in the last interval_days days (ddp_window), a sitting in them that ran Device Run sessions
    and was not admitted."""
    days, start = ddp_window(dev, now)
    last = sessions[0] if sessions else None
    if dev.get("auto") is False:
        return False, "auto: false, by hand only"
    if not switch_on:
        return False, ("off: ops/autopilot/switch.json ddp_weekly is not true (a Googler runs the DDP set "
                       f"on their side); by hand: dashboard_job.py {key}")
    if last and last[0] >= start:
        return False, f"done: admitted {last[0]:%F %H:%M} {last[1]}, within {days:g} days"
    if tried:
        return False, (f"{tried[0]} ran Device Run sessions in the last {days:g} days and was not admitted ({tried[1]}: "
                       f"{one_line(tried[2], 120)}): a person looks before another sitting is billed; "
                       f"by hand: dashboard_job.py {key}")
    return True, ("due: " + (f"last admitted {last[0]:%F %H:%M} {last[1]}" if last else "never measured")
                  + f", none in the last {days:g} days")


def ddp_sitting(schedule, key, dev, args, cells=None, suffix=None):
    """One sitting of a Developer Device Platform lab unit -> (exit code, reason, campaign dir, the dirs
    it wrote SESSION.json in; a dry run: the one it would). No hold, no reboot, no anchor phase: the
    switch (ddp_weekly), the doctor's DDP checks (ddp_doctor), the plan (its Device Run sessions within
    ddp_max_sessions: nothing is billed past the cap), then `bench matrix <cells> --ddp <id>` under
    gtimeout timeout_hours (it uploads what the bucket lacks, runs the sessions one after another, pulls,
    scrubs the logcats, writes the records, rebuilds the summary), then SESSION.json: admitted when the
    sitting wrote records (DDP_REASON; anchor null), the sessions, jobs and device minutes."""
    dry = args.dry_run
    ddp_id, cells = dev.get("ddp_id"), cells or dev.get("cells")
    if not ddp_id or not cells:
        raise ConfigError(f"schedule.json {key}: a ddp device needs ddp_id and cells")
    camp = (f"{datetime.date.today().isoformat()}-dashboard-v1-{key}-{ddp_id}"
            + (("-" + suffix.strip("-")) if suffix else ""))
    rel = campaign_rel(camp, "ddp")
    started = time.strftime("%F %T")
    log(f"=== slot {key} ({dev['display']}, DDP {ddp_id}) campaign {camp}" + (" [dry-run]" if dry else ""))
    on, cap = load_switch()
    if not on:
        raise ConfigError("ops/autopilot/switch.json ddp_weekly is not true: the lab-unit slot is off "
                          "(docs/dashboard-autopilot-v1.md §9)")
    if os.path.exists(os.path.join(ROOT, rel, "SESSION.json")) or glob.glob(
            os.path.join(ROOT, rel, "app-path-android", "*.json")):
        raise ConfigError(f"{rel} holds a sitting already: a second one today takes --suffix")
    rc, out = ddp_doctor()
    if rc != 0:
        fails = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("FAIL")]
        raise NotReady("doctor (check_ddp) FAILED: " + one_line(" | ".join(fails) or out))
    log("doctor (check_ddp): ready")
    for ln in out.splitlines():
        if ln.strip():
            log("  " + ln.strip())
    plan = ddp_plan(cells, ddp_id, camp)
    log(f"ddp plan: {plan['jobs']} jobs in {plan['sessions']} Device Run sessions on {ddp_id} (engine "
        f"{plan['engine']}), {plan['skipped']} rows skipped; {plan['upload_objects']} upload candidates, "
        f"{plan['upload_bytes'] / 1e9:.2f} GB (the run uploads what the bucket lacks); run_ddp's estimate "
        f"{plan['device_minutes']} device-min; cap {cap} sessions (ops/autopilot/switch.json ddp_max_sessions)")
    for s in plan["skips"]:
        log(f"  ddp skip: {s}")
    if plan["uncached"]:
        log(f"  not in the local HF cache (the run downloads them): {', '.join(plan['uncached'])}")
    if not plan["jobs"]:
        raise ConfigError(f"no row of {cells} runs on DDP")
    if plan["sessions"] > cap:
        raise ConfigError(f"the plan needs {plan['sessions']} Device Run sessions, ops/autopilot/switch.json "
                          f"ddp_max_sessions is {cap}: nothing started")
    if dry:
        log("plan:")
    rc = run_matrix(cells, "ddp", camp, {}, float(dev.get("timeout_hours", 6)) * 3600, dry, ddp=ddp_id)
    if dry:
        log(f"  SESSION.json would read admitted true once the sitting writes records ({DDP_REASON}), anchor "
            "null, ddp {id, sessions, jobs, device_minutes}")
        return EXIT_OK, "ok", rel, [rel]
    if not os.path.isdir(os.path.join(ROOT, rel)):
        why = f"bench matrix --ddp exit {rc} before its campaign dir: no Device Run session ({log_tail()})"
        return (EXIT_TIMEOUT if rc == 124 else EXIT_DEVICE), why, rel, []
    facts = ddp_facts(rel)
    want = set(plan["cells"])
    have = {(r["runtime"], r["model_id"], r["task"]) for r in load_rows()
            if r["campaign"] == rel and r["device"] == dev["identifier"]} & want
    admitted = bool(have)
    reason = DDP_REASON if admitted else f"no record (bench matrix --ddp exit {rc}: {log_tail()})"
    write_session(rel, {"campaign": rel, "phase": "payload", "cells": cells, "device_key": key,
                        "device_display": dev["display"], "device_identifier": dev["identifier"],
                        "platform": "ddp", "attempt": 1, "started": started, "ended": time.strftime("%F %T"),
                        "admitted": admitted, "verdict": "TIMEOUT" if rc == 124 else "COMPLETED",
                        "reason": reason, "anchor": None, "runner_exit": rc,
                        "cells_expected": len(want), "cells_with_records": len(have),
                        "ddp": {"id": ddp_id, "sessions": facts["sessions"], "jobs": facts["jobs"],
                                "device_minutes": facts["device_minutes"], "results": facts["results"],
                                "plan": {"sessions": plan["sessions"], "jobs": plan["jobs"],
                                         "device_minutes_estimate": plan["device_minutes"]}},
                        **campaign_notes(rel)})
    log(f"ddp: {len(facts['sessions'])} Device Run sessions ({', '.join(facts['sessions']) or 'none'}), "
        f"{facts['jobs']} jobs {facts['results']}, {facts['device_minutes']} device-min; {len(have)} of "
        f"{len(want)} cells with records")
    log(f"render_dashboard exit {sh([PY, os.path.join(ROOT, 'scripts', 'render_dashboard.py')], timeout=300)[0]}")
    if rc == 124:
        return EXIT_TIMEOUT, "timeout", rel, [rel]
    if not admitted:
        return EXIT_DEVICE, reason, rel, [rel]
    return EXIT_OK, "ok" if rc == 0 else f"ok; bench matrix --ddp exit {rc}", rel, [rel]


def ddp_slot(schedule, key, dev, args, cells=None, suffix=None):
    """A lab unit's sitting with its close: the ledger line, the done line, then the post over its dir
    when it exits 0 (no hold to release first) -> its exit code."""
    t0, started = time.time(), time.strftime("%F %T")
    code, reason, camp, sitting = EXIT_CONFIG, "", "", []
    try:
        code, reason, camp, sitting = ddp_sitting(schedule, key, dev, args, cells, suffix)
    except NotReady as e:
        code, reason = EXIT_DEVICE, str(e)
        log(f"DEVICE: {e}")
    except ConfigError as e:
        code, reason = EXIT_CONFIG, str(e)
        log(f"CONFIG: {e}")
    if not args.dry_run:
        ledger({"started": started, "ended": time.strftime("%F %T"), "device": key, "campaign": camp or "",
                "verdict": VERDICT_NAME.get(code, str(code)), "reason": one_line(reason), "exit": code,
                "minutes": round((time.time() - t0) / 60, 1), "attempt": 1})
    log(f"=== done: {VERDICT_NAME.get(code, code)} ({reason}) exit {code}")
    post_sitting(code, sitting, args.dry_run, post_args(args, sitting))
    return code


def ddp_after(schedule, args, now=None, rows=None, admitted=None, tried=None):
    """auto, after the attached device's sitting (or at a firing with none): each lab unit (platform
    ddp) whose weekly sitting is due (ddp_due) runs one, one after another; never the firing's device.
    `ddp: …` lines in the auto log say what was decided; a sitting logs to <date>-<key>.log. `tried`:
    key -> ddp_tried (default: read from results/raw). -> {key: exit code} of the sittings run."""
    units = {k: d for k, d in schedule.get("devices", {}).items() if d.get("platform") == "ddp"}
    if not units:
        return {}
    open_log("auto")
    try:
        on, _ = load_switch()
    except ConfigError as e:
        log(f"ddp: {e}; no lab-unit sitting")
        return {}
    now = now or datetime.datetime.now().astimezone()
    rows = load_rows() if rows is None else rows
    admitted = load_admission() if admitted is None else admitted
    sessions = device_sessions({"devices": units}, rows, admitted, regression_watch.retake_sitting_dirs(ROOT))
    out = {}
    for key, dev in units.items():
        t = tried.get(key) if tried is not None else ddp_tried(key, ddp_window(dev, now)[1])
        due, why = ddp_due(key, dev, now, sessions.get(key) or [], on, t)
        log(f"ddp: {key} ({dev['display']}): {why}")
        if not due:
            continue
        if not args.dry_run:
            other = device_lock(key)
            if other:
                log(f"ddp: {key}: a sitting is running on it (pid {other}); none started")
                continue
        log(f"ddp: {key}: its sitting starts now (log {datetime.date.today().isoformat()}-{key}.log)")
        open_log(key)
        try:
            out[key] = ddp_slot(schedule, key, dev, args)
        finally:
            _unlock(f".job.lock.{key}")
            open_log("auto")
        log(f"ddp: {key}: {VERDICT_NAME.get(out[key], out[key])}, exit {out[key]}")
    return out


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


def device_sessions(schedule, rows, admitted, skip=()):
    """key -> [(ended, campaign)] of the device's admitted dashboard sessions,
    newest first. A session is a `-dashboard-v1-` campaign that is not the
    anchor probe, matched on the device's identifier and platform, whose
    SESSION.json does not say admitted:false (absent = admitted, as in
    render_dashboard); its time is its last record's. Hand-run first passes
    count the same way as the job's own sittings; the autopilot's retake
    sittings (`skip`: their SESSION.json names the retakes) do not."""
    out = {}
    for key, dev in schedule.get("devices", {}).items():
        plat = CSV_PLATFORM[PLATFORM_TOKEN[dev["platform"]]]
        ended = {}
        for r in rows:
            camp = r["campaign"]
            if (DASHBOARD_CAMPAIGN not in camp or re.search(ANCHOR_CAMPAIGN_RE, camp) or camp in skip
                    or r["platform"] != plat or r["device"] != dev["identifier"]
                    or not admitted.get(camp, True)):
                continue
            t = parse_ts(r["timestamp"])
            if t and (camp not in ended or t > ended[camp]):
                ended[camp] = t
        out[key] = sorted(((t, c) for c, t in ended.items()), reverse=True)
    return out


def load_session_cells():
    """campaign (results/raw/<name>) -> the cells file its SESSION.json names (the job's sittings; a
    hand run has no SESSION.json)."""
    out = {}
    for f in glob.glob(os.path.join(ROOT, "results", "raw", "*", "SESSION.json")):
        try:
            with open(f) as fh:
                cells = json.load(fh).get("cells")
        except (OSError, ValueError, AttributeError):
            continue
        if cells:
            out[os.path.relpath(os.path.dirname(f), ROOT)] = cells
    return out


def part_sessions(parts, sessions, session_cells):
    """part tag -> [(ended, campaign)], newest first, of a device's admitted weekly sessions
    (device_sessions) that cover the part: a session whose SESSION.json names a part's cells file
    covers that part; any other (the whole set, a --cells file, a hand run) covers every part, as it
    covers a device without parts."""
    by_file = {p["cells"]: p["tag"] for p in parts}
    out = {p["tag"]: [] for p in parts}
    for t, camp in sessions:
        tag = by_file.get(session_cells.get(camp))
        for p in parts:
            if tag in (None, p["tag"]):
                out[p["tag"]].append((t, camp))
    return out


def parts_pending(parts, covered, monday):
    """The tags of the parts with no admitted session since `monday` (part_sessions), in the week's order."""
    return [p["tag"] for p in parts if not (covered[p["tag"]] and covered[p["tag"]][0][0] >= monday)]


def sitting_part(schedule, key, dev, args, now=None, rows=None, admitted=None, skip=None,
                 session_cells=None):
    """(the part of the device's weekly set this sitting runs, why), or (None, "") for a device without
    parts and for an explicit --cells file (single-file mode: a retake, a slot file). --part names it;
    else the first part, in the week's order, with no admitted session since Monday; else (every part
    done this week: a sitting by hand) the part whose newest admitted session is the oldest."""
    parts = device_parts(dev)
    if not parts or args.cells:
        return None, ""
    want = getattr(args, "part", None)
    if want:
        part = next((p for p in parts if p["tag"] == want), None)
        if part is None:
            raise ConfigError(f"--part {want}: the parts of {key} are {', '.join(p['tag'] for p in parts)}")
        return part, "named by --part"
    now = now or datetime.datetime.now().astimezone()
    rows = load_rows() if rows is None else rows
    admitted = load_admission() if admitted is None else admitted
    skip = regression_watch.retake_sitting_dirs(ROOT) if skip is None else skip
    session_cells = load_session_cells() if session_cells is None else session_cells
    covered = part_sessions(parts, device_sessions({"devices": {key: dev}}, rows, admitted, skip)[key],
                            session_cells)
    pending = parts_pending(parts, covered, week_start(now))
    if pending:
        done = [f"{p['tag']} admitted {covered[p['tag']][0][0]:%F %H:%M}" for p in parts
                if p["tag"] not in pending]
        return (next(p for p in parts if p["tag"] == pending[0]),
                f"the first part pending this week (pending: {', '.join(pending)}"
                + (f"; {', '.join(done)}" if done else "") + ")")
    part = min(parts, key=lambda p: covered[p["tag"]][0][0])
    return part, (f"every part admitted this week; the one whose newest session is the oldest "
                  f"({covered[part['tag']][0][0]:%F %H:%M})")


def plan_left(schedule, dev, sessions, session_cells, monday):
    """What of a device's weekly plan (a device without parts) has no admitted session since `monday`
    (`sessions`: device_sessions of the device, newest first; `session_cells`: campaign -> the cells file
    its SESSION.json names) -> {"set": "whole" (none of it: the sitting runs the set whole or in its
    storage halves, phase_b_halves) | [its split files still to run, in their order] | None (done),
    "extras": [its extra files still to run, in their order]}. A session counts for the file its
    SESSION.json names: the set's file covers the set and its halves, a half or an extra file itself; a
    hand run with no SESSION.json covers the whole plan, as any admitted session covered the week until
    2026-10-31; a --cells file (a slot, a coverage run, a retake by hand) covers none of it. Since then a
    sitting can stop at the device's release_by with runs left (§11), and the week is done only when
    every run of the plan was admitted."""
    files, hand = set(), False
    for t, camp in sessions:
        if t < monday:
            continue
        f = session_cells.get(camp)
        hand = hand or f is None
        files.add(f)
    split = [h["cells"] for h in dev.get("split", [])]
    if hand or (schedule.get("cells") and schedule["cells"] in files):
        rest = None
    elif split and any(f in files for f in split):
        rest = [f for f in split if f not in files] or None
    else:
        rest = "whole"
    extras = [] if hand else [e["cells"] for e in dev.get("extra_cells", []) if e["cells"] not in files]
    return {"set": rest, "extras": extras}


def left_tags(dev, left):
    """The runs `left` (plan_left) names, by their campaign tags: "set", a half's or an extra file's tag."""
    extras = {e["cells"]: e for e in dev.get("extra_cells", [])}
    out = ["set"] if left["set"] == "whole" else [run_tag(f, extras) for f in left["set"] or []]
    return out + [run_tag(f, extras) for f in left["extras"]]


def sitting_left(schedule, key, dev, args, now=None, rows=None, admitted=None, skip=None, session_cells=None):
    """The runs of the weekly plan a sitting makes when earlier sittings this week made the others
    (plan_left), or None for the whole plan: nothing of it admitted this week, or all of it (a sitting by
    key on a week done runs it all again, as before), a device whose set is in parts (sitting_part), an
    explicit --cells file."""
    if device_parts(dev) or args.cells or dev.get("platform") == "ddp":
        return None
    now = now or datetime.datetime.now().astimezone()
    rows = load_rows() if rows is None else rows
    admitted = load_admission() if admitted is None else admitted
    skip = regression_watch.retake_sitting_dirs(ROOT) if skip is None else skip
    session_cells = load_session_cells() if session_cells is None else session_cells
    left = plan_left(schedule, dev, device_sessions({"devices": {key: dev}}, rows, admitted, skip)[key],
                     session_cells, week_start(now))
    if (left["set"] is None and not left["extras"]) or (
            left["set"] == "whole" and len(left["extras"]) == len(dev.get("extra_cells", []))):
        return None
    return left


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


def resolve_device(schedule, key, exclude=None, now=None, rows=None, admitted=None, retakes=None,
                   skip=None, session_cells=None):
    """(key, dev, report). An explicit key resolves as given (report []).

    `auto`: the device to measure at this firing — among the devices whose weekly
    plan is not all admitted since Monday 00:00 local (plan_left: the set, or each
    of its storage halves, and each extra file; a device whose set is in parts:
    while a part has none, part_sessions; `session_cells`, default the
    SESSION.json files, names each session's cells file), the attached, unheld
    ones (the iPhone only inside its auto_window after auto_idle_hours without a
    record; the Mac only while no heavy pipeline runs), ordered by the age of
    their last admitted session, oldest first (never measured = oldest; ties
    in schedule order); an entry with `auto: false` is never a candidate (by hand
    only, state by-hand), nor is a lab unit (platform ddp, state ddp: main() decides
    its sitting after the attached device's, ddp_after). A device with a pending retake (`retakes`: key -> count,
    default logs/dashboard-job/retakes.json) is a candidate though its weekly set
    is done (weekly_done in its report entry: the firing runs the retake only), and
    those devices go first; the autopilot's retake sittings (`skip`, default the
    SESSION.json files that name retakes) are not weekly sessions. `exclude` maps
    keys already tried this firing to (state, detail). The report has one dict per
    device — key, state (done / by-hand / ddp / candidate / busy / not-ready / waiting),
    detail, last, weekly_done — for the log."""
    register_devices(schedule)
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
    retakes = regression_watch.pending_counts(LOG_DIR, root=ROOT) if retakes is None else retakes
    skip = regression_watch.retake_sitting_dirs(ROOT) if skip is None else skip
    session_cells = load_session_cells() if session_cells is None else session_cells
    sessions = device_sessions(schedule, rows, admitted, skip)
    monday = week_start(now)
    report, ranked = [], []
    for i, (k, dev) in enumerate(devices.items()):
        last = sessions[k][0] if sessions[k] else None
        entry = {"key": k, "last": last[0] if last else None, "state": "candidate",
                 "detail": (f"last admitted {last[0]:%F %H:%M}" if last else "never measured")}
        report.append(entry)
        if dev.get("auto") is False:
            entry.update(state="by-hand", detail=f"auto: false, by hand only; {entry['detail']}")
            continue
        if dev.get("platform") == "ddp":
            # a lab unit uses no device on this host: never the firing's one device
            entry.update(state="ddp", detail=f"lab unit, decided after the attached device's sitting; "
                                             f"{entry['detail']}")
            continue
        pending = retakes.get(k, 0)
        retake_text = f"{pending} retake{'s' if pending != 1 else ''} pending"
        parts = device_parts(dev)
        if parts:
            # a weekly set in parts is done when every part has an admitted session this week
            todo = parts_pending(parts, part_sessions(parts, sessions[k], session_cells), monday)
            week_done = not todo
            if todo:
                entry["detail"] += f"; part{'s' if len(todo) > 1 else ''} {', '.join(todo)} pending this week"
        else:
            # done when every run of the weekly plan has an admitted session this week (plan_left): a
            # sitting stopped at release_by leaves runs for a later firing (§11)
            left = plan_left(schedule, dev, sessions[k], session_cells, monday)
            week_done = left["set"] is None and not left["extras"]
            if not week_done and last and last[0] >= monday:
                entry["detail"] += f"; {', '.join(left_tags(dev, left))} pending this week"
        if week_done:
            if not pending:
                entry.update(state="done", detail=f"admitted {last[0]:%F %H:%M} {last[1]}")
                continue
            entry.update(weekly_done=True,
                         detail=f"{retake_text}; weekly set done ({last[0]:%F %H:%M} {last[1]})")
        elif pending:
            entry["detail"] += f"; {retake_text}"
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
            holder = device_lock_holder(k)
            if holder:
                raise Busy(f"a dashboard sitting is running on it (pid {holder})")
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
        # a pending retake first (the next firing re-measures a red cell), then the oldest
        ranked.append(((0 if pending else 1,) + ((1, last[0].timestamp(), i) if last else (0, 0, i)), k))
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

_LOCKS = {}


def _try_lock(name):
    """-> None when this process now holds the flock on LOG_DIR/<name>, else
    the pid written by the holder (or '?')."""
    os.makedirs(LOG_DIR, exist_ok=True)
    fh = open(os.path.join(LOG_DIR, name), "a+")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.seek(0)
        holder = fh.read().strip() or "?"
        fh.close()
        return holder
    fh.seek(0)
    fh.truncate()
    fh.write(str(os.getpid()))
    fh.flush()
    _LOCKS[name] = fh
    return None


def _unlock(name):
    fh = _LOCKS.pop(name, None)
    if fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_UN)
        finally:
            fh.close()


def device_lock(key):
    """One sitting per DEVICE (since 2026-09-08; until then one per host).
    The devices are independent — a phone sitting is adb traffic on the host
    while the Mac measures itself — so sittings on different devices run side
    by side; two on the same device cannot (the hold files serialize the
    phones with the sibling lanes too, and the Mac has its runner guard). The
    derived files both sittings regenerate at their close (results/summary,
    DASHBOARD.md) are written atomically (bench_common.atomic_write)."""
    return _try_lock(f".job.lock.{key}")


def device_lock_holder(key):
    """pid of a sitting running on `key`, or None (a probe; no lock is kept)."""
    holder = _try_lock(f".job.lock.{key}")
    if holder is None:
        _unlock(f".job.lock.{key}")
    return holder


def choose_lock():
    """`auto` only, held from the device choice until that device's lock is
    taken: two autos side by side (a manual one beside the launchd firing)
    would otherwise both pick the same free device. Blocks instead of
    failing — a choice takes seconds."""
    os.makedirs(LOG_DIR, exist_ok=True)
    fh = open(os.path.join(LOG_DIR, ".choose.lock"), "a+")
    fcntl.flock(fh, fcntl.LOCK_EX)
    _LOCKS[".choose.lock"] = fh


def choose_unlock():
    _unlock(".choose.lock")


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
    ap.add_argument("--suffix", help="campaign-name suffix (e.g. -retake) so a second run on the "
                                     "same day does not land in that day's campaign dir")
    ap.add_argument("--part", metavar="TAG",
                    help="on a device whose weekly set is in parts (schedule.json \"parts\"): run this "
                         "part (default: the first part with no admitted session this week). Not with "
                         "auto or --cells")
    ap.add_argument("--dry-run", action="store_true",
                    help="preflight and print the plan; take no hold, capture nothing")
    ap.add_argument("--once", action="store_true",
                    help="no busy polling / abort retry — one attempt")
    ap.add_argument("--no-retake", action="store_true",
                    help="run no pending retake of the device before its weekly set (--cells implies it)")
    ap.add_argument("--no-ddp", action="store_true",
                    help="auto: no lab-unit (DDP) sitting after the attached device's")
    ap.add_argument("--post-page-out", metavar="DIR",
                    help="the post builds the page into DIR/<the sitting's last campaign> "
                         "(scripts/dashboard_post.py --page-out)")
    ap.add_argument("--no-page-commit", action="store_true",
                    help="the post commits nothing in the page repo (scripts/dashboard_post.py --no-page-commit)")
    ap.add_argument("--hold-held-by", type=int, metavar="PID",
                    help="the device hold is held by this live pid (a keeper that queued for the "
                         "phone): the job neither acquires nor releases it; exit 2 when the pid is "
                         "dead or the hold names another pid. Not with auto")
    ap.add_argument("--no-post", action="store_true",
                    help="print the post command after a sitting that exits 0 and run nothing: no "
                         "check, commit, page or push (a person runs it after review)")
    ap.add_argument("--release-by", metavar="HH:MM|none",
                    help="give the hold back by this local time (the first after this invocation began) "
                         "instead of the device's schedule.json release_by; none: no such time")
    args = ap.parse_args()
    if args.hold_held_by is not None and args.device == "auto":
        ap.error("--hold-held-by names one device's hold: not with auto")
    if args.release_by is not None and args.release_by.lower() != "none" and not RELEASE_BY_RE.match(args.release_by):
        ap.error(f"--release-by {args.release_by}: HH:MM local time, or none")
    # the invocation's start: a sitting's release_by is the first after it (release_deadline)
    args.started_at = datetime.datetime.now()
    global HOLD_KEEPER, NO_POST
    HOLD_KEEPER = args.hold_held_by
    NO_POST = args.no_post

    try:
        schedule = json.load(open(args.schedule))
        register_devices(schedule)
        check_parts(schedule)
        check_release_by(schedule)
    except (OSError, ValueError) as e:
        print(f"schedule unreadable: {e}", file=sys.stderr)
        return EXIT_CONFIG
    auto = args.device == "auto"
    if args.part is not None and (auto or args.cells):
        ap.error("--part names a part of one device's weekly set: not with auto or --cells")
    key, dev, _ = resolve_device(schedule, args.device)
    if not auto and dev.get("platform") == "ddp" and HOLD_KEEPER is not None:
        ap.error("--hold-held-by: a lab unit (platform ddp) has no hold")
    tags = [p["tag"] for p in device_parts(dev)] if not auto else []
    if args.part is not None and args.part not in tags:
        ap.error(f"--part {args.part}: the weekly set of {key} has "
                 + (f"the parts {', '.join(tags)}" if tags else "no parts"))
    if not args.dry_run and not auto:
        other = device_lock(key)
        if other:
            print(f"a dashboard sitting is already running on {key} (pid {other}); exit {EXIT_BUSY}")
            return EXIT_BUSY
    open_log("auto" if auto else key)
    if not auto and dev.get("platform") == "ddp":
        # a lab unit by hand: its sitting, ledger line and post (no retake, no busy poll, one attempt)
        return ddp_slot(schedule, key, dev, args, cells=args.cells, suffix=args.suffix)

    retry = schedule.get("retry", {})
    poll = float(retry.get("busy_poll_minutes", 15)) * 60
    window = float(retry.get("busy_window_minutes", 120)) * 60
    max_attempts = int(retry.get("max_attempts_per_slot", 2))
    abort_wait = retry.get("abort_retry_after_minutes", {})
    t0 = time.time()
    attempt_no, code, reason, camp = 1, EXIT_CONFIG, "", ""
    sitting = []      # the campaign dirs of the last attempt (its SESSION.json dirs), for the post step
    started = time.strftime("%F %T")
    tried = {}        # auto: key -> (state, detail) for devices passed over this firing
    pinned = False    # auto: an abort retry stays on the device it aborted on
    retaken = set()   # devices whose pending retakes this firing has run (one retake sitting each)
    retake_only = False   # auto chose a device for its retake: its weekly set is done this week
    own_ledger = False    # the retake sitting wrote the firing's ledger line; nothing else ran
    while True:
        if auto and not pinned:
            now = datetime.datetime.now().astimezone()
            if not args.dry_run:
                choose_lock()
            key, dev, report = resolve_device(schedule, "auto", exclude=tried, now=now,
                                              retakes={} if (args.cells or args.no_retake) else None)
            if key and not args.dry_run:
                other = device_lock(key)
                if other:  # taken between the probe and now: pass it over
                    for e in report:
                        if e["key"] == key:
                            e.update(state="busy", detail=f"a sitting started on it (pid {other})")
                    tried[key] = ("busy", f"a sitting is running on it (pid {other})")
                    key = dev = None
            if not args.dry_run:
                choose_unlock()
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
                late = [e for e in report if e["state"] == "waiting" and e["key"] in tried]
                if notready:
                    code, reason = EXIT_DEVICE, "; ".join(f"{e['key']}: {e['detail']}" for e in notready)
                elif busy:
                    code, reason = EXIT_BUSY, "busy: " + ", ".join(busy)
                elif late:
                    code, reason = EXIT_OK, "nothing to measure now: " + "; ".join(
                        f"{e['key']}: {e['detail']}" for e in late)
                else:
                    code, reason = EXIT_OK, "nothing pending this week"
                break
            open_log(key)
            log(f"auto chose {key} (the decision is in {datetime.date.today().isoformat()}-auto.log)")
            retake_only = any(e["key"] == key and e.get("weekly_done") for e in report)
        late = None   # TooLate: the device's release_by leaves no room for this sitting's first runs (§11)
        if key not in retaken and not (args.cells or args.no_retake):
            # stage 3a: the device's pending retakes as their own sitting before its weekly set
            retaken.add(key)
            try:
                rcode = retake_sitting(schedule, key, dev, args, weekly_follows=not retake_only)
            except TooLate as e:
                retaken.discard(key)    # nothing ran: no ledger line, no retake attempt
                late = e
            if late is None and rcode == EXIT_BUSY:
                retaken.discard(key)    # taken again with the device, after the busy poll
            if late is None and rcode in (EXIT_BUSY, EXIT_DEVICE) and auto and not pinned:
                tried[key] = ("busy" if rcode == EXIT_BUSY else "not-ready",
                              f"its retake sitting: {VERDICT_NAME[rcode]}")
                _unlock(f".job.lock.{key}")
                open_log("auto")
                continue
            if late is None and retake_only:
                code = EXIT_OK if rcode is None else rcode
                reason = ("the retake sitting only: the weekly set is done this week" if rcode is not None
                          else "nothing to retake (expired or superseded, or the retake state unusable: the log says which)")
                camp, sitting, own_ledger = "", [], True
                break
        if late is None:
            sitting = []
            try:
                code, reason, camp, sitting = attempt(schedule, key, dev, attempt_no, args)
            except TooLate as e:
                late = e
            except Busy as e:
                code, reason = EXIT_BUSY, str(e)
                log(f"BUSY: {e}")
            except NotReady as e:
                code, reason = EXIT_DEVICE, str(e)
                log(f"DEVICE: {e}")
            except ConfigError as e:
                code, reason = EXIT_CONFIG, str(e)
                log(f"CONFIG: {e}")
        if late is not None:
            log(f"TOO LATE: {late}")
            if auto and not pinned:
                # passed over for this firing, not polled again: the time to release_by only gets shorter
                tried[key] = ("waiting", str(late))
                _unlock(f".job.lock.{key}")
                open_log("auto")
                continue
            # by key: busy (exit 3); an abort retry that no longer fits keeps the abort's verdict
            code, reason = (EXIT_ABORTED, f"{reason}; the retry not started: {late}") if pinned else (EXIT_BUSY, str(late))
            break
        if auto and not pinned and code in (EXIT_BUSY, EXIT_DEVICE):
            # pass over this device now; a busy one is reconsidered after the poll
            tried[key] = ("busy" if code == EXIT_BUSY else "not-ready", reason)
            _unlock(f".job.lock.{key}")
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
    if not args.dry_run and not own_ledger and not (auto and not key and code == EXIT_OK):
        ledger({"started": started, "ended": ended, "device": key or "auto", "campaign": camp or "",
                "verdict": VERDICT_NAME.get(code, str(code)), "reason": reason,
                "exit": code, "minutes": round((time.time() - t0) / 60, 1),
                "attempt": attempt_no})
    log(f"=== done: {VERDICT_NAME.get(code, code)} ({reason}) exit {code}")
    # after the ledger line and outside the hold (attempt() released it): the sitting's
    # campaign dirs to the post step; nothing it does changes `code` or the line above
    post_sitting(code, sitting, args.dry_run, post_args(args, sitting))
    if auto and not args.no_ddp:
        # the lab units after the attached device's sitting: that device is free again first
        if key:
            _unlock(f".job.lock.{key}")
        ddp_after(schedule, args)
    return code


if __name__ == "__main__":
    sys.exit(main())
