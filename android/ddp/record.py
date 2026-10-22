"""Records of a DDP session (android/ddp/run_ddp.py): one result.v1 JSON per run (two per run
for a context-prompt cell, iteration 1 cold and 2 warm), built from what the job pulled
(<campaign>/ddp/<session>/<job>/<execution>/artifacts/data/local/tmp/llmbench/ddp-out/, written
by android/ddp/ddp_cell.sh) and the session report, with the keys and rules of
android/bench/run_cell.py main's extended record (run_cell 1405-1563), plus:
  conditions.ddp  the session / job / execution ids and times, the catalog id and schedule key,
                  the unit's ro.build.fingerprint / ro.serialno / ro.product.device, the job's
                  executionTimeout, the execution's resultType, the run's index in the job
  conditions.engineCache  what the engine's caches did in the run, read from its raw log (D13):
                  xnnpackWeightCache built / loaded / absent, gpuCache loaded / not-loaded / absent
  device.ddp      catalog id, fingerprint, serial (scripts/build_summary.py: the device column)
  provenance      ddpSessionDir, wrapper, wrapperSha256 (+ ddpMissing: what the unit did not give)
A value the unit did not report stays null with its reason in provenance.ddpMissing — never
estimated. The witness is the shas the wrapper read on the unit (provenance.txt) against
android/engine-pins.json: the launched tool's field and every so_files entry. The record id and
conditions.launchID are uuid5s of the session / job / execution / run (/ iteration), so records
rebuilt from the same pulled output (run_ddp.py --records-only) carry the same ids and file names
(D13; build_summary drops a repeated id).
"""
import datetime
import hashlib
import json
import os
import re
import shutil
import statistics
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "android", "bench"))
import parsers  # noqa: E402
import run_cell  # noqa: E402
from device_probe import THERMAL_NAMES  # noqa: E402

HARNESS = "android/ddp/run_ddp.py"
WRAPPER_REL = "android/ddp/ddp_cell.sh"
HARNESS_STAMP = run_cell.HARNESS_STAMP + "+ddp-route-c"
OUTPUT_DIR = f"{run_cell.DEV_DIR}/ddp-out"
PROPS = ("ro.product.model", "ro.product.device", "ro.build.fingerprint", "ro.serialno",
         "ro.build.version.release", "ro.build.version.security_patch", "ro.soc.model")
# D13: the cache lines of a LiteRT-LM raw log. A CPU run after the first may rebuild the XNNPACK weight
# cache (its file name carries the pushed model's mtime second, which can differ by one between two
# processes: lane memory litertlm-xnnpack-cache-name-jitter), so firstEver (run 1, D10) does not say it
XNNPACK_BUILT = "weight cache build for"
XNNPACK_LOADED = "weight cache loaded from"
GPU_LOADED = "Initialized InferenceContext from serialized data"


def read(path):
    with open(path, errors="replace") as fh:
        return fh.read()


def parse_provenance(text):
    """ddp_cell.sh's provenance.txt -> {"props": {getprop name: value}, "args": [argv],
    "sha": {device path: sha256}}."""
    props, args, shas = {}, [], {}
    for line in text.splitlines():
        if line.startswith("arg: "):
            args.append(line[len("arg: "):])
            continue
        parts = line.split()
        if len(parts) == 2 and run_cell.is_sha256(parts[0]):
            shas[parts[1]] = parts[0]
            continue
        name, sep, value = line.partition(": ")
        if sep and name in PROPS:
            props[name] = value.strip()
    return {"props": props, "args": args, "sha": shas}


def parse_state(text):
    """run<i>.state -> {"gate": {key: value}, "start": {...}, "end": {...}}; each phase holds epoch,
    ns, thermal, wakefulness, stay_on and the raw dumpsys battery text."""
    out = {"gate": {}, "start": {}, "end": {}}
    block = None
    for line in text.splitlines():
        if block is not None:
            if line == f"{block}_battery_end":
                block = None
            else:
                out[block]["battery"] = out[block].get("battery", "") + line + "\n"
            continue
        m = re.match(r"^(start|end)_battery_begin$", line)
        if m:
            block = m.group(1)
            out[block]["battery"] = ""
            continue
        key, sep, value = line.partition("=")
        if not sep:
            continue
        phase, _, name = key.partition("_")
        if phase in ("start", "end") and name:
            out[phase][name] = value
        else:
            out["gate"][key] = value
    return out


