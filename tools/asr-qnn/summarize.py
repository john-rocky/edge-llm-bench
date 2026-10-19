#!/usr/bin/env python3
"""The asr-qnn-v1 A2 numbers from the record dir's raw files (docs/asr-qnn-v1.md), recomputed, not copied.

  python3 -I tools/asr-qnn/summarize.py <record dir> --set <librispeech-test-clean set dir> [--py <python with jiwer>]
      [--burst <tag>] [--s4 <tag>] [--cold <tag>] [--warm <tag>] [--window-frames 3000]

Writes <record>/summary/summary.json, <record>/summary/<s4 tag>.score.json and <burst tag>.score.json (the
leaderboard normalizer, corpus WER, tools/omni-eval/score.py through run_score.py), and prints one line per number.

- burst (driver JSONL, pace burst, set S32): RTF_burst = sum of processing seconds / sum of audio seconds over the
  utterances counted (no error, not excluded by the cap rule), the median of the per-utterance RTF, the excluded,
  retaken, wait numbers; the driver's footer is checked against the recomputation.
- sustained (cli JSONL from to_jsonl.py): WER and S / D / I over S4, RTF over the timed utterances with the run's
  largest ceiling fall (an NPU arm's capped run counts, marked: fairness-rules cpu-cap-rule).
- truncation: an utterance is truncated when sherpa printed its "Truncate it to" line inside the utterance's span
  (driver: between its "[asr-qnn] begin" and "end" lines; cli: before its name line, to_jsonl.py), cross-checked
  with the driver's feature_frames > the window.
- load: the recognizer constructor (driver header load_ms; cli "recognizer init time"), cold = the first process
  after the push, warm = a later process. VmHWM: the driver's footer and the 1 s sampler's largest read.
"""
import argparse
import json
import pathlib
import re
import statistics
import subprocess
import sys

TRUNC_RE = re.compile(r"Number of input frames (\d+) is too large\. Truncate it to (\d+) frames\.")
MARK_RE = re.compile(r"^\[asr-qnn\] (begin|end) (\S+) (\S+)")


