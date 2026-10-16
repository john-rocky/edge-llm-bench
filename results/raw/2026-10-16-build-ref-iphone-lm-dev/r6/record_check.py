#!/usr/bin/env python3
"""The retake's records, checked key by key: python3 -I K/r6/record_check.py <campaign dir> <archive sha256> <session id>...
For each session: its records in <campaign>/device-jsonl/ (by conditions.ddp.sessionId), one line per run with the
values the round reports, then the checks (engine, artifact, device, DDP stamps, the thermal gate keys, runtime by
arm, decode, reply). Prints ALL OK or the failures; exit 0 / 1."""
import glob
import json
import os
import sys

camp, archive_sha, sessions = sys.argv[1], sys.argv[2], sys.argv[3:]
ARTIFACT = "CLiteRTLM.xcframework.zip@v0.18.0 sha256:d765b99592d4ec3d0c9e2bd69469454af06c834861340672da1891c0c121c347"
CELLS = {"litert-community/Qwen3-1.7B": "gpu", "litert-community/Qwen3-1.7B/int8": "cpu"}
recs = [(f, json.load(open(f))) for f in sorted(glob.glob(os.path.join(camp, "device-jsonl", "*.json")))]
fails = []


def num(v, digits=2):
    return "None" if v is None else f"{v:.{digits}f}"


def need(cond, what):
    if not cond:
        fails.append(what)


for sid in sessions:
    mine = sorted(((f, r) for f, r in recs if ((r.get("conditions") or {}).get("ddp") or {}).get("sessionId") == sid),
                  key=lambda x: x[1].get("timestamp") or "")
    print(f"== {sid}: {len(mine)} record(s)")
    need(len(mine) == 4, f"{sid}: {len(mine)} records, not 4")
    for i, (f, r) in enumerate(mine, 1):
        m, d, c = r.get("metrics") or {}, r.get("device") or {}, (r.get("conditions") or {}).get("ddp") or {}
        model = (r.get("model") or {}).get("id")
        backend = (c.get("argv") or [""])[-1]
        print(f"  run {c.get('runIndex')}: {os.path.basename(f)} runtime={r.get('runtime')} model={model} "
              f"decode={num(m.get('decodeTokensPerSecond'))} cold={m.get('coldRun')} initial={m.get('initialThermalState')} "
              f"final={m.get('finalThermalState')} gate={c.get('thermalGateWaitedSeconds')}/{c.get('thermalGateState')}/"
              f"{c.get('thermalGateTimedOut')} load={num(m.get('loadTimeSeconds'), 1)}s tokens={m.get('generatedTokenCount')} "
              f"{m.get('stopReason')}")
        need(r.get("engineVersion") == "v0.18.0", f"{f}: engineVersion {r.get('engineVersion')}")
        need(r.get("engineArtifact") == ARTIFACT, f"{f}: engineArtifact")
        need(d.get("modelIdentifier") == "iPhone17,1" and d.get("buildConfiguration") == "Release",
             f"{f}: device {d.get('modelIdentifier')} {d.get('buildConfiguration')}")
        need(d.get("ddp") == {"deviceId": "iphone16pro-18-3", "displayName": "iPhone 16 Pro", "osVersion": "18.3"},
             f"{f}: device.ddp {d.get('ddp')}")
        need(c.get("runIndex") == i and c.get("resultType") == "PASSED" and c.get("xcodeVersion") == "xcode-26-2"
             and c.get("archiveSha256") == archive_sha and (c.get("archiveBuildInfo") or {}).get("litert_lm") == "v0.18.0",
             f"{f}: conditions.ddp runIndex / resultType / xcode / archive")
        need(isinstance(c.get("thermalGateWaitedSeconds"), int) and isinstance(c.get("thermalGateTimedOut"), bool)
             and c.get("thermalGateState") in ("nominal", "fair", "serious", "critical"),
             f"{f}: thermalGate* {c.get('thermalGateWaitedSeconds')!r} {c.get('thermalGateTimedOut')!r} {c.get('thermalGateState')!r}")
        need(CELLS.get(model, backend) == backend and r.get("runtime") == ("litert-lm" if backend == "gpu" else "litert-lm-cpu"),
             f"{f}: runtime {r.get('runtime')} for --litert-backend {backend}")
        need((m.get("decodeTokensPerSecond") or 0) > 0 and m.get("coldRun") == (i == 1), f"{f}: decode / coldRun")
        need(len((r.get("outputSample") or "").strip()) > 60, f"{f}: outputSample")
    samples = sorted({(r.get("outputSample") or "")[:200] for _, r in mine})
    print(f"  texts: {len(samples)} distinct of {len(mine)}; run 1 first 100 characters: "
          f"{json.dumps((mine[0][1].get('outputSample') or '')[:100]) if mine else ''}")
print("ALL OK" if not fails else "FAILURES:\n" + "\n".join(fails))
sys.exit(1 if fails else 0)
