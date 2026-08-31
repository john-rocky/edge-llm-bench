#!/usr/bin/env python3
"""Device-free end-to-end selftest of the Android lane (CI: android-driver-selftest).

Runs run_campaign.py -> run_cell.py -> parsers against a fake `adb` whose
device state lives in a temp dir, so CI and a fresh clone verify the whole
capture path — record shape, firstEver labelling via the on-device marker,
witness stamping, capture gate + quarantine + retry — with no phone attached.
The fake scripts ENGINE OUTPUT, never verdicts: the gate judges real records.

  python3 android/bench/selftest.py     # exit 0 = pass; temp dirs kept on failure

Captures go under the selftest's own temp dir (BENCH_RAW_ROOT), never into
results/raw — build_summary globs that tree unconditionally, so a leaked fake
row would pool into the real accumulation layer.
"""
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FAKE_ADB = '''#!/usr/bin/env python3
import hashlib, json, os, shutil, sys

STATE = %(state)r
DEV = "/data/local/tmp/llmbench"


def mp(p):
    return p.replace(DEV, os.path.join(STATE, "dev"))


def engine(cmd):
    sched = os.path.join(STATE, "schedule.json")
    q = json.load(open(sched))
    d = q.pop(0) if q else 20.0
    json.dump(q, open(sched, "w"))
    for _ in range(3):
        print("VmRSS:\\t  520000 kB")
    print("===ENGINE_OUTPUT===")
    if "./llama-cli" in cmd:
        print("[ Prompt: 200.0 t/s | Generation: %%s t/s ]" %% d)
    else:
        print("Prefill Turn 1: Processed 21 tokens in 100.00ms duration.")
        print("Decode Turn 1: Processed 128 tokens")
        print("Time to first token: 0.42 s")
        print("Prefill Speed: 210.0 tokens/sec")
        print("Decode Speed: %%s tokens/sec" %% d)
    print("EXIT_CODE=0")
    return 0


def shell(cmd):
    if cmd.startswith("getprop"):
        print({"ro.product.model": "FakePhone",
               "ro.build.version.release": "16",
               "ro.build.version.security_patch": "2026-08-05",
               "ro.soc.model": "FakeSoC",
               "ro.product.device": "fake"}.get(cmd.split()[1], ""))
        return 0
    if "dumpsys thermalservice" in cmd:
        print("Thermal Status: 0")
        return 0
    if "dumpsys battery" in cmd:
        print("  level: 100\\n  status: 2\\n  USB powered: true")
        return 0
    if "===ENGINE_OUTPUT===" in cmd:
        return engine(cmd)
    if cmd.startswith("sha256sum"):
        p = mp(cmd.split()[1])
        if not os.path.exists(p):
            print("sha256sum: " + p + ": No such file or directory")
            return 1
        print(hashlib.sha256(open(p, "rb").read()).hexdigest() + "  " + p)
        return 0
    if cmd.startswith("stat -c %%s"):
        p = mp(cmd.split()[-1])
        if not os.path.exists(p):
            print("stat: " + p + ": No such file or directory")
            return 1
        print(os.path.getsize(p))
        return 0
    if cmd.startswith("ls ") and "echo present" in cmd:
        print("present" if os.path.exists(mp(cmd.split()[1])) else "absent")
        return 0
    if cmd.startswith("mkdir -p") and "touch" in cmd:
        mk, touch = cmd.split("&&")
        os.makedirs(mp(mk.split()[-1]), exist_ok=True)
        open(mp(touch.split()[-1]), "w").close()
        return 0
    if cmd.startswith("mkdir"):
        os.makedirs(mp(cmd.split()[-1]), exist_ok=True)
        return 0
    sys.stderr.write("fake-adb: unhandled shell: " + cmd + "\\n")
    return 1


def main(argv):
    if argv and argv[0] == "-s":
        argv = argv[2:]
    if not argv:
        return 0
    if argv[0] == "wait-for-device":
        return 0
    if argv[0] == "get-serialno":
        print("FAKESELF")
        return 0
    if argv[0] == "push":
        dst = mp(argv[2])
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(argv[1], dst)
        print("1 file pushed")
        return 0
    if argv[0] == "shell":
        return shell(" ".join(argv[1:]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
'''

_fails = []


def ok(cond, msg):
    print(("  ok  " if cond else "  FAIL ") + msg)
    if not cond:
        _fails.append(msg)


def run_campaign(env, cells_path):
    return subprocess.call(
        [sys.executable, os.path.join(ROOT, "android", "bench", "run_campaign.py"),
         cells_path], env=env)


def records(out_dir, prefix):
    files = sorted(f for f in glob.glob(os.path.join(out_dir, prefix + "*.json")))
    return [(f, json.load(open(f))) for f in files]


