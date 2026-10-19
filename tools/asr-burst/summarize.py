#!/usr/bin/env python3
"""Summarize one burst run (asr-burst-v1, docs/asr-burst-v1.md) and check its text.

  summarize.py <REC>/<tag>.jsonl --set-dir .build/asr-burst/set [--set S32|S16] [--out <REC>/summary]
               [--also <jsonl of an earlier run whose rows of the set count, e.g. a stopped S16 run>]
               [--text-ref <jsonl of another run of the same model>] [--text-ref-label <name>]

Writes <out>/<tag>.summary.json and <out>/<tag>.score.json (tools/omni-eval/score.py: the Open ASR
Leaderboard normalizer, corpus WER, S/D/I, over the rows the run covered; S16's WER is a reference,
the lane's WER comes from S4). The numbers:
  RTF_burst = sum of processing seconds / sum of audio seconds over the counted rows (no error, last
  attempt's ceiling fall <= the line), the median utterance RTF of those rows, the excluded and
  retaken rows, the waits (first attempt: from the previous utterance's end), each process's load,
  VmHWM (the largest over the processes, footer and sampler), the process state (cpuset,
  Cpus_allowed_list, foreground), dexopt / debuggable, the registration lines of the load log, the
  probes before / after, the witnesses (WAV chain, model hashes, native libraries), and the text
  check: each row's text against --text-ref's row of the same id (exact, and after strip()). For the
  LiteRT arms the per-window mel / encode / decode medians of the set's first and last 10
  utterances (the JIT has warmed up after W: the times do not keep falling).
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import statistics
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
REG = re.compile(r"registered|Replacing \d+ out of \d+ node|delegate|Delegate|Dispatch|NPU|npu_|OpenCL|GPU accelerator|"
                 r"accelerator|sherpa-onnx|OfflineRecognizerConfig|onnxruntime|TDT model|vocab_size|fallback|Fallback|"
                 r"[Ee]rror|failed")


def load(path):
    return [json.loads(line) for line in open(path) if line.strip()]


def median(xs):
    return statistics.median(xs) if xs else None


def r5(x):
    return None if x is None else round(x, 5)


def probe(path):
    if not path.exists():
        return None
    p = json.loads(path.read_text())
    return {
        "mac_time": p.get("mac_time"),
        "battery_celsius": p.get("battery_celsius"),
        "thermal_status": p.get("thermal_status"),
        "hal_ap": next((v for k, v in (p.get("hal_current") or {}).items() if k.upper().startswith("AP")), None),
        "hal_skin": next((v for k, v in (p.get("hal_current") or {}).items() if "SKIN" in k.upper()), None),
        "ceilings": {k: {"max_khz": v.get("max_khz"), "hw_khz": v.get("hw_khz"), "drop_pct": v.get("ceiling_drop_pct")}
                     for k, v in (p.get("cpufreq") or {}).items()},
        "mem_available_kb": p.get("mem_available_kb"),
        "wakefulness": p.get("wakefulness"),
    }


def chain_of(paths):
    sha = hashlib.sha256()
    for p in paths:
        sha.update(pathlib.Path(p).read_bytes())
    return sha.hexdigest()


def text_check(utts, ref_path, label):
    ref = {r["id"]: r for r in load(ref_path) if "id" in r}
    same = same_strip = missing = 0
    diffs = []
    for u in utts:
        r = ref.get(u["id"])
        if r is None:
            missing += 1
            continue
        if u["text"] == r["text"]:
            same += 1
        elif u["text"].strip() == r["text"].strip():
            same_strip += 1
        else:
            a, b = u["text"].split(), r["text"].split()
            k = next((i for i in range(min(len(a), len(b))) if a[i] != b[i]), min(len(a), len(b)))
            diffs.append({"id": u["id"], "at_word": k, "this": " ".join(a[max(0, k - 3):k + 6]),
                          "ref": " ".join(b[max(0, k - 3):k + 6]), "words_this": len(a), "words_ref": len(b)})
    return {"ref": label or str(ref_path), "ref_path": str(ref_path), "compared": len(utts) - missing,
            "missing_in_ref": missing, "identical": same, "identical_after_strip": same_strip,
            "different": len(diffs), "examples": diffs[:5]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--set-dir", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--text-ref", default="")
    ap.add_argument("--text-ref-label", default="")
    ap.add_argument("--line-pct", type=float, default=15.0)
    ap.add_argument("--set", default="S32", choices=["S32", "S16"])
    ap.add_argument("--also", action="append", default=[])
    args = ap.parse_args()

    run = pathlib.Path(args.jsonl)
    tag = run.name[: -len(".jsonl")]
    rec_dir = run.parent
    out = pathlib.Path(args.out) if args.out else rec_dir / "summary"
    out.mkdir(parents=True, exist_ok=True)
    rows = load(run)
    also_rows = []
    for extra in args.also:
        for r in load(extra):
            if "id" in r:
                also_rows.append(dict(r, from_run=pathlib.Path(extra).name[: -len(".jsonl")]))
    headers = [r for r in rows if r.get("type") == "header"]
    footers = [r for r in rows if r.get("type") == "footer"]
    warmups = [r for r in rows if r.get("type") == "warmup"]
    utts = [r for r in rows if "id" in r]
    set_dir = pathlib.Path(args.set_dir)
    s16 = [line.rstrip("\n").split("\t") for line in open(set_dir / f"manifest-{args.set}.tsv") if line.strip()]
    s16_ids = [i for i, _ in s16]
    meta = {json.loads(l)["id"]: l for l in open(set_dir / f"manifest-{args.set}.jsonl") if l.strip()}
    set_rec = json.loads((set_dir / f"SET-{args.set}.json").read_text())

    # Rows covered, in the set's order; a later row of the same id (a restarted process) wins, and a
    # row of this run wins over an earlier run's (--also).
    by_id = {}
    for u in also_rows:
        if u["id"] in meta:
            by_id[u["id"]] = u
    for u in utts:
        by_id[u["id"]] = dict(u, from_run=tag)
    covered = [i for i in s16_ids if i in by_id]
    extra_ids = [i for i in by_id if i not in set(s16_ids)]
    final = [by_id[i] for i in covered]

    # WER over the covered rows (score.py imports the vendored normalizer as `leaderboard`).
    tmp = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
    for i in covered:
        tmp.write(meta[i])
    tmp.close()
    pred = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
    for u in final:
        pred.write(json.dumps({k: u[k] for k in ("id", "text", "audio_seconds", "processing_seconds")}) + "\n")
    pred.close()
    alias = pathlib.Path(tempfile.mkdtemp())
    (alias / "leaderboard").symlink_to(ROOT / "tools/omni-eval/leaderboard_normalizer")
    env = dict(os.environ, PYTHONPATH=str(alias), PYTHONDONTWRITEBYTECODE="1")
    score = subprocess.run([sys.executable, str(ROOT / "tools/omni-eval/score.py"), "--manifest", tmp.name,
                            "--pred", pred.name], env=env, capture_output=True, text=True)
    if score.returncode != 0:
        print(score.stderr, file=sys.stderr)
        return 1
    score_json = json.loads(score.stdout)
    score_json["rows"] = f"{len(covered)} of {args.set} ({tag})"
    (out / f"{tag}.score.json").write_text(json.dumps(score_json, indent=2) + "\n")

    ok = [u for u in final if not u.get("error")]
    counted = [u for u in ok if not u.get("excluded")]
    excluded = [u for u in ok if u.get("excluded")]
    retaken = [u for u in final if u.get("attempts", 1) > 1]
    audio = sum(u["audio_seconds"] for u in counted)
    wall = sum(u["processing_seconds"] for u in counted)
    waits = [u["wait_s"] for u in final if u.get("wait_s") is not None]
    drops_first = [(u.get("retake") or {}).get("first", {}).get("cap_drop_pct", u.get("cap_drop_pct")) for u in final]
    drops_last = [u.get("cap_drop_pct") for u in final]
    stage = {}
    for u in ok:
        for k, v in (u.get("stage_ms") or {}).items():
            stage.setdefault(k, []).append(v)
    mel = [x for u in ok for x in u.get("mel_ms", [])]
    enc = [x for u in ok for x in u.get("encode_ms", [])]
    dec = [x for u in ok for x in u.get("decode_ms", [])]
    def window_medians(us):
        return {k: median([x for u in us for x in u.get(key, [])]) for k, key in
                (("mel_ms", "mel_ms"), ("encode_ms", "encode_ms"), ("decode_ms", "decode_ms"))}
    jit_check = None
    if enc:
        first10, last10 = ok[:10], ok[-10:]
        jit_check = {"first_10": {"ids": [u["id"] for u in first10], "windows": sum(len(u.get("encode_ms", [])) for u in first10),
                                  "audio_s": round(sum(u["audio_seconds"] for u in first10), 2), **window_medians(first10)},
                     "last_10": {"ids": [u["id"] for u in last10], "windows": sum(len(u.get("encode_ms", [])) for u in last10),
                                 "audio_s": round(sum(u["audio_seconds"] for u in last10), 2), **window_medians(last10)}}
    per_utt_stage = {}
    for k, key in (("mel", "mel_ms"), ("encode", "encode_ms"), ("decode", "decode_ms")):
        vals = [sum(u.get(key, [])) for u in ok if u.get(key)]
        if vals:
            per_utt_stage[k] = {"median_ms": median(vals), "sum_s": sum(vals) / 1000.0}
    for k, vals in stage.items():
        per_utt_stage[k] = {"median_ms": median(vals), "sum_s": sum(vals) / 1000.0}

    vm = [f.get("vmhwm_kb") for f in footers if f.get("vmhwm_kb")] + [f.get("sampler_max_hwm_kb") for f in footers if f.get("sampler_max_hwm_kb")]
    load_log = rec_dir / f"{tag}.load-logcat.txt"
    reg = []
    if load_log.exists():
        seen = set()
        for line in open(load_log, errors="replace"):
            body = line.split(": ", 1)[-1].rstrip("\n") if ": " in line else line.rstrip("\n")
            if REG.search(line) and " D ASR" not in line and body not in seen:
                seen.add(body)
                reg.append(line.rstrip("\n"))
    segs = sorted(p.name for p in rec_dir.glob(f"{tag}.probe-before*.json"))
    chain_expected = set_rec["wav_sha256_chain"] if len(covered) == len(s16_ids) else \
        chain_of([dict(s16)[i] for i in s16_ids[: len(covered)]]) if covered == s16_ids[: len(covered)] else None
    summary = {
        "tag": tag,
        "harness": headers[0].get("harness") if headers else None,
        "engine": headers[0].get("engine") if headers else None,
        "model_name": headers[0].get("model_name") if headers else None,
        "backend": headers[0].get("backend") if headers else None,
        "num_threads": headers[0].get("num_threads") if headers else None,
        "litert_version": headers[0].get("litert_version") if headers else None,
        "sherpa_onnx_version": headers[0].get("sherpa_onnx_version") if headers else None,
        "onnxruntime_version": headers[0].get("onnxruntime_version") if headers else None,
        "gpu_precision": headers[0].get("gpu_precision") if headers else None,
        "npu_htp_performance_mode": headers[0].get("npu_htp_performance_mode") if headers else None,
        "input_ms": headers[0].get("input_ms") if headers else None,
        "processes": [{k: h.get(k) for k in ("pid", "load_label", "load_ms", "start_after", "utterances_todo",
                                             "foreground_state", "foreground_error", "screen_start", "process_state",
                                             "debuggable", "dexopt_app", "dexopt_test", "oat_files_mapped",
                                             "thermal_status_start", "battery_celsius_start", "started_utc")}
                      for h in headers],
        "warmups": [{k: w.get(k) for k in ("warmup_id", "processing_seconds", "audio_seconds", "error")} for w in warmups],
        "rows_written": len(utts),
        "set": args.set,
        "rows_covered_of_s16": len(covered),
        "rows_from_runs": {name: sum(1 for u in final if u.get("from_run") == name) for name in sorted({u.get("from_run") for u in final})},
        "rows_outside_s16": extra_ids,
        "rows_ok": len(ok),
        "rows_failed": [{"id": u["id"], "error": u["error"]} for u in final if u.get("error")],
        "rows_counted": len(counted),
        "rows_excluded": len(excluded),
        "rows_retaken": len(retaken),
        "retake_text_differs": sum(1 for u in retaken if not (u.get("retake") or {}).get("text_same", True)),
        "counted_audio_seconds": round(audio, 3),
        "counted_processing_seconds": round(wall, 3),
        "rtf_burst": r5(wall / audio) if audio else None,
        "rtfx_burst": round(audio / wall, 2) if wall else None,
        "median_utterance_rtf_burst": r5(median([u["processing_seconds"] / u["audio_seconds"] for u in counted])),
        "rtf_all_ok_rows": r5(sum(u["processing_seconds"] for u in ok) / sum(u["audio_seconds"] for u in ok)) if ok else None,
        "wait_sum_s": round(sum(waits), 3),
        "wait_median_s": median(waits),
        "wait_max_s": max(waits) if waits else None,
        "wait_over_1s": sum(1 for w in waits if w > 1.0),
        "wait_timeouts": sum(1 for u in final if u.get("wait_timed_out")),
        "retake_wait_sum_s": round(sum((u.get("retake") or {}).get("wait_s", 0.0) for u in retaken), 3),
        "cap_drop_first_attempt": {"max": max([d for d in drops_first if d is not None], default=None),
                                   "median": median([d for d in drops_first if d is not None]),
                                   "over_line": sum(1 for d in drops_first if d is not None and d > args.line_pct)},
        "cap_drop_last_attempt_max": max([d for d in drops_last if d is not None], default=None),
        "cap_drop_engine_cpus_max": max([u.get("cap_drop_engine_cpus_pct") for u in final if u.get("cap_drop_engine_cpus_pct") is not None], default=None),
        "cpus_allowed_rows": sorted({u.get("cpus_allowed") for u in final if u.get("cpus_allowed")}),
        "windows": len(enc),
        "window_ms": {"mel_median": median(mel), "encode_median": median(enc), "decode_median": median(dec)} if enc else None,
        "per_utterance_stage": per_utt_stage,
        "jit_check_window_ms": jit_check,
        "wer_percent_s16_reference": score_json.get("wer_percent"),
        "substitutions": score_json.get("substitutions"),
        "deletions": score_json.get("deletions"),
        "insertions": score_json.get("insertions"),
        "reference_words": score_json.get("reference_words"),
        "empty_hypotheses": score_json.get("empty_hypotheses"),
        "vmhwm_kb_max": max(vm) if vm else None,
        "vmhwm_kb_per_process": [f.get("vmhwm_kb") for f in footers],
        "sampler_max_hwm_kb_per_process": [f.get("sampler_max_hwm_kb") for f in footers],
        "cpuset_seen": sorted({c for f in footers for c in (f.get("cpuset_seen") or [])}),
        "cpus_allowed_seen": sorted({c for f in footers for c in (f.get("cpus_allowed_seen") or [])}),
        "foreground_state_end": [f.get("foreground_state_end") for f in footers],
        "thermal_status_end": [f.get("thermal_status_end") for f in footers],
        "battery_celsius_end": [f.get("battery_celsius_end") for f in footers],
        "probes": {name: probe(rec_dir / name) for name in segs + sorted(p.name for p in rec_dir.glob(f"{tag}.probe-after*.json"))},
        "registration_lines": reg[:40],
        "selection_wav_sha256_chain": [f.get("selection_wav_sha256_chain") for f in footers],
        "chain_expected": chain_expected,
        "chain_matches": all(f.get("selection_wav_sha256_chain") == chain_expected for f in footers) if chain_expected and footers else None,
        "model_sha256": [f.get("model_sha256") or f.get("model_files_sha256") for f in footers],
        "native_libs_loaded": [f.get("native_libs_loaded") for f in footers],
        "native_libs": footers[-1].get("native_libs") if footers else None,
        "text_check": text_check(final, args.text_ref, args.text_ref_label) if args.text_ref and os.path.exists(args.text_ref) else None,
        "retake_examples": [{"id": u["id"], "first": (u.get("retake") or {}).get("first", {}).get("cap_drop_pct"),
                             "last": u.get("cap_drop_pct"), "text_same": (u.get("retake") or {}).get("text_same")}
                            for u in retaken[:10]],
    }
    (out / f"{tag}.summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    brief = {k: summary[k] for k in ("tag", "rows_covered_of_s16", "rows_counted", "rows_excluded", "rows_retaken",
                                     "rtf_burst", "median_utterance_rtf_burst", "wait_sum_s", "wait_median_s",
                                     "wait_timeouts", "vmhwm_kb_max", "wer_percent_s16_reference", "chain_matches")}
    brief["loads_ms"] = [(p["load_label"], p["load_ms"]) for p in summary["processes"]]
    if summary["text_check"]:
        tc = summary["text_check"]
        brief["text_check"] = f'{tc["identical"]}+{tc["identical_after_strip"]} of {tc["compared"]} same, {tc["different"]} differ ({tc["ref"]})'
    print(json.dumps(brief))
    return 0


if __name__ == "__main__":
    sys.exit(main())