def battery(text):
    """device_probe.battery's reading of a stored dumpsys battery text; None fields without one."""
    if not text or not text.strip():
        return {"batteryLevel": None, "batteryState": None, "rawStatus": None, "temperatureC": None}
    level = re.search(r"level: (\d+)", text)
    status = re.search(r"status: (\d+)", text)
    plugged = re.search(r"(AC|USB|Wireless) powered: true", text)
    temperature = re.search(r"temperature:\s*(-?\d+)", text)
    return {"batteryLevel": int(level.group(1)) / 100 if level else None,
            "batteryState": "charging" if plugged else "unplugged",
            "rawStatus": int(status.group(1)) if status else None,
            "temperatureC": int(temperature.group(1)) / 10 if temperature else None}


def thermal(line):
    """device_probe.thermal_status's reading of a stored `Thermal Status:` line."""
    m = re.search(r"Thermal Status: (\d+)", line or "")
    raw = int(m.group(1)) if m else None
    return raw, THERMAL_NAMES.get(raw, f"unknown({raw})")


def screen(wake_line, stay_on):
    """device_probe.screen_conditions' form, from the wrapper's reads before the run."""
    m = re.search(r"mWakefulness=(\w+)", wake_line or "")
    if not m:
        value = "unknown (no mWakefulness line in dumpsys power)"
    else:
        value = "on-usb" if m.group(1) == "Awake" else f"off-usb (mWakefulness={m.group(1)})"
    return {"screen": value, "screenSource": "measured",
            "stayOnWhilePluggedIn": (stay_on or "").strip() or None}


def epoch(phase):
    """(seconds since the epoch as a float, its source) of a state phase: date +%s%N when the
    unit printed it, else date +%s."""
    ns = phase.get("ns", "")
    if ns.isdigit() and len(ns) >= 16:
        return int(ns) / 1e9, "ns"
    s = phase.get("epoch", "")
    return (float(s), "s") if s.isdigit() else (None, None)


def witness(binname, shas, pins, engine_dir=None):
    """run_cell.observed_engine's rule on the shas the wrapper read on the unit: the pins tag whose
    entry holds the launched tool's sha in its field (run_cell.pin_key) and, beside it on the
    unit, every so_files entry of that tag; else 'unknown (…)' in observed_engine's wording."""
    if binname.split("/")[0].startswith("executorch-"):
        build_dir, runner = binname.split("/", 1)
        backend = next((b for b in run_cell.EXECUTORCH_BACKENDS if build_dir.endswith("-" + b)), "")
        field = f"{runner}_{backend}_sha256" if backend else f"{runner}_sha256"
        sha = shas.get(f"{run_cell.DEV_DIR}/{binname}")
        if sha is None:
            return f"unknown (on-device {binname} sha not in provenance.txt)", None
        for tag, entry in pins.get("executorch", {}).items():
            if entry.get(field) == sha:
                return tag, sha
        return f"unknown (on-device {binname} sha unmatched in android/engine-pins.json)", sha
    engine, field = run_cell.pin_key(binname)
    dev_path = (run_cell.side_path(engine_dir, run_cell.SIDE_DIRS[engine][0], binname)
                if engine_dir else f"{run_cell.DEV_DIR}/{binname}")
    sha = shas.get(dev_path)
    if sha is None:
        return f"unknown (on-device {binname} sha not in provenance.txt)", None
    for tag, entry in pins.get(engine, {}).items():
        if entry.get(field) == sha:
            libs = entry.get("so_files") or {}
            bad = [name for name in sorted(libs)
                   if shas.get(run_cell.side_path(engine_dir, run_cell.SIDE_DIRS[engine][1], name)
                               if engine_dir else f"{run_cell.DEV_DIR}/{name}") != libs[name]]
            if bad:
                return (f"unknown (on-device {tag} {binname} with lib {', '.join(bad)} "
                        "unmatched in android/engine-pins.json)"), sha
            return pins[engine][tag].get("engine_version", tag), sha
    return f"unknown (on-device {binname} sha unmatched in android/engine-pins.json)", sha


