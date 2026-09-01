"""One Android endurance session (endurance-chat-<N>m; methodology/endurance.md).

The turn loop runs ON DEVICE (litert_lm_endurance_main — the harness driver
build_litert_lm_endurance.sh stages against the pinned LiteRT-LM tag); this
module is the host half:

  - streams the driver's ENDURANCE_TURN lines into the .turns.ndjson sidecar
    AS THEY ARRIVE (crash-safety: a USB drop or driver death at turn 37
    leaves turns 1..36 on the host disk),
  - stamps each turn with the latest thermal state (dumpsys thermalservice,
    sampled ~15 s by a background thread — per-turn dumpsys would contend
    with sub-second turns),
  - derives the within-session verdicts (decay windows, memory slope,
    degeneracy counts) exactly as the Mac EnduranceSession does, and
  - writes one schema-v1 record + raw console log (stored-report-rule).

Memory basis: the driver self-samples /proc/self/status VmRSS at each turn
boundary — the same field run_cell.py's 0.5 s sampler reads for every other
Android cell, but exactly turn-aligned. phys_footprint has no Android
equivalent, so the footprint* fields stay absent and the slope fields carry
memorySlopeBasis="resident-vmrss" (never fabricated).

Sessions are never pooled: one invocation = one session = one record
(runs=1 enforced by validate_cells).
"""
import datetime
import hashlib
import json
import os
import queue
import re
import statistics
import subprocess
import sys
import threading
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from device_probe import battery, device_info, thermal_status  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENDURANCE_TASK = re.compile(r"^endurance-chat-(\d+)m$")
DECAY_WINDOW_SECONDS = 300.0
STALL_SECONDS = 180      # driver-side: no stream event => hang
TURN_SECONDS = 600       # driver-side: absolute per-turn bound => hang
THERMAL_SAMPLE_SECONDS = 15


def median(xs):
    return statistics.median(xs) if xs else 0.0


def least_squares_slope(points):
    """OLS slope of y over x; None under 3 points or without x variance
    (the Mac EnduranceSession.leastSquaresSlope, ported)."""
    if len(points) < 3:
        return None
    n = float(len(points))
    sx = sum(p[0] for p in points)
    sy = sum(p[1] for p in points)
    sxx = sum(p[0] * p[0] for p in points)
    sxy = sum(p[0] * p[1] for p in points)
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-9:
        return None
    return (n * sxy - sx * sy) / denom


class ThermalSampler(threading.Thread):
    """Latest-known thermal state, refreshed every ~15 s off the turn path."""

    def __init__(self, serial):
        super().__init__(daemon=True)
        self.serial = serial
        self.raw, self.name = thermal_status(serial)
        self._stop = threading.Event()

    def run(self):
        while not self._stop.wait(THERMAL_SAMPLE_SECONDS):
            try:
                self.raw, self.name = thermal_status(self.serial)
            except Exception:
                pass  # transient adb drop; keep the last known state

    def stop(self):
        self._stop.set()