def jsonl(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def typed(rows, t):
    return [r for r in rows if r.get("type") == t]


def stderr_spans(path):
    """{id: [[frames_in, frames_to], ...]} for the truncation lines inside each attempt's begin / end span."""
    out, cur = {}, None
    if not pathlib.Path(path).exists():
        return out
    for line in open(path, errors="replace"):
        text = line.rstrip("\n").partition("\t")[2]
        m = MARK_RE.match(text)
        if m:
            cur = m.group(2) if m.group(1) == "begin" else None
            if cur is not None:
                out.setdefault(cur, [])
            continue
        t = TRUNC_RE.search(text)
        if t and cur is not None:
            out[cur].append([int(t.group(1)), int(t.group(2))])
    return out


def sampler(path):
    """(largest VmHWM kB, {policy: (min kHz, hw kHz)}) from a device_run.sh .vmhwm.log."""
    if not pathlib.Path(path).exists():
        return None, {}
    cols, hw, hwm, mins = [], {}, None, {}
    for line in open(path):
        if line.startswith("# epoch"):
            cols = line[2:].split()
        elif line.startswith("# cpuinfo_max_freq_kHz"):
            hw = {k: int(v) for k, v in (x.split("=") for x in line.split()[2:]) if v}
        elif line.strip() and not line.startswith("#"):
            d = dict(zip(cols, line.split()))
            if d.get("VmHWM_kB"):
                hwm = max(hwm or 0, int(d["VmHWM_kB"]))
            for k, v in d.items():
                if k.endswith("_scaling_max_kHz") and v.isdigit():
                    p = k[: -len("_scaling_max_kHz")]
                    mins[p] = min(mins.get(p, int(v)), int(v))
    return hwm, {p: (mins[p], hw.get(p)) for p in mins}


def drop(ceil):
    vals = [(1 - lo / hi) * 100 for lo, hi in ceil.values() if hi]
    return round(max(vals), 1) if vals else None


def score(py, rec, tag, manifest, out):
    r = subprocess.run([py, "-I", str(pathlib.Path(__file__).resolve().parent / "run_score.py"), "--manifest", str(manifest),
                        "--pred", str(rec / f"{tag}.jsonl")], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"score {tag}: {r.stderr[-500:]}")
    out.write_text(r.stdout)
    return json.loads(r.stdout)


def driver_run(rec, tag, window):
    rows = jsonl(rec / f"{tag}.jsonl")
    header, footer = typed(rows, "header"), typed(rows, "footer")
    utt = typed(rows, "utterance")
    spans = stderr_spans(rec / f"{tag}.stderr.log")
    hwm, ceil = sampler(rec / f"{tag}.vmhwm.log")
    trunc = {u["id"]: spans.get(u["id"]) for u in utt if spans.get(u["id"])}
    over = [u["id"] for u in utt if (u.get("feature_frames") or 0) > window]
    stdout = rec / f"{tag}.stdout.log"
    qnn = [l.rstrip("\n") for l in open(stdout, errors="replace")] if stdout.exists() else []
    return {
        "header": header[0] if header else {}, "footer": footer[-1] if footer else {}, "rows": utt,
        "warmup": typed(rows, "warmup"), "truncated": trunc, "feature_frames_over_window": over,
        "sampler_vmhwm_kb": hwm, "sampler_ceilings": ceil, "sampler_drop_pct": drop(ceil), "qnn_stdout": qnn,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("record_dir")
    ap.add_argument("--set", required=True)
    ap.add_argument("--py", default=str(pathlib.Path.home() / "parakeet-env/bin/python"))
    ap.add_argument("--burst", default="a2-sherpa-qnn-ctc-30s-S32-burst")
    ap.add_argument("--s4", default="a2-sherpa-qnn-ctc-30s-S4")
    ap.add_argument("--cold", default="smoke3-cold")
    ap.add_argument("--warm", default="warm1")
    ap.add_argument("--window-frames", type=int, default=3000)
    ap.add_argument("--work", default="", help="dir for the burst set's reference manifest (not committed)")
    a = ap.parse_args()
    rec, sdir = pathlib.Path(a.record_dir), pathlib.Path(a.set)
    (rec / "summary").mkdir(exist_ok=True)
    full = {r["id"]: r for r in jsonl(sdir / "manifest.jsonl")}
    s = {"record": str(rec), "window_frames": a.window_frames}
    problems = []

    # burst (driver; the set is the list it ran: S32 since LANE §0 amendment 5)
    if (rec / f"{a.burst}.jsonl").exists():
        b = driver_run(rec, a.burst, a.window_frames)
        rows = b["rows"]
        counted = [r for r in rows if not r.get("error") and not r.get("excluded")]
        audio = sum(r["audio_seconds"] for r in counted)
        proc = sum(r["processing_seconds"] for r in counted)
        waits = [r["wait_s"] for r in rows if r.get("wait_s") is not None]
        drops = [r["cap_drop_pct"] for r in rows if r.get("cap_drop_pct") is not None]
        rtf = proc / audio if audio else None
        fb = b["footer"].get("burst", {})
        if fb and rtf is not None and abs(fb.get("rtf_burst", 0) - rtf) > 1e-3 * rtf:
            problems.append(f"burst: footer rtf_burst {fb.get('rtf_burst')} != recomputed {rtf} (row rounding to 1 ms aside)")
        work = pathlib.Path(a.work) if a.work else rec / "summary"
        work.mkdir(parents=True, exist_ok=True)
        mref = work / "manifest-burst.jsonl"
        mref.write_text("".join(json.dumps(full[r["id"]], ensure_ascii=False) + "\n" for r in rows))
        sc = score(a.py, rec, a.burst, mref, rec / "summary" / f"{a.burst}.score.json")
        if not a.work:
            mref.unlink()
        s["burst"] = {
            "utterances": len(rows), "errors": sum(1 for r in rows if r.get("error")),
            "counted": len(counted), "excluded": sum(1 for r in rows if r.get("excluded") and not r.get("error")),
            "retaken": sum(1 for r in rows if r.get("attempts", 1) > 1),
            "retake_text_differs": sum(1 for r in rows if r.get("retake") and not r["retake"].get("text_same")),
            "counted_audio_seconds": round(audio, 3), "counted_processing_seconds": round(proc, 3),
            "rtf_burst": round(rtf, 6) if rtf else None, "rtfx_burst": round(1 / rtf, 2) if rtf else None,
            "median_utterance_rtf": round(statistics.median(r["processing_seconds"] / r["audio_seconds"] for r in counted), 6) if counted else None,
            "footer_rtf_burst": fb.get("rtf_burst"),
            "wait_sum_s": round(sum(waits), 3), "wait_median_s": statistics.median(waits) if waits else None,
            "wait_max_s": max(waits) if waits else None, "wait_timeouts": sum(1 for r in rows if r.get("wait_timed_out")),
            "cap_drop_pct_max": max(drops) if drops else None, "cap_drop_over_15": sum(1 for d in drops if d > 15),
            "cpus_allowed_seen": sorted({r.get("cpus_allowed") or "" for r in rows}),
            "cpuset_seen": sorted({r.get("cpuset") or "" for r in rows}),
            "truncated": b["truncated"], "feature_frames_over_window": b["feature_frames_over_window"],
            "wer_burst_set_reference_only": {k: sc[k] for k in ("wer_percent", "substitutions", "deletions", "insertions", "reference_words", "empty_hypotheses")},
            "load_ms": b["header"].get("load_ms"), "load_label": b["header"].get("load_label"),
            "vmhwm_kb_footer": b["footer"].get("vmhwm_kb"), "vmhwm_kb_sampler": b["sampler_vmhwm_kb"],
            "sampler_drop_pct": b["sampler_drop_pct"],
            "stage_ms_median": {k: round(statistics.median(r["stage_ms"][k] for r in counted if k in r.get("stage_ms", {})), 3)
                                for k in ("read", "create_stream", "accept_waveform", "decode", "get_result")} if counted else None,
            "warmup": [{k: w.get(k) for k in ("warmup_id", "processing_seconds", "feature_frames", "error")} for w in b["warmup"]],
            "qnn_stdout_lines": b["qnn_stdout"][:20],
            "elapsed_seconds": b["footer"].get("elapsed_seconds"),
        }

    # sustained S4 (cli, to_jsonl.py output)
    if (rec / f"{a.s4}.jsonl").exists():
        rows = jsonl(rec / f"{a.s4}.jsonl")
        utt, footer, header = typed(rows, "utterance"), typed(rows, "footer")[-1], typed(rows, "header")[0]
        sc = score(a.py, rec, a.s4, sdir / "manifest-S4.jsonl", rec / "summary" / f"{a.s4}.score.json")
        s["sustained_S4"] = {
            "utterances": len(utt), "missing": footer.get("missing"),
            "wer_percent": sc["wer_percent"], "substitutions": sc["substitutions"], "deletions": sc["deletions"],
            "insertions": sc["insertions"], "reference_words": sc["reference_words"], "empty_hypotheses": sc["empty_hypotheses"],
            "rtf": footer.get("rtf"), "rtfx": footer.get("rtfx"), "median_utterance_rtf": footer.get("median_utterance_rtf"),
            "cpu_cap_drop_pct": footer.get("cpu_cap_drop_pct"), "cpu_ceilings": footer.get("cpu_ceilings"),
            "cap_mark": f"cpu-capped, counted (accelerator arm), max drop {footer.get('cpu_cap_drop_pct')} %" if (footer.get("cpu_cap_drop_pct") or 0) > 0 else "not capped",
            "truncated": footer.get("truncated_utterances"),
            "load_seconds": header.get("load_seconds"), "load_line": header.get("load_line"),
            "vmhwm_kb_sampler": footer.get("peak_vmhwm_kb"),
            "process_wall_seconds": [x.get("process_wall_seconds") for x in footer.get("attempts", [])],
            "hangs": footer.get("hangs"), "problems": footer.get("problems"),
        }
        if "burst" in s:  # the same model and code path: the texts of the burst set's utterances should agree
            s4_text = {u["id"]: u["text"] for u in utt}
            b_rows = jsonl(rec / f"{a.burst}.jsonl")
            pairs = [(u["id"], u["text"], s4_text.get(u["id"])) for u in typed(b_rows, "utterance")]
            diff = [p for p in pairs if p[2] is not None and p[1] != p[2]]
            s["text_burst_vs_sustained"] = {"compared": sum(1 for p in pairs if p[2] is not None), "same": sum(1 for p in pairs if p[2] is not None and p[1] == p[2]),
                                            "differ_examples": diff[:3]}

    # load and memory of the short processes
    for key, tag in (("cold", a.cold), ("warm", a.warm)):
        if (rec / f"{tag}.jsonl").exists():
            d = driver_run(rec, tag, a.window_frames)
            s[f"load_{key}"] = {
                "tag": tag, "load_ms": d["header"].get("load_ms"), "load_label": d["header"].get("load_label"),
                "utterances": len(d["rows"]), "texts": [[r["id"], r["text"]] for r in d["rows"]],
                "errors": [r["id"] for r in d["rows"] if r.get("error")], "truncated": d["truncated"],
                "vmhwm_kb_footer": d["footer"].get("vmhwm_kb"), "qnn_stdout_lines": d["qnn_stdout"][:20],
                "libs_mapped_after_load": d["header"].get("libs_mapped_after_load"),
            }

    # the phone's state around the runs
    probes = {}
    for p in sorted(rec.glob("probe-*.json")):
        d = json.loads(p.read_text())
        probes[d["label"]] = {"battery_C": d["battery"]["temperature_C"], "thermal_status": d["thermal_status"],
                              "hal": {t["name"]: t["value_C"] for t in d.get("hal_temperatures", []) if t["name"] in ("AP", "SKIN", "BAT")},
                              "ceilings": {k: [v["scaling_max_freq_kHz"], v["cpuinfo_max_freq_kHz"]] for k, v in d["policies"].items()}}
    s["probes"] = probes
    s["problems"] = problems
    (rec / "summary" / "summary.json").write_text(json.dumps(s, indent=2, ensure_ascii=False) + "\n")
    for k, v in s.items():
        if isinstance(v, dict) and k not in ("probes",):
            print(k, json.dumps({kk: vv for kk, vv in v.items() if kk not in ("rows", "qnn_stdout_lines", "texts", "cpu_ceilings", "libs_mapped_after_load")}, ensure_ascii=False)[:1500])
    print("problems:", problems)


if __name__ == "__main__":
    main()
