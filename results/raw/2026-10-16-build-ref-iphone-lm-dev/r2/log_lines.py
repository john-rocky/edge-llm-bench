#!/usr/bin/env python3
"""K/r2/log_lines.py <name>=<ddp-out dir> ... — counts from each run's raw log (ddp-out/run<i>.log: the sampler
lines and the engine's output) for K/ROUND2.md "op と delegate の観察" (read only; prints text):
delegate lines ("Replacing N out of M node(s) with delegate (D) node, yielding P partitions for subgraph S"),
registered accelerators (RegisterAccelerator name=), NPU registry warnings, E / F lines (glog E/F, ERROR: / FATAL:),
Invalid decode, the GPU program-cache lines, the Mali weights-preparation warning, Init Executor ms, the
BenchmarkInfo rates; then, per pair of named dirs, the log sources (file.cc:line) of run 1 that only one has."""
import os
import re
import sys
from collections import Counter

REPLACING = re.compile(r"Replacing (\d+) out of (\d+) node\(s\) with delegate \((\S+)\) node, yielding (\d+) partitions"
                       r" for subgraph (\d+)(?: \(([^)]*)\))?")
REGISTER = re.compile(r"RegisterAccelerator: ptr=\S+, name=(.+)$")
EF = re.compile(r"^(?:[EF]\d{4} |ERROR: |FATAL: |F \d|E \d)")
SOURCE = re.compile(r"(?:\[([A-Za-z0-9_./-]+\.(?:cc|h|cpp|c)):\d+\]|\s([A-Za-z0-9_./-]+\.(?:cc|h|cpp|c)):\d+\])")
LEVEL = re.compile(r"^(INFO|WARNING|ERROR|VERBOSE|DEBUG): |^([IWEF])\d{4} ")


def counts(path):
    text = open(path, errors="replace").read()
    lines = text.splitlines()
    out = {"replacing": [m.groups() for m in REPLACING.finditer(text)],
           "registered": Counter(m.group(1).strip() for l in lines for m in [REGISTER.search(l)] if m),
           "npu_not_found": sum("NPU accelerator could not be loaded" in l for l in lines),
           "e_f_lines": [l[:160] for l in lines if EF.match(l)],
           "invalid_decode": text.lower().count("invalid decode"),
           "gpu_api_from_serialized": text.count("Initializing OpenCL-based API from serialized data"),
           "gpu_context_from_serialized": text.count("Initialized InferenceContext from serialized data"),
           "weights_prep_disabled": text.count("Weights preparation on Gpu is disabled"),
           "webgpu_mentions": sum("webgpu" in l.lower() and "RegisterAccelerator" not in l
                                  and "Weights preparation on Gpu is disabled" not in l for l in lines),
           "levels": Counter((m.group(1) or m.group(2)) for l in lines for m in [LEVEL.match(l)] if m)}
    for key, rx in (("init_executor_ms", r"Init Executor: ([0-9.]+) ms"), ("ttft_s", r"Time to first token: ([0-9.]+) s"),
                    ("prefill", r"Prefill Speed: ([0-9.]+) tokens/sec"), ("decode", r"Decode Speed: ([0-9.]+) tokens/sec"),
                    ("prefill_tokens", r"Prefill Turn 1: Processed (\d+) tokens"),
                    ("decode_tokens", r"Decode Turn 1: Processed (\d+) tokens")):
        m = re.search(rx, text)
        out[key] = m.group(1) if m else None
    out["sources"] = Counter((m.group(1) or m.group(2)).rsplit("/", 1)[-1] for l in lines for m in [SOURCE.search(l)] if m)
    return out


def main(pairs):
    named = []
    for p in pairs:
        name, _, d = p.partition("=")
        named.append((name, d))
        print(f"=== {name}")
        for i in (1, 2, 3):
            path = os.path.join(d, f"run{i}.log")
            if not os.path.isfile(path):
                print(f"run{i}: no run{i}.log")
                continue
            c = counts(path)
            print(f"run{i}: registered {dict(c['registered'])}; NPU-not-found warnings {c['npu_not_found']}; "
                  f"E/F lines {len(c['e_f_lines'])}; Invalid decode {c['invalid_decode']}; "
                  f"'Initializing OpenCL-based API from serialized data' {c['gpu_api_from_serialized']}; "
                  f"'Initialized InferenceContext from serialized data' {c['gpu_context_from_serialized']}; "
                  f"weights-preparation-disabled {c['weights_prep_disabled']}; other WebGPU lines {c['webgpu_mentions']}; "
                  f"levels {dict(c['levels'])}")
            print(f"      Init Executor {c['init_executor_ms']} ms, TTFT {c['ttft_s']} s, prefill {c['prefill_tokens']} tok "
                  f"{c['prefill']} tok/s, decode {c['decode_tokens']} tok {c['decode']} tok/s")
            for g in c["replacing"]:
                print(f"      delegate {g[2]}: {g[0]}/{g[1]} nodes, {g[3]} partition(s), subgraph {g[4]} ({g[5]})")
            for l in c["e_f_lines"]:
                print(f"      E/F: {l}")
    for k in range(0, len(named) - 1, 2):
        (a, da), (b, db) = named[k], named[k + 1]
        ca, cb = counts(os.path.join(da, "run1.log")), counts(os.path.join(db, "run1.log"))
        only_a = sorted(set(ca["sources"]) - set(cb["sources"]))
        only_b = sorted(set(cb["sources"]) - set(ca["sources"]))
        moved = sorted(s for s in set(ca["sources"]) & set(cb["sources"]) if ca["sources"][s] != cb["sources"][s])
        print(f"\n=== run 1 log sources: {a} vs {b}")
        print(f"only in {a}: {', '.join(f'{s} x{ca['sources'][s]}' for s in only_a) or 'none'}")
        print(f"only in {b}: {', '.join(f'{s} x{cb['sources'][s]}' for s in only_b) or 'none'}")
        print(f"in both, other line counts: {', '.join(f'{s} {ca['sources'][s]}/{cb['sources'][s]}' for s in moved) or 'none'}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
