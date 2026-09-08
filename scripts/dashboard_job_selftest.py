#!/usr/bin/env python3
"""Device-free selftest of the dashboard job's `auto` device choice (CI).

`./bench dashboard-job auto` measures, among the devices with no admitted
dashboard session since Monday 00:00 local, the attached unheld one whose last
admitted session is oldest (docs/dashboard-recurring-job-v1.md §3). This pins
that choice against a fake `adb` (attachment) and temp hold files, with the
accumulation-layer rows and SESSION.json verdicts handed in directly — no
phone, no results/raw, no log file under logs/dashboard-job.

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
    if argv[:1] == ["shell"]:
        cmd = " ".join(argv[1:])
        if "dumpsys thermalservice" in cmd:
            print("Thermal Status: 0")
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

    if _fails:
        print(f"\n{len(_fails)} failure(s); temp dir kept: {tmp}")
        return 1
    shutil.rmtree(tmp)
    print("\nselftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