def derive(turns, planned_minutes, cap, status, failure_detail, sidecar_name):
    """Within-session verdicts from the turn series — the Mac
    EnduranceSession derivation, resident-basis (methodology/endurance.md)."""
    elapsed = (turns[-1]["startedAtSeconds"] + turns[-1].get("wallSeconds", 0.0)
               if turns else 0.0)
    rates = [t["decodeTokensPerSecond"] for t in turns
             if t.get("decodeTokensPerSecond", 0) > 0]
    first_w = [t["decodeTokensPerSecond"] for t in turns
               if t["startedAtSeconds"] < DECAY_WINDOW_SECONDS
               and t.get("decodeTokensPerSecond", 0) > 0]
    last_w = [t["decodeTokensPerSecond"] for t in turns
              if t["startedAtSeconds"] >= elapsed - DECAY_WINDOW_SECONDS
              and t.get("decodeTokensPerSecond", 0) > 0]
    windows_valid = elapsed > 2 * DECAY_WINDOW_SECONDS and first_w and last_w
    first_med = median(first_w) if windows_valid else None
    last_med = median(last_w) if windows_valid else None
    decay_pct = ((first_med - last_med) / first_med * 100
                 if first_med and last_med is not None else None)

    resident = [(t, t["residentAfterTurnMB"]) for t in turns
                if t.get("residentAfterTurnMB", -1) is not None
                and t.get("residentAfterTurnMB", -1) >= 0]
    slope_turn = least_squares_slope([(float(t["turn"]), mb) for t, mb in resident])
    slope_min = least_squares_slope(
        [(t["startedAtSeconds"] / 60.0, mb) for t, mb in resident])

    degenerate = [t for t in turns if t.get("degenerate")]
    summary = {
        "plannedMinutes": planned_minutes,
        "elapsedSeconds": elapsed,
        "turnsCompleted": len(turns),
        "conversationRollovers": sum(1 for t in turns if t.get("rollover")),
        "turnOutputTokenCap": cap,
        "status": status,
        "windowSeconds": DECAY_WINDOW_SECONDS,
        "degenerateTurnCount": len(degenerate),
        "memorySlopeBasis": "resident-vmrss",
        "turnsSidecar": sidecar_name,
    }
    if failure_detail:
        summary["failureDetail"] = failure_detail
    if first_med is not None:
        summary["decodeTokSFirstWindowMedian"] = first_med
        summary["decodeTokSLastWindowMedian"] = last_med
        summary["decodeDecayPercent"] = decay_pct
    if slope_turn is not None:
        summary["memorySlopeMBPerTurn"] = slope_turn
    if slope_min is not None:
        summary["memorySlopeMBPerMinute"] = slope_min
    if resident:
        summary["residentAfterFirstTurnMB"] = resident[0][1]
        summary["residentAfterLastTurnMB"] = resident[-1][1]
    if degenerate:
        summary["firstDegenerateTurn"] = degenerate[0]["turn"]
    return summary, rates, elapsed


def _reader(pipe, q):
    for line in iter(pipe.readline, ""):
        q.put(line)
    q.put(None)


