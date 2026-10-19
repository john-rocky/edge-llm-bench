#!/usr/bin/env python3
"""Score and summarize one AsrBenchTest run (asr-litert-app-v1, docs/asr-litert-app-v1.md).

  summarize.py <REC>/<tag>.jsonl [<REC>/<tag>-p2.jsonl ...] --set-dir <prep set dir> [--rows S4|full|S4:<N>]
               [--tag <name>] [--out <REC>/summary]

Several JSONL files are one run split over holds (the second resumed after the first one's last
utterance); they are joined in the order given and named by --tag (default: the first file's name).

Writes <out>/<tag>.score.json = tools/omni-eval/score.py's output (Open ASR Leaderboard normalizer,
corpus WER, S/D/I) against the manifest of the rows the run covered, and <out>/<tag>.summary.json:
RTF = sum of utterance wall seconds / sum of audio seconds over the rows without an error (model
load excluded), RTFx, median utterance RTF, per-window stage times, empty windows, every process's
load, memory, heat, CPU ceilings (cpu-cap-rule depth over the policies of the CPUs the process was
allowed on) and the witnesses (WAV chain of the selection, model sha256, native library sha256).
"""
import argparse
import json
import os
import pathlib
import statistics
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]


def load(path):
    return [json.loads(line) for line in open(path) if line.strip()]


def pct(values, q):
    if not values:
        return None
    s = sorted(values)
    return s[min(len(s) - 1, int(round(q * (len(s) - 1))))]


def cpu_cap(footer):
    """Largest (1 - min / hw) * 100 over the policies whose CPUs the process may run on."""
    allowed = set()
    for spec in footer.get("cpus_allowed_seen") or []:
        for part in spec.split(","):
            a, _, b = part.partition("-")
            allowed.update(range(int(a), int(b or a) + 1))
    out = {}
    for name, p in (footer.get("cpu_ceilings") or {}).items():
        cpus = {int(c) for c in (p.get("cpus") or "").split()}
        if p.get("min_khz") is None or not p.get("hw_khz"):
            out[name] = {"cpus": p.get("cpus"), "drop_pct": None}
            continue
        out[name] = {"cpus": p.get("cpus"), "hw_khz": p["hw_khz"], "min_khz": p["min_khz"],
                     "drop_pct": round((1 - p["min_khz"] / p["hw_khz"]) * 100, 1),
                     "engine_cpus": bool(cpus & allowed) if allowed else None}
    eng = [v["drop_pct"] for v in out.values() if v.get("drop_pct") is not None and v.get("engine_cpus") is not False]
    return out, (max(eng) if eng else None)


def sampler_footer(path, probe_path):
    """A footer-like record from <stem>.vmhwm.log, for a part whose process was stopped before its
    footer: max VmRSS / VmHWM, the Cpus_allowed_list values seen and each policy's lowest ceiling
    (each policy's CPUs and hardware maximum from the run's probe-before.json)."""
    if not os.path.exists(path):
        return {}
    probe = json.load(open(probe_path)).get("cpufreq", {}) if os.path.exists(probe_path) else {}
    cols, rss, hwm, cpus, mins = [], 0, 0, set(), {}
    for line in open(path):
        if line.startswith("#"):
            cols = [c.split(" (")[0] for c in line.lstrip("# ").rstrip("\n").split("\t")]
            continue
        f = line.rstrip("\n").split("\t")
        rss, hwm = max(rss, int(f[1])), max(hwm, int(f[2]))
        if f[3]:
            cpus.add(f[3])
        for name, v in zip(cols[4:], f[4:]):
            if v.isdigit():
                pol = name.split("_")[0]
                mins[pol] = min(mins.get(pol, int(v)), int(v))
    ceilings = {pol: {"cpus": probe.get(pol, {}).get("cpus"), "hw_khz": probe.get(pol, {}).get("hw_khz"),
                      "min_khz": low} for pol, low in mins.items()}
    return {"vmhwm_kb": hwm, "sampler_max_rss_kb": rss, "cpus_allowed_seen": sorted(cpus),
            "cpu_ceilings": ceilings, "from_sampler": True}


