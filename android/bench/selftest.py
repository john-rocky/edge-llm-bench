#!/usr/bin/env python3
"""Device-free end-to-end selftest of the Android lane (CI: android-driver-selftest).

Runs run_campaign.py -> run_cell.py -> parsers against a fake `adb` whose
device state lives in a temp dir, so CI and a fresh clone verify the whole
capture path — record shape, firstEver labelling via the on-device marker,
witness stamping, capture gate + quarantine + retry, and the endurance
session path (streaming turn sidecar, host-derived decay/slope/degeneracy
verdicts, failed-runs-stay) — with no phone attached. The fake scripts
ENGINE OUTPUT, never verdicts: the gate and the endurance derivations judge
real records.

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


def endurance(cmd):
    # Scripted DRIVER OUTPUT (never verdicts): the host harness derives
    # decay/slope/degeneracy from these lines exactly as from a real driver.
    spec = json.load(open(os.path.join(STATE, "endurance_script.json")))
    print("ENDURANCE_LOAD " + json.dumps(spec.get("load", {"loadSeconds": 1.5})))
    for t in spec["turns"]:
        print("ENDURANCE_TURN " + json.dumps(t))
    if spec.get("session") is not None:
        print("ENDURANCE_SESSION " + json.dumps(spec["session"]))
    return spec.get("exit", 0)


def shell(cmd):
    # "./" = actually running the driver; a bare mention (sha256sum for the
    # witness stamp) must fall through to the real handlers
    if "./litert_lm_endurance_main" in cmd:
        return endurance(cmd)
    if cmd.startswith("tail "):
        p = mp(cmd.split()[-1])
        if os.path.exists(p):
            sys.stdout.write(open(p).read()[-8192:])
        return 0
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
    if argv[0] == "exec-out":  # streaming path (endurance driver)
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
    for name in ("litert_lm_main", "litert_lm_endurance_main", "llama-cli"):
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

    # --- campaign C: endurance session, completed --------------------------
    # Scripted driver output; the HOST derives the verdicts (decay windows,
    # resident slope, degeneracy counts, medians) — this pins that math and
    # the streaming sidecar path with no phone and no 30-minute wait.
    def turn(i, t, rate, rollover=False, degenerate=False):
        d = {"turn": i, "promptIndex": (i - 1) % 12, "startedAtSeconds": t,
             "rollover": rollover, "ttftMS": 500.0, "wallSeconds": 5.0,
             "chunkCount": 200, "prefillTokens": 30,
             "prefillTokensPerSecond": 60.0, "decodeTokens": 256,
             "decodeTokensPerSecond": rate,
             "decodeTokensPerSecondWallClock": rate * 0.9,
             "kvTokensAfterTurn": 100 * i, "residentAfterTurnMB": 1000.0 + i,
             "stopReason": "length", "degenerate": degenerate,
             "outputHead": "fake output"}
        if rollover:
            d["rolloverReason"] = "budget"
        return d

    spec_c = {
        "load": {"loadSeconds": 1.5},
        # first 300 s window: 20 tok/s; last window: 10 tok/s -> decay 50%;
        # resident 1001..1006 over turns 1..6 -> slope exactly 1.0 MB/turn
        "turns": [turn(1, 0, 20.0), turn(2, 10, 20.0), turn(3, 20, 20.0),
                  turn(4, 650, 10.0, rollover=True),
                  turn(5, 660, 10.0, degenerate=True), turn(6, 700, 10.0)],
        "session": {"status": "completed", "turnsCompleted": 6,
                    "elapsedSeconds": 705.0, "loadSeconds": 1.5,
                    "plannedMinutes": 30, "contextTokens": 1024,
                    "turnCap": 256, "residentFinalMB": 1006.0,
                    "residentPeakMB": 1010.0},
        "exit": 0,
    }
    json.dump(spec_c, open(os.path.join(state, "endurance_script.json"), "w"))
    cells_c = os.path.join(tmp, "c.cells")
    with open(cells_c, "w") as fh:
        fh.write(f"android litert-lm fake/model endurance-chat-30m runs=1 "
                 f"backend=gpu context-tokens=1024 file={litert_model}\n")
    env["CAMPAIGN"] = "selftest-c"
    print("--- campaign C (endurance session: sidecar + derived verdicts)")
    rc = run_campaign(env, cells_c)
    ok(rc == 0, f"campaign C exits 0 (got {rc})")

    out_c = os.path.join(raw_root, "selftest-c", "app-path-android")
    erecs = records(out_c, "litert-lm-gpu_fake_model_endurance-chat-30m")
    ok(len(erecs) == 1, f"1 endurance record (got {len(erecs)})")
    if erecs:
        _, r = erecs[0]
        e = r.get("endurance", {})
        ok(e.get("status") == "completed", "endurance.status completed")
        ok(e.get("decodeDecayPercent") == 50.0,
           f"decay derived from window medians (got {e.get('decodeDecayPercent')})")
        ok(abs(e.get("memorySlopeMBPerTurn", 0) - 1.0) < 1e-9,
           f"resident slope 1.0 MB/turn (got {e.get('memorySlopeMBPerTurn')})")
        ok(e.get("memorySlopeBasis") == "resident-vmrss",
           "slope basis disclosed as resident (no fabricated phys_footprint)")
        ok(e.get("conversationRollovers") == 1, "rollover counted")
        ok(e.get("degenerateTurnCount") == 1 and e.get("firstDegenerateTurn") == 5,
           "degeneracy flags lifted from the turn series")
        ok(r["metrics"]["decodeTokensPerSecond"] == 15.0,
           "session decode = median of per-turn engine rates")
        ok(r["metrics"].get("memoryMedianResidentMB") == 1003.5,
           "memoryMedianResidentMB = median of per-turn VmRSS")
        ok("firstEver" not in r["metrics"],
           "marker from campaign A covers endurance too (shared engine cache)")
        ok(str(r["engineVersion"]).startswith("unknown"),
           "endurance binary witness: unmatched sha stamps 'unknown'")
        ok(r["conditions"]["sampler"].startswith("topK40/topP0.9/temp0.7"),
           "driver-set protocol sampler recorded")
        sidecar = os.path.join(out_c, e.get("turnsSidecar", ""))
        ok(os.path.exists(sidecar), "turns sidecar stored beside the record")
        if os.path.exists(sidecar):
            lines = [json.loads(ln) for ln in open(sidecar) if ln.strip()]
            ok(len(lines) == 6, f"sidecar has all 6 turns (got {len(lines)})")
            ok(all(t.get("thermalState") == "nominal" for t in lines),
               "host stamps thermal state onto every turn line")
        ok(os.path.exists(os.path.join(out_c, r["provenance"]["rawLog"])),
           "endurance raw console log stored (stored-report-rule)")
    ok(not os.path.exists(os.path.join(out_c, "FLAGGED.txt")),
       "clean endurance capture not flagged")

    # --- campaign D: endurance crash mid-session (failed-runs-stay) --------
    spec_d = {
        "turns": [turn(1, 0, 22.0), turn(2, 10, 21.0)],
        "session": {"status": "crash", "turnsCompleted": 2,
                    "elapsedSeconds": 15.0, "loadSeconds": 1.5,
                    "plannedMinutes": 30, "contextTokens": 1024,
                    "turnCap": 256,
                    "failureDetail": "INTERNAL: The new rendered template "
                                     "string does not start with the previous"},
        "exit": 1,
    }
    json.dump(spec_d, open(os.path.join(state, "endurance_script.json"), "w"))
    env["CAMPAIGN"] = "selftest-d"
    print("--- campaign D (endurance crash keeps record + partial series)")
    rc = run_campaign(env, cells_c)
    ok(rc == 0, f"campaign D exits 0 (got {rc})")
    out_d = os.path.join(raw_root, "selftest-d", "app-path-android")
    drecs = records(out_d, "litert-lm-gpu_fake_model_endurance-chat-30m")
    ok(len(drecs) == 1, f"crash session still writes its record (got {len(drecs)})")
    if drecs:
        _, r = drecs[0]
        ok(r["endurance"].get("status") == "crash"
           and "rendered template" in r["endurance"].get("failureDetail", ""),
           "crash status + failure detail on the record")
        sidecar = os.path.join(out_d, r["endurance"].get("turnsSidecar", ""))
        partial = ([json.loads(ln) for ln in open(sidecar) if ln.strip()]
                   if os.path.exists(sidecar) else [])
        ok(len(partial) == 2, f"partial series kept: 2 turns on disk (got {len(partial)})")
    fails_txt = os.path.join(out_d, "FAILURES.txt")
    ok(os.path.exists(fails_txt) and "endurance-chat-30m" in open(fails_txt).read(),
       "failed session logged to FAILURES.txt")
    ok(not glob.glob(os.path.join(out_d, "*.json.attempt1")),
       "a crash session is never quarantine-retried (failed-runs-stay)")

    if _fails:
        print(f"\n{len(_fails)} failure(s); temp dir kept: {tmp}")
        return 1
    shutil.rmtree(tmp)
    print("\nselftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