def run(args):
    """One session. Returns 0 iff the session completed (failed-runs-stay:
    the record and partial sidecar stand either way)."""
    import run_cell as rc  # late import; run_cell imports this module

    m = ENDURANCE_TASK.match(args.task)
    minutes = int(m.group(1))
    cap = int(os.environ.get("ENDURANCE_TURN_CAP", "256"))
    if cap != 256:
        print(f"endurance: DIAGNOSTIC turn cap {cap} — not protocol; must not "
              "land in a standing campaign", file=sys.stderr)
    context_tokens = args.context_tokens or 4096
    arm = f"litert-lm-{args.backend}"
    pins = rc.load_pins()

    model_dev, model_local = rc.ensure_model(
        args.model_id, args.file, "litert-lm", args.serial)
    prompts_local = os.path.join(ROOT, "prompts", "text", "endurance-chat.turns.txt")
    if not os.path.exists(prompts_local):
        raise SystemExit("prompts/text/endurance-chat.turns.txt missing "
                         "(scripts/gen_task_prompts.py; the script is part of "
                         "the measurement contract)")
    prompts_dev = f"{rc.DEV_DIR}/prompts/endurance-chat.turns.txt"
    rc.adb(["shell", "mkdir", "-p", f"{rc.DEV_DIR}/prompts"], args.serial)
    rc.adb(["push", prompts_local, prompts_dev], args.serial)
    turn_script_sha = hashlib.sha256(open(prompts_local, "rb").read()).hexdigest()

    engine_version, engine_artifact = rc.observed_engine(
        "litert_lm_endurance_main", pins, args.serial)

    # firstEver: same on-device marker as every litert cell — the engine
    # caches are shared per (artifact, backend), so an endurance session on a
    # fresh pair is the cache build and is labelled as such.
    marker = (f"{rc.DEV_DIR}/markers/"
              f"{os.path.basename(model_dev)}.{args.backend}.cachebuilt")
    out = rc.adb(["shell", f"ls {marker} >/dev/null 2>&1 && echo present || echo absent"],
                 args.serial)
    cache_built = "present" in out

    os.makedirs(args.out, exist_ok=True)
    dev = device_info(args.serial)
    model_sha = rc.sha256_file(model_local)
    batt0 = battery(args.serial)
    raw_status, thermal_name = thermal_status(args.serial)

    now = datetime.datetime.now(datetime.timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H-%M-%S.%f")
    base = f"{arm}_{args.model_id.replace('/', '_')}_{args.task}_{stamp}_run1"
    sidecar_name = base + ".turns.ndjson"
    log_name = base + ".log"

    taskset = f"taskset {rc.CPU_MASK} " if rc.CPU_MASK else ""
    dev_cmd = (f"cd {rc.DEV_DIR} && LD_LIBRARY_PATH=. {taskset}"
               f"./litert_lm_endurance_main --backend={args.backend} "
               f"--model_path={model_dev} --prompts_file={prompts_dev} "
               f"--minutes={minutes} --turn_cap={cap} "
               f"--context_tokens={context_tokens} "
               f"--stall_seconds={STALL_SECONDS} --turn_seconds={TURN_SECONDS} "
               f"2>{rc.DEV_DIR}/endurance_err.txt")
    deadline = time.time() + minutes * 60 + max(args.timeout, 1500)

    sampler = ThermalSampler(args.serial)
    sampler.start()
    t0 = time.time()
    proc = subprocess.Popen(
        ["adb"] + (["-s", args.serial] if args.serial else []) + ["exec-out", dev_cmd],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    q = queue.Queue()
    threading.Thread(target=_reader, args=(proc.stdout, q), daemon=True).start()

    turns, load_info, driver_session = [], {}, None
    host_failure = None
    console = []
    sidecar_path = os.path.join(args.out, sidecar_name)
    with open(sidecar_path, "w") as sidecar:
        while True:
            # Host watchdog is a BACKSTOP behind the driver's own (stall 180 s
            # / turn 600 s): it only fires when the driver itself went silent
            # past its own bounds — a wedged engine or a dead USB link.
            try:
                line = q.get(timeout=TURN_SECONDS + 240)
            except queue.Empty:
                host_failure = (f"host-watchdog: no driver output for "
                                f"{TURN_SECONDS + 240}s")
                proc.kill()
                break
            if line is None:
                break
            console.append(line)
            line = line.strip()
            if line.startswith("ENDURANCE_TURN "):
                try:
                    turn = json.loads(line[len("ENDURANCE_TURN "):])
                except json.JSONDecodeError:
                    continue
                turn["thermalState"] = sampler.name
                turn["thermalRawStatus"] = sampler.raw
                sidecar.write(json.dumps(turn, sort_keys=True) + "\n")
                sidecar.flush()
                turns.append(turn)
                d = turn.get("decodeTokensPerSecond")
                print(f"turn={turn['turn']} t={int(turn['startedAtSeconds'])}s "
                      f"decode={f'{d:.1f}' if d else '-'}tok/s "
                      f"kv={turn.get('kvTokensAfterTurn', -1)} "
                      f"rssMB={int(turn.get('residentAfterTurnMB', -1))} "
                      f"stop={turn.get('stopReason')}"
                      f"{' ROLLOVER' if turn.get('rollover') else ''}"
                      f"{' DEGENERATE' if turn.get('degenerate') else ''}",
                      file=sys.stderr)
            elif line.startswith("ENDURANCE_LOAD "):
                try:
                    load_info = json.loads(line[len("ENDURANCE_LOAD "):])
                except json.JSONDecodeError:
                    pass
            elif line.startswith("ENDURANCE_SESSION "):
                try:
                    driver_session = json.loads(line[len("ENDURANCE_SESSION "):])
                except json.JSONDecodeError:
                    pass
            if time.time() > deadline:
                host_failure = "host-watchdog: session deadline exceeded"
                proc.kill()
                break
    proc.wait()
    elapsed_wall = time.time() - t0
    sampler.stop()

    # On-device stderr tail into the console log (engine error text lives
    # there; the driver keeps stdout machine-parseable).
    try:
        err_tail = rc.adb(["shell", f"tail -c 8192 {rc.DEV_DIR}/endurance_err.txt"],
                          args.serial)
        if err_tail.strip():
            console.append("=== device endurance_err.txt (tail) ===\n" + err_tail)
    except Exception:
        pass

    if driver_session:
        status = driver_session.get("status", "crash")
        failure_detail = driver_session.get("failureDetail")
    else:
        status = "hang" if host_failure else "crash"
        failure_detail = host_failure or "driver exited without a session line"

    end_status, end_name = thermal_status(args.serial)
    batt1 = battery(args.serial)
    summary, engine_rates, elapsed = derive(
        turns, minutes, cap, status, failure_detail, sidecar_name)

    wall_rates = [t["decodeTokensPerSecondWallClock"] for t in turns
                  if t.get("decodeTokensPerSecondWallClock", 0) > 0]
    resident = [t["residentAfterTurnMB"] for t in turns
                if t.get("residentAfterTurnMB", -1) >= 0]
    prompt_tokens = sum(t.get("prefillTokens", 0) for t in turns)
    gen_tokens = sum(t.get("decodeTokens", 0) for t in turns)
    prefill_seconds = sum(
        t["prefillTokens"] / t["prefillTokensPerSecond"] for t in turns
        if t.get("prefillTokens") and t.get("prefillTokensPerSecond", 0) > 0)

    metrics = {
        "coldRun": True,  # one fresh process per session; no warm regime
        "harnessStamp": rc.HARNESS_STAMP + "+endurance-r1",
        "decodeTokensPerSecond": median(engine_rates),
        "promptTokenCount": prompt_tokens,
        "generatedTokenCount": gen_tokens,
        "streamedChunkCount": sum(t.get("chunkCount", 0) for t in turns),
        "totalGenerationTimeSeconds": elapsed,
        "stopReason": "stop" if status == "completed" else "error",
        "initialThermalState": thermal_name,
        "finalThermalState": end_name,
        "contextTokensConfigured": context_tokens,
    }
    if load_info.get("loadSeconds") is not None:
        metrics["loadTimeSeconds"] = load_info["loadSeconds"]
    if turns and turns[0].get("ttftMS") is not None:
        metrics["firstTokenLatencyMS"] = int(round(turns[0]["ttftMS"]))
    if prefill_seconds > 0:
        metrics["promptTokensPerSecond"] = prompt_tokens / prefill_seconds
    if wall_rates:
        metrics["decodeTokensPerSecondWallClock"] = median(wall_rates)
    if resident:
        metrics["memoryMedianResidentMB"] = median(resident)
    if driver_session and driver_session.get("residentPeakMB", -1) >= 0:
        metrics["memoryPeakResidentMB"] = driver_session["residentPeakMB"]
    if driver_session and driver_session.get("residentFinalMB", -1) >= 0:
        metrics["memoryFinalResidentMB"] = driver_session["residentFinalMB"]
    if (args.first_ever) or not cache_built:
        metrics["firstEver"] = True
    if proc.returncode == 0 and not cache_built:
        rc.adb(["shell", f"mkdir -p {rc.DEV_DIR}/markers && touch {marker}"],
               args.serial)

    with open(os.path.join(args.out, log_name), "w") as fh:
        fh.writelines(console)

    rec = {
        "schemaVersion": 1,
        "id": str(uuid.uuid4()),
        "runtime": arm,
        "engineVersion": engine_version,
        "engineArtifact": engine_artifact,
        "model": {"id": args.model_id, "quantization": rc.guess_quant(model_dev),
                  "file": os.path.basename(model_dev), "sha256": model_sha},
        "task": args.task,
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "device": {**dev, "batteryLevel": batt0["batteryLevel"],
                   "batteryState": batt0["batteryState"],
                   "batteryLevelFinal": batt1["batteryLevel"]},
        "conditions": {
            "sampler": "topK40/topP0.9/temp0.7 (driver-set; endurance protocol)",
            "cpuAffinity": f"taskset {rc.CPU_MASK}" if rc.CPU_MASK else "none",
            "contextTokens": context_tokens,
            "turnScriptSha256": turn_script_sha,
            "thermalRawStatus": raw_status,
            "thermalRawStatusFinal": end_status,
            "screen": "on-usb",
            "elapsedSeconds": round(elapsed_wall, 1),
            "exitCode": proc.returncode,
        },
        "metrics": metrics,
        "endurance": summary,
        "provenance": {"rawLog": log_name,
                       "harness": "android/bench/endurance_cell.py"},
    }
    with open(os.path.join(args.out, base + ".json"), "w") as fh:
        json.dump(rec, fh, indent=2)

    print(f"endurance status={status} turns={len(turns)} "
          f"rollovers={summary['conversationRollovers']} "
          f"decode_median={metrics['decodeTokensPerSecond']:.2f}tok/s "
          f"decay={summary.get('decodeDecayPercent', 'n/a')} "
          f"mem_slope={summary.get('memorySlopeMBPerTurn', 'n/a')}MB/turn "
          f"degenerate_turns={summary['degenerateTurnCount']} "
          f"thermal={thermal_name}->{end_name}")
    if status != "completed":
        print(f"endurance session did not complete ({status}): "
              f"{failure_detail} — record kept (failed-runs-stay)", file=sys.stderr)
    return 0 if status == "completed" else 1
