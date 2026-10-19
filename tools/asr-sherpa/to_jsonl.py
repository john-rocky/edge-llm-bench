#!/usr/bin/env python3
"""Turn one device_run.sh capture of sherpa-onnx into the JSONL tools/omni-eval/score.py reads.

  to_jsonl.py <record dir> <tag> --manifest manifest-S4.jsonl --lookup manifest.jsonl
              [--cmd <tag>.cmd] [--hw-probe probe-<tag>-before.json] > <tag>.jsonl

Reads <tag>[.a<k>].{stdout.log,stderr.log,exit,vmhwm.log,cpus,scp} and <tag>.hangs from the
record dir. Writes a header, one line per utterance of --manifest the process returned
(id, text, audio_seconds, processing_seconds), and a footer.

Timing (sherpa-onnx-offline-parallel --batch-size=1 --nj=1): device_run.sh stamps every stderr
line with the phone's $EPOCHREALTIME as it arrives. The binary prints a file's path to stderr
after decoding it, then the JSON result to stdout, then "----" to stderr, then reads the next
file. An utterance's processing seconds = the stamp of its path line minus the stamp of the
"----" line before it, so the span covers reading this file, its feature extraction and its
decode. The first file of each attempt is the warm-up file W: the binary decodes it once
untimed before its loop and the start of its timed decode is not visible; W's result goes to
the footer, not to the utterances. A binary that decodes all its files in one batch (the
plain sherpa-onnx-offline) gets processing_seconds = null (do not score it with score.py).
"""
import argparse
import json
import pathlib
import re
import statistics
import sys

TIMING = ("processing_seconds = phone $EPOCHREALTIME stamp of the stderr line naming the file "
          "minus the stamp of the previous file's '----' line (covers reading this file, its "
          "feature extraction and its decode); model load excluded")
BINARY_RTF_NOTE = ("binary_rtf_line is the binary's own print: its numerator sums the timed "
                   "batches (W's timed decode included) in whole milliseconds, its denominator "
                   "counts W twice (the untimed warm-up adds W's seconds too); not used as the RTF")
TEXT_RE = re.compile(r'"text": "((?:[^"\\]|\\.)*)"')


