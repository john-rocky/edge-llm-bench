#!/usr/bin/env python3
"""Device-free selftest of the dashboard job's `auto` device choice (CI).

`./bench dashboard-job auto` measures, among the devices with no admitted
dashboard session since Monday 00:00 local, the attached unheld one whose last
admitted session is oldest (docs/dashboard-recurring-job-v1.md §3). This pins
that choice against a fake `adb` (attachment) and temp hold files, with the
accumulation-layer rows and SESSION.json verdicts handed in directly — no
phone, no results/raw, no log file under logs/dashboard-job. The same rows
pin session admission (§4): the reference is the newest admitted session
whose anchor ran the same engine build, none = first session on that build.
Last, a dry-run sitting on a fake phone pins the side-build check: a cells
file whose engine-build=<tag> build is not on the phone is skipped by itself
and the rest of the sitting runs; and the post step's place: a dry-run
sitting that exits 0 prints the scripts/dashboard_post.py command over the
campaign dirs it would create, after its done line, and any other exit
prints none. A pending retake (stage 3a) makes a device done this week a
candidate again, ahead of the others, and a retake sitting is not the week's
session (the retake sitting itself: scripts/regression_watch_selftest.py).

  python3 scripts/dashboard_job_selftest.py     # exit 0 = pass
"""
import argparse
import contextlib
import datetime
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

FAKE_ADB = '''#!/usr/bin/env python3
import os, sys
STATE = __STATE__


def main(argv):
    if argv[:1] == ["devices"]:
        print("List of devices attached")
        for ln in open(os.path.join(STATE, "devices.txt")):
            if ln.strip():
                print(ln.strip() + "\\tdevice")
        return 0
    if argv[:1] == ["-s"]:
        argv = argv[2:]
    if argv[:1] == ["reboot"]:
        with open(os.path.join(STATE, "rebooted.txt"), "a") as fh:
            fh.write("reboot\\n")
        with open(os.path.join(STATE, "uptime_s.txt"), "w") as fh:
            fh.write("30")
        return 0
    if argv[:1] == ["shell"]:
        cmd = " ".join(argv[1:])
        if "dumpsys thermalservice" in cmd:
            print("Thermal Status: 0")
        elif cmd.startswith("cat /proc/uptime"):
            up = os.path.join(STATE, "uptime_s.txt")
            s = open(up).read().strip() if os.path.exists(up) else "600"
            print(s + " " + s)
        elif cmd.startswith("cat /proc/meminfo"):
            print("MemTotal:        7754700 kB")
            print("MemAvailable:    3700000 kB")
            print("SwapTotal:       3877344 kB")
            print("SwapFree:        2500000 kB")
        elif cmd.startswith("getprop sys.boot_completed"):
            print("1")
        elif cmd.startswith("am kill-all"):
            pass
        elif cmd.startswith("ls ") and "/models" in cmd:
            print("fake.gguf")
        elif cmd.startswith("ls ") and "/engines/" in cmd:
            # the side-build tools on the fake phone: the paths listed in engines.txt
            listed = os.path.join(STATE, "engines.txt")
            have = set(open(listed).read().split()) if os.path.exists(listed) else set()
            paths = [p for p in cmd[3:].split() if p.startswith("/")]
            for p in paths:
                if p in have:
                    print(p)
            return 0 if all(p in have for p in paths) else 1
        elif cmd.startswith("dumpsys power"):
            print("  mWakefulness=Awake")
        elif "scaling_max_freq" in cmd:
            print("2000000 2000000")
        elif cmd.startswith("df -k"):
            print("/dev/block 100000000 40000000 60000000 40% /data")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
'''

# the lab unit's `bench` in a temp ROOT (the job's doctor and plan probes are faked in the selftest):
# `matrix <cells> --ddp <id> --campaign <c>` leaves the campaign dir a DDP run leaves (ddp/session-1.json
# with two jobs' execution times, SKIPPED.txt) and exits FAKE_BENCH_RC
FAKE_BENCH = '''#!/usr/bin/env python3
import json, os, sys
a = sys.argv[1:]
if a[:1] == ["matrix"] and "--ddp" in a and "--dry-run" not in a:
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "raw",
                     a[a.index("--campaign") + 1] + "-android")
    os.makedirs(os.path.join(d, "ddp"))
    os.makedirs(os.path.join(d, "app-path-android"))
    job = lambda name, start, end: {"displayName": name, "result": {"resultType": "PASSED"},
                                    "executionReports": [{"startTime": start, "endTime": end}]}
    with open(os.path.join(d, "ddp", "session-1.json"), "w") as fh:
        json.dump({"name": "projects/p/locations/global/sessions/session-fake0001",
                   "sessionReport": {"jobReports": [
                       job("j01", "2099-01-01T00:00:00.5Z", "2099-01-01T00:09:30.5Z"),
                       job("j02", "2099-01-01T00:00:00Z", "2099-01-01T00:05:00.123456789Z")]}}, fh)
    with open(os.path.join(d, "app-path-android", "SKIPPED.txt"), "w") as fh:
        fh.write("CELL_SKIP litert-lm-cpu m/B short-chat exclude-on=s26 reason=x\\n")
    sys.exit(int(os.environ.get("FAKE_BENCH_RC", "0")))
'''

_fails = []


def ok(cond, msg):
    print(("  ok  " if cond else "  FAIL ") + msg)
    if not cond:
        _fails.append(msg)


