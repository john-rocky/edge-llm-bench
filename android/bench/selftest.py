#!/usr/bin/env python3
"""Device-free end-to-end selftest of the Android lane (CI: android-driver-selftest).

Runs run_campaign.py -> run_cell.py -> parsers against a fake `adb` whose
device state lives in a temp dir, so CI and a fresh clone verify the whole
capture path — record shape, firstEver labelling via the on-device marker,
witness stamping, capture gate + quarantine + retry, the endurance
session path (streaming turn sidecar, host-derived decay/slope/degeneracy
verdicts, failed-runs-stay), the default text check of context-prompt
launches (text-check-rule), exclude-on= per device, and a phone lost under a
running engine (the launch fails, never re-run) — with no phone attached. The fake scripts
ENGINE OUTPUT, never verdicts: the gate, the text screen and the endurance
derivations judge real records.

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
import hashlib, json, os, re, shutil, sys

STATE = %(state)r
DEV = "/data/local/tmp/llmbench"
# the reply a two-iteration launch prints before each BenchmarkInfo: on task
# unless the test wrote STATE/off_task
ON_TASK = %(on_task)r
OFF_TASK = %(off_task)r


def mp(p):
    return p.replace(DEV, os.path.join(STATE, "dev"))


def engine(cmd):
    sched = os.path.join(STATE, "schedule.json")
    q = json.load(open(sched))
    d = q.pop(0) if q else 20.0
    json.dump(q, open(sched, "w"))
    # the sampler's reads, only for the fields the runner's grep asks for
    # (status order: VmHWM before VmRSS); VmHWM rises 600000 -> 640000 kB
    for hwm in (600000, 610000, 640000):
        if "VmHWM" in cmd:
            print("VmHWM:\\t  %%d kB" %% hwm)
        if "VmRSS" in cmd:
            print("VmRSS:\\t  520000 kB")
    print("===ENGINE_OUTPUT===")
    if "./llama-cli" in cmd:
        print("[ Prompt: 200.0 t/s | Generation: %%s t/s ]" %% d)
    elif "./litert_lm_advanced_main" in cmd and "--num_iterations=2" in cmd:
        ctx = re.search(r"--max_num_tokens=(\\d+)", cmd).group(1)
        print("max_tokens: " + ctx)
        reply = OFF_TASK if os.path.exists(os.path.join(STATE, "off_task")) else ON_TASK
        # the 1024 task's prompt is 1,339 tokens (fits ctx 2048 with the 256 budget)
        prompt = 1339 if "long-context-1024-gen256" in cmd else 1986
        for count, rate in ((256, d), (93, d + 0.25)):
            print("I0000 00:00:1.000000 1 litert_lm_lib.cc:868] Running single-turn conversation")
            print(reply)
            print("BenchmarkInfo:")
            print("Prefill Turn 1: Processed %%d tokens in 1s duration." %% prompt)
            print("Decode Turn 1: Processed %%d tokens" %% count)
            print("Time to first token: 1.2 s")
            print("Prefill Speed: %%d.0 tokens/sec" %% prompt)
            print("Decode Speed: %%s tokens/sec" %% rate)
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


def lost(flag):
    """The phone leaves the bus under this one command (STATE/<flag> set by the test,
    consumed here): adb ends with an error and no output, as when the Pixel 8a rebooted
    under a running engine (2026-10-07 15:58)."""
    p = os.path.join(STATE, flag)
    if not os.path.exists(p):
        return False
    os.remove(p)
    sys.stderr.write("adb: device offline\\n")
    return True


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
        if lost("drop_probe"):
            return 1
        print("Thermal Status: 0")
        return 0
    if "dumpsys battery" in cmd:
        print("  level: 100\\n  status: 2\\n  USB powered: true\\n  temperature: 316")
        return 0
    if "dumpsys power" in cmd:
        # screen state; a campaign changes it by writing STATE/wakefulness
        p = os.path.join(STATE, "wakefulness")
        print("  mWakefulness=" + (open(p).read().strip() if os.path.exists(p) else "Awake"))
        return 0
    if cmd == "settings get global stay_on_while_plugged_in":
        print("0")
        return 0
    if "===ENGINE_OUTPUT===" in cmd:
        with open(os.path.join(STATE, "engine_calls"), "a") as fh:
            fh.write("engine shell\\n")
        if lost("drop_engine"):
            return 1
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
    if cmd.startswith("rm -f "):
        import glob as _g
        for pat in cmd.split()[2:]:
            for p in _g.glob(mp(pat)):
                os.remove(p)
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

# Scripted replies of the fake two-iteration engine (context-prompt cells): the
# runner's text check (parsers.text_integrity, on by default) passes the first
# and flags the second text-off-task-screen — the engine output is scripted, the
# verdict is the real screen's.
ON_TASK = ("Running on-device AI means the phone answers without a network: replies stay "
           "local, private data never leaves the handset, and the assistant keeps working "
           "offline on a plane or in a tunnel.")
OFF_TASK = ("Please share the document you want summarised and the questions you have about "
            "it, and I will answer each of them in order with short explanations.")

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
        fh.write(FAKE_ADB % {"state": state, "on_task": ON_TASK, "off_task": OFF_TASK})
    os.chmod(adb, 0o755)

    # fake on-device engine binaries (sha deliberately unmatched in the pins
    # registry -> the witness must stamp "unknown", never a guessed tag)
    for name in ("litert_lm_main", "litert_lm_advanced_main", "litert_lm_endurance_main", "llama-cli"):
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
               COOLDOWN="0", THERMAL_WAIT="5", GATE_COOLDOWN="0",
               BENCH_TEST_LOCK_DIR=tmp)
    env.pop("ROUNDS", None)  # inherited round mode must not alter legacy fixtures
    env.pop("BENCH_ROUND_WAKEFULNESS", None)  # nor an inherited sitting-mode screen state
    env.pop("BENCH_TEXT_CHECK", None)  # the default (on for context-prompt cells) is under test

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
    # VmHWM is read on every launch, not only under BENCH_STRICT_SMOKE (unset here)
    ok(len(lit + lla) == 4 and all(
        r["metrics"].get("memoryMedianResidentMB") == 520000 / 1024
        and r["metrics"].get("memoryPeakResidentMB") == 640000 / 1024
        and r["metrics"]["memoryPeakResidentMB"] >= r["metrics"]["memoryMedianResidentMB"]
        and "VmHWM" in r["provenance"].get("rssBasis", "") for _, r in lit + lla),
       "memoryPeakResidentMB = largest VmHWM read / 1024 >= the VmRSS median, rssBasis recorded")
    ok(len(lit + lla) == 4 and all(
        r["conditions"].get("screen") == "on-usb" and r["conditions"].get("screenSource") == "measured"
        and r["conditions"].get("stayOnWhilePluggedIn") == "0" for _, r in lit + lla),
       "screen read before every launch: Awake -> on-usb, screenSource measured, Stay awake setting beside it")
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

    # --- campaign B2: the bundle was deleted from the device (storage
    # rotation between split sessions) while its marker survived; the
    # re-push must drop the marker so run 1 is labelled firstEver again
    # (Pixel 8a 2026-09-07: markers outlived 7 of their 10 bundles)
    for f in glob.glob(os.path.join(dev, "models", "*fake_model.litertlm*")):
        os.remove(f)
    schedule([25.2, 24.9])
    env["CAMPAIGN"] = "selftest-b2"
    print("--- campaign B2 (bundle deleted on device, marker stale -> re-push relabels firstEver)")
    rc = run_campaign(env, cells_b)
    ok(rc == 0, f"campaign B2 exits 0 (got {rc})")
    out_b2 = os.path.join(raw_root, "selftest-b2", "app-path-android")
    again = records(out_b2, "litert-lm-gpu_")
    ok(len(again) == 2, f"2 records after the re-push (got {len(again)})")
    if len(again) == 2:
        ok(again[0][1]["metrics"].get("firstEver") is True,
           "run 1 after a re-push is labelled firstEver (cache rebuilt, marker invalidated)")
        ok("firstEver" not in again[1][1]["metrics"], "run 2 after the re-push not labelled")

    # --- campaign B3: a collapse the slowest/median test cannot see, then a
    # uniformly slow retry (Pixel 8a 2026-09-08/09: 4.9 then 1.6 / 1.4 in one
    # capture; the block re-run 1.3 / 0.9 / 1.3 after 5.2 / 5.3 / 2.5) ------
    cells_b3 = os.path.join(tmp, "b3.cells")
    with open(cells_b3, "w") as fh:
        fh.write(f"android litert-lm fake/model short-chat runs=3 "
                 f"backend=gpu file={litert_model}\n")
    # rounds: one fast run beside two slow (median 5.0 under half of 25.0 ->
    # COLLAPSE 20); the block retry is uniformly slow (5.1 / 5.0 / 5.2 -> every
    # within-capture test passes, LEVEL 20 of the quarantined 25.0)
    schedule([25.0, 5.0, 5.0, 5.1, 5.0, 5.2])
    env["CAMPAIGN"] = "selftest-b3"
    print("--- campaign B3 (median collapsed beside one fast run -> COLLAPSE; uniformly slow retry -> LEVEL, kept + flagged)")
    rc = run_campaign(env, cells_b3)
    ok(rc == 0, f"campaign B3 exits 0 (got {rc})")
    out_b3 = os.path.join(raw_root, "selftest-b3", "app-path-android")
    kept3 = records(out_b3, "litert-lm-gpu_")
    quarantined3 = glob.glob(os.path.join(out_b3, "*.json.attempt1"))
    ok(len(kept3) == 3, f"retry triple stands as the capture (got {len(kept3)})")
    ok(len(quarantined3) == 3, f"flagged triple quarantined as .attempt1 (got {len(quarantined3)})")
    if len(kept3) == 3:
        ok([r["metrics"]["decodeTokensPerSecond"] for _, r in kept3] == [5.1, 5.0, 5.2],
           "kept records are the retry, not the flagged triple")
    flagged3 = os.path.join(out_b3, "FLAGGED.txt")
    txt3 = open(flagged3).read() if os.path.exists(flagged3) else ""
    ok("first='COLLAPSE 20'" in txt3,
       f"first capture judged COLLAPSE 20 (median 5.0 under half the fastest 25.0): {txt3.strip()!r}")
    ok("retry='LEVEL 20'" in txt3,
       "retry judged LEVEL 20 (median 5.1 of the quarantined un-collapsed 25.0), kept with the flag")

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
    with open(os.path.join(state, "wakefulness"), "w") as fh:
        fh.write("Dozing")  # screen off: recorded, not refused
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
        ok(r["conditions"].get("screen") == "off-usb (mWakefulness=Dozing)"
           and r["conditions"].get("screenSource") == "measured",
           f"endurance: a dozing phone is stamped off-usb (got {r['conditions'].get('screen')!r})")
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

    # --- opt-in long-context round mode, same real driver / fake transport ---
    cells_round = os.path.join(tmp, "round.cells")
    with open(cells_round, "w") as fh:
        fh.write(f"android llama.cpp fake/gguf short-chat anchor=1 file={gguf_model}\n")
        for ctx in (2304, 4096, 8192):
            fh.write(f"android litert-lm fake/model long-context-2048-gen256 backend=gpu "
                     f"context-tokens={ctx} file={litert_model}\n")
    # Wide spread would trigger a legacy retry; round mode must keep the
    # original rounds intact and leave admission to the session reviewer.
    schedule([100.0, 25.0, 25.0, 25.0, 5.0, 5.0, 5.0, 100.0])
    # sitting mode sets BENCH_ROUND_WAKEFULNESS from its per-round dumpsys read
    # (it also pins the engine sha, which the fake binaries cannot match); the
    # fake phone reads Awake again, so the env value must be the one stamped
    os.remove(os.path.join(state, "wakefulness"))
    env.update(CAMPAIGN="selftest-round", ROUNDS="2", BENCH_ROUND_WAKEFULNESS="Dozing")
    print("--- round campaign (2 iterations, reversal, anchor, gate off)")
    rc = run_campaign(env, cells_round)
    ok(rc == 0, f"round campaign exits 0 (got {rc})")
    out_round = os.path.join(raw_root, "selftest-round", "app-path-android")
    pairs = records(out_round, "litert-lm-gpu_")
    controls = records(out_round, "llama.cpp_")
    ok(len(pairs) == 12 and len(controls) == 2, "12 iteration records and 2 cold-process anchors")
    ok(all(r["conditions"]["regime"] == "cold-process" for _, r in controls), "anchor regime stays cold-process")
    grouped = {}
    for _, r in pairs:
        grouped.setdefault(r["conditions"]["launchID"], []).append(r)
    ok(len(grouped) == 6, "6 engine launches produced 12 records")
    for rows in grouped.values():
        rows.sort(key=lambda r: r["conditions"]["iterationIndex"])
        ok([r["metrics"]["generatedTokenCount"] for r in rows] == [256, 93], "per-iteration counts remain separate")
        ok([r["conditions"]["regime"] for r in rows] == ["cold", "warm"], "cold/warm labels per launch")
        ok(all(r["conditions"]["batteryTemperatureInitialC"] == 31.6 for r in rows), "battery temperature is Celsius")
        ok(all(r["metrics"].get("memoryPeakResidentMB") == 640000 / 1024 for r in rows),
           "both iteration records carry the launch's VmHWM peak")
    with open(os.path.join(out_round, "launch_order.jsonl")) as fh:
        order = [json.loads(line) for line in fh]
    ok([d["cell"] for d in order[4:]] == [d["cell"] for d in order[:4]][::-1], "full order reversed, including anchor")
    ok(not glob.glob(os.path.join(out_round, "*.json.attempt1")), "round mode never block-retries wide spread")
    ok(len(pairs + controls) == 14 and all(
        r["conditions"].get("screen") == "Dozing" and r["conditions"].get("screenSource") == "env"
        for _, r in pairs + controls),
       "sitting-mode BENCH_ROUND_WAKEFULNESS wins over the per-launch read (screenSource env)")
    # text check on by default for context-prompt cells (no BENCH_TEXT_CHECK in env)
    ok(len(pairs) == 12 and all(
        r["conditions"].get("textCheck", {}).get("status") == "PASS"
        and open(os.path.join(out_round, r["provenance"]["decodedText"])).read() == ON_TASK
        for _, r in pairs),
       "context-prompt records carry textCheck PASS and their decoded text by default")
    ok(len(controls) == 2 and not any("textCheck" in r["conditions"] for _, r in controls),
       "a llama.cpp launch is not text-checked (no context-prompt path)")
    env.pop("ROUNDS")
    env.pop("BENCH_ROUND_WAKEFULNESS")

    # --- campaign E: the weekly job's shape for a 1024 cell (context-tokens=,
    # no ROUNDS, no BENCH_TEXT_CHECK) with off-task replies: text-check-rule —
    # records, texts and log stay (failed-runs-stay), flagged FAIL; the launch is
    # listed in FAILURES.txt; the gate never re-runs it (a re-run reproduces it)
    cells_e = os.path.join(tmp, "e.cells")
    with open(cells_e, "w") as fh:
        fh.write(f"android litert-lm fake/model long-context-1024-gen256 runs=2 backend=gpu "
                 f"context-tokens=2048 file={litert_model}\n")
    open(os.path.join(state, "off_task"), "w").close()
    schedule([25.0, 25.5])
    env["CAMPAIGN"] = "selftest-e"
    print("--- campaign E (weekly-path 1024 cell, off-task text -> textCheck FAIL, kept, not retried)")
    rc = run_campaign(env, cells_e)
    os.remove(os.path.join(state, "off_task"))
    ok(rc == 0, f"campaign E exits 0 (got {rc})")
    out_e = os.path.join(raw_root, "selftest-e", "app-path-android")
    erecs_e = records(out_e, "litert-lm-gpu_fake_model_long-context-1024-gen256")
    ok(len(erecs_e) == 4, f"2 launches x 2 iteration records kept (got {len(erecs_e)})")
    ok(len(erecs_e) == 4 and all(
        r["conditions"].get("textCheck", {}).get("status") == "FAIL"
        and r["conditions"]["textCheck"]["flags"] == ["text-off-task-screen"]
        and r["conditions"].get("protocolFlags") == ["text-off-task-screen"]
        and r["metrics"].get("decodeTokensPerSecond")
        and open(os.path.join(out_e, r["provenance"]["decodedText"])).read() == OFF_TASK
        for _, r in erecs_e),
       "off-task replies: textCheck FAIL text-off-task-screen (the only flag), rate and text kept")
    fails_e = os.path.join(out_e, "FAILURES.txt")
    ok(os.path.exists(fails_e) and open(fails_e).read().count("long-context-1024-gen256") == 2,
       "both text-failed launches listed in FAILURES.txt")
    ok(not glob.glob(os.path.join(out_e, "*.json.attempt1")),
       "a text-failed capture is never quarantine-retried")

    # --- campaign X: exclude-on=<schedule key>:<reason> skips a row on the device
    # that key names and runs it on every other one (the Pixel 8a's 4B-class rows,
    # 2026-10-07). The serials are the registry's own (ops/dashboard-v1/schedule.json);
    # the fake adb answers whatever serial is set, and the lock goes to the temp dir
    # (BENCH_LOCK_DIR), never to the real /tmp lock of a phone in use.
    registry = json.load(open(os.path.join(ROOT, "ops", "dashboard-v1", "schedule.json")))["devices"]
    cells_x = os.path.join(tmp, "x.cells")
    with open(cells_x, "w") as fh:
        fh.write(f"android llama.cpp fake/gguf short-chat runs=1 file={gguf_model}\n"
                 f"android litert-lm fake/model short-chat runs=1 backend=gpu file={litert_model} "
                 "exclude-on=pixel8a:selftest-does-not-fit\n")
    for key, skips in (("pixel8a", True), ("s26", False)):
        env_x = dict(env, BENCH_ANDROID_SERIAL=registry[key]["serial"], BENCH_LOCK_DIR=tmp,
                     CAMPAIGN=f"selftest-x-{key}")
        env_x.pop("BENCH_TEST_LOCK_DIR")
        schedule([21.0, 22.0])
        print(f"--- campaign X on the {key} serial (exclude-on=pixel8a: "
              f"{'skipped here' if skips else 'runs here'})")
        rc = run_campaign(env_x, cells_x)
        ok(rc == 0, f"campaign X ({key}) exits 0 (got {rc})")
        out_x = os.path.join(raw_root, f"selftest-x-{key}", "app-path-android")
        skip_txt = os.path.join(out_x, "SKIPPED.txt")
        skip_txt = open(skip_txt).read() if os.path.exists(skip_txt) else ""
        lit_x, lla_x = records(out_x, "litert-lm-gpu_"), records(out_x, "llama.cpp_")
        ok(len(lla_x) == 1, f"{key}: the row without exclude-on runs (got {len(lla_x)} records)")
        if skips:
            ok(not lit_x and skip_txt.strip() == "CELL_SKIP litert-lm-gpu fake/model short-chat "
                                                   "exclude-on=pixel8a reason=selftest-does-not-fit",
               f"{key}: the exclude-on row is skipped, SKIPPED.txt names its key and reason: {skip_txt.strip()!r}")
        else:
            ok(len(lit_x) == 1 and not skip_txt,
               f"{key}: the exclude-on row runs on a device it does not name "
               f"(got {len(lit_x)} records, SKIPPED.txt {skip_txt.strip()!r})")

    # --- campaign F: the phone drops off the bus under a running engine. The engine
    # shell is never re-run (2026-10-07: a reboot mid-launch had the shell replayed on
    # the rebooted Pixel 8a, and the replay's record read as one run): that launch fails
    # with no record and is listed in FAILURES.txt, the next launch runs. A probe that
    # loses the phone is still retried, with one line in the campaign log.
    cells_f = os.path.join(tmp, "f.cells")
    with open(cells_f, "w") as fh:
        fh.write(f"android llama.cpp fake/gguf short-chat runs=2 file={gguf_model}\n")
    calls = os.path.join(state, "engine_calls")
    if os.path.exists(calls):
        os.remove(calls)
    for flag in ("drop_probe", "drop_engine"):
        open(os.path.join(state, flag), "w").close()
    schedule([20.0, 20.5])
    env["CAMPAIGN"] = "selftest-f"
    print("--- campaign F (device lost under the first engine shell and the first probe)")
    p = subprocess.run([sys.executable, os.path.join(ROOT, "android", "bench", "run_campaign.py"), cells_f],
                       env=env, capture_output=True, text=True)
    print(p.stdout + p.stderr)
    out_f = os.path.join(raw_root, "selftest-f", "app-path-android")
    lla_f = records(out_f, "llama.cpp_")
    n_calls = len(open(calls).read().splitlines()) if os.path.exists(calls) else 0
    fails_f = os.path.join(out_f, "FAILURES.txt")
    fails_f = open(fails_f).read() if os.path.exists(fails_f) else ""
    retried = [ln for ln in (p.stdout + p.stderr).splitlines() if ln.startswith("adb retry after device loss: ")]
    ok(p.returncode == 0, f"campaign F exits 0 (got {p.returncode})")
    ok(n_calls == 2 and len(lla_f) == 1 and lla_f[0][1]["metrics"]["decodeTokensPerSecond"] == 20.0,
       f"the lost engine shell is not re-run: 2 engine shells for 2 launches (got {n_calls}), "
       f"1 record, the second launch's (got {[r['metrics'].get('decodeTokensPerSecond') for _, r in lla_f]})")
    ok(fails_f.strip() == "llama.cpp fake/gguf short-chat rc=1",
       f"the lost launch is listed in FAILURES.txt: {fails_f.strip()!r}")
    ok(len(retried) == 1 and "dumpsys thermalservice" in retried[0] and "ENGINE_OUTPUT" not in retried[0],
       f"the lost probe is retried, one log line naming it, none for the engine shell: {retried}")
    for flag in ("drop_probe", "drop_engine"):
        if os.path.exists(os.path.join(state, flag)):
            os.remove(os.path.join(state, flag))

    rc = subprocess.call([sys.executable, os.path.join(ROOT, "android", "bench", "test_longctx.py")])
    ok(rc == 0, "long-context device-free unit checks")
    if _fails:
        print(f"\n{len(_fails)} failure(s); temp dir kept: {tmp}")
        return 1
    shutil.rmtree(tmp)
    print("\nselftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
