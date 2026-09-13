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

  python3 scripts/dashboard_job_selftest.py     # exit 0 = pass
"""
import datetime
import os
import shutil
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
    # the per-device job locks live under LOG_DIR; keep the selftest's probes and
    # its held lock inside the temp dir, never under logs/dashboard-job
    dj.LOG_DIR = os.path.join(tmp, "logs")

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

    if _fails:
        print(f"\n{len(_fails)} failure(s); temp dir kept: {tmp}")
        return 1
    shutil.rmtree(tmp)
    print("\nselftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
