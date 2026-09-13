#!/usr/bin/env python3
"""Write the <tag>_<backend>.prof.json (and .ctrl.json) records for a hand-run Mac pair from
its logs - the shape android/bench/run_profile.py writes (schema/result.v1.json), so that
scripts/profile/profile_report.py reads the decode-step count and exit code off the record.
Every number comes from the log; nothing is typed in.

  python3 write_records.py <profiles-dir> <tag> <backend> --bin <litert_lm_advanced_main> \
      --model <bundle> --engine-version v0.16.0 [--model-id litert-community/Qwen3-0.6B] \
      [--quant "INT4 (mixed, blockwise gs32)"]
"""
import argparse, hashlib, json, os, platform, re, statistics, subprocess, sys, time, uuid


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sysctl(key):
    return subprocess.run(["sysctl", "-n", key], capture_output=True, text=True).stdout.strip()


def parse(log):
    text = open(log, errors="replace").read()
    m = {}
    g = lambda pat, cast=float: (lambda r: cast(r.group(1)) if r else None)(re.search(pat, text))
    m["firstTokenLatencyMS"] = (lambda v: round(v * 1000, 1) if v is not None else None)(g(r"Time to first token: ([0-9.]+) s"))
    m["promptTokenCount"] = g(r"Prefill Turn 1: Processed (\d+) tokens", int)
    m["promptTokensPerSecond"] = g(r"Prefill Speed: ([0-9.]+) tokens/sec")
    m["generatedTokenCount"] = g(r"Decode Turn 1: Processed (\d+) tokens", int)
    m["decodeTokensPerSecond"] = g(r"Decode Speed: ([0-9.]+) tokens/sec")
    m["initTotalMS"] = g(r"Init Total: ([0-9.]+) ms")
    rss = [int(x) for x in re.findall(r"^VmRSS:\s+(\d+) kB", text, re.M)]
    m["memoryMedianResidentMB"] = round(statistics.median(rss) / 1024, 2) if rss else None
    m["memoryPeakResidentMB"] = round(max(rss) / 1024, 2) if rss else None
    ec = re.search(r"^EXIT_CODE=(\d+)", text, re.M)
    acc = re.search(r"Dynamically loaded GPU accelerator\(([^)]+)\) registered", text)
    return m, (int(ec.group(1)) if ec else None), (acc.group(1) if acc else None), text


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir"); ap.add_argument("tag"); ap.add_argument("backend", choices=["cpu", "gpu"])
    ap.add_argument("--bin", required=True); ap.add_argument("--model", required=True)
    ap.add_argument("--engine-version", required=True)
    ap.add_argument("--model-id", default="litert-community/Qwen3-0.6B")
    ap.add_argument("--quant", default="INT4 (mixed, blockwise gs32)")
    ap.add_argument("--context-tokens", type=int, default=1024)
    a = ap.parse_args()
    p, d = re.search(r"_(\d+)x(\d+)_ctx", a.tag).groups()
    bin_sha, model_sha = sha256(a.bin), sha256(a.model)
    device = {"modelIdentifier": sysctl("hw.model"), "modelName": "Mac Studio", "systemName": "macOS",
              "systemVersion": platform.mac_ver()[0], "soc": sysctl("machdep.cpu.brand_string"),
              "memoryGB": int(sysctl("hw.memsize")) // (1 << 30)}
    ctrl_id = None
    for kind in ("ctrl", "prof"):
        log = os.path.join(a.dir, f"{a.tag}_{a.backend}_{kind}.log")
        if not os.path.exists(log):
            print(f"missing {log}", file=sys.stderr); return 1
        metrics, ec, acc, _ = parse(log)
        rid = str(uuid.uuid4())
        rec = {"schemaVersion": 1, "id": rid, "runtime": f"litert-lm-{a.backend}",
               "engineVersion": a.engine_version, "engineArtifact": bin_sha,
               "model": {"id": a.model_id, "quantization": a.quant, "file": os.path.basename(a.model), "sha256": model_sha},
               "task": f"native-benchmark-{p}x{d}",
               "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getmtime(log))),
               "device": device,
               "conditions": {"profiling": kind == "prof", "sampler": "engine-default", "cpuAffinity": "none",
                              "contextTokens": a.context_tokens, "gpuAccelerator": acc, "exitCode": ec},
               "metrics": {**{k: v for k, v in metrics.items() if v is not None}, "coldRun": True,
                           "harnessStamp": "2026-09-13-mac-native-cli-by-hand" + ("+profiling" if kind == "prof" else "")},
               "provenance": {"rawLog": os.path.basename(log),
                              "harness": "results/raw/2026-09-13-profile-smoke-mac/profiles/run_pair_mac.sh (run by hand; not ./bench profile)",
                              "engineBuild": "LiteRT-LM tag v0.16.0 (924e79c9), 'bazel build //runtime/engine:litert_lm_advanced_main' on this host, the tag's prebuilt/macos_arm64 dylibs beside the binary"}}
        if kind == "ctrl":
            ctrl_id = rid
            rec["provenance"]["note"] = "control run: the unprofiled twin of the .prof.json record beside it; the warm-up (cache-building) run before it is <tag>_<backend>_warmup.log"
        else:
            rec["provenance"].update({"controlRecord": ctrl_id, "controlLog": f"{a.tag}_{a.backend}_ctrl.log",
                                      "note": "profiled run: the rate carries the profiler's cost and is not a speed row"})
        out = os.path.join(a.dir, f"{a.tag}_{a.backend}.{kind}.json")
        json.dump(rec, open(out, "w"), indent=2)
        print(f"wrote {out}: exit={ec} decode={metrics['decodeTokensPerSecond']} prefill={metrics['promptTokensPerSecond']} accelerator={acc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
