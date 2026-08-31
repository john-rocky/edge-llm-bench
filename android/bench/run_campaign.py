#!/usr/bin/env python3
"""Android campaign runner — consumes the unified cells grammar
(matrices/README.md) filtered to platform=android and drives run_cell.py.

  CAMPAIGN=<name> python3 android/bench/run_campaign.py matrices/release-regression-litert.cells

Order and discipline (fairness rules as code):
  - anchor=1 cells run FIRST (session-anchor normalization).
  - payload cells run INTERLEAVED PER ROUND across arms (interleave-arms):
    round 1 of every cell, then round 2 of every cell — never one arm's block.
  - >=COOLDOWN s between runs; the thermal gate waits for status 0 (nominal)
    up to THERMAL_WAIT s and records the state either way.
  - exclude=/manual= cells are skipped with the reason logged (SKIPPED.txt).
  - capture gate (scripts/cell_gate.py; mac/iPhone parity): a flagged cell is
    quarantined in raw (*.json.attempt1, outside build_summary's glob) and
    re-runs ONCE as a block after GATE_COOLDOWN s; a flagged retry stands
    with a FLAGGED.txt note. SHORT never retries (failed-runs-stay).
    GATE_RETRY=0 disables. The cold-only regime trips COLLAPSE (50% bar),
    not SPREAD — Android cold trials legitimately spread 15-30%.
"""
import fcntl
import glob
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from device_probe import thermal_status  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COOLDOWN = int(os.environ.get("COOLDOWN", "120"))
THERMAL_WAIT = int(os.environ.get("THERMAL_WAIT", "600"))
GATE_COOLDOWN = int(os.environ.get("GATE_COOLDOWN", "180"))
GATE_RETRY = os.environ.get("GATE_RETRY", "1") == "1"
SERIAL = os.environ.get("BENCH_ANDROID_SERIAL")


def parse_cells(path):
    anchors, payload, skipped = [], [], []
    for lineno, raw in enumerate(open(path), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if parts[0] != "android" or len(parts) < 4:
            continue
        cell = {"runtime": parts[1], "model_id": parts[2], "task": parts[3], "opts": {}}
        for kv in parts[4:]:
            k, _, v = kv.partition("=")
            cell["opts"][k] = v
        reason = cell["opts"].get("exclude") or ("manual" if cell["opts"].get("manual") else None)
        if reason:
            skipped.append((cell, reason))
        elif cell["opts"].get("anchor"):
            anchors.append(cell)
        else:
            payload.append(cell)
    return anchors, payload, skipped


def wait_nominal(out_dir):
    t0 = time.time()
    while time.time() - t0 < THERMAL_WAIT:
        raw, name = thermal_status(SERIAL)
        if raw == 0:
            return name
        print(f"thermal gate: status={name} — waiting…")
        time.sleep(30)
    with open(os.path.join(out_dir, "THERMAL_GATE.txt"), "a") as fh:
        fh.write(f"gate timeout after {THERMAL_WAIT}s at {time.strftime('%F %T')}; ran anyway\n")
    return name


def run_cell_once(cell, out_dir, runs):
    cmd = [sys.executable, os.path.join(ROOT, "android", "bench", "run_cell.py"),
           "--runtime", cell["runtime"], "--model-id", cell["model_id"],
           "--task", cell["task"], "--runs", str(runs), "--out", out_dir]
    if runs > 1:  # the >=COOLDOWN discipline holds INSIDE a multi-run cell too
        cmd += ["--cooldown", str(COOLDOWN)]
    if cell["opts"].get("backend"):
        cmd += ["--backend", cell["opts"]["backend"]]
    if cell["opts"].get("file"):
        cmd += ["--file", cell["opts"]["file"]]
    if cell["opts"].get("max-tokens"):
        cmd += ["--max-tokens", cell["opts"]["max-tokens"]]
    if cell["opts"].get("context-tokens"):
        cmd += ["--context-tokens", cell["opts"]["context-tokens"]]
    if SERIAL:
        cmd += ["--serial", SERIAL]
    print(f"\n=== {cell['runtime']}{'/' + cell['opts'].get('backend', '') if cell['opts'].get('backend') else ''} "
          f"{cell['model_id']} {cell['task']} ({time.strftime('%H:%M:%S')})")
    rc = subprocess.call(cmd)
    if rc:
        with open(os.path.join(out_dir, "FAILURES.txt"), "a") as fh:
            fh.write(f"{cell['runtime']} {cell['model_id']} {cell['task']} rc={rc}\n")


def arm_of(cell):
    # mirrors run_cell.py's arm: backend is part of arm identity for litert-lm only
    if cell["runtime"] == "litert-lm":
        return f"litert-lm-{cell['opts'].get('backend')}"
    return cell["runtime"]


def cell_id(cell):
    return f"{arm_of(cell)} {cell['model_id']} {cell['task']}"


def cell_records(cell, out_dir):
    """This cell's schema-v1 records, oldest first (names embed the UTC stamp;
    *.json.attempt1 quarantine files fall outside the pattern by suffix)."""
    pat = (f"{arm_of(cell)}_{cell['model_id'].replace('/', '_')}_"
           f"{cell['task']}_*.json")
    return sorted(glob.glob(os.path.join(out_dir, pat)))


def note(out_dir, fname, line):
    print(line)
    with open(os.path.join(out_dir, fname), "a") as fh:
        fh.write(line + "\n")


RETRY_VERDICTS = ("HOT", "SPREAD", "DEAD", "COLLAPSE")


def gate_verdict(cell, out_dir, runs):
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "cell_gate.py"),
                        "--runs", str(runs)] + cell_records(cell, out_dir),
                       capture_output=True, text=True)
    # a crashed gate must not read as a pass (an empty verdict matched no flag
    # pattern and the capture sailed through — audited 2026-08-27, iPhone runner)
    return r.stdout.strip() or "GATE_ERROR"


