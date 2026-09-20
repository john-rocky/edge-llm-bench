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
    GATE_RETRY=0 disables. The cold-only regime trips COLLAPSE (50% bar,
    slowest/median or median/fastest), not SPREAD — Android cold trials
    legitimately spread 15-30%. The retry is also judged for LEVEL: its
    median under half the quarantined capture's un-collapsed median (a
    uniformly slow block re-run passes every within-capture test; Pixel 8a
    2026-09-08) is flagged and kept, never re-run a third time.
"""
import fcntl
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from device_probe import thermal_status, adb  # noqa: E402
from run_cell import capture_stem, engine_command, DEV_DIR, CPU_MASK  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COOLDOWN = int(os.environ.get("COOLDOWN", "120"))
THERMAL_WAIT = int(os.environ.get("THERMAL_WAIT", "600"))
GATE_COOLDOWN = int(os.environ.get("GATE_COOLDOWN", "180"))
GATE_RETRY = os.environ.get("GATE_RETRY", "1") == "1"
SERIAL = os.environ.get("BENCH_ANDROID_SERIAL")
STRICT_SMOKE = os.environ.get("BENCH_STRICT_SMOKE") == "1"


def parse_cells(path):
    anchors, payload, skipped = [], [], []
    with open(path) as fh:
        lines = fh.readlines()
    for lineno, raw in enumerate(lines, 1):
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
    name = "unavailable"
    deadline = float(os.environ.get("BENCH_SESSION_DEADLINE", "inf"))
    while time.time() - t0 < THERMAL_WAIT and time.time() < deadline:
        raw, name = thermal_status(SERIAL)
        if raw == 0:
            return name
        print(f"thermal gate: status={name} — waiting…")
        time.sleep(min(30, max(0, deadline - time.time())))
    with open(os.path.join(out_dir, "THERMAL_GATE.txt"), "a") as fh:
        fh.write(f"gate timeout after {THERMAL_WAIT}s at {time.strftime('%F %T')}; ran anyway\n")
    return name


def launch_records(out_dir, launch):
    rows = []
    for path in glob.glob(os.path.join(out_dir, "*.json")):
        with open(path) as fh:
            row = json.load(fh)
        if row.get("conditions", {}).get("launchIndex") == launch:
            rows.append(row)
    return rows


def run_cell_once(cell, out_dir, runs, rnd=None, launch=None, gate_timed_out=False):
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
    if rnd is not None:
        cmd += ["--round-index", str(rnd), "--launch-index", str(launch)]
    if gate_timed_out:
        cmd += ["--gate-timed-out"]
    print(f"\n=== {cell['runtime']}{'/' + cell['opts'].get('backend', '') if cell['opts'].get('backend') else ''} "
          f"{cell['model_id']} {cell['task']} ({time.strftime('%H:%M:%S')})")
    rc = subprocess.call(cmd)
    if rc:
        with open(os.path.join(out_dir, "FAILURES.txt"), "a") as fh:
            identity = (cell_id(cell, True) if rnd is not None else
                        f"{cell['runtime']} {cell['model_id']} {cell['task']}")
            fh.write(f"{identity} rc={rc}\n")
    return rc


def arm_of(cell):
    # mirrors run_cell.py's arm: backend is part of arm identity for litert-lm only
    if cell["runtime"] == "litert-lm":
        return f"litert-lm-{cell['opts'].get('backend')}"
    return cell["runtime"]


def cell_id(cell, round_mode=False):
    legacy = f"{arm_of(cell)} {cell['model_id']} {cell['task']}"
    if not round_mode and (not cell["opts"].get("context-tokens") or cell["task"].startswith(("native-", "endurance-"))):
        return legacy
    return (legacy + " " +
            f"context-tokens={cell['opts'].get('context-tokens', 'default')} "
            f"file={cell['opts'].get('file', 'auto')}")


def cell_records(cell, out_dir):
    """This cell's schema-v1 records, oldest first (names embed the UTC stamp;
    *.json.attempt1 quarantine files fall outside the pattern by suffix)."""
    opts = cell["opts"]
    ctx = int(opts["context-tokens"]) if opts.get("context-tokens") else None
    pat = capture_stem(cell["runtime"], opts.get("backend"), cell["model_id"],
                       cell["task"], opts.get("file"), ctx) + "_*.json"
    return sorted(glob.glob(os.path.join(out_dir, pat)))


def note(out_dir, fname, line):
    print(line)
    with open(os.path.join(out_dir, fname), "a") as fh:
        fh.write(line + "\n")


RETRY_VERDICTS = ("HOT", "SPREAD", "DEAD", "COLLAPSE")


def gate_verdict(cell, out_dir, runs, previous=()):
    cmd = [sys.executable, os.path.join(ROOT, "scripts", "cell_gate.py"),
           "--runs", str(runs)] + cell_records(cell, out_dir)
    if previous:  # the quarantined capture a retry replaces -> LEVEL can fire
        cmd += ["--previous"] + list(previous)   # after the positionals (nargs="*")
    r = subprocess.run(cmd, capture_output=True, text=True)
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
    quarantined = []
    for f in cell_records(cell, out_dir)[-runs:]:
        os.rename(f, f + ".attempt1")  # stays in raw for audit, outside the *.json glob
        quarantined.append(f + ".attempt1")
    note(out_dir, "session_provenance.txt",
         f"gate retry {cell_id(cell)} verdict={verdict} (block re-run, not interleaved)")
    time.sleep(GATE_COOLDOWN)
    wait_nominal(out_dir)
    run_cell_once(cell, out_dir, runs)
    retry = gate_verdict(cell, out_dir, runs, previous=quarantined)
    if retry == "GATE_ERROR" or retry.split()[0] in RETRY_VERDICTS + ("LEVEL",):
        note(out_dir, "FLAGGED.txt",
             f"GATE_FAIL {cell_id(cell)} first='{verdict}' retry='{retry}' "
             "(retry kept; ⚠ downstream)")


def round_schedule(anchors, payload, rounds):
    """One launch/cell/round; reversing the WHOLE order preserves triples."""
    cells = anchors + payload
    launch = 0
    for rnd in range(1, rounds + 1):
        for cell in (cells if rnd % 2 else list(reversed(cells))):
            launch += 1
            yield rnd, launch, cell


def planned_command(cell):
    """Pure command construction: no downloads, probes, locks or device calls."""
    opts = cell["opts"]
    filename = opts.get("file")
    if not filename:
        raise ValueError("dry-run requires explicit file= (no network resolution)")
    filename = os.path.basename(filename) if os.path.isabs(filename) or filename.startswith(("~", "./", "../")) else filename
    model = f"{DEV_DIR}/models/{cell['model_id'].replace('/', '_')}_{filename}"
    prompt = f"{DEV_DIR}/prompts/{cell['task']}.txt"
    with open(os.path.join(ROOT, "prompts", "text", "budgets.tsv")) as fh:
        budgets = dict(line.strip().split("\t") for line in fh)
    ctx = int(opts["context-tokens"]) if opts.get("context-tokens") else None
    limit = int(opts["max-tokens"]) if opts.get("max-tokens") else None
    command, binary, sampler, _ = engine_command(
        cell["runtime"], opts.get("backend"), model, cell["task"], prompt,
        int(budgets[cell["task"]]) if cell["task"] in budgets else None, limit, ctx)
    affinity = f"taskset {CPU_MASK} " if CPU_MASK else ""
    return f"cd {DEV_DIR} && LD_LIBRARY_PATH=. {affinity}{command}", binary, sampler


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cells_file")
    ap.add_argument("--dry-run", action="store_true", help="print round plan without ANY device/network access")
    args = ap.parse_args()
    cells_file = args.cells_file
    rounds = int(os.environ["ROUNDS"]) if "ROUNDS" in os.environ else None
    if rounds is not None and rounds < 1:
        ap.error("ROUNDS must be positive")
    anchors, payload, skipped = parse_cells(cells_file)
    if rounds is None and any(c["task"] == "long-context-2048-gen256" for c in anchors + payload):
        ap.error("long-context-2048-gen256 requires opt-in ROUNDS=N")
    if args.dry_run:
        if rounds is None:
            ap.error("--dry-run requires opt-in ROUNDS=N")
        for cell, reason in skipped:
            print(json.dumps({"skip": cell_id(cell), "reason": reason}))
        for rnd, launch, cell in round_schedule(anchors, payload, rounds):
            command, binary, sampler = planned_command(cell)
            print(json.dumps({"round": rnd, "launch": launch, "cell": cell_id(cell, True),
                              "anchor": cell["opts"].get("anchor") == "1",
                              "command": command, "binary": binary, "sampler": sampler,
                              "cooldownSeconds": COOLDOWN, "gateAutoRetry": False}))
        return 0
    if rounds is not None and not SERIAL:
        ap.error("round mode requires BENCH_ANDROID_SERIAL (explicit device)")
    if os.environ.get("BENCH_TEST_LOCK_DIR") and SERIAL != "FAKESELF":
        ap.error("BENCH_TEST_LOCK_DIR is only for the FAKESELF selftest fixture")
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
    lock_dir = os.environ.get("BENCH_LOCK_DIR") or os.environ.get("BENCH_TEST_LOCK_DIR", "/tmp")
    lock = open(os.path.join(lock_dir, f"edge-llm-bench-android-{lock_key}.lock"), "w")
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
    if rounds is not None and os.path.isdir(out_dir) and os.listdir(out_dir):
        print("round mode requires a fresh campaign (stored-report-rule)", file=sys.stderr)
        return 2
    os.makedirs(out_dir, exist_ok=True)
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

    if rounds is not None:
        note(out_dir, "session_provenance.txt",
             f"rounds={rounds} alternate=1 gate=off launches-per-cell-per-round=1 "
             "litert-context-iterations=2 llama-regime=cold-process")
        failed = False
        sitting = os.environ.get("BENCH_SITTING") == "1"
        started = float(os.environ.get("BENCH_DRIVER_START_EPOCH", time.time()))
        deadline = float(os.environ.get("BENCH_SESSION_DEADLINE", "inf"))
        per_round = len(anchors) + len(payload)
        timeout_count, current_round, completed_rounds = 0, 0, []
        pending_stop = None
        for rnd, launch, cell in round_schedule(anchors, payload, rounds):
            if sitting and rnd != current_round:
                if pending_stop or time.time() >= deadline or (rnd == 8 and time.time() - started > 135 * 60):
                    note(out_dir, "SITTING_STOP.txt", pending_stop or "driver time budget at round boundary")
                    return 2
                current_round = rnd
                try:
                    power = adb(["shell", "dumpsys", "power"], SERIAL)
                    wake = re.search(r"\bmWakefulness=(\w+)", power)
                    os.environ["BENCH_ROUND_WAKEFULNESS"] = wake.group(1) if wake else "unknown"
                    with open(os.path.join(out_dir, f"power_round{rnd:02d}.txt"), "w") as fh:
                        fh.write(power)
                    note(out_dir, "round_state.jsonl", json.dumps({"round": rnd, "timestamp": time.strftime('%F %T'), "mWakefulness": os.environ["BENCH_ROUND_WAKEFULNESS"]}))
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                    pending_stop = "device-lost-at-round-probe"
                    note(out_dir, "DEVICE_LOST.txt", str(exc))
            if sitting and (pending_stop and pending_stop.startswith("device-lost") or time.time() >= deadline):
                note(out_dir, "UNRUN_CELLS.jsonl", json.dumps({"round": rnd, "launch": launch, "cell": cell_id(cell, True), "reason": pending_stop or "150-minute-cap"}))
                if launch % per_round == 0:
                    note(out_dir, "round_completion.jsonl", json.dumps({"round": rnd, "complete": False, "reason": pending_stop or "150-minute-cap", "completedRounds": completed_rounds}))
                    return 2
                continue
            if launch > 1:
                time.sleep(min(COOLDOWN, max(0, deadline - time.time())) if sitting else COOLDOWN)
            try:
                gate_state = wait_nominal(out_dir)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                if not sitting:
                    raise
                pending_stop = "device-lost-at-thermal-gate"
                note(out_dir, "DEVICE_LOST.txt", str(exc))
                note(out_dir, "UNRUN_CELLS.jsonl", json.dumps({"round": rnd, "launch": launch, "cell": cell_id(cell, True), "reason": pending_stop}))
                if launch % per_round == 0:
                    note(out_dir, "round_completion.jsonl", json.dumps({"round": rnd, "complete": False, "reason": pending_stop, "completedRounds": completed_rounds}))
                    return 2
                continue
            if sitting and time.time() >= deadline:
                note(out_dir, "SITTING_STOP.txt", f"150-minute cap before launch {launch}; round {rnd} incomplete")
                return 2
            if STRICT_SMOKE and not sitting and gate_state != "nominal":
                note(out_dir, "SMOKE_STOP.txt", f"thermal gate timed out at {gate_state}; no next launch")
                return 1
            note(out_dir, "launch_order.jsonl", json.dumps(
                {"round": rnd, "launch": launch, "cell": cell_id(cell, True)}))
            rc = run_cell_once(cell, out_dir, 1, rnd, launch, gate_state != "nominal")
            failed |= bool(rc)
            if sitting:
                if rc == 5:
                    note(out_dir, "SITTING_STOP.txt", f"PIN MISMATCH before launch {launch}")
                    return 5
                observed = launch_records(out_dir, launch)
                if any(r["conditions"].get("thermalGateTimeoutNonNominal") for r in observed):
                    timeout_count += 1
                flags = {f for r in observed for f in r["conditions"].get("protocolFlags", [])}
                if not observed or flags & {"host-adb-failure", "end-state-unavailable"}:
                    pending_stop = "device-lost-or-cell-failed-before-record"
                elif timeout_count >= 3:
                    pending_stop = "three-non-nominal-launch-starts-after-gate-timeout"
                if launch % per_round == 0:
                    round_rows = [r for n in range(launch - per_round + 1, launch + 1) for r in launch_records(out_dir, n)]
                    expected_rows = sum(2 if c["runtime"] == "litert-lm" and c["opts"].get("context-tokens") else 1 for c in anchors + payload)
                    complete = len(round_rows) == expected_rows
                    if complete:
                        completed_rounds.append(rnd)
                    note(out_dir, "round_completion.jsonl", json.dumps({"round": rnd, "complete": complete, "records": len(round_rows), "expectedRecords": expected_rows, "completedRounds": completed_rounds, "gateTimeoutNonNominalStarts": timeout_count, "elapsedDriverSeconds": time.time() - started, "pendingStop": pending_stop}))
                    if pending_stop:
                        note(out_dir, "SITTING_STOP.txt", pending_stop)
                        return 2
            if STRICT_SMOKE and not sitting and rc:
                note(out_dir, "SMOKE_STOP.txt", f"launch {launch} failed; no next launch")
                return 1
            if os.environ.get("BENCH_REVIEW_AFTER_LAUNCH") == "1":
                print(f"REVIEW launch {launch}: inspect stored text; enter CONTINUE or STOP", flush=True)
                if sys.stdin.readline().strip() != "CONTINUE":
                    note(out_dir, "REVIEW_STOP.txt", f"stopped after launch {launch} for text review")
                    return 4
        print(f"\ncampaign dir: {os.path.dirname(out_dir)}")
        return int(failed)

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