def main():
    tmp = tempfile.mkdtemp(prefix="dashboard-job-selftest-")
    state = os.path.join(tmp, "state")
    bin_dir = os.path.join(tmp, "bin")
    os.makedirs(state)
    os.makedirs(bin_dir)
    adb = os.path.join(bin_dir, "adb")
    with open(adb, "w") as fh:
        fh.write(FAKE_ADB.replace("__STATE__", repr(state)))
    os.chmod(adb, 0o755)
    os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")

    import dashboard_job as dj
    REAL_PGREP = dj.pgrep   # the module's own; later cases replace dj.pgrep with fakes

    # the per-device job locks live under LOG_DIR; keep the selftest's probes and
    # its held lock inside the temp dir, never under logs/dashboard-job
    dj.LOG_DIR = os.path.join(tmp, "logs")

    # the Mac guard's heavy-pipeline rule is anchored at the program the process runs
    # (2026-10-08: two agent CLI sessions' prompt text named the coreai venv's python and
    # the unanchored rule read an idle Mac as busy)
    heavy = dj.mac_heavy_command
    ok(not heavy("/Users/u/.local/bin/claude --model m 'まず coreai-models/.venv/bin/python export_x.py を読んで'"),
       "mac guard: an agent CLI whose prompt names the coreai venv python is not heavy")
    ok(heavy("/Users/u/code/coreai-models/.venv/bin/python export_simple_template.py --L 128"),
       "mac guard: the coreai venv python is heavy")
    ok(heavy("python3 -m coreai.llm.export --platform iOS"), "mac guard: python -m coreai.llm.export is heavy")
    ok(heavy("/Users/u/.venv-et151/bin/python3.12 -m executorch.extension.llm.export.export_llm --config q.yaml"),
       "mac guard: an ExecuTorch export is heavy")
    ok(heavy("/opt/x/release/llm-benchmark --model a.aimodel"), "mac guard: llm-benchmark is heavy")
    ok(not heavy("python3 scripts/build_summary.py"), "mac guard: a summary build is not heavy")
    ok(heavy("/Users/u/code/hf-to-litertlm/.venv/bin/python scripts/convert.py Qwen/Qwen3-1.7B --out x"),
       "mac guard: the hf-to-litertlm one-command export (scripts/convert.py) is heavy")
    ok(not heavy("/Users/u/.local/bin/claude --model m 'read scripts/convert.py first'"),
       "mac guard: an agent CLI whose prompt names convert.py is not heavy")
    # the Mac measurement window: the sitting flocks the lock schedule.json names and writes the
    # timing label; a lock another process holds is Busy; the release empties it
    import fcntl as _fcntl
    qpath = os.path.join(tmp, "_GPU_LOCK")
    ql = dj.quiet_lock_take({"quiet_lock": qpath}, "m4max 2099-01-01-dashboard-v1-m4max")
    line = open(qpath).read()
    fd2 = os.open(qpath, os.O_RDWR)
    try:
        _fcntl.flock(fd2, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
        held = False
    except OSError:
        held = True
    dj.quiet_lock_release(ql)
    try:
        _fcntl.flock(fd2, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
        free_after = True
    except OSError:
        free_after = False
    try:
        dj.quiet_lock_take({"quiet_lock": qpath}, "m4max again")
        busy = False
    except dj.Busy:
        busy = True
    _fcntl.flock(fd2, _fcntl.LOCK_UN)
    os.close(fd2)
    ok(line.startswith("dashboard-job m4max 2099-01-01-dashboard-v1-m4max timing pid ") and held and free_after
       and open(qpath).read() == "" and busy and dj.quiet_lock_take({}, "x") is None,
       f"quiet lock: label written and flock held during the sitting, empty and free after, Busy while another "
       f"process holds it, none without schedule quiet_lock ({held}, {free_after}, {busy})")
    # bench work goes last: a free window other jobs want is Busy too, counted as quiet_rank.py counts the
    # jobs a window waits for (a live, not stopped waiter registered in <lock>.waiters/ or
    # <lock>.yield_waiters/, the job a held <lock>.yield_slots/<i> names), and the lock is let go
    # untouched (line and mtime)
    import signal as _signal
    wdir, ydir, sdir = qpath + ".waiters", qpath + ".yield_waiters", qpath + ".yield_slots"
    for d in (wdir, ydir, sdir):
        os.makedirs(d)

    def lock_free():
        fd = os.open(qpath, os.O_RDONLY)
        try:
            _fcntl.flock(fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
            return True
        except OSError:
            return False
        finally:
            os.close(fd)

    def take(label):
        """-> (Busy's reason or None, the lock's line while taken, its flock held while taken)"""
        try:
            q = dj.quiet_lock_take({"quiet_lock": qpath}, label)
        except dj.Busy as e:
            return str(e), None, None
        try:
            return None, open(qpath).read(), not lock_free()
        finally:
            dj.quiet_lock_release(q)

    def untouched():
        return lock_free() and open(qpath).read() == "" and os.stat(qpath).st_mtime_ns == 10 ** 18

    def register(directory, pid, text, mtime=None):
        path = os.path.join(directory, str(pid))
        with open(path, "w") as fh:
            fh.write(text)
        if mtime:
            os.utime(path, (mtime, mtime))
        return path

    kids = []

    def child(code, *args):
        p = subprocess.Popen([sys.executable, "-c", code, *args], stdout=subprocess.PIPE, text=True)
        kids.append(p)
        return p

    def hold_slot(name, line):
        """a child that holds slot `name`, its line `line` ({pid} = the child's pid) -> (child, held)"""
        p = child("import fcntl, os, sys, time\n"
                  "fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o644)\n"
                  "fcntl.flock(fd, fcntl.LOCK_EX)\n"
                  "os.write(fd, sys.argv[2].replace('{pid}', str(os.getpid())).encode())\n"
                  "print('held', flush=True)\n"
                  "time.sleep(60)\n", os.path.join(sdir, name), line)
        return p, p.stdout.readline().strip() == "held"

    live, stopped = child("import time; time.sleep(60)"), child("import time; time.sleep(60)")
    gone = subprocess.Popen([sys.executable, "-c", "pass"])
    gone.wait()
    try:
        os.utime(qpath, ns=(10 ** 18, 10 ** 18))
        # waiter case: a live window waiter (quiet_hold), whatever its class word, then a live job
        # waiting for a build slot (quiet_yield)
        w = register(wdir, live.pid, "lane x timing")
        waiter_why = take("m4max waiter")[0]
        register(wdir, live.pid, "bench edge-llm-bench x timing")
        bench_why = take("m4max bench waiter")[0]
        waiter_left = untouched()
        os.unlink(w)
        y = register(ydir, live.pid, "bash build.sh")
        yield_why = take("m4max yield waiter")[0]
        yield_left = untouched()
        os.unlink(y)
        # slot case: a held slot whose line starts with its job's pid, then a scheduler's line that
        # names a live root
        h0, h0_held = hold_slot("0", "{pid} bazel --batch build //x")
        slot_why = take("m4max slot")[0]
        h0.kill()
        h0.wait()
        h6, h6_held = hold_slot("6", f"{{pid}} adopted {live.pid}")
        sched_why = take("m4max adopted")[0]
        slot_left = untouched()
        h6.kill()
        h6.wait()
        # free case: no job that can take its turn: dead pids' files, a file older than its pid's process
        # (a reused pid), a stopped waiter, the lock line's holder, held slots whose line names a dead
        # job, slot 0 released with its holder
        os.kill(stopped.pid, _signal.SIGSTOP)
        os.waitpid(stopped.pid, os.WUNTRACED)
        register(wdir, gone.pid, "lane y timing")
        register(ydir, gone.pid, "bash y.sh")
        register(ydir, live.pid, "bash old.sh", mtime=10 ** 9)
        register(wdir, stopped.pid, "lane s timing")
        register(ydir, stopped.pid, "bash s.sh")
        register(wdir, live.pid, "lane h timing")
        with open(qpath, "w") as fh:
            fh.write(f"lane h timing pid {live.pid} since 2099-01-01T00:00:00+0900")
        h1, h1_held = hold_slot("1", f"{gone.pid} bazel --batch build //y")
        h7, h7_held = hold_slot("7", f"{{pid}} thaw {gone.pid} z")
        free_why, free_line, free_held = take("m4max free")
    finally:
        for p in kids:
            if p.poll() is None:
                p.kill()
                p.wait()
    ok(waiter_why is not None and f"1 job(s) waiting for the window (pid {live.pid}: lane x timing)" in waiter_why
       and bench_why is not None and f"(pid {live.pid}: bench edge-llm-bench x timing)" in bench_why
       and "build slot" not in waiter_why and waiter_left,
       f"quiet lock, bench goes last: a live window waiter registered next to the lock = Busy, a bench one "
       f"too, the lock let go untouched ({waiter_why}; {bench_why}; untouched {waiter_left})")
    ok(yield_why is not None and f"1 job(s) waiting for a build slot (pid {live.pid}: bash build.sh)" in yield_why
       and "waiting for the window" not in yield_why and yield_left,
       f"quiet lock, bench goes last: a live job registered waiting for a build slot = Busy, the lock let go "
       f"untouched ({yield_why}; untouched {yield_left})")
    ok(h0_held and h6_held and slot_why is not None
       and f"1 job(s) holding a build slot (pid {h0.pid}: slot 0: {h0.pid} bazel" in slot_why
       and sched_why is not None and f"(pid {live.pid}: slot 6: {h6.pid} adopted {live.pid})" in sched_why
       and "waiting for" not in slot_why + sched_why and slot_left,
       f"quiet lock, bench goes last: a held build slot = Busy for the job its line names (a scheduler's "
       f"line: its root), the lock let go untouched ({slot_why}; {sched_why}; untouched {slot_left})")
    ok(h1_held and h7_held and free_why is None and (free_line or "").startswith("dashboard-job m4max free timing pid ")
       and free_held and open(qpath).read() == "",
       f"quiet lock, bench goes last: dead and reused-pid files, a stopped waiter, the lock line's holder, "
       f"slots held for dead jobs and a released slot leave it free: taken and released ({free_why})")
    ok(not heavy("node /x/claude --prompt 'release/llm-benchmark --model'"), "mac guard: llm-benchmark named inside another argv is not heavy")

    def attached(*serials):
        with open(os.path.join(state, "devices.txt"), "w") as fh:
            fh.write("".join(s + "\n" for s in serials))

    hold_b = os.path.join(tmp, "hold_beta")
    schedule = {
        "devices": {
            "alpha": {"platform": "android", "display": "Fake A", "identifier": "FakeA",
                      "serial": "FAKE-A", "hold": os.path.join(tmp, "hold_alpha")},
            "beta": {"platform": "android", "display": "Fake B", "identifier": "FakeB",
                     "serial": "FAKE-B", "hold": hold_b},
            "fone": {"platform": "iphone", "display": "Fake phone", "identifier": "FakeP",
                     "udid": "FAKE-UDID", "app": "x.y", "auto_window": "05:00-08:00",
                     "auto_idle_hours": 4},
        },
    }
    # a fixed local "now" at 02:00: 30 min ago is always this week (Monday 00:00
    # local at the earliest), 8+ days ago always an earlier week
    now = datetime.datetime.now().astimezone().replace(hour=2, minute=0, second=0, microsecond=0)

    def ts(**delta):
        t = (now - datetime.timedelta(**delta)).astimezone(datetime.timezone.utc)
        return t.strftime("%Y-%m-%dT%H:%M:%SZ")

    def row(camp, dev, **delta):
        return {"campaign": f"results/raw/{camp}", "platform": "android",
                "timestamp": ts(**delta), "device": dev}

    def choose(rows, admitted=None):
        key, dev, report = dj.resolve_device(schedule, "auto", now=now, rows=rows,
                                             admitted=admitted or {})
        return key, {e["key"]: e for e in report}

    attached("FAKE-A", "FAKE-B")
    older_a = [row("d21-dashboard-v1-alpha-android", "FakeA", days=21),
               row("d14-dashboard-v1-beta-android", "FakeB", days=14)]
    older_b = [row("d14-dashboard-v1-alpha-android", "FakeA", days=14),
               row("d21-dashboard-v1-beta-android", "FakeB", days=21)]

    print("--- two free devices, neither measured this week: the older last-admitted goes first")
    key, rep = choose(older_a)
    ok(key == "alpha", f"alpha (21 d) before beta (14 d): chose {key}")
    key, rep = choose(older_b)
    ok(key == "beta", f"beta (21 d) before alpha (14 d): chose {key} — age, not schedule order")
    ok(rep["fone"]["state"] == "waiting" and "window" in rep["fone"]["detail"],
       f"iPhone at 02:00 is outside its window, never probed: {rep['fone']['detail']}")
    key, rep = choose([row("d14-dashboard-v1-beta-android", "FakeB", days=14)])
    ok(key == "alpha", f"a device never measured counts as oldest: chose {key}")

    print("--- an entry with auto: false is never chosen by auto, however old; the explicit key still resolves")
    schedule["devices"]["hand"] = {"platform": "android", "display": "Fake H", "identifier": "FakeH",
                                   "serial": "FAKE-H", "hold": os.path.join(tmp, "hold_hand"), "auto": False}
    attached("FAKE-A", "FAKE-B", "FAKE-H")
    key, rep = choose(older_a)
    ok(key == "alpha" and rep["hand"]["state"] == "by-hand",
       f"hand (never measured, attached, unheld) is passed over: chose {key} ({rep['hand']['detail']})")
    key, rep = choose(older_a + [row("now-dashboard-v1-alpha-android", "FakeA", minutes=20),
                                 row("now-dashboard-v1-beta-android", "FakeB", minutes=30)])
    ok(key is None and rep["hand"]["state"] == "by-hand",
       f"alpha and beta done this week, hand pending -> nothing to measure (chose {key})")
    k2, d2, rep2 = dj.resolve_device(schedule, "hand")
    ok(k2 == "hand" and d2["serial"] == "FAKE-H" and rep2 == [],
       "the explicit key resolves the by-hand device")
    del schedule["devices"]["hand"]
    attached("FAKE-A", "FAKE-B")

    print("--- a device whose sitting is running (its .job.lock.<key> held) is busy; others still go")
    import fcntl
    os.makedirs(dj.LOG_DIR, exist_ok=True)
    held = open(os.path.join(dj.LOG_DIR, ".job.lock.alpha"), "a+")
    fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
    held.seek(0); held.truncate(); held.write("4242"); held.flush()
    key, rep = choose(older_a)
    ok(key == "beta" and rep["alpha"]["state"] == "busy" and "sitting" in rep["alpha"]["detail"],
       f"alpha's sitting running -> beta: chose {key} ({rep['alpha']['detail']})")
    fcntl.flock(held, fcntl.LOCK_UN); held.close()
    key, rep = choose(older_a)
    ok(key == "alpha", f"lock released -> alpha again: chose {key}")

    print("--- a device with an admitted session this week is not chosen again")
    this_week = older_b + [row("now-dashboard-v1-beta-android", "FakeB", minutes=30)]
    key, rep = choose(this_week)
    ok(key == "alpha", f"beta done this week -> alpha, though beta's earlier session is older: chose {key}")
    ok(rep["beta"]["state"] == "done", f"beta reported done: {rep['beta']['detail']}")
    both = this_week + [row("now-dashboard-v1-alpha-android", "FakeA", minutes=20)]
    key, rep = choose(both)
    ok(key is None, f"both done this week -> nothing to measure (chose {key})")
    refused = older_b + [row("now-dashboard-v1-beta-android", "FakeB", minutes=30)]
    key, rep = choose(refused, admitted={"results/raw/now-dashboard-v1-beta-android": False})
    ok(key == "beta", f"a refused sitting (SESSION.json admitted:false) is not done: chose {key}")
    probe = older_b + [row("now-dashboard-v1-beta-anchor-android", "FakeB", minutes=30)]
    key, rep = choose(probe)
    ok(key == "beta", f"the anchor probe alone is not a session: chose {key}")

    print("--- a pending retake: the device is a candidate though its weekly set is done, and goes first")
    week = older_b + [row("now-dashboard-v1-beta-android", "FakeB", minutes=30)]
    key, _, rep = dj.resolve_device(schedule, "auto", now=now, rows=week, admitted={}, retakes={"beta": 2}, skip=set())
    rep = {e["key"]: e for e in rep}
    ok(key == "beta" and rep["beta"].get("weekly_done") is True and "2 retakes pending" in rep["beta"]["detail"],
       f"beta done this week, 2 retakes pending: chosen before alpha's weekly set ({rep['beta']['detail']})")
    retake = "now-dashboard-v1-beta-retake-x-android"
    key, _, rep = dj.resolve_device(schedule, "auto", now=now, rows=older_b + [row(retake, "FakeB", minutes=30)],
                                    admitted={}, retakes={}, skip={f"results/raw/{retake}"})
    rep = {e["key"]: e for e in rep}
    ok(key == "beta" and rep["beta"]["state"] == "candidate"
       and rep["beta"]["detail"].startswith("last admitted ") and "retake" not in rep["beta"]["detail"],
       f"beta's retake sitting this week is not its weekly session: a candidate on its 21-day-old session, "
       f"chosen as the oldest ({key}: {rep['beta']['detail']})")

    print("--- held or detached devices are passed over")
    with open(hold_b, "w") as fh:
        fh.write('{"pid": %d, "script": "selftest-parent", "device": "beta", "started": "now"}'
                 % os.getppid())
    key, rep = choose(older_b)
    ok(key == "alpha" and rep["beta"]["state"] == "busy",
       f"beta held by a live pid -> alpha: chose {key} ({rep['beta']['state']})")
    os.remove(hold_b)
    attached("FAKE-A")
    key, rep = choose(older_b)
    ok(key == "alpha" and rep["beta"]["state"] == "not-ready",
       f"beta not visible to adb -> alpha: chose {key} ({rep['beta']['detail']})")
    key, rep = choose(older_b + [row("now-dashboard-v1-alpha-android", "FakeA", minutes=5)])
    ok(key is None and rep["beta"]["state"] == "not-ready",
       "alpha done, beta detached -> no device, beta reported not-ready for the ledger")

    print("--- reboot_before: a phone past its uptime limit is rebooted (under the hold); a fresh one, a dry run, an unconfigured device are not")
    rb = {"serial": "alpha", "reboot_before": {"uptime_hours": 2, "settle_seconds": 0,
                                                "reboot_grace_seconds": 0, "boot_timeout_seconds": 10}}
    marker = os.path.join(state, "rebooted.txt")
    with open(os.path.join(state, "uptime_s.txt"), "w") as fh:
        fh.write(str(13 * 3600))
    ok(dj.android_reboot_if_stale(rb, dry=True) is False and not os.path.exists(marker),
       "dry run at 13 h uptime: reports, never reboots")
    ok(dj.android_reboot_if_stale(rb, dry=False) is True and os.path.exists(marker),
       "13 h uptime > 2 h: rebooted, boot_completed seen, settled, background dropped")
    os.remove(marker)
    ok(dj.android_reboot_if_stale(rb, dry=False) is False and not os.path.exists(marker),
       "30 s after the reboot: within the limit, no second reboot")
    ok(dj.android_reboot_if_stale({"serial": "alpha"}, dry=False) is False and not os.path.exists(marker),
       "no reboot_before in the device entry: never rebooted")

    print("--- admission: the reference is the newest admitted session whose anchor ran the SAME engine build")
    adm_schedule = {"anchors": "matrices/anchors.cells",
                    "admission": {"min_anchor_runs": 2, "collapse_ratio": 0.5,
                                  "thermal_tolerance_pct": 5.0}}
    pixel = {"identifier": "FakeA", "platform": "android"}
    own = "results/raw/now-anchor-android"

    def anchor_rows(camp, tpss, engine, thermal="nominal", **delta):
        """Three cold llama.cpp anchor runs of one session, two minutes apart,
        the newest `delta` ago — the android primary anchor of matrices/anchors.cells."""
        base = datetime.timedelta(**delta)
        out = []
        for i, tps in enumerate(tpss):
            t = (now - base - datetime.timedelta(minutes=2 * (len(tpss) - 1 - i)))
            out.append({"campaign": camp, "platform": "android", "device": "FakeA",
                        "timestamp": t.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "runtime": "llama.cpp", "model_id": "unsloth/Qwen3-0.6B-GGUF",
                        "task": "short-chat", "engine_version": engine, "decode_tps": str(tps),
                        "cold_run": "True", "first_ever": "", "thermal_initial": thermal})
        return out

    real_load_rows, real_load_admission = dj.load_rows, dj.load_admission

    def judge(rows, admitted=None):
        dj.load_rows = lambda path=None: rows
        dj.load_admission = lambda: admitted or {}
        verdict, reason, details = dj.admit(adm_schedule, pixel, own, "android")
        return verdict, reason, details["anchors"][0], details

    # the 2026-09-13 Pixel 8a numbers: the sitting on the pin b8999 (median 28.2),
    # another lane's session two days earlier on b10903 (55.0), the last b8999
    # session before it (29.7)
    mine = anchor_rows(own, (29.1, 28.2, 25.9), "b8999", minutes=0)
    lane = anchor_rows("results/raw/lane-b10903-android", (55.0, 55.0, 55.0), "b10903", days=2)
    pin = anchor_rows("results/raw/pin-b8999-android", (32.0, 29.7, 25.9), "b8999", days=2, hours=6)

    verdict, reason, p, details = judge(mine + pin)
    ok(verdict and p["reference"]["campaign"] == "results/raw/pin-b8999-android"
       and abs(p["ratio"] - 28.2 / 29.7) < 1e-9 and reason == "anchor nominal, ratio 0.949 vs reference (b8999)",
       f"same build only: reference is the pin session, {reason}")
    ok(p["engine_version"] == "b8999" and p["reference"]["engine_version"] == "b8999"
       and p["reference_any_version"]["campaign"] == "results/raw/pin-b8999-android",
       "the session's build, the reference's build and the build-blind reference are in the details")
    ok(len(details["anchors"]) == 2 and details["anchors"][1]["cell"].startswith("litert-lm-gpu")
       and details["anchors"][1]["median"] is None,
       "the secondary (litert) anchor is recorded alongside, absent here, and does not gate")
    verdict, reason, p, _ = judge(anchor_rows(own, (10.0, 9.0, 11.0), "b8999", minutes=0) + pin)
    ok(verdict is False and reason == "anchor-collapse", f"same build, median 10 vs 29.7: {reason}")
    verdict, reason, p, _ = judge(mine)
    ok(verdict and reason == "anchor nominal, first session on this device"
       and p["reference"] is None and p["reference_any_version"] is None,
       f"no earlier session at all: {reason}")

    verdict, reason, p, _ = judge(mine + lane)
    ok(verdict and p["reference"] is None and p["ratio"] is None
       and p["reference_any_version"]["campaign"] == "results/raw/lane-b10903-android"
       and p["reference_any_version"]["engine_version"] == "b10903"
       and reason == ("anchor nominal, first session with engine version b8999 on this device "
                      "(newest admitted session ran b10903)"),
       f"only a newer-build session exists (the build-blind rule read 0.513): {reason}")
    verdict, reason, p, _ = judge(mine + lane + pin)
    ok(verdict and p["reference"]["campaign"] == "results/raw/pin-b8999-android"
       and abs(p["ratio"] - 28.2 / 29.7) < 1e-9
       and p["reference_any_version"]["campaign"] == "results/raw/lane-b10903-android",
       f"newer b10903 session skipped, older b8999 session taken: {reason}; "
       f"excluded {p['reference_any_version']['campaign']} kept as reference_any_version")
    verdict, reason, p, _ = judge(mine + lane + pin, admitted={"results/raw/pin-b8999-android": False})
    ok(verdict and p["reference"] is None and "first session with engine version b8999" in reason,
       "a refused session on the same build is no reference either")

    prev1 = anchor_rows("results/raw/prev1-android", (30.0, 29.0, 31.0), "", days=2)
    verdict, reason, p, _ = judge(mine + prev1)
    ok(verdict and p["reference"] is None and p["reference_any_version"]["campaign"] == "results/raw/prev1-android"
       and p["reference_any_version"]["engine_version"] is None and "unstamped rows" in reason,
       f"rows without an engine stamp (pre-v1) never match: {reason}")
    unstamped = anchor_rows(own, (29.1, 28.2, 25.9), "", minutes=0)
    verdict, reason, p, _ = judge(unstamped + lane + pin)
    ok(verdict and p["engine_version"] is None and p["reference"]["campaign"] == "results/raw/lane-b10903-android"
       and reason == "anchor nominal, ratio 0.513 vs reference (anchor rows unstamped: reference of any build)",
       f"a session whose own rows carry no stamp is judged build-blind and says so: {reason}")

    hot = anchor_rows(own, (29.5, 29.0, 30.0), "b8999", thermal="fair", minutes=0)  # 29.5: 0.7% off 29.7
    verdict, reason, p, _ = judge(hot + lane + pin)
    ok(verdict and reason.startswith("non-nominal start (fair) admitted") and p["reference_nominal"]["campaign"]
       == "results/raw/pin-b8999-android", f"hot start within 5% of the same-build all-nominal session: {reason}")
    near = anchor_rows("results/raw/lane-near-android", (28.5, 28.0, 29.0), "b10903", days=2)
    verdict, reason, p, _ = judge(hot + near)
    ok(verdict is False and reason == "anchor-thermal" and p["reference_nominal"] is None
       and p["reference_any_version"]["campaign"] == "results/raw/lane-near-android",
       f"hot start with an all-nominal session on another build only (28.5, within 5%): {reason}")
    dj.load_rows, dj.load_admission = real_load_rows, real_load_admission

    print("--- side builds: a cells file whose engine-build=<tag> build is not on the phone is skipped by "
          "itself, the rest of the sitting runs (dry-run plan, fake adb)")
    cells_dir = os.path.join(tmp, "cells")
    os.makedirs(cells_dir)

    def cells_file(name, *rows):
        path = os.path.join(cells_dir, name)
        with open(path, "w") as fh:
            fh.write("\n".join(rows) + "\n")
        return path

    anchor = "android llama.cpp unsloth/Qwen3-0.6B-GGUF short-chat anchor=1 runs=3 file=Qwen3-0.6B-Q4_K_M.gguf"
    half = cells_file("set-android-h1.cells", anchor)
    side = cells_file("side-android-s26-short.cells", anchor,
                      "android llama.cpp unsloth/Qwen3-0.6B-GGUF short-chat backend=npu "
                      "engine-build=b11469-snapdragon file=Qwen3-0.6B-Q4_K_M.gguf",
                      "android llama.cpp unsloth/Qwen3-0.6B-GGUF short-chat backend=gpu "
                      "engine-build=b11469-snapdragon file=Qwen3-0.6B-Q4_K_M.gguf")
    tool = "/data/local/tmp/llmbench/engines/b11469-snapdragon/bin/llama-cli"
    sched = {"anchors": "matrices/anchors.cells", "cells": half}
    s26 = {"platform": "android", "display": "Fake S", "identifier": "FakeS", "serial": "FAKE-S",
           "cpu_mask": "", "hold": os.path.join(tmp, "hold_s"), "storage_gb_full": 100,
           "timeout_hours": 3, "split": [{"cells": half, "min_free_gb": 1}],
           "extra_cells": [{"cells": side, "tag": "npu", "min_free_gb": 1, "timeout_hours": 4}]}
    attached("FAKE-S")
    engines = os.path.join(state, "engines.txt")
    real_pgrep = dj.pgrep
    dj.pgrep = lambda pattern: []   # host drivers of other lanes are not this test's business
    base = f"{datetime.date.today().isoformat()}-dashboard-v1-s26"

    def plan(cells=None):
        args = argparse.Namespace(suffix=None, dry_run=True, cells=cells)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code, reason, _, _ = dj.attempt(sched, "s26", s26, 1, args)
        return code, reason, buf.getvalue()

    def matrix_line(text, cells, camp):
        return any(f"bench matrix {cells} --platform android --campaign {camp} " in ln
                   for ln in text.splitlines())

    if os.path.exists(engines):
        os.remove(engines)
    code, reason, text = plan()
    ok(code == dj.EXIT_OK and matrix_line(text, half, f"{base}-h1"),
       f"build absent: the storage half still runs (exit {code})")
    ok(not matrix_line(text, side, f"{base}-npu") and f"skipping {side}: side build not on the phone ({tool};" in text,
       "build absent: the side-build file has no bench matrix line, the skip names its missing tool")
    ok(reason == "ok; skipped, side build not on the phone: side-android-s26-short.cells",
       f"build absent: the sitting's reason names the skipped file for the ledger: {reason!r}")
    with open(engines, "w") as fh:
        fh.write(tool + "\n")
    code, reason, text = plan()
    ok(code == dj.EXIT_OK and reason == "ok" and matrix_line(text, half, f"{base}-h1")
       and matrix_line(text, side, f"{base}-npu") and "side build not on the phone" not in text,
       f"build present: both run, the extra file as its own session under its tag (-npu): {reason!r}")
    ok(any("gtimeout --kill-after=60 14400 " in ln and f"bench matrix {side} " in ln for ln in text.splitlines()),
       "build present: the extra file's session runs under its own timeout_hours (4 h)")
    os.remove(engines)
    try:
        plan(cells=side)
        ok(False, "a --cells retake of a side-build file whose build is absent: device not ready")
    except dj.NotReady as e:
        ok("side build not on the phone" in str(e),
           f"a --cells retake of a side-build file whose build is absent: device not ready ({e})")

    print("--- post: a sitting that exits 0 hands the campaign dirs it wrote SESSION.json in to "
          "scripts/dashboard_post.py after its ledger line (a dry run prints the command); any other exit hands none")
    sched_path = os.path.join(tmp, "schedule-post.json")
    with open(sched_path, "w") as fh:
        json.dump(dict(sched, devices={"s26": s26}), fh)

    def job(*argv):
        buf = io.StringIO()
        saved = sys.argv
        sys.argv = ["dashboard_job.py", *argv, "--schedule", sched_path]
        try:
            with contextlib.redirect_stdout(buf):
                code = dj.main()
        finally:
            sys.argv = saved
        return code, buf.getvalue().splitlines()

    want = [f"results/raw/{base}-anchor-android", f"results/raw/{base}-h1-android"]
    code, lines = job("s26", "--dry-run")
    posts = [i for i, ln in enumerate(lines) if "post: $ " in ln]
    done = [i for i, ln in enumerate(lines) if "=== done: OK" in ln]
    ok(code == dj.EXIT_OK and len(posts) == 1 and done and posts[0] > done[0]
       and lines[posts[0]].endswith(f" {dj.POST} {want[0]} {want[1]}   [dry-run: printed, not run]"),
       "a dry-run sitting that exits 0: one post command after its done line, over the anchor phase and the "
       "half it would create (the skipped side-build file has no dir)")
    attached()
    code, lines = job("s26", "--dry-run")
    ok(code == dj.EXIT_DEVICE and not any("post: $ " in ln for ln in lines),
       f"the phone not attached (exit {code}): no post command")
    attached("FAKE-S")
    with contextlib.redirect_stdout(io.StringIO()):
        none = [dj.post_sitting(c, want, True) for c in (dj.EXIT_ABORTED, dj.EXIT_TIMEOUT, dj.EXIT_DEVICE,
                                                          dj.EXIT_BUSY, dj.EXIT_CONFIG)]
        empty = dj.post_sitting(dj.EXIT_OK, [], True)
        cmd = dj.post_sitting(dj.EXIT_OK, want, True)
    ok(none == [None] * 5 and empty is None and cmd == [dj.PY, dj.POST] + want,
       "post_sitting builds the command for exit 0 with dirs only (aborted, timeout, device, busy, config: none)")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cmd = dj.post_sitting(dj.EXIT_OK, ["results/raw/no-such-campaign-android"], False)
    ok(cmd is not None and "post exit 2 (usage;" in buf.getvalue() and "the sitting's exit 0 stands" in buf.getvalue(),
       "a run (not dry) whose post fails: one line with its exit, the sitting's exit unchanged")
    proto = cells_file("proto-android-x.cells",
                       "android llama.cpp unsloth/Qwen3-0.6B-GGUF native-benchmark-1024x256 backend=npu "
                       "engine-build=b11469-snapdragon file=Qwen3-0.6B-Q4_K_M.gguf",
                       "android litert-lm Qwen/Qwen3-0.6B short-chat backend=npu "
                       "engine-build=main-20260821-selfbuilt file=/fake/model_qualcomm_SM8850.litertlm",
                       "android litert-lm Qwen/Qwen3-1.7B short-chat backend=npu "
                       "engine-build=gone-build exclude=no-bundle")
    ok(dj.side_build_tools(proto) == [
        "/data/local/tmp/llmbench/engines/b11469-snapdragon/bin/llama-bench",
        "/data/local/tmp/llmbench/engines/main-20260821-selfbuilt/litert_lm_advanced_main"]
       and dj.side_build_tools(half) == [] and dj.side_build_tools(side) == [tool],
       "the tool each side-build row launches: llama-bench for a native benchmark, llama-cli for a "
       "prompt, the flat LiteRT-LM NPU tool; none for an excluded row or a file without side builds")
    # host drivers: run_cell.py names its phone in argv (--serial); a campaign driver names it
    # only in its environment (BENCH_ANDROID_SERIAL, read by driver_serial), and one that names
    # no phone either way counts as busy
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], env={**os.environ, "BENCH_ANDROID_SERIAL": "FAKE-XYZ"})
    plain = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], env={k: v for k, v in os.environ.items()
                                                  if k != "BENCH_ANDROID_SERIAL"})
    try:
        ok(dj.driver_serial(child.pid) == "FAKE-XYZ" and dj.driver_serial(plain.pid) is None,
           "driver_serial reads BENCH_ANDROID_SERIAL out of a live process's environment, None without it")
    finally:
        child.kill(); plain.kill(); child.wait(); plain.wait()
    ok(dj.driver_serial(child.pid) is None, "driver_serial of a process that is gone: None")
    # pgrep(): one record per matched pid; a Claude session's multi-line prompt argument whose later
    # line starts with a number is not a process (2026-10-19 05:49: "3 asset ..." read as pid 3)
    real_sh = dj.sh
    fake_fl = ("82049 /Users/USER/.local/bin/claude --session-id x --dangerously-skip-permissions run text\n"
               "## stop\n3 asset lines, bench matrix smoke / run_campaign.py named here\n"
               "91288 python3 android/bench/run_campaign.py matrices/x.cells\n")
    dj.sh = lambda cmd, **kw: ((0, fake_fl) if cmd[:2] == ["pgrep", "-fl"] else (0, "82049\n91288\n")
                               if cmd[:2] == ["pgrep", "-f"] else real_sh(cmd, **kw))
    try:
        got = REAL_PGREP("run_campaign.py")
        ok(got == ["91288 python3 android/bench/run_campaign.py matrices/x.cells"],
           f"pgrep: the agent CLI's prompt lines are not drivers, even one that starts with a number ({got})")
    finally:
        dj.sh = real_sh
    real_driver_serial = dj.driver_serial
    drv = "91288 python3 android/bench/run_campaign.py matrices/x.cells"
    for line, env_serial, busy, what in [
            (drv, "OTHER-PHONE", False, "the job's own campaign driver on another phone"),
            (drv, "FAKE-S", True, "a campaign driver on this phone"),
            (drv, None, True, "a campaign driver that names no phone"),
            ("91288 python3 android/bench/run_cell.py --serial OTHER-PHONE x", "FAKE-S", False,
             "run_cell.py on another phone (argv wins)"),
            ("91288 python3 android/bench/run_cell.py --serial FAKE-S x", None, True, "run_cell.py on this phone")]:
        dj.pgrep = lambda pattern, _l=(line,): list(_l)
        dj.driver_serial = lambda pid, _s=env_serial: _s if pid == 91288 else None
        try:
            dj.preflight_android(s26, True, [half])
            ok(not busy, f"host driver, {what}: the phone is not busy")
        except dj.Busy as e:
            ok(busy, f"host driver, {what}: busy ({e})")
    dj.driver_serial = real_driver_serial

    print("--- a DDP lab unit (stage 4): never the firing's device; its weekly sitting after the attached "
          "device's, on the switch, once a week (doctor and plan faked, a gcloud that must never run on PATH)")
    # the DDP route's own selftest (android/ddp/selftest.py) runs the plan and a faked billed path on the
    # pinned engine files; here CI has neither them nor an HF cache: the job's two probes are faked, and a
    # gcloud first on PATH records any call (its 1b trap): the job itself never calls gcloud
    dj.pgrep = lambda pattern: []   # the host-driver cases above left a busy driver in place
    gcalls = os.path.join(state, "gcloud-calls.txt")
    with open(os.path.join(bin_dir, "gcloud"), "w") as fh:
        fh.write(f"#!/bin/sh\necho \"$@\" >> {gcalls}\nexit 1\n")
    os.chmod(os.path.join(bin_dir, "gcloud"), 0o755)
    switch = os.path.join(tmp, "switch.json")
    real_switch, real_doctor, real_plan = dj.SWITCH, dj.ddp_doctor, dj.ddp_plan
    dj.SWITCH = switch

    def set_switch(on=True, cap=16):
        with open(switch, "w") as fh:
            json.dump({"push_bench": False, "ddp_weekly": on, "ddp_max_sessions": cap}, fh)

    doctor = {"rc": 0}
    plans = []

    def fake_plan(cells, ddp_id, campaign):
        plans.append((cells, ddp_id, campaign))
        return {"cells": [("litert-lm-cpu", "m/A", "short-chat"), ("litert-lm-gpu", "m/A", "short-chat")],
                "skips": ["litert-lm-cpu m/B short-chat: x (exclude-on s26)"], "jobs": 2,
                "sessions": doctor.get("sessions", 1), "skipped": 1, "device_minutes": 30.0,
                "engine": "v0.18.0", "upload_objects": 12, "upload_bytes": 3e9, "uncached": []}
    dj.ddp_doctor = lambda: (doctor["rc"], "  ok  gcloud\n" if not doctor["rc"] else "FAIL gcloud sign-in  gcloud auth login\n")
    dj.ddp_plan = fake_plan
    unit_cells = cells_file("unit-android.cells",
                            "android litert-lm m/A short-chat backend=cpu file=a.litertlm",
                            "android litert-lm m/A short-chat backend=gpu file=a.litertlm")
    unit = {"platform": "ddp", "display": "Fake lab unit", "identifier": "FakeU (DDP fake-1)",
            "ddp_id": "fake-1", "cells": unit_cells, "timeout_hours": 2}
    sched_ddp = os.path.join(tmp, "schedule-ddp.json")
    with open(sched_ddp, "w") as fh:
        json.dump(dict(sched, devices={"s26": s26, "unit": unit}), fh)
    today = datetime.date.today().isoformat()
    ucamp = f"{today}-dashboard-v1-unit-fake-1"

    def job_ddp(*argv):
        buf = io.StringIO()
        saved = sys.argv
        sys.argv = ["dashboard_job.py", *argv, "--schedule", sched_ddp]
        try:
            with contextlib.redirect_stdout(buf):
                code = dj.main()
        finally:
            sys.argv = saved
        return code, buf.getvalue().splitlines()

    def at(lines, text):
        return next((i for i, ln in enumerate(lines) if text in ln), None)

    attached("FAKE-A", "FAKE-B")
    sched_units = dict(schedule, devices=dict(schedule["devices"], unit=unit))
    k3, _, rep3 = dj.resolve_device(sched_units, "auto", now=now, rows=older_a, admitted={}, retakes={}, skip=set())
    rep3 = {e["key"]: e for e in rep3}
    ok(k3 == "alpha" and rep3["unit"]["state"] == "ddp" and "after the attached device's sitting" in rep3["unit"]["detail"],
       f"auto: the lab unit (never measured) is no candidate, alpha is chosen ({k3}; unit: {rep3['unit']['detail']})")

    set_switch(True)
    attached("FAKE-S")
    code, lines = job_ddp("auto", "--dry-run")
    i_done, i_ddp = at(lines, "=== done: OK"), at(lines, "ddp: unit (Fake lab unit): due: never measured")
    i_slot = at(lines, f"=== slot unit (Fake lab unit, DDP fake-1) campaign {ucamp}")
    i_mat = at(lines, f"bench matrix {unit_cells} --ddp fake-1 --campaign {ucamp}")
    posts = [i for i, ln in enumerate(lines) if "post: $ " in ln]
    ok(code == dj.EXIT_OK and None not in (i_done, i_ddp, i_slot, i_mat) and i_done < i_ddp < i_slot < i_mat
       and len(posts) == 2 and posts[1] > i_mat and lines[posts[1]].endswith(
           f" {dj.POST} results/raw/{ucamp}-android   [dry-run: printed, not run]"),
       f"auto --dry-run: s26's sitting, its done line and post, then `ddp: unit … due`, the unit's bench matrix "
       f"--ddp line and its post over results/raw/{ucamp}-android (exit {code})")
    ok(any("gtimeout --kill-after=60 7200 " in ln and "--ddp fake-1" in ln for ln in lines),
       "the lab unit's sitting runs under its timeout_hours (2 h)")
    ok(any("ddp plan: 2 jobs in 1 Device Run sessions on fake-1" in ln for ln in lines)
       and any("ddp skip: litert-lm-cpu m/B short-chat" in ln for ln in lines),
       "the plan's jobs, sessions and skipped rows are logged before anything runs")
    attached()
    code, lines = job_ddp("auto", "--dry-run")
    ok(code == dj.EXIT_DEVICE and at(lines, "-> no device to measure now") is not None
       and at(lines, f"bench matrix {unit_cells} --ddp fake-1") is not None,
       f"no attached device (s26 not visible, exit {code}): the lab unit's sitting still runs after the choice")
    attached("FAKE-S")
    code, lines = job_ddp("auto", "--dry-run", "--no-ddp")
    ok(code == dj.EXIT_OK and not any("ddp:" in ln or "--ddp" in ln for ln in lines),
       "--no-ddp: no ddp: line, no lab-unit sitting")
    set_switch(False)
    code, lines = job_ddp("auto", "--dry-run")
    ok(at(lines, "ddp: unit (Fake lab unit): off: ops/autopilot/switch.json ddp_weekly is not true") is not None
       and at(lines, "--ddp fake-1") is None,
       "ddp_weekly false: one `ddp: … off` line, no lab-unit sitting")
    code, lines = job_ddp("unit", "--dry-run")
    ok(code == dj.EXIT_CONFIG and at(lines, "ddp_weekly is not true") is not None and at(lines, "--ddp fake-1") is None,
       f"ddp_weekly false: the lab unit by hand refuses too (exit {code}, CONFIG)")
    set_switch(True)
    code, lines = job_ddp("unit", "--dry-run")
    ok(code == dj.EXIT_OK and at(lines, f"bench matrix {unit_cells} --ddp fake-1 --campaign {ucamp}") is not None
       and at(lines, "SESSION.json would read admitted true") is not None,
       f"the lab unit by hand (dashboard_job.py unit): its sitting, exit {code}")
    set_switch(True, cap=1)
    doctor["sessions"] = 2
    code, lines = job_ddp("unit", "--dry-run")
    ok(code == dj.EXIT_CONFIG and at(lines, "the plan needs 2 Device Run sessions") is not None
       and at(lines, "--ddp fake-1 --campaign") is None,
       f"a plan over ddp_max_sessions (2 > 1): nothing started, exit {code}")
    doctor.update(sessions=1, rc=1)
    set_switch(True)
    n_plans = len(plans)
    code, lines = job_ddp("unit", "--dry-run")
    ok(code == dj.EXIT_DEVICE and at(lines, "doctor (check_ddp) FAILED: FAIL gcloud sign-in") is not None
       and len(plans) == n_plans, f"the doctor FAILs (gcloud signed out): exit {code}, no plan, no sitting")
    doctor["rc"] = 0

    print("--- the lab unit's window (interval_days, 6): due, done (an admitted session in the last 6 days), "
          "tried (a billed sitting in them not admitted), off, by hand")
    urow = lambda camp, **d: dict(row(camp, "FakeU (DDP fake-1)", **d), platform="android")
    sess_of = lambda rows: dj.device_sessions({"devices": {"unit": unit}}, rows, {}, set()).get("unit") or []
    due, why = dj.ddp_due("unit", unit, now, sess_of([urow("d9-dashboard-v1-unit-fake-1-android", days=9)]), True, None)
    ok(due and why.startswith("due: last admitted"), f"last admitted 9 days ago: {why}")
    due, why = dj.ddp_due("unit", unit, now, sess_of([urow("now-dashboard-v1-unit-fake-1-android", minutes=40)]), True, None)
    ok(not due and why.startswith("done: admitted") and why.endswith("within 6 days"),
       f"an admitted session 40 min ago: {why}")
    due, why = dj.ddp_due("unit", unit, now, sess_of([urow("now-dashboard-v1-unit-fake-1-android", minutes=40)]), True, None)
    rows_refused = [urow("now-dashboard-v1-unit-fake-1-android", minutes=40)]
    due, why = dj.ddp_due("unit", unit, now, dj.device_sessions({"devices": {"unit": unit}}, rows_refused,
                          {"results/raw/now-dashboard-v1-unit-fake-1-android": False}, set()).get("unit") or [],
                          True, ("now-dashboard-v1-unit-fake-1-android", "DEVICE", "no record"))
    ok(not due and "was not admitted" in why and "a person looks" in why, f"a billed sitting in the window, not admitted: {why}")
    due, why = dj.ddp_due("unit", unit, now, [], False, None)
    ok(not due and why.startswith("off:"), f"the switch off: {why}")
    due, why = dj.ddp_due("unit", dict(unit, auto=False), now, [], True, None)
    ok(not due and "by hand" in why, f"auto: false: {why}")
    traw = os.path.join(tmp, "troot", "results", "raw")
    for name, started, adm, sessions in (("a-dashboard-v1-unit-fake-1-android", now - datetime.timedelta(hours=1), False, ["s-1"]),
                                         ("b-dashboard-v1-unit-fake-1-r-android", now - datetime.timedelta(days=9), False, ["s-2"]),
                                         ("c-dashboard-v1-unit-fake-1-x-android", now - datetime.timedelta(hours=2), False, []),
                                         ("d-dashboard-v1-unit-fake-1-y-android", now - datetime.timedelta(hours=3), True, ["s-3"])):
        os.makedirs(os.path.join(traw, name))
        with open(os.path.join(traw, name, "SESSION.json"), "w") as fh:
            json.dump({"started": started.strftime("%Y-%m-%d %H:%M:%S"), "admitted": adm, "verdict": "DEVICE",
                       "reason": "no record", "ddp": {"sessions": sessions}}, fh)
    tried = dj.ddp_tried("unit", dj.ddp_window(unit, now)[1], root=os.path.join(tmp, "troot"))
    ok(tried and tried[0] == "a-dashboard-v1-unit-fake-1-android",
       f"ddp_tried: the window's sitting that ran sessions and was not admitted (not one 9 days old, not one that "
       f"posted none, not an admitted one): {tried}")

    # the rolling window, not the attached devices' Monday week: a Sunday-night sitting is not repeated
    # by the Monday 02:00 firing (the 2026-10-18 real sitting ran on a Sunday night)
    mon = datetime.datetime(2026, 10, 19, 2, 0).astimezone()

    def urow_at(t):
        return {"campaign": "results/raw/x-dashboard-v1-unit-fake-1-android", "platform": "android",
                "device": "FakeU (DDP fake-1)",
                "timestamp": t.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    due, why = dj.ddp_due("unit", unit, mon, sess_of([urow_at(mon - datetime.timedelta(hours=2, minutes=30))]), True, None)
    ok(not due and why.endswith("within 6 days"),
       f"a sitting that ended Sunday 23:30: the Monday 02:00 firing does not repeat it ({why})")
    due, why = dj.ddp_due("unit", unit, mon, sess_of([urow_at(mon - datetime.timedelta(days=6, hours=1))]), True, None)
    ok(due and why.endswith("none in the last 6 days"), f"6 days and an hour before the firing: due ({why})")
    due, why = dj.ddp_due("unit", dict(unit, interval_days=3), mon,
                          sess_of([urow_at(mon - datetime.timedelta(days=4))]), True, None)
    ok(due and why.endswith("none in the last 3 days"), f"interval_days 3 in the entry: 4 days ago is due ({why})")

    print("--- the lab unit's sitting, run against a fake bench in a temp ROOT: SESSION.json, ledger line, post")
    froot = os.path.join(tmp, "froot")
    os.makedirs(os.path.join(froot, "results", "raw"))
    with open(os.path.join(froot, "bench"), "w") as fh:
        fh.write(FAKE_BENCH)
    os.chmod(os.path.join(froot, "bench"), 0o755)
    with open(os.path.join(bin_dir, "gtimeout"), "w") as fh:   # GNU coreutils' name on macOS; CI has none
        fh.write("#!/bin/sh\nshift 2\nexec \"$@\"\n")
    os.chmod(os.path.join(bin_dir, "gtimeout"), 0o755)
    fake_post = os.path.join(tmp, "fake_post.py")
    with open(fake_post, "w") as fh:
        fh.write(f"import sys\nopen({os.path.join(state, 'post-argv.txt')!r}, 'a').write(' '.join(sys.argv[1:]) + '\\n')\n")
    real_root, real_post, real_rows = dj.ROOT, dj.POST, dj.load_rows
    dj.ROOT, dj.POST = froot, fake_post
    urel = f"results/raw/{ucamp}-android"
    dj.load_rows = lambda path=None: [{"campaign": urel, "device": "FakeU (DDP fake-1)", "runtime": "litert-lm-gpu",
                                       "model_id": "m/A", "task": "short-chat"}]
    pdir = os.path.join(tmp, "pages")
    code, lines = job_ddp("unit", "--once", "--post-page-out", pdir, "--no-page-commit")
    dj._unlock(".job.lock.unit")    # main() keeps its device lock to the process's end
    sjson = os.path.join(froot, urel, "SESSION.json")
    sdoc = json.load(open(sjson)) if os.path.exists(sjson) else {}
    ok(code == dj.EXIT_OK and sdoc.get("admitted") is True and sdoc.get("reason") == dj.DDP_REASON
       and sdoc.get("anchor", "x") is None and sdoc.get("platform") == "ddp" and sdoc.get("job") == "dashboard-v1",
       f"exit {code}; SESSION.json admitted true, the lab unit's reason, anchor null, platform ddp")
    d = sdoc.get("ddp") or {}
    ok(d.get("id") == "fake-1" and d.get("sessions") == ["session-fake0001"] and d.get("jobs") == 2
       and d.get("device_minutes") == 14.5 and d.get("plan", {}).get("sessions") == 1,
       f"ddp: the unit id, the session the dir pulled, 2 jobs, 9.5 + 5.0 device-min (nanosecond times read): {d}")
    ok(sdoc.get("cells_expected") == 2 and sdoc.get("cells_with_records") == 1 and sdoc.get("skipped"),
       f"cells: the plan's 2 jobs, 1 with records (the summary's rows of the campaign and the unit); SKIPPED kept "
       f"({sdoc.get('cells_with_records')}/{sdoc.get('cells_expected')})")
    led = open(os.path.join(dj.LOG_DIR, "ledger.tsv")).read().splitlines()
    ok(led and led[-1].split("\t")[2:5] == ["unit", urel, "OK"], f"one ledger line: {led[-1].split(chr(9))[2:5]}")
    argv_post = open(os.path.join(state, "post-argv.txt")).read().split() if os.path.exists(
        os.path.join(state, "post-argv.txt")) else []
    ok(argv_post == ["--page-out", os.path.join(pdir, f"{ucamp}-android"), "--no-page-commit", urel],
       f"the post over the dir, with --page-out <dir>/<campaign> and --no-page-commit passed through: {argv_post}")
    code, lines = job_ddp("unit", "--once")
    dj._unlock(".job.lock.unit")
    ok(code == dj.EXIT_CONFIG and at(lines, "holds a sitting already") is not None,
       f"a second sitting the same day without --suffix: refused before the doctor (exit {code})")
    dj.load_rows = lambda path=None: []
    os.environ["FAKE_BENCH_RC"] = "1"
    code, lines = job_ddp("unit", "--once", "--suffix", "r2")
    dj._unlock(".job.lock.unit")
    os.environ.pop("FAKE_BENCH_RC")
    s2 = json.load(open(os.path.join(froot, f"results/raw/{ucamp}-r2-android", "SESSION.json")))
    ok(code == dj.EXIT_DEVICE and s2.get("admitted") is False and s2["reason"].startswith("no record (bench matrix --ddp exit 1")
       and s2.get("runner_exit") == 1, f"no record written: admitted false, exit {code} (DEVICE), no post")
    ok(open(os.path.join(state, "post-argv.txt")).read().count("\n") == 1, "no post after the sitting that wrote nothing")
    dj.ROOT, dj.POST, dj.load_rows = real_root, real_post, real_rows
    dj.SWITCH, dj.ddp_doctor, dj.ddp_plan = real_switch, real_doctor, real_plan
    ok(not os.path.exists(gcalls), "no gcloud call in any of it (the trap first on PATH)")
    os.remove(os.path.join(bin_dir, "gcloud"))

    dj.pgrep = real_pgrep
    lock = "/tmp/edge-llm-bench-android-FAKE-S.lock"   # the preflight's campaign-lock probe
    if os.path.exists(lock):
        os.remove(lock)

    # check_holds: a sibling hold that names another phone is skipped; the same phone, or no device, is busy
    hdir = os.path.join(tmp, "holds"); os.makedirs(hdir, exist_ok=True)
    other = os.path.join(hdir, ".iphone_hold")
    live = os.getppid()
    hdev = {"display": "iPhone 18 Pro", "identifier": "iPhone19,2", "hold": os.path.join(hdir, ".device_hold"),
            "hold_also_check": [other]}
    dj.register_devices({"devices": {"p18": {"display": "iPhone 18 Pro", "identifier": "iPhone19,2"},
                                     "p17": {"display": "iPhone 17 Pro", "identifier": "iPhone18,1"}}})
    verdicts = []
    for hold in ({"pid": live, "script": "x-17pro", "device": "iPhone 17 Pro", "started": "2026-10-19 12:23:30"},
                 {"pid": live, "script": "x-18pro", "device": "iPhone 18 Pro", "started": "2026-10-19 12:23:30"},
                 {"pid": live, "script": "x-nodev", "started": "2026-10-19 12:23:30"}):
        with open(other, "w") as fh:
            json.dump(hold, fh)
        try:
            dj.check_holds(hdev, True)
            verdicts.append("free")
        except dj.Busy:
            verdicts.append("busy")
    ok(verdicts == ["free", "busy", "busy"],
       f"check_holds: another phone's hold is skipped, the same phone's and an unnamed one are busy ({verdicts})")
    if os.path.exists(other):
        os.remove(other)
    with open(hdev["hold"], "w") as fh:     # the phone's own hold file, labelled with another device
        json.dump({"pid": live, "script": "dashboard_job.py", "device": "iPhone 17 Pro", "started": "now"}, fh)
    try:
        dj.check_holds(hdev, True)
        own = "free"
    except dj.Busy:
        own = "busy"
    os.remove(hdev["hold"])
    ok(own == "busy", f"check_holds: the device's own hold file is busy whatever device it names ({own})")

    # iphone_runner_busy: a runner that drives another phone (BENCH_UDID) shares only the host
    real_pgrep_i, real_env_i = dj.pgrep, dj.driver_env
    dj.pgrep = lambda pattern: ["4242 bash scripts/bench_matrix_iphone.sh run matrices/x.cells"]
    dj.register_devices({"devices": {"p18": {"display": "iPhone 18 Pro", "udid": "00008160-MINE", "coredevice": "C7A7-MINE"},
                                     "p17": {"display": "iPhone 17 Pro", "udid": "00008150-OTHER"}}})
    rdev = {"display": "iPhone 18 Pro", "udid": "00008160-MINE", "hold_also_check": [other]}
    outcomes = []
    for env_udid, hold in (("00008150-OTHER", None), ("00008160-MINE", None), ("C7A7-MINE", None), ("UNKNOWN-ID", None),
                           (None, {"pid": live, "script": "x-17pro", "device": "iPhone 17 Pro"}),
                           (None, {"pid": live, "script": "x-18pro", "device": "iPhone 18 Pro"}), (None, None)):
        dj.driver_env = lambda pid, var, _u=env_udid: _u if var == "BENCH_UDID" else None
        if hold is None:
            if os.path.exists(other):
                os.remove(other)
        else:
            with open(other, "w") as fh:
                json.dump(hold, fh)
        outcomes.append("busy" if dj.iphone_runner_busy("00008160-MINE", rdev) else "free")
    # two runners whose phone cannot be read and one other phone holding a sibling lock: one runner may be ours
    dj.pgrep = lambda pattern: ["4242 bash scripts/bench_matrix_iphone.sh run a.cells",
                                "4343 bash scripts/bench_matrix_iphone.sh run b.cells"]
    dj.driver_env = lambda pid, var: None
    with open(other, "w") as fh:
        json.dump({"pid": live, "script": "x-17pro", "device": "iPhone 17 Pro"}, fh)
    outcomes.append("busy" if dj.iphone_runner_busy("00008160-MINE", rdev) else "free")
    os.remove(other)
    dj.pgrep, dj.driver_env = real_pgrep_i, real_env_i
    ok(outcomes == ["free", "busy", "busy", "busy", "free", "busy", "busy", "busy"],
       f"iphone_runner_busy: the runner's phone from its environment (another phone free; this phone by udid or coredevice, "
       f"an unknown id: busy), else from the live sibling hold (another phone free; this phone or no hold: busy), two "
       f"unreadable runners for one other-phone hold: busy ({outcomes})")

    # cells_with_records: a row exclude-on= names for the device is not expected of it (the runner skips it
    # with a CELL_SKIP line and no record); other devices still expect it (Pixel 8a 2026-10-19: every sitting
    # of a file with 4B-class rows had read as partial)
    xcells = os.path.join(tmp, "exclude-on.cells")
    with open(xcells, "w") as fh:
        fh.write("android llama.cpp m/A short-chat\n"
                 "android llama.cpp m/B short-chat exclude=never\n"
                 "android llama.cpp m/C short-chat exclude-on=pixel8a:too-big\n"
                 "mac llama.cpp m/A short-chat\n")
    real_rows_x = dj.load_rows
    dj.load_rows = lambda path=None: [{"campaign": "results/raw/x-android", "device": "Pixel 8a",
                                       "runtime": "llama.cpp", "model_id": "m/A", "task": "short-chat"}]
    try:
        counts = [dj.cells_with_records("results/raw/x-android", xcells, "android", "Pixel 8a", k)
                  for k in ("pixel8a", "s26", None)]
    finally:
        dj.load_rows = real_rows_x
    ok(counts == [(1, 1), (2, 1), (2, 1)],
       f"cells_with_records: the exclude-on=pixel8a row is not expected on pixel8a, expected elsewhere: {counts}")

    hold_estimate_cases(tmp, dj)

    if _fails:
        print(f"\n{len(_fails)} failure(s); temp dir kept: {tmp}")
        return 1
    shutil.rmtree(tmp)
    print("\nselftest OK")
    return 0


HOLD_ETA_DATA = os.path.join(ROOT, "scripts", "testdata", "hold-eta")


def hold_estimate_cases(tmp, dj):
    """The hold's release estimate (scripts/hold_eta.py, docs/dashboard-recurring-job-v1.md §10): the
    keys go into an owned hold only, in one step, beside its own keys; the 2026-10-26 Galaxy S26
    sitting's log read line by line (scripts/testdata/hold-eta: the runner's lines it reads, with the
    gate lines today's runner adds, and the lengths of the logs before that day) gives a time within
    30 min of the real release once round 3/3 of the main matrix is over, and names the sessions after
    it; a running command lets the estimate read the log; a dry run says what the hold would read."""
    import hold_eta
    print("--- hold release estimate: written into an owned hold only, beside its keys; the 2026-10-26 "
          "S26 log read line by line; the job's poll while a command runs; the dry-run line")
    hdir = os.path.join(tmp, "eta-holds")
    os.makedirs(hdir)
    hold = os.path.join(hdir, ".device_hold")
    own = {"pid": os.getpid(), "script": "edge-llm-bench/scripts/dashboard_job.py", "device": "S26",
           "started": "2026-10-26 02:00:06"}
    with open(hold, "w") as fh:
        json.dump(own, fh)   # as device_hold.acquire writes it
    fields = {"expected_release": "2026-10-26 12:48", "release_basis": "npu: round 2/3 done, ~40m left",
              "release_updated": "2026-10-26 12:07:03"}
    wrote = hold_eta.note_hold(hold, os.getpid(), fields)
    text = open(hold).read()
    again = hold_eta.note_hold(hold, os.getpid(), dict(fields, expected_release="2026-10-26 12:50"))
    back = json.loads(open(hold).read())
    ok(wrote and again and "\n" not in text.strip() and list(json.loads(text)) == list(own) + list(fields)
       and back["expected_release"] == "2026-10-26 12:50" and len(back) == len(own) + len(fields)
       and sorted(os.listdir(hdir)) == [".device_hold"],
       f"note_hold: one line, the hold's own keys first and unchanged, the three keys replaced on a rewrite, "
       f"no temp file left ({text.strip()[:80]}...)")
    ok(dj.read_hold(hold) == back, "read_hold reads a hold with the estimate as the JSON it is")
    foreign = dict(own, pid=os.getppid())   # a live pid that is not this process
    with open(hold, "w") as fh:
        json.dump(foreign, fh)
    before = open(hold).read()
    dj.HOLD_KEEPER = None   # an earlier case's --hold-held-by stays in the module
    try:
        dj.check_holds({"hold": hold}, True)
        busy = False
    except dj.Busy:
        busy = True
    with open(hold, "w") as fh:
        json.dump(dict(foreign, **fields), fh)
    try:
        dj.check_holds({"hold": hold}, True)
        busy_eta = False
    except dj.Busy:
        busy_eta = True
    with open(hold, "w") as fh:
        fh.write(before)
    refused = hold_eta.note_hold(hold, os.getpid(), fields)
    gone = os.path.join(hdir, ".device_hold.gone")
    legacy = os.path.join(hdir, ".device_hold.legacy")
    open(legacy, "w").close()
    ok(busy and busy_eta and not refused and open(hold).read() == before
       and not hold_eta.note_hold(gone, os.getpid(), fields) and not os.path.exists(gone)
       and not hold_eta.note_hold(legacy, os.getpid(), fields) and open(legacy).read() == "",
       "note_hold: another pid's hold, a missing hold and a legacy empty hold are left as they are; "
       "check_holds reads another pid's hold as busy with the estimate keys or without")

    # the 2026-10-26 Galaxy S26 sitting, read line by line with the lengths of the logs before that day
    with open(os.path.join(HOLD_ETA_DATA, "history-s26-before-2026-10-26.json")) as fh:
        lengths = json.load(fh)
    schedule = {"anchors": "matrices/anchors.cells", "cells": "matrices/dashboard-text-v1.cells",
                "devices": {"s26": {"platform": "android", "expected_hours": 10.3, "extra_cells": [
                    {"cells": "matrices/dashboard-ortgenai-v1-android-ort.cells"},
                    {"cells": "matrices/dashboard-npu-v1-android-s26-short.cells", "tag": "npu"}]}}}
    rows, released = hold_eta.replay(os.path.join(HOLD_ETA_DATA, "2026-10-26-s26-job-log.txt"), "s26", schedule,
                                     lengths, cells_root=HOLD_ETA_DATA)

    def off_min(row):
        return (row[2] - released).total_seconds() / 60

    main_end = datetime.datetime(2026, 10, 26, 10, 22, 25)
    round3 = [r for r in rows if r[1].startswith("--- round 3/3") and r[0] < main_end][:1]
    plan_rows = [r for r in rows if r[1].startswith("gate plan: re-run 4 ")]
    ok(released == datetime.datetime(2026, 10, 26, 12, 47, 58) and len(round3) == 1 and len(plan_rows) == 1
       and abs(off_min(round3[0])) <= 30 and abs(off_min(plan_rows[0])) <= 30,
       f"10-26 S26: at the main matrix's round 3/3 (and its gate plan line) the time is within 30 min of the "
       f"release 12:47:58: {round3[0][2]:%H:%M} ({off_min(round3[0]):+.0f} min), {plan_rows[0][2]:%H:%M} "
       f"({off_min(plan_rows[0]):+.0f} min)" if round3 and plan_rows else "10-26 S26: no round 3/3 or gate plan row")
    aheads = [r for r in rows if r[1].startswith("gate ahead: ")]
    ok(len(aheads) == 4 and all(f"{i} gate re-run" in r[3] for i, r in enumerate(aheads, 1))
       and off_min(aheads[-1]) - off_min(aheads[0]) >= 30,
       "10-26 S26: each gate ahead line during round 3 adds its re-run to the time: "
       + ", ".join(f"{r[0]:%H:%M} {off_min(r):+.0f}" for r in aheads))
    pending = [r for r in rows if r[0] < datetime.datetime(2026, 10, 26, 10, 22, 25)]
    ok(pending and all(" ort ~" in r[3] and " npu ~" in r[3] for r in pending),
       "10-26 S26: until the main matrix exits, every basis names the ONNX Runtime and NPU sessions after it")
    tail = [r for r in rows if r[0] >= datetime.datetime(2026, 10, 26, 10, 22, 25)]
    ok(tail and all(abs(off_min(r)) <= 10 for r in tail),
       "10-26 S26: from the main matrix's exit on, the time is within 10 min of the release: "
       + ", ".join(f"{r[0]:%H:%M} {off_min(r):+.0f}" for r in tail[:6]))
    marks = [r for r in rows if r[1].startswith(("--- round", "gate plan", "[2026-10-26"))]
    ok(len(marks) >= 15 and len({r[2] for r in marks}) >= 10,
       f"10-26 S26: a time at each mark (runs, rounds, the gate), and it moves: {len(marks)} marks, "
       f"{len({r[2] for r in marks})} distinct times")

    # the job's poll: the estimate reads the log while a command runs and rewrites the hold (the log says
    # the times of now, as a live sitting's does: the poll reads the clock)
    log_path = os.path.join(tmp, "eta-job.log")
    t0 = datetime.datetime.now().replace(microsecond=0)
    with open(log_path, "w") as fh:
        fh.write(f"[{t0:%Y-%m-%d %H:%M:%S}] hold taken: x\n")
    with open(hold, "w") as fh:
        json.dump(own, fh)
    stages = hold_eta.plan_stages([("matrix", "matrices/anchors.cells", "anchor"),
                                   ("matrix", "matrices/dashboard-ortgenai-v1-android-ort.cells", "ort")],
                                  schedule["devices"]["s26"], "s26", lengths, root=HOLD_ETA_DATA)
    said = []
    note = hold_eta.HoldNote(hold, os.getpid(), hold_eta.Sitting(stages, lengths), log_path,
                             os.path.getsize(log_path), warn=said.append)
    first = note.update(now=t0, force=True)
    with open(log_path, "a") as fh:
        # the runner's line is written in two parts: the poll reads only whole lines
        fh.write(f"[{t0:%Y-%m-%d %H:%M:%S}] $ gtimeout --kill-after=60 2700 /x/bench matrix matrices/anchors.cells "
                 f"--platform android --campaign c-anchor   env: \n=== litert-lm/gpu litert-community/Qwen3-0.6B "
                 f"short-chat ({t0:%H:%M:%S})\nrun 1/3\nrun 2")
    calls = []
    real_update = note.update

    def counted(now=None, force=False):
        calls.append(1)
        return real_update(now=now, force=force)
    note.update = counted
    real_poll = dj.WATCH_POLL_S
    dj.WATCH_POLL_S = 0.2
    try:
        rc = dj.run_logged([sys.executable, "-c", "import time, sys; time.sleep(1.0); sys.exit(3)"],
                           dict(os.environ), watch=note)
    finally:
        dj.WATCH_POLL_S = real_poll
        note.update = real_update
    during = json.loads(open(hold).read())
    note.stop()
    os.remove(hold)
    after = note.update(now=t0 + datetime.timedelta(hours=1), force=True)
    at = datetime.datetime.strptime(during.get("expected_release", "2000-01-01 00:00"), hold_eta.RELEASE_FMT)
    ok(first is not None and rc == 3 and len(calls) >= 3
       and during.get("release_basis", "").startswith("anchor: 1 launch in, ~") and " ort ~" in during["release_basis"]
       and t0 + datetime.timedelta(minutes=15) <= at <= t0 + datetime.timedelta(minutes=60)
       and during["pid"] == os.getpid() and note.partial == b"run 2" and after is None
       and not os.path.exists(hold) and any(s.startswith("hold release estimate: ") for s in said),
       f"the job's poll: the command's exit code stands ({rc}), the estimate read the log {len(calls)} times while "
       f"it ran (a half-written line waits) and the hold says the anchor run is under way, ~{(at - t0).seconds // 60} "
       f"min to the release ({during.get('release_basis', '')[:60]}...); after stop() nothing is written, the "
       f"released hold is not made again")

    # the dry run says what the hold would read (the side-build case above: the extra file runs)
    real_pgrep = dj.pgrep
    dj.pgrep = lambda pattern: []
    try:
        state = os.path.join(tmp, "state")
        with open(os.path.join(state, "engines.txt"), "w") as fh:
            fh.write("/data/local/tmp/llmbench/engines/b11469-snapdragon/bin/llama-cli\n")
        cells_dir = os.path.join(tmp, "cells")
        sched = {"anchors": "matrices/anchors.cells", "cells": os.path.join(cells_dir, "set-android-h1.cells")}
        dev = {"platform": "android", "display": "Fake S", "identifier": "FakeS", "serial": "FAKE-S",
               "cpu_mask": "", "hold": os.path.join(tmp, "hold_s"), "storage_gb_full": 1, "timeout_hours": 3,
               "expected_hours": 2,
               "extra_cells": [{"cells": os.path.join(cells_dir, "side-android-s26-short.cells"), "tag": "npu"}]}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code, _, _, _ = dj.attempt(sched, "s26", dev, 1, argparse.Namespace(suffix=None, dry_run=True, cells=None))
        line = next((ln for ln in buf.getvalue().splitlines() if "the hold would read expected_release " in ln), "")
    finally:
        dj.pgrep = real_pgrep
    ok(code == dj.EXIT_OK and line.endswith("[dry-run]") and "anchor ~" in line and "set ~" in line and "npu ~" in line,
       f"a dry-run sitting logs what its hold would read, every run counted: {line.strip()[:160]}")


if __name__ == "__main__":
    sys.exit(main())