def apply_gate(cell, out_dir, runs):
    """Judge a completed cell; quarantine + re-run ONCE if flagged (spread-rule
    as code, mac/iPhone parity). The retry is a consecutive block — disclosed
    in session_provenance.txt because it deviates from per-round interleaving."""
    if not GATE_RETRY:
        return
    verdict = gate_verdict(cell, out_dir, runs)
    if verdict == "GATE_ERROR":
        note(out_dir, "FLAGGED.txt", f"GATE_ERROR {cell_id(cell)} (gate crashed; capture unjudged)")
        return
    if verdict.split()[0] not in RETRY_VERDICTS:
        return  # OK, or SHORT — a crash/timeout is never retried (failed-runs-stay)
    print(f"gate: {verdict} — quarantine + cooldown {GATE_COOLDOWN}s, re-run once")
    for f in cell_records(cell, out_dir)[-runs:]:
        os.rename(f, f + ".attempt1")  # stays in raw for audit, outside the *.json glob
    note(out_dir, "session_provenance.txt",
         f"gate retry {cell_id(cell)} verdict={verdict} (block re-run, not interleaved)")
    time.sleep(GATE_COOLDOWN)
    wait_nominal(out_dir)
    run_cell_once(cell, out_dir, runs)
    retry = gate_verdict(cell, out_dir, runs)
    if retry == "GATE_ERROR" or retry.split()[0] in RETRY_VERDICTS:
        note(out_dir, "FLAGGED.txt",
             f"GATE_FAIL {cell_id(cell)} first='{verdict}' retry='{retry}' "
             "(retry kept; ⚠ downstream)")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    cells_file = sys.argv[1]
    # One driver per device. Two campaigns interleaving on one phone poison
    # BOTH sets of numbers (measured 2026-08-27: a contended anchor read 0.4
    # tok/s against a clean 22-26, and a payload cell 5.0 against 25.9) — and
    # the round-robin runner outlives its last log line, so "looks finished"
    # is not finished. The lock makes the mistake impossible instead of rare.
    # Key the lock on the EFFECTIVE serial, not the raw env: with one device
    # attached, a driver with BENCH_ANDROID_SERIAL set and one without would
    # take different lock files and both drive the same phone. adb resolves
    # the default for us; if it can't (0 or 2+ devices, no env), the run was
    # doomed anyway and the shared 'default' key is the safe fallback.
    lock_key = SERIAL
    if not lock_key:
        r = subprocess.run(["adb", "get-serialno"], capture_output=True, text=True)
        got = r.stdout.strip()
        lock_key = got if r.returncode == 0 and got and got != "unknown" else "default"
    lock = open(f"/tmp/edge-llm-bench-android-{lock_key}.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print(f"another campaign is already driving device {lock_key} — "
              "refusing to start (two drivers corrupt both campaigns)", file=sys.stderr)
        return 3
    campaign = os.environ.get("CAMPAIGN", time.strftime("%Y-%m-%d") + "-android-matrix")
    # BENCH_RAW_ROOT: selftest.py redirects captures into its temp dir — a
    # failed selftest must never leak fake rows where build_summary globs
    raw_root = os.environ.get("BENCH_RAW_ROOT") or os.path.join(ROOT, "results", "raw")
    out_dir = os.path.join(raw_root, campaign, "app-path-android")
    os.makedirs(out_dir, exist_ok=True)
    anchors, payload, skipped = parse_cells(cells_file)
    for cell, reason in skipped:
        line = f"CELL_SKIP {cell['runtime']} {cell['model_id']} {cell['task']} reason={reason}"
        print(line)
        with open(os.path.join(out_dir, "SKIPPED.txt"), "a") as fh:
            fh.write(line + "\n")
    if not anchors and not payload:
        print("no android cells in this file")
        return 0

    with open(os.path.join(out_dir, "session_provenance.txt"), "a") as fh:
        fh.write(f"session start {time.strftime('%F %T')} cells={cells_file} "
                 f"cooldown={COOLDOWN}s\n")

    first = True
    for cell in anchors:  # anchors first, all their runs at once
        if not first:
            time.sleep(COOLDOWN)
        first = False
        wait_nominal(out_dir)
        runs = int(cell["opts"].get("runs", "3"))
        run_cell_once(cell, out_dir, runs)
        # gate anchors immediately: a contended anchor poisons every
        # anchor-normalized verdict of the session, so it must not stand
        # while the payload measures against it
        apply_gate(cell, out_dir, runs)

    # payload: interleave per round (round-robin across cells)
    max_rounds = max((int(c["opts"].get("runs", "3")) for c in payload), default=0)
    for rnd in range(1, max_rounds + 1):
        for cell in payload:
            if rnd > int(cell["opts"].get("runs", "3")):
                continue
            time.sleep(int(cell["opts"].get("cooldown", COOLDOWN)))
            wait_nominal(out_dir)
            run_cell_once(cell, out_dir, 1)
        print(f"--- round {rnd}/{max_rounds} complete (publish every round)")
    for cell in payload:  # a payload cell is complete only after its last round
        apply_gate(cell, out_dir, int(cell["opts"].get("runs", "3")))
    print(f"\ncampaign dir: {os.path.dirname(out_dir)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