def engine_cache(console, backend, log_name):
    """conditions.engineCache of one run from its raw log -> (value, ddpMissing reason or None).
    xnnpackWeightCache: "built" (a 'weight cache build for' line), "loaded" ('weight cache loaded from'
    and no build), "absent" (neither; on a CPU run its reason goes to provenance.ddpMissing). gpuCache:
    on a GPU run "loaded" (an 'Initialized InferenceContext from serialized data' line) or
    "not-loaded", on a CPU run "absent"."""
    if XNNPACK_BUILT in console:
        xnnpack = "built"
    elif XNNPACK_LOADED in console:
        xnnpack = "loaded"
    else:
        xnnpack = "absent"
    gpu = ("loaded" if GPU_LOADED in console else "not-loaded") if backend == "gpu" else "absent"
    missing = None
    if xnnpack == "absent" and backend != "gpu":
        missing = (f"conditions.engineCache.xnnpackWeightCache: {log_name} has neither '{XNNPACK_BUILT}' "
                   f"nor '{XNNPACK_LOADED}'")
    return {"xnnpackWeightCache": xnnpack, "gpuCache": gpu}, missing


def record_uuid(meta, run, iteration=None):
    """D13: a record's id (with its iteration) or its launch's launchID (without), a uuid5 of
    edge-llm-bench/ddp/<session>/<job>/<execution>/run<i>[/iter<k>]; an execution the report names
    without a job or execution id is named by its pulled directory instead."""
    ids = (meta.get("sessionId"), meta.get("jobId"), meta.get("executionId"))
    where = "/".join(ids) if all(ids) else meta["ddpSessionDir"]
    name = f"edge-llm-bench/ddp/{where}/run{run}" + (f"/iter{iteration}" if iteration else "")
    return str(uuid.uuid5(uuid.NAMESPACE_URL, name))