def host_ceilings(path):
    """Lowest scaling_max_freq per policy column over the driver's polls (<tag>.cpufreq-host.tsv)."""
    if not os.path.exists(path):
        return None
    mins = None
    for line in open(path):
        if line.startswith("time"):
            continue
        vals = [int(v) for v in line.split("\t")[1].strip().strip(",").split(",") if v.strip().isdigit()]
        mins = vals if mins is None else [min(a, b) for a, b in zip(mins, vals)]
    return mins


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl", nargs="+")
    ap.add_argument("--tag", default="")
    ap.add_argument("--set-dir", required=True)
    ap.add_argument("--rows", default="S4",
                    help="S4, full, S4:<N> (the first N rows of S4) or every:<K>:<N> (manifest rows 0, K, 2K, ..., N of them)")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    parts = [pathlib.Path(p) for p in args.jsonl]
    run = parts[0]
    tag = args.tag or run.name[: -len(".jsonl")]
    out = pathlib.Path(args.out) if args.out else run.parent / "summary"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for p in parts:
        part_rows = load(p)
        if not any(r.get("type") == "footer" for r in part_rows):
            stem = str(p)[: -len(".jsonl")]
            part_rows.append({"type": "footer", **sampler_footer(stem + ".vmhwm.log", stem + ".probe-before.json")})
        rows += part_rows
    if len(parts) > 1:
        # score.py reads one file: the joined rows go to a temporary JSONL.
        joined = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
        for r in rows:
            joined.write(json.dumps(r) + "\n")
        joined.close()
        run = pathlib.Path(joined.name)
    headers = [r for r in rows if r.get("type") == "header"]
    footers = [r for r in rows if r.get("type") == "footer"]
    utts = [r for r in rows if "id" in r]

    set_dir = pathlib.Path(args.set_dir)
    if args.rows == "full":
        manifest = set_dir / "manifest.jsonl"
        expected_chain = json.load(open(set_dir / "SET.json"))["wav_sha256_chain"]
    elif args.rows.startswith("every:"):
        _, k, n = args.rows.split(":")
        tmp = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
        with open(set_dir / "manifest.jsonl") as f:
            rows_all = [line for line in f if line.strip()]
        for line in rows_all[:: int(k)][: int(n)]:
            tmp.write(line)
        tmp.close()
        manifest, expected_chain = pathlib.Path(tmp.name), None
    else:
        manifest = set_dir / "manifest-S4.jsonl"
        expected_chain = json.load(open(set_dir / "SET-S4.json"))["wav_sha256_chain"]
        if ":" in args.rows:
            n = int(args.rows.split(":")[1])
            tmp = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
            with open(manifest) as f:
                for i, line in enumerate(f):
                    if i < n:
                        tmp.write(line)
            tmp.close()
            manifest, expected_chain = pathlib.Path(tmp.name), None

    # score.py imports the vendored normalizer as `leaderboard`.
    alias = pathlib.Path(tempfile.mkdtemp())
    (alias / "leaderboard").symlink_to(ROOT / "tools/omni-eval/leaderboard_normalizer")
    env = dict(os.environ, PYTHONPATH=str(alias))
    score = subprocess.run([sys.executable, str(ROOT / "tools/omni-eval/score.py"), "--manifest", str(manifest),
                            "--pred", str(run)], env=env, capture_output=True, text=True)
    if score.returncode != 0:
        print(score.stderr, file=sys.stderr)
        return 1
    score_json = json.loads(score.stdout)
    (out / f"{tag}.score.json").write_text(json.dumps(score_json, indent=2) + "\n")

    ok = [u for u in utts if not u.get("error")]
    failed = [{"id": u["id"], "error": u["error"]} for u in utts if u.get("error")]
    audio = sum(u["audio_seconds"] for u in ok)
    wall = sum(u["processing_seconds"] for u in ok)
    utt_rtf = [u["processing_seconds"] / u["audio_seconds"] for u in ok]
    enc = [x for u in ok for x in u.get("encode_ms", [])]
    dec = [x for u in ok for x in u.get("decode_ms", [])]
    mel = [x for u in ok for x in u.get("mel_ms", [])]
    later = [t for u in ok for t in u.get("tokens", [])[1:]]
    footer = footers[-1] if footers else {}
    cap_list = [cpu_cap(f) for f in footers] or [cpu_cap({})]
    caps, cap_drop = max(cap_list, key=lambda c: -1 if c[1] is None else c[1])
    # Encoder frames per window that carry audio, against the frames the decoder walks. FileAudioSource:
    # window k covers samples [k * step, k * step + interval) with zeros past the end of the file; mel hop
    # 160 samples, encoder subsampling 8. TdtDecoder loops `while (timeIndex < maxTimeIndex)`: every
    # window walks all of its encoder frames (the decode signature's time axis: 63 for 5 s, 375 for 30 s).
    input_ms = headers[0].get("input_ms") if headers else None
    overlap_ms = headers[0].get("overlap_ms") if headers else None
    frames_per_window = {5000: 63, 30000: 375}.get(input_ms)
    frames_audio = frames_walked = None
    if input_ms and overlap_ms is not None and frames_per_window:
        interval, step = input_ms * 16, (input_ms - overlap_ms) * 16
        frames_audio = frames_walked = 0
        for u in ok:
            total = round(u["audio_seconds"] * 16000)
            for k in range(len(u.get("encode_ms", []))):
                real = max(0, min(interval, total - k * step))
                frames_audio += min(frames_per_window, -(-real // (160 * 8)))
                frames_walked += frames_per_window
    host = [host_ceilings(str(p.parent / f"{p.name[: -len('.jsonl')]}.cpufreq-host.tsv")) for p in parts]
    chains = [f["selection_wav_sha256_chain"] for f in footers if f.get("selection_wav_sha256_chain")]
    summary = {
        "tag": tag,
        "rows": args.rows,
        "model_name": headers[0].get("model_name") if headers else None,
        "backend": headers[0].get("backend") if headers else None,
        "litert_version": headers[0].get("litert_version") if headers else None,
        "gpu_precision": headers[0].get("gpu_precision") if headers else None,
        "npu_htp_performance_mode": headers[0].get("npu_htp_performance_mode") if headers else None,
        "num_threads": headers[0].get("num_threads") if headers else None,
        "processes": [{k: h.get(k) for k in ("pid", "load_label", "load_ms", "tokenizer_ms", "start_after",
                                             "utterances_todo", "thermal_status_start", "battery_celsius_start",
                                             "foreground", "started_utc")} for h in headers],
        "utterances_rows": len(utts),
        "utterances_ok": len(ok),
        "utterances_failed": failed,
        "audio_seconds": round(audio, 3),
        "processing_seconds": round(wall, 3),
        "rtf": round(wall / audio, 5) if audio else None,
        "rtfx": round(audio / wall, 2) if wall else None,
        "median_utterance_rtf": round(statistics.median(utt_rtf), 5) if utt_rtf else None,
        "windows": len(enc),
        "encode_ms_median": pct(enc, 0.5), "encode_ms_p90": pct(enc, 0.9),
        "decode_ms_median": pct(dec, 0.5), "decode_ms_p90": pct(dec, 0.9),
        "mel_ms_median": pct(mel, 0.5),
        "empty_windows": sum(1 for u in ok for t in u.get("tokens", []) if t == 0),
        "later_windows": len(later),
        "later_windows_empty": sum(1 for t in later if t == 0),
        "wer_percent": score_json.get("wer_percent"),
        "substitutions": score_json.get("substitutions"),
        "deletions": score_json.get("deletions"),
        "insertions": score_json.get("insertions"),
        "reference_words": score_json.get("reference_words"),
        "empty_hypotheses": score_json.get("empty_hypotheses"),
        "encoder_frames_with_audio": frames_audio,
        "encoder_frames_walked": frames_walked,
        "parts": [p.name for p in parts],
        "vmhwm_kb": max((f.get("vmhwm_kb") or 0 for f in footers), default=None) or None,
        "sampler_max_rss_kb": max((f.get("sampler_max_rss_kb") or 0 for f in footers), default=None) or None,
        "thermal_status_end": footer.get("thermal_status_end"),
        "battery_celsius_end": footer.get("battery_celsius_end"),
        "cpus_allowed_seen": sorted({c for f in footers for c in (f.get("cpus_allowed_seen") or [])}),
        "cpu_ceilings": caps,
        "cpu_cap_drop_pct": cap_drop,
        "host_poll_min_ceilings_khz": host if len(host) > 1 else host[0],
        "selection_wav_sha256_chain": chains[0] if chains else None,
        "chain_matches_set": all(c == expected_chain for c in chains) if expected_chain and chains else None,
        "model_sha256": footer.get("model_sha256"),
        "native_libs": footer.get("native_libs"),
    }
    (out / f"{tag}.summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: summary[k] for k in ("tag", "utterances_ok", "rtf", "rtfx", "median_utterance_rtf",
                                              "wer_percent", "vmhwm_kb", "cpu_cap_drop_pct", "chain_matches_set")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
