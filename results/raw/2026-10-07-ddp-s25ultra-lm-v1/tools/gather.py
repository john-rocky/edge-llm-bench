#!/usr/bin/env python3
"""Copy DDP LiteRT-LM sessions into the campaign dir and read the first (cache-writing) process from the log.

gather.py <campaign dir> <session id>...
  ddp-session/<session>/<job>/metrics.pb, metrics.pb.txt (protoc --decode), provenance.txt,
  logcat-process.txt (the logcat lines of the benchmark binary's two processes only)
Prints one JSON line per job: what the first process reported (cold init, its one prefill/decode).
"""
import json
import pathlib
import re
import shutil
import subprocess
import sys

CACHE = pathlib.Path.home() / ".cache" / "litert-cli" / "ddp"
PROTO_ROOT = pathlib.Path.home() / ".cache" / "litert-samples-benchmark" / "litert-lm" / "v0.17.0"
LINE = re.compile(r"^\d\d-\d\d \d\d:\d\d:\d\d\.\d+\s+(\d+)\s+(\d+) \w (\S+)\s*: ?(.*)$")

campaign = pathlib.Path(sys.argv[1])
for sid in sys.argv[2:]:
    for job in sorted(d for d in (CACHE / sid).iterdir() if d.is_dir()):
        out = campaign / "ddp-session" / sid / job.name
        out.mkdir(parents=True, exist_ok=True)
        for name in ("metrics.pb", "provenance.txt"):
            if (job / name).exists():
                shutil.copyfile(job / name, out / name)
        if (job / "metrics.pb").exists():
            with open(job / "metrics.pb", "rb") as f:
                run = subprocess.run(["protoc", "--proto_path=.", "--decode=litert.lm.proto.LitertLmMetricsList",
                                      "runtime/proto/litert_lm_metrics.proto"], cwd=PROTO_ROOT, stdin=f,
                                     capture_output=True, text=True)
            if run.returncode == 0:
                (out / "metrics.pb.txt").write_text(run.stdout)
            else:
                print(f"protoc failed on {sid}/{job.name}: {run.stderr.strip()}", file=sys.stderr)
        lines = (job / "logcat.txt").read_text(errors="replace").splitlines()
        pids = []
        for l in lines:
            m = LINE.match(l)
            if m and "litert_lm_lib.cc" in m.group(4) and "Choose backend" in m.group(4) and m.group(1) not in pids:
                pids.append(m.group(1))
        kept = [l for l in lines if (m := LINE.match(l)) and m.group(1) in pids]
        (out / "logcat-process.txt").write_text("\n".join(kept) + "\n")
        first = {"session": sid, "job": job.name, "pids": pids, "process_lines": len(kept), "logcat_lines": len(lines)}
        if pids:
            mine = [m.group(4) for l in lines if (m := LINE.match(l)) and m.group(1) == pids[0]]
            text = "\n".join(mine)
            for key, pat in (("cold_init_total_ms", r"Init Total: ([\d.]+) ms"), ("first_prefill_tok_s", r"Prefill Speed: ([\d.]+)"),
                             ("first_decode_tok_s", r"Decode Speed: ([\d.]+)"), ("first_ttft_s", r"Time to first token: ([\d.]+) s"),
                             ("first_peak_private_mb", r"Peak private footprint: ([\d.]+)MB")):
                m = re.search(pat, text)
                first[key] = float(m.group(1)) if m else None
            errs = [m.group(4) for l in lines if (m := LINE.match(l)) and m.group(1) in pids and m.group(3) == "native"
                    and re.search(r"Failed to|Invalid decode|INTERNAL:|FATAL", m.group(4))]
            first["errors"] = errs[:3]
        print(json.dumps(first))