def records_for_execution(job, exec_dir, out_dir, meta):
    """Write the records of one execution of one job. -> ([(record path or None, clean)], notes)."""
    written, notes = [], []
    where = f"{job['cellId']} ({meta['jobDisplayName']}, execution {meta['executionId']})"
    ddp_out = os.path.join(exec_dir, "artifacts", OUTPUT_DIR.lstrip("/"))
    prov_path = os.path.join(ddp_out, "provenance.txt")
    if not os.path.isfile(prov_path):
        notes.append(f"{where}: no provenance.txt pulled (result {meta['resultType']}) — no record")
        return [(None, False)] * job["runs"], notes
    prov = parse_provenance(read(prov_path))
    missing = []
    props = {}
    for name in PROPS:
        props[name] = prov["props"].get(name) or None
        if props[name] is None:
            missing.append(f"{name}: empty in provenance.txt")
    runtime = job.get("runtime", "litert-lm")
    engine_build = job.get("engineBuild")
    engine_dir = f"{run_cell.ENGINES_DIR}/{engine_build}" if engine_build else None
    engine_version, engine_artifact = witness(job["binname"], prov["sha"], run_cell.load_pins(), engine_dir)
    model_sha = prov["sha"].get(job["modelDevice"])
    if model_sha is None:
        missing.append(f"model.sha256: no provenance.txt line for {job['modelDevice']}")
    dev = {"modelIdentifier": props["ro.product.model"], "systemName": "Android",
           "systemVersion": props["ro.build.version.release"],
           "securityPatch": props["ro.build.version.security_patch"],
           "soc": props["ro.soc.model"], "product": props["ro.product.device"]}
    ddp_device = {"deviceId": job["deviceId"], "buildFingerprint": props["ro.build.fingerprint"],
                  "serial": props["ro.serialno"]}
    paired = job["paired"]
    budget = job["maxTokens"] or job["budget"]
    sampler, cmd, binname = job["sampler"], job["command"], job["binname"]
    model_dev = job["modelDevice"]
    stem = job["stem"]
    et = None
    if runtime == "executorch":
        et = parsers.executorch_inputs(run_cell.EXECUTORCH_MODEL_DIR, job["file"], job["task"],
                                       job.get("recipe"), ROOT)
    prompt_text = None
    if engine_dir and not job["task"].startswith("native-benchmark-"):
        with open(os.path.join(ROOT, "prompts", "text", f"{job['task']}.txt")) as fh:
            prompt_text = fh.read()
    # D10: every job starts on a clean unit; as on the attached-phone route, every run until the first
    # clean exit is (or may be finishing) the cache build (litert-lm, or llama.cpp GPU side build)
    cache_built = not (runtime == "litert-lm" or (engine_dir and job["backend"] == "gpu" and binname != "llama-bench"))
    for i in range(1, job["runs"] + 1):
        log_path = os.path.join(ddp_out, f"run{i}.log")
        if not os.path.isfile(log_path):
            skipped = os.path.join(ddp_out, f"run{i}.skipped")
            why = read(skipped).strip() if os.path.isfile(skipped) else "no run log pulled"
            notes.append(f"{where} run {i}: {why} — no record")
            written.append((None, False))
            continue
        console = read(log_path)
        state_path = os.path.join(ddp_out, f"run{i}.state")
        st = parse_state(read(state_path) if os.path.isfile(state_path) else "")
        run_missing = list(missing)
        raw_status, thermal_name = thermal(st["start"].get("thermal"))
        end_status, end_name = thermal(st["end"].get("thermal"))
        batt, end_batt = battery(st["start"].get("battery")), battery(st["end"].get("battery"))
        if batt["batteryLevel"] is None:
            run_missing.append(f"battery: no dumpsys battery level before run {i}")
        scr = screen(st["start"].get("wakefulness"), st["start"].get("stay_on"))
        t_start, unit = epoch(st["start"])
        t_end, _ = epoch(st["end"])
        if t_start is None:
            if not meta.get("executionStartTime"):
                notes.append(f"{where} run {i}: no start time in run{i}.state nor in the report — no record")
                written.append((None, False))
                continue
            run_missing.append(f"run {i} start time: not in run{i}.state; the execution's startTime stands in")
            t_start = datetime.datetime.fromisoformat(meta["executionStartTime"].replace("Z", "+00:00")).timestamp()
        elapsed = round(t_end - t_start, 1) if t_end is not None and unit else None
        if elapsed is None:
            run_missing.append(f"elapsedSeconds: run{i}.state has no start / end epoch")
        rss_kb = [int(x) for x in (line.split()[1] for line in console.splitlines() if line.startswith("VmRSS"))]
        rss_mb = statistics.median(rss_kb) / 1024 if rss_kb else None
        exit_code = 1
        for line in console.splitlines():
            if line.startswith("EXIT_CODE="):
                try:
                    exit_code = int(line.split("=", 1)[1])
                except ValueError:
                    pass
        cpu_cond, cpu_capped = run_cell.cpu_conditions(console, job["mask"])
        start_capped = st["gate"].get("cpucap_timed_out") == "1"
        gate_timed_out = st["gate"].get("thermal_gate_timed_out") == "1"
        cpu_flags = (["cpu-capped"] if cpu_capped else []) + (["cpu-capped-at-start"] if start_capped else [])
        cache = None
        if runtime == "litert-lm":
            cache, cache_missing = engine_cache(console, job["backend"], f"run{i}.log")
            if cache_missing:
                run_missing.append(cache_missing)
        launch_id = record_uuid(meta, i)
        et_fields = None
        tests = None
        cold = True
        if paired:
            iteration_metrics, launch_checks = parsers.context_prompt_results(console, job["contextTokens"], budget)
            iteration_metrics += [{} for _ in range(max(0, 2 - len(iteration_metrics)))]
            metrics = iteration_metrics[0]
        elif runtime == "llama.cpp" and job["task"].startswith("native-benchmark-"):
            tests = parsers.parse_llama_bench_json(console)
            metrics = {}
            for t in tests:
                if t["kind"] == "prefill":
                    metrics["promptTokensPerSecond"] = t["avg_ts"]
                    metrics["promptTokenCount"] = t["n_prompt"]
                else:
                    metrics["decodeTokensPerSecond"] = t["avg_ts"]
                    metrics["generatedTokenCount"] = t["n_gen"]
            cold = False
            invalid = console.lower().count("invalid decode")
            launch_checks = {"invalidDecodeCount": invalid,
                             "protocolFlags": ["invalid-decode"] if invalid else []}
        elif runtime == "llama.cpp":
            metrics = parsers.parse_llama_cli(console)
            invalid = console.lower().count("invalid decode")
            launch_checks = {"invalidDecodeCount": invalid,
                             "protocolFlags": ["invalid-decode"] if invalid else []}
        elif et:
            et_fields = run_cell.executorch_fields(console, et, budget, job["contextTokens"])
            metrics = dict(et_fields["metrics"])
            invalid = console.lower().count("invalid decode")
            launch_checks = {"invalidDecodeCount": invalid,
                             "protocolFlags": (["invalid-decode"] if invalid else []) + list(et_fields["flags"])}
        else:
            metrics = parsers.parse_litert(console)
            invalid = console.lower().count("invalid decode")
            launch_checks = {"invalidDecodeCount": invalid,
                             "protocolFlags": ["invalid-decode"] if invalid else []}
        side_cond, backend_flags = {}, []
        if engine_dir and runtime == "llama.cpp":
            device = run_cell.LLAMA_DEVICES[job["backend"]]
            bench = binname == "llama-bench"
            lines = (parsers.llama_bench_device_lines(tests) if bench
                     else parsers.llama_backend_lines(console))
            side_cond = {"engineBuild": engine_build, "ggmlDevice": device, "nGpuLayers": 99,
                         "threads": run_cell.SIDE_THREADS,
                         "flashAttn": "auto (llama-bench default)" if bench else "on",
                         "ubatch": run_cell.SIDE_UBATCH if not bench or job["backend"] == "npu"
                         else "512 (llama-bench default)",
                         "hexagonOpPoll": 1, "engineCommand": f"{job['env']} {cmd}",
                         "backendRegistered": lines}
            if not parsers.llama_backend_registered(lines, device, run_cell.LLAMA_DEVICE_BUFFERS[device],
                                                    binname, tests):
                backend_flags = ["backend-not-registered"]
        if exit_code != 0:
            launch_checks["protocolFlags"].append(f"engine-exit-{exit_code}")
        metrics.update({"coldRun": cold, "harnessStamp": HARNESS_STAMP + (run_cell.EXECUTORCH_STAMP if et else ""),
                        "initialThermalState": thermal_name, "finalThermalState": end_name})
        if rss_mb is not None:
            metrics["memoryMedianResidentMB"] = rss_mb
        high_water = [int(line.split()[1]) for line in console.splitlines() if line.startswith("VmHWM:")]
        if high_water:
            metrics["memoryPeakResidentMB"] = max(high_water) / 1024
        if et:
            engine_peak = metrics.get("memoryPeakEngineReportedMB")
            if engine_peak and engine_peak > metrics.get("memoryPeakResidentMB", 0):
                metrics["memoryPeakResidentMB"] = engine_peak
        if not cache_built:
            metrics["firstEver"] = True
        if exit_code == 0 and not cache_built and not launch_checks.get("protocolFlags") and not backend_flags:
            cache_built = True

        when = datetime.datetime.fromtimestamp(int(t_start), datetime.timezone.utc)
        iso = when.strftime("%Y-%m-%dT%H:%M:%SZ")
        stamp = when.strftime("%Y-%m-%dT%H-%M-%S")
        console_name = f"{stem}_{stamp}_run{i}.log"
        shutil.copyfile(log_path, os.path.join(out_dir, console_name))
        rec = {
            "schemaVersion": 1,
            "id": record_uuid(meta, i, 1),
            "runtime": job["arm"],
            "engineVersion": engine_version,
            "engineArtifact": engine_artifact,
            "model": {"id": job["modelId"], "quantization": run_cell.guess_quant(model_dev),
                      "file": os.path.basename(model_dev), "sha256": model_sha},
            "task": job["task"],
            "timestamp": iso,
            "device": {**dev, "batteryLevel": batt["batteryLevel"], "batteryState": batt["batteryState"],
                       "ddp": ddp_device},
            "conditions": {"sampler": sampler,
                           "cpuAffinity": f"taskset {job['mask']}" if job["mask"] else "none",
                           **cpu_cond,
                           "contextTokens": job["ctxNote"],
                           **({"promptVersion": job["promptVersion"]} if job.get("promptVersion") else {}),
                           **({"chatMode": "single-turn template default (-st)"}
                              if runtime == "llama.cpp" and not job["task"].startswith("native-") else {}),
                           "thermalRawStatus": raw_status,
                           "thermalRawStatusFinal": end_status,
                           **scr, "elapsedSeconds": elapsed,
                           "exitCode": exit_code,
                           **({"engineCache": cache} if cache is not None else {}),
                           **side_cond},
            "metrics": metrics,
            "provenance": {"rawLog": console_name, "harness": HARNESS,
                           "rssBasis": run_cell.RSS_BASIS + (run_cell.SIDE_RSS_NOTE if engine_dir else ""),
                           "modelShaSource": "device",
                           "ddpSessionDir": meta["ddpSessionDir"], "wrapper": WRAPPER_REL,
                           "wrapperSha256": job["wrapper"]["sha256"]},
        }
        if et:
            rec["model"].update(et_fields["model"])
            rec["conditions"].update(et_fields["conditions"], warm=False)
            rec["provenance"].update(et_fields["provenance"])
            rec["provenance"]["rssBasis"] += run_cell.EXECUTORCH_RSS_NOTE[et["runner"]]
            rec["outputSample"] = (et_fields["text"] or "")[:200]
        rec["conditions"].update({
            "roundIndex": None, "launchIndex": None,
            "launchID": launch_id, "elapsedScope": "whole-launch",
            "stateAndMemoryScope": "whole-launch",
            "batteryTemperatureInitialC": batt.get("temperatureC"),
            "batteryTemperatureFinalC": end_batt.get("temperatureC"),
            "batteryLevelFinal": end_batt.get("batteryLevel"),
            "thermalGateTimedOut": gate_timed_out,
            "thermalGateTimeoutNonNominal": gate_timed_out and thermal_name != "nominal",
            "initialThermalNonNominal": thermal_name != "nominal",
            "outputTokenBudget": budget,
            "engineCommand": f"{job['env']} {cmd}" if engine_dir else cmd, **launch_checks,
        })
        rec["conditions"]["ddp"] = {
            "sessionId": meta["sessionId"], "jobId": meta["jobId"], "executionId": meta["executionId"],
            "deviceId": job["deviceId"], "deviceKey": job["deviceKey"],
            "buildFingerprint": props["ro.build.fingerprint"], "serial": props["ro.serialno"],
            "product": props["ro.product.device"],
            "jobStartTime": meta["jobStartTime"], "jobEndTime": meta["jobEndTime"],
            "executionStartTime": meta["executionStartTime"], "executionEndTime": meta["executionEndTime"],
            "executionTimeout": f"{job['executionTimeout']}s", "resultType": meta["resultType"], "runIndex": i}
        if run_missing:
            rec["provenance"]["ddpMissing"] = run_missing
        samples = iteration_metrics if paired else [metrics]
        checking = os.environ.get("BENCH_TEXT_CHECK", "1") == "1"
        if paired and checking:
            printed_texts = parsers.context_prompt_texts(console)
        elif engine_dir and binname != "llama-bench" and checking:
            printed_texts = [parsers.llama_cli_reply(console, prompt_text)]
        elif et and checking:
            printed_texts = [et_fields["text"] or ""]
        else:
            printed_texts = None
        any_text_failure = False
        for iteration, sample in enumerate(samples, 1):
            row = {**rec, "id": record_uuid(meta, i, iteration),
                   "metrics": {**metrics, **sample}, "conditions": dict(rec["conditions"]),
                   "provenance": dict(rec["provenance"])}
            if paired:
                row["metrics"] = {k: v for k, v in metrics.items() if k in (
                    "harnessStamp", "initialThermalState", "finalThermalState",
                    "memoryMedianResidentMB", "memoryPeakResidentMB", "firstEver")}
                row["metrics"].update(sample)
                row["metrics"]["coldRun"] = iteration == 1
                if iteration > 1:
                    row["metrics"].pop("firstEver", None)
            row["conditions"]["iterationIndex"] = iteration
            row["conditions"]["regime"] = ("cold" if iteration == 1 else "warm") if paired else "cold-process"
            if printed_texts is not None:
                value = printed_texts[iteration - 1] if iteration <= len(printed_texts) else ""
                verdict = parsers.text_integrity(value)
                row["conditions"]["protocolFlags"] = list(row["conditions"].get("protocolFlags", [])) + verdict["flags"]
                row["conditions"]["textCheck"] = verdict
                row["conditions"]["textOutputSHA256"] = hashlib.sha256(value.encode()).hexdigest()
                text_name = f"{stem}_{stamp}_run{i}_iter{iteration}.decoded.txt"
                with open(os.path.join(out_dir, text_name), "w") as fh:
                    fh.write(value)
                row["provenance"]["decodedText"] = text_name
                any_text_failure |= bool(row["conditions"]["protocolFlags"])
            if cpu_flags or backend_flags:
                row["conditions"]["protocolFlags"] = (list(row["conditions"].get("protocolFlags", []))
                                                      + cpu_flags + backend_flags)
            name = f"{stem}_{stamp}_run{i}{'_iter' + str(iteration) if paired else ''}.json"
            with open(os.path.join(out_dir, name), "w") as fh:
                json.dump(row, fh, indent=2)
        d = metrics.get("decodeTokensPerSecond")
        clean = bool(exit_code == 0 and d and not launch_checks.get("protocolFlags")
                     and not any_text_failure and not backend_flags)
        written.append((os.path.join(out_dir, f"{stem}_{stamp}_run{i}"), clean))
        notes.append(f"{where} run {i}/{job['runs']} {'OK' if clean else f'FAIL(exit={exit_code})'} "
                     f"decode={d} thermal={thermal_name}->{end_name}")
        if cpu_capped:
            notes.append(f"cpu-capped {stem}_{stamp}_run{i}: " + "; ".join(cpu_capped)
                         + " — the record stays, no number pools it (cpu-cap-rule)")
    return written, notes