def load_jsonl(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def result_text(line):
    try:
        return json.loads(line)["text"]
    except (json.JSONDecodeError, KeyError):  # e.g. -inf in ys_log_probs; text is std::quoted
        m = TEXT_RE.search(line)
        if not m:
            raise
        return re.sub(r"\\(.)", r"\1", m.group(1))


def read_attempt(base, list_path):
    """One process: its list, stderr events, stdout results, exit line, memory samples."""
    entries = [l.split() for l in open(list_path) if l.strip()]
    by_path = {p: i for i, (_, p) in enumerate(entries)}
    names, seps = [], []  # names: (stamp, list index, stamp of the "----" line just before it)
    last_sep = None
    info = {"stamps": 0}
    for line in open(f"{base}.stderr.log", errors="replace"):
        ts, _, text = line.rstrip("\n").partition("\t")
        info["stamps"] += 1
        t = float(ts)
        info.setdefault("first_stamp", t)
        info["last_stamp"] = t
        if text in by_path:
            names.append((t, by_path[text], last_sep))
            last_sep = None
        elif text == "----":
            seps.append(t)
            last_sep = t
        elif m := re.search(r"recognizer init time: ([0-9.]+)", text):
            info["load_seconds"] = float(m.group(1))
            info["load_line"] = text
        elif m := re.search(r"recognizer created in ([0-9.]+) s", text):
            info["load_seconds"] = float(m.group(1))
            info["load_line"] = text
        elif m := re.match(r"Elapsed seconds: ([0-9.]+) s", text):
            info["binary_elapsed_seconds"] = float(m.group(1))
        elif text.startswith("Real time factor (RTF):"):
            info["binary_rtf_line"] = text
        elif text.startswith("SPEEDUP:"):
            info["binary_speedup_line"] = text
        elif m := re.match(r"num threads: (\d+)", text):
            info["num_threads"] = int(m.group(1))
        elif m := re.match(r"decoding method: (\S+)", text):
            info["decoding_method"] = m.group(1)
    raw = open(f"{base}.stdout.log", errors="replace").read()
    results = raw.split("\n")[:-1]  # a last line without its newline was cut by a kill
    exit_line = pathlib.Path(f"{base}.exit").read_text().strip() if pathlib.Path(f"{base}.exit").exists() else ""
    ex = dict(kv.split("=", 1) for kv in exit_line.split() if "=" in kv)
    samples, hw = [], {}
    cols = []
    vm = pathlib.Path(f"{base}.vmhwm.log")
    if vm.exists():
        for line in open(vm):
            if line.startswith("# epoch"):
                cols = line[2:].split()
            elif line.startswith("# cpuinfo_max_freq_kHz"):
                hw = {k: int(v) for k, v in (x.split("=") for x in line.split()[2:]) if v}
            elif line.strip() and not line.startswith("#"):
                samples.append(dict(zip(cols, line.split())))
    cpus = pathlib.Path(f"{base}.cpus")
    return {
        "entries": entries, "names": names, "seps": seps, "results": results, "info": info,
        "exit": ex, "samples": samples, "hw": hw,
        "cpus_allowed_list": cpus.read_text().strip() if cpus.exists() else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("record_dir")
    ap.add_argument("tag")
    ap.add_argument("--manifest", required=True, help="the set scored (manifest-S4.jsonl)")
    ap.add_argument("--lookup", required=True, help="manifest.jsonl of the full set (W's seconds)")
    ap.add_argument("--cmd", default="")
    ap.add_argument("--batch", action="store_true", help="one-batch binary: no per-file timing")
    args = ap.parse_args()

    rec = pathlib.Path(args.record_dir)
    want = [r["id"] for r in load_jsonl(args.manifest)]
    seconds = {r["id"]: r["seconds_written"] for r in load_jsonl(args.lookup)}
    attempts = []
    k = 1
    while True:
        base = rec / (args.tag if k == 1 else f"{args.tag}.a{k}")
        lst = rec / (f"{args.tag}.scp" if k == 1 else f"{args.tag}.a{k}.scp")
        if not pathlib.Path(f"{base}.stderr.log").exists():
            break
        attempts.append(read_attempt(base, lst))
        k += 1
    if not attempts:
        sys.exit(f"no capture for {args.tag} in {rec}")

    utts, warmups, problems = {}, [], []
    for a_i, a in enumerate(attempts, 1):
        names, seps, results, entries = a["names"], a["seps"], a["results"], a["entries"]
        if [i for _, i, _ in names] != list(range(len(names))):
            problems.append(f"attempt {a_i}: stderr file order differs from the list order")
        for j, (t_name, i, t_sep) in enumerate(names):
            uid = entries[i][0]
            if j >= len(results):
                continue  # finished, but its result was still buffered when the process died
            text = result_text(results[j])
            if args.batch:
                proc = None
            elif j == 0:
                warmups.append({"attempt": a_i, "id": uid, "text": text,
                                "audio_seconds": seconds[uid]})
                continue
            else:
                proc = t_name - t_sep if t_sep is not None else None
            if uid in utts:
                problems.append(f"{uid} returned twice; the later attempt's line is kept")
            utts[uid] = {"type": "utterance", "id": uid, "text": text,
                         "audio_seconds": seconds[uid], "processing_seconds": proc,
                         "session_create_seconds": 0.0, "attempt": a_i, "t_end_epoch": t_name,
                         "error": ""}
    extra = [u for u in utts if u not in set(want)]
    missing = [u for u in want if u not in utts]
    if extra:
        problems.append(f"{len(extra)} returned ids are not in the manifest: {extra[:3]}")

    first = attempts[0]
    printed = lambda k: next((a["info"][k] for a in attempts if k in a["info"]), None)  # a killed process prints no tail
    cmd = pathlib.Path(args.cmd).read_text().strip() if args.cmd else ""
    header = {
        "type": "header", "model_name": "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8",
        "backend": "cpu", "runtime": "sherpa-onnx v1.13.8 (k2-fsa release, android-aarch64-termux-static)",
        "num_threads": printed("num_threads"),
        "decoding_method": printed("decoding_method"),
        "cmd": cmd, "utterances": len(want),
        "load_seconds": first["info"].get("load_seconds"), "load_line": first["info"].get("load_line"),
    }
    print(json.dumps(header))
    ordered = [utts[u] for u in want if u in utts]
    for u in ordered:
        print(json.dumps(u, ensure_ascii=False))

    audio = sum(u["audio_seconds"] for u in ordered)
    timed = [u for u in ordered if u["processing_seconds"] is not None]
    proc = sum(u["processing_seconds"] for u in timed)
    per = [u["processing_seconds"] / u["audio_seconds"] for u in timed]
    peak_hwm = max((int(s["VmHWM_kB"]) for a in attempts for s in a["samples"] if s.get("VmHWM_kB")), default=None)
    peak_rss = max((int(s["VmRSS_kB"]) for a in attempts for s in a["samples"] if s.get("VmRSS_kB")), default=None)
    ceilings, drop = {}, None
    for a in attempts:
        for pol, hw in a["hw"].items():
            vals = [int(s[f"{pol}_scaling_max_kHz"]) for s in a["samples"] if s.get(f"{pol}_scaling_max_kHz")]
            if not vals:
                continue
            c = ceilings.setdefault(pol, {"hw_kHz": hw, "min_kHz": min(vals), "samples": 0})
            c["min_kHz"] = min(c["min_kHz"], min(vals))
            c["samples"] += len(vals)
    if ceilings:
        drop = round(max((1 - c["min_kHz"] / c["hw_kHz"]) * 100 for c in ceilings.values()), 1)
    hangs_file = rec / f"{args.tag}.hangs"
    footer = {
        "type": "footer", "utterances": len(ordered), "missing": missing,
        "failures": len(missing), "total_audio_seconds": round(audio, 4),
        "total_processing_seconds": round(proc, 6) if timed else None,
        "timed_utterances": len(timed),
        "rtf": round(proc / sum(u["audio_seconds"] for u in timed), 6) if timed else None,
        "rtfx": round(sum(u["audio_seconds"] for u in timed) / proc, 3) if timed else None,
        "median_utterance_rtf": round(statistics.median(per), 6) if per else None,
        "timing_definition": None if args.batch else TIMING,
        "warmup": warmups,
        "attempts": [{
            "attempt": i, "exit": a["exit"], "load_seconds": a["info"].get("load_seconds"),
            "binary_elapsed_seconds": a["info"].get("binary_elapsed_seconds"),
            "binary_rtf_line": a["info"].get("binary_rtf_line"),
            "binary_speedup_line": a["info"].get("binary_speedup_line"),
            "process_wall_seconds": round(float(a["exit"]["t1"]) - float(a["exit"]["t0"]), 3) if a["exit"].get("t1") else None,
            "files_finished": len(a["names"]), "results": len(a["results"]),
            "cpus_allowed_list": a["cpus_allowed_list"], "vm_samples": len(a["samples"]),
            "battery_temp_first_last": [a["samples"][0].get("battery_temp_0.1C"), a["samples"][-1].get("battery_temp_0.1C")] if a["samples"] else None,
        } for i, a in enumerate(attempts, 1)],
        "binary_rtf_note": None if args.batch else BINARY_RTF_NOTE,
        "process_wall_note": "t1 - t0 around the exec on the phone clock; includes the binary's two 10 s sleeps, the load and the untimed warm-up: a reference value",
        "hangs": hangs_file.read_text().splitlines() if hangs_file.exists() else [],
        "peak_vmhwm_kb": peak_hwm, "peak_vmrss_kb": peak_rss,
        "peak_rss_bytes": peak_hwm * 1024 if peak_hwm else 0,
        "cpu_ceilings": ceilings, "cpu_cap_drop_pct": drop,
        "problems": problems,
    }
    print(json.dumps(footer, ensure_ascii=False))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