def main():
    tmp = tempfile.mkdtemp(prefix="android-lane-selftest-")
    state = os.path.join(tmp, "state")
    dev = os.path.join(state, "dev")
    bin_dir = os.path.join(tmp, "bin")
    raw_root = os.path.join(tmp, "raw")
    for d in (dev, bin_dir, raw_root):
        os.makedirs(d)

    adb = os.path.join(bin_dir, "adb")
    with open(adb, "w") as fh:
        fh.write(FAKE_ADB % {"state": state})
    os.chmod(adb, 0o755)

    # fake on-device engine binaries (sha deliberately unmatched in the pins
    # registry -> the witness must stamp "unknown", never a guessed tag)
    for name in ("litert_lm_main", "llama-cli"):
        with open(os.path.join(dev, name), "w") as fh:
            fh.write("fake " + name)

    litert_model = os.path.join(tmp, "fake_model.litertlm")
    gguf_model = os.path.join(tmp, "fake.gguf")
    for p in (litert_model, gguf_model):
        with open(p, "w") as fh:
            fh.write("weights of " + os.path.basename(p))

    env = dict(os.environ,
               PATH=bin_dir + os.pathsep + os.environ.get("PATH", ""),
               BENCH_ANDROID_SERIAL="FAKESELF", BENCH_RAW_ROOT=raw_root,
               COOLDOWN="0", THERMAL_WAIT="5", GATE_COOLDOWN="0")

    def schedule(vals):
        json.dump(vals, open(os.path.join(state, "schedule.json"), "w"))

    # --- campaign A: anchor (litert, 2 runs) + payload (llama, 2 rounds) ----
    cells_a = os.path.join(tmp, "a.cells")
    with open(cells_a, "w") as fh:
        fh.write(f"android litert-lm fake/model short-chat anchor=1 runs=2 "
                 f"backend=gpu file={litert_model}\n"
                 f"android llama.cpp fake/gguf short-chat runs=2 file={gguf_model}\n")
    schedule([25.0, 24.5, 20.6, 20.1])
    env["CAMPAIGN"] = "selftest-a"
    print("--- campaign A (clean capture, firstEver detection)")
    rc = run_campaign(env, cells_a)
    ok(rc == 0, f"campaign A exits 0 (got {rc})")

    out_a = os.path.join(raw_root, "selftest-a", "app-path-android")
    lit = records(out_a, "litert-lm-gpu_")
    lla = records(out_a, "llama.cpp_")
    ok(len(lit) == 2, f"2 litert records (got {len(lit)})")
    ok(len(lla) == 2, f"2 llama records (got {len(lla)})")
    if len(lit) == 2:
        r1, r2 = lit[0][1], lit[1][1]
        ok(r1["metrics"].get("firstEver") is True, "litert run 1 labelled firstEver")
        ok("firstEver" not in r2["metrics"], "litert run 2 not labelled")
        ok(r1["runtime"] == "litert-lm-gpu", "backend is part of arm identity")
        ok(str(r1["engineVersion"]).startswith("unknown"),
           "unmatched binary sha stamps 'unknown', never a guessed tag")
        want = hashlib.sha256(open(litert_model, "rb").read()).hexdigest()
        ok(r1["model"]["sha256"] == want, "model sha256 is the pushed artifact's")
        ok(r1["metrics"]["decodeTokensPerSecond"] == 25.0, "decode parsed from engine output")
        ok(os.path.exists(os.path.join(out_a, r1["provenance"]["rawLog"])),
           "raw console log stored next to the record (stored-report-rule)")
    if len(lla) == 2:
        ok(all("firstEver" not in r["metrics"] for _, r in lla),
           "llama.cpp never labelled firstEver (no persistent compile cache)")
        ok(lla[0][1]["metrics"]["decodeTokensPerSecond"] == 20.6, "llama bracket summary parsed")
    marker = glob.glob(os.path.join(dev, "markers", "*.gpu.cachebuilt"))
    ok(len(marker) == 1, "on-device cache marker written after first clean run")
    ok(not os.path.exists(os.path.join(out_a, "FLAGGED.txt")), "clean capture not flagged")

    # --- campaign B: same model again (marker persists) + collapsed round ---
    cells_b = os.path.join(tmp, "b.cells")
    with open(cells_b, "w") as fh:
        fh.write(f"android litert-lm fake/model short-chat runs=2 "
                 f"backend=gpu file={litert_model}\n")
    # rounds 1-2 produce a contended-device signature (5.0 beside 25.0 ->
    # COLLAPSE); the block retry produces a clean pair
    schedule([25.0, 5.0, 24.0, 24.8])
    env["CAMPAIGN"] = "selftest-b"
    print("--- campaign B (COLLAPSE -> quarantine -> retry once)")
    rc = run_campaign(env, cells_b)
    ok(rc == 0, f"campaign B exits 0 (got {rc})")

    out_b = os.path.join(raw_root, "selftest-b", "app-path-android")
    kept = records(out_b, "litert-lm-gpu_")
    quarantined = glob.glob(os.path.join(out_b, "*.json.attempt1"))
    ok(len(kept) == 2, f"retry pair stands as the capture (got {len(kept)})")
    ok(len(quarantined) == 2, f"flagged pair quarantined as .attempt1 (got {len(quarantined)})")
    if len(kept) == 2:
        ok([r["metrics"]["decodeTokensPerSecond"] for _, r in kept] == [24.0, 24.8],
           "kept records are the retry, not the flagged pair")
        ok(all("firstEver" not in r["metrics"] for _, r in kept),
           "marker survives across invocations — no re-label on a warm cache")
    prov = os.path.join(out_b, "session_provenance.txt")
    ok(os.path.exists(prov) and "gate retry" in open(prov).read(),
       "block re-run disclosed in session_provenance.txt")
    ok(not os.path.exists(os.path.join(out_b, "FLAGGED.txt")),
       "clean retry leaves no FLAGGED.txt")

    if _fails:
        print(f"\n{len(_fails)} failure(s); temp dir kept: {tmp}")
        return 1
    shutil.rmtree(tmp)
    print("\nselftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