def execution_dirs(session_id, job_report):
    """-> [(execution report, path of its directory relative to <campaign>/ddp)] from the report's
    output files (gs://<bucket>/automation/sessions/<session>/<job>/<execution>/…), else from the
    job and execution display names."""
    out = []
    for ex in job_report.get("executionReports", []):
        rel = None
        for f in ex.get("outputFiles", []):
            path = (f.get("gcsOutputFile") or {}).get("path", "")
            m = re.search(r"/automation/sessions/(" + re.escape(session_id) + r"/[^/]+/[^/]+)/", path)
            if m:
                rel = m.group(1)
                break
        if rel is None:
            rel = f"{session_id}/{job_report.get('displayName')}/{ex.get('displayName') or 'execution-' + ex.get('id', '')}"
        out.append((ex, rel))
    return out


def write_session(s, session, campaign_dir, out_dir):
    """Records of every job of one finished session (plan s from run_ddp.plan, session = the
    Session resource). -> ([(record stem or None, clean)], notes); FAILURES.txt lines for jobs
    without a clean run per launch."""
    report = session.get("sessionReport", {})
    session_id = session.get("name", "").rsplit("/", 1)[-1]
    by_name = {j["displayName"]: j for j in s["jobs"]}
    written, notes = [], []
    seen = set()
    for jr in report.get("jobReports", []):
        job = by_name.get(jr.get("displayName"))
        if job is None:
            notes.append(f"session {session_id}: job {jr.get('displayName')!r} is not in the plan — skipped")
            continue
        seen.add(job["displayName"])
        for ex, rel in execution_dirs(session_id, jr):
            meta = {"sessionId": session_id, "jobId": jr.get("id"), "jobDisplayName": jr.get("displayName"),
                    "executionId": ex.get("id"), "jobStartTime": jr.get("startTime"), "jobEndTime": jr.get("endTime"),
                    "executionStartTime": ex.get("startTime"), "executionEndTime": ex.get("endTime"),
                    "resultType": (ex.get("result") or {}).get("resultType"), "ddpSessionDir": f"ddp/{rel}"}
            w, n = records_for_execution(job, os.path.join(campaign_dir, "ddp", rel), out_dir, meta)
            written += w
            notes += n
            if not all(clean for _, clean in w):
                with open(os.path.join(out_dir, "FAILURES.txt"), "a") as fh:
                    fh.write(f"{job['cellId']} ddp={job['deviceId']} session={session_id} job={jr.get('displayName')} "
                             f"execution={ex.get('id')} result={meta['resultType']} "
                             f"clean={sum(1 for _, c in w if c)}/{job['runs']}\n")
    for name in sorted(set(by_name) - seen):
        notes.append(f"session {session_id}: planned job {name} has no job report — no record")
        with open(os.path.join(out_dir, "FAILURES.txt"), "a") as fh:
            fh.write(f"{by_name[name]['cellId']} ddp={by_name[name]['deviceId']} session={session_id} "
                     f"job={name} no-job-report\n")
    return written, notes
