#!/usr/bin/env python3
"""Summarize one run of the decoder-PR check (asr-pr-v1, docs/asr-pr-v1.md; asr-fix-v1's summarize.py)
and check its text.

  summarize.py <REC>/<tag>.jsonl --set-dir .build/asr-pr/set [--out <REC>/summary]
               [--text-ref <jsonl>=<label>]... [--compare <jsonl>=<label>]... [--line-pct 15]

The set comes from the run's header: every 32 = S32 (manifest-device.tsv), the edge manifest
(manifest-edge.tsv) = edge2, and `limit` = its first N rows.
Writes <out>/<tag>.summary.json and, for S32, <out>/<tag>.score.json (tools/omni-eval/score.py: the
Open ASR Leaderboard normalizer, corpus WER, S/D/I, over the rows the run covered; the edge inputs
have no reference text). The numbers:
  - text: WER, S/D/I, reference words, empty hypotheses (score.py), the rows with an error (the
    app's exceptions), the non-error rows with an empty text;
  - sustained runs (pace none): RTF = sum of processing seconds / sum of audio seconds over the rows
    without an error, and the lowest CPU ceiling the run saw per policy (cpu-cap-rule);
  - burst runs: asr-burst-v1's RTF_burst (counted rows), median, excluded / retaken rows, waits, falls;
  - the decoder per window: the samples up to the last non-zero one the pipeline handed the
    recognizer (window_valid_samples), their feature frames, the time limit the PR's
    TdtDecoder.getTimeLimit gives for them (min(maxTimeIndex, ceil(n / 8) + 4), computed here from the
    recorded counts; maxTimeIndex = ceil(the window's feature frames / 8), 375 for 30 s), the largest
    time index of a token the decoder emitted (window_last_token_time), and the windows with a token
    at or past their limit (none expected);
  - each process's load, VmHWM (the largest over the processes, footer and sampler), where it ran,
    dexopt / debuggable, the registration lines of the load log, the probes, the witnesses;
  - warm check: the first 10 and the last 10 rows of the run, per window mel / encode / decode ms;
  - --text-ref: each row's text against the reference run's row of the same id (exact / after strip);
  - --compare: the reference run scored over exactly the same ids (WER, S/D/I, empty, errors).
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
                 r"accelerator|TDT model|vocab_size|fallback|Fallback|[Ee]rror|failed")
SETS = {32: "S32"}


def time_limit(valid_frames, max_time_index):
    """The PR's TdtDecoder.getTimeLimit for a window's feature frames n: min(maxTimeIndex, ceil(n / 8) + 4)."""
    return min(max_time_index, (valid_frames + 7) // 8 + 4)


def load(path):
    return [json.loads(line) for line in open(path) if line.strip()]


def median(xs):
    return statistics.median(xs) if xs else None


def mean(xs):
    return round(sum(xs) / len(xs), 2) if xs else None


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


def cpu_list(text):
    """Cpus_allowed_list ("0-5,7") or related_cpus ("0 1 2 3 4 5") -> a set of CPU numbers."""
    cpus = set()
    for part in re.split(r"[,\s]+", text or ""):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            cpus.update(range(int(a), int(b) + 1))
        elif part:
            cpus.add(int(part))
    return cpus


def score(meta_lines, rows):
    """score.py over these manifest lines and rows (it imports the vendored normalizer as `leaderboard`)."""
    tmp = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
    for line in meta_lines:
        tmp.write(line)
    tmp.close()
    pred = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
    for u in rows:
        pred.write(json.dumps({k: u.get(k) for k in ("id", "text", "audio_seconds", "processing_seconds", "error")
                               if u.get(k) is not None}) + "\n")
    pred.close()
    alias = pathlib.Path(tempfile.mkdtemp())
    (alias / "leaderboard").symlink_to(ROOT / "tools/omni-eval/leaderboard_normalizer")
    env = dict(os.environ, PYTHONPATH=str(alias), PYTHONDONTWRITEBYTECODE="1")
    out = subprocess.run([sys.executable, str(ROOT / "tools/omni-eval/score.py"), "--manifest", tmp.name,
                          "--pred", pred.name], env=env, capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(out.stderr)
    return json.loads(out.stdout)


def rows_by_id(path):
    by_id = {}
    for r in load(path):
        if "id" in r:
            by_id[r["id"]] = r  # a later row of the same id (a restarted process) wins
    return by_id


def text_check(utts, ref_path, label):
    ref = rows_by_id(ref_path)
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
    return {"ref": label, "ref_path": str(ref_path), "compared": len(utts) - missing,
            "missing_in_ref": missing, "identical": same, "identical_after_strip": same_strip,
            "different": len(diffs), "examples": diffs[:5]}


def split_ref(arg):
    path, _, label = arg.partition("=")
    return pathlib.Path(path), label or path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--set-dir", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--text-ref", action="append", default=[])
    ap.add_argument("--compare", action="append", default=[])
    ap.add_argument("--line-pct", type=float, default=15.0)
    args = ap.parse_args()

    run = pathlib.Path(args.jsonl)
    tag = run.name[: -len(".jsonl")]
    rec_dir = run.parent
    out = pathlib.Path(args.out) if args.out else rec_dir / "summary"
    out.mkdir(parents=True, exist_ok=True)
    rows = load(run)
    headers = [r for r in rows if r.get("type") == "header"]
    footers = [r for r in rows if r.get("type") == "footer"]
    warmups = [r for r in rows if r.get("type") == "warmup"]
    utts = [r for r in rows if "id" in r]
    h0 = headers[0] if headers else {}
    every = int(h0.get("every") or 0)
    limit = int(h0.get("limit") or 0)
    set_dir = pathlib.Path(args.set_dir)
    edge = str(h0.get("manifest") or "").endswith("manifest-edge.tsv")
    if edge:
        set_name = "edge2"
        sel = [line.rstrip("\n").split("\t")[:2] for line in open(set_dir / "manifest-edge.tsv") if line.strip()]
        sel = [(i, str(set_dir / p)) for i, p in sel]
        meta = {}
        set_rec = json.loads((set_dir / "SET-edge.json").read_text())
    elif every in SETS:
        set_name = SETS[every]
        sel = [line.rstrip("\n").split("\t") for line in open(set_dir / f"manifest-{set_name}.tsv") if line.strip()]
        meta = {json.loads(l)["id"]: l for l in open(set_dir / f"manifest-{set_name}.jsonl") if l.strip()}
        set_rec = json.loads((set_dir / f"SET-{set_name}.json").read_text())
    else:
        raise SystemExit(f"{run}: header every={every} manifest={h0.get('manifest')}, not S32 or the edge set")
    if limit > 0:
        sel = sel[:limit]
    sel_ids = [i for i, _ in sel]
    pace = h0.get("pace")
    max_time_index = (int(h0.get("input_ms") or 30000) // 10 + 7) // 8

    by_id = {}
    for u in utts:
        by_id[u["id"]] = u
    covered = [i for i in sel_ids if i in by_id]
    extra_ids = [i for i in by_id if i not in set(sel_ids)]
    final = [by_id[i] for i in covered]

    if edge:
        score_json = {"rows": f"{len(covered)} of {set_name} ({tag}): no reference text, not scored"}
    else:
        score_json = score([meta[i] for i in covered], final)
        score_json["rows"] = f"{len(covered)} of {set_name}{f' first {limit}' if limit else ''} ({tag})"
        (out / f"{tag}.score.json").write_text(json.dumps(score_json, indent=2) + "\n")

    ok = [u for u in final if not u.get("error")]
    errors = [{"id": u["id"], "error": u["error"]} for u in final if u.get("error")]
    empty_texts = [u["id"] for u in ok if not u["text"].strip()]

    # Sustained: RTF over the rows without an error, and the CPU ceilings the process saw.
    sustained = None
    if pace in (None, "none"):  # asr-litert-app-v1's sustained records carry no pace field
        audio = sum(u["audio_seconds"] for u in ok)
        wall = sum(u["processing_seconds"] for u in ok)
        engine_cpus = set()
        for f in footers:
            for c in f.get("cpus_allowed_seen") or []:
                engine_cpus |= cpu_list(c)
        drops = {}
        for f in footers:
            for name, c in (f.get("cpu_ceilings") or {}).items():
                if c.get("hw_khz") and c.get("min_khz") is not None:
                    d = round((1 - c["min_khz"] / c["hw_khz"]) * 100, 1)
                    engine = bool(cpu_list(c.get("cpus")) & engine_cpus)
                    prev = drops.get(name)
                    if prev is None or d > prev["drop_pct"]:
                        drops[name] = {"drop_pct": d, "min_khz": c["min_khz"], "hw_khz": c["hw_khz"], "engine": engine}
        engine_drop = max([v["drop_pct"] for v in drops.values() if v["engine"]], default=None)
        backend = h0.get("backend")
        capped = engine_drop is not None and engine_drop > args.line_pct
        sustained = {
            "audio_seconds": round(audio, 3),
            "processing_seconds": round(wall, 3),
            "rtf": r5(wall / audio) if audio else None,
            "median_utterance_rtf": r5(median([u["processing_seconds"] / u["audio_seconds"] for u in ok])),
            "ceiling_drop_per_policy": drops,
            "engine_cpus": sorted(engine_cpus),
            "engine_ceiling_drop_max_pct": engine_drop,
            "cpu_capped": capped,
            "rtf_counts": not (capped and backend == "cpu"),
            "rtf_note": (f"cpu-cap-rule: the engine CPUs' ceiling fell {engine_drop} % (> {args.line_pct} %), "
                         "no RTF for a CPU arm") if capped and backend == "cpu" else
                        (f"capped {engine_drop} %, counted with the mark (accelerator arm)" if capped else None),
        }

    # Burst: asr-burst-v1's numbers over the counted rows.
    burst = None
    if pace == "burst":
        counted = [u for u in ok if not u.get("excluded")]
        excluded = [u for u in ok if u.get("excluded")]
        retaken = [u for u in final if u.get("attempts", 1) > 1]
        audio = sum(u["audio_seconds"] for u in counted)
        wall = sum(u["processing_seconds"] for u in counted)
        waits = [u["wait_s"] for u in final if u.get("wait_s") is not None]
        drops_first = [(u.get("retake") or {}).get("first", {}).get("cap_drop_pct", u.get("cap_drop_pct")) for u in final]
        drops_last = [u.get("cap_drop_pct") for u in final]
        burst = {
            "rows_counted": len(counted),
            "rows_excluded": len(excluded),
            "rows_retaken": len(retaken),
            "retake_text_differs": sum(1 for u in retaken if not (u.get("retake") or {}).get("text_same", True)),
            "counted_audio_seconds": round(audio, 3),
            "counted_processing_seconds": round(wall, 3),
            "rtf_burst": r5(wall / audio) if audio else None,
            "rtfx_burst": round(audio / wall, 2) if wall else None,
            "median_utterance_rtf_burst": r5(median([u["processing_seconds"] / u["audio_seconds"] for u in counted])),
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
            "cap_drop_engine_cpus_max": max([u.get("cap_drop_engine_cpus_pct") for u in final
                                             if u.get("cap_drop_engine_cpus_pct") is not None], default=None),
            "cpus_allowed_rows": sorted({u.get("cpus_allowed") for u in final if u.get("cpus_allowed")}),
            "retake_examples": [{"id": u["id"], "first": (u.get("retake") or {}).get("first", {}).get("cap_drop_pct"),
                                 "last": u.get("cap_drop_pct"), "text_same": (u.get("retake") or {}).get("text_same")}
                                for u in retaken[:10]],
        }

    # The decoder per window (rows without an error): the counts the pipeline handed the recognizer,
    # the time limit the PR's decoder computes from them, and the last time index it emitted a token at.
    windows = []
    for u in ok:
        vs = u.get("window_valid_samples") or []
        vf = u.get("window_valid_frames") or []
        lt = u.get("window_last_token_time") or []
        for k in range(len(vs)):
            n = vf[k] if k < len(vf) else None
            lim = time_limit(n, max_time_index) if n is not None and n >= 0 else max_time_index
            windows.append({"id": u["id"], "window": k, "valid_samples": vs[k], "valid_frames": n, "time_limit": lim,
                            "last_token_time": lt[k] if k < len(lt) else None})
    limits = [w["time_limit"] for w in windows]
    past = [w for w in windows if w["last_token_time"] is not None and w["last_token_time"] >= w["time_limit"]]
    decoder = {
        "tdt_time_limit": h0.get("tdt_time_limit"),
        "tdt_max_symbols_per_step": h0.get("tdt_max_symbols_per_step"),
        "max_time_index": max_time_index,
        "windows": len(windows),
        "time_limit_mean": mean(limits),
        "time_limit_median": median(limits),
        "windows_stopped_before_max": sum(1 for x in limits if x < max_time_index),
        "windows_full": [f'{w["id"]}#{w["window"]}' for w in windows if w["time_limit"] == max_time_index],
        "windows_with_a_token_at_or_past_the_limit": [f'{w["id"]}#{w["window"]}' for w in past],
        "windows_without_tokens": sum(1 for w in windows if w["last_token_time"] == -1),
        "last_token_time_max_minus_limit": max([w["last_token_time"] - w["time_limit"] for w in windows
                                                if w["last_token_time"] is not None and w["last_token_time"] >= 0], default=None),
        "valid_samples_mean": mean([w["valid_samples"] for w in windows]),
        "valid_frames_mean": mean([w["valid_frames"] for w in windows if w["valid_frames"] is not None]),
        "per_window": windows if edge else None,
    }

    def group(us):
        mel_w = [x for u in us for x in u.get("mel_ms", [])]
        enc_w = [x for u in us for x in u.get("encode_ms", [])]
        dec_w = [x for u in us for x in u.get("decode_ms", [])]
        return {
            "ids": [u["id"] for u in us],
            "audio_seconds": [u["audio_seconds"] for u in us],
            "windows": len(enc_w),
            "mel_ms_per_window_median": median(mel_w),
            "encode_ms_per_window_median": median(enc_w),
            "decode_ms_per_window_median": median(dec_w),
            "rows": [{"id": u["id"], "mel_ms": u.get("mel_ms"), "encode_ms": u.get("encode_ms"),
                      "decode_ms": u.get("decode_ms")} for u in us],
        }
    in_run_order = [u for u in utts if "id" in u and not u.get("error") and u["id"] in set(covered)]
    warm_check = {"first10": group(in_run_order[:10]), "last10": group(in_run_order[-10:])} if len(in_run_order) >= 20 else None

    stage = {}
    for u in ok:
        for k, v in (u.get("stage_ms") or {}).items():
            stage.setdefault(k, []).append(v)
    mel = [x for u in ok for x in u.get("mel_ms", [])]
    enc = [x for u in ok for x in u.get("encode_ms", [])]
    dec = [x for u in ok for x in u.get("decode_ms", [])]
    per_utt_stage = {}
    for k, key in (("mel", "mel_ms"), ("encode", "encode_ms"), ("decode", "decode_ms")):
        vals = [sum(u.get(key, [])) for u in ok if u.get(key)]
        if vals:
            per_utt_stage[k] = {"median_ms": median(vals), "sum_s": sum(vals) / 1000.0}
    for k, vals in stage.items():
        per_utt_stage[k] = {"median_ms": median(vals), "sum_s": sum(vals) / 1000.0}

    vm = [f.get("vmhwm_kb") for f in footers if f.get("vmhwm_kb")] + \
         [f.get("sampler_max_hwm_kb") for f in footers if f.get("sampler_max_hwm_kb")]
    # The sampler log has one section per process ("... (pid N)"); a process stopped at a sitting's
    # deadline writes no footer, so its VmHWM and cpusets are only here.
    sampler = {}
    vm_log = rec_dir / f"{tag}.vmhwm.log"
    if vm_log.exists():
        pid = None
        for line in open(vm_log, errors="replace"):
            if line.startswith("#"):
                m = re.search(r"\(pid (\d+)\)", line)
                pid = m.group(1) if m else None
                continue
            cols = line.rstrip("\n").split("\t")
            if pid is None or len(cols) < 7 or not cols[2].isdigit():
                continue
            s = sampler.setdefault(pid, {"samples": 0, "vmhwm_kb_max": 0, "cpuset_cpus": {}})
            s["samples"] += 1
            s["vmhwm_kb_max"] = max(s["vmhwm_kb_max"], int(cols[2]))
            key = f"{cols[6]} {cols[3]}"
            s["cpuset_cpus"][key] = s["cpuset_cpus"].get(key, 0) + 1
    vm += [s["vmhwm_kb_max"] for s in sampler.values()]
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
    paths = dict(sel)
    chain_expected = set_rec["wav_sha256_chain"] if not limit and len(covered) == len(sel_ids) else \
        chain_of([paths[i] for i in sel_ids[: len(covered)]]) if covered == sel_ids[: len(covered)] and \
        all(os.path.exists(paths[i]) for i in sel_ids[: len(covered)]) else None

    compares = []
    for arg in args.compare:
        path, label = split_ref(arg)
        if not path.exists():
            compares.append({"ref": label, "ref_path": str(path), "missing": True})
            continue
        ref = rows_by_id(path)
        ids = [i for i in covered if i in ref]
        mine = score([meta[i] for i in ids], [by_id[i] for i in ids])
        theirs = score([meta[i] for i in ids], [ref[i] for i in ids])
        pick = ("wer_percent", "substitutions", "deletions", "insertions", "reference_words", "empty_hypotheses", "runner_failures")
        compares.append({"ref": label, "ref_path": str(path), "ids_in_both": len(ids),
                         "this": {k: mine.get(k) for k in pick}, "ref_scores": {k: theirs.get(k) for k in pick},
                         "ref_errors": sum(1 for i in ids if ref[i].get("error")),
                         "this_errors": sum(1 for i in ids if by_id[i].get("error"))})

    summary = {
        "tag": tag,
        "harness": h0.get("harness"),
        "engine": h0.get("engine"),
        "model_name": h0.get("model_name"),
        "backend": h0.get("backend"),
        "pace": pace,
        "set": set_name,
        "limit": limit,
        "num_threads": h0.get("num_threads"),
        "litert_version": h0.get("litert_version"),
        "gpu_precision": h0.get("gpu_precision"),
        "input_ms": h0.get("input_ms"),
        "processes": [{k: h.get(k) for k in ("pid", "load_label", "load_ms", "start_after", "utterances_todo",
                                             "foreground_state", "foreground_top_app", "foreground_error", "screen_start",
                                             "process_state", "debuggable", "dexopt_app", "dexopt_test", "oat_files_mapped",
                                             "thermal_status_start", "battery_celsius_start", "started_utc")}
                      for h in headers],
        "warmups": [{k: w.get(k) for k in ("warmup_id", "processing_seconds", "audio_seconds", "windows", "error")} for w in warmups],
        "rows_written": len(utts),
        "rows_covered": len(covered),
        "rows_selected": len(sel_ids),
        "rows_outside_selection": extra_ids,
        "rows_ok": len(ok),
        "rows_failed": errors,
        "empty_texts": empty_texts,
        "wer_percent": score_json.get("wer_percent"),
        "substitutions": score_json.get("substitutions"),
        "deletions": score_json.get("deletions"),
        "insertions": score_json.get("insertions"),
        "reference_words": score_json.get("reference_words"),
        "empty_hypotheses": score_json.get("empty_hypotheses"),
        "sustained": sustained,
        "burst": burst,
        "decoder": decoder,
        "window_ms": {"mel_median": median(mel), "encode_median": median(enc), "decode_median": median(dec)} if enc else None,
        "per_utterance_stage": per_utt_stage,
        "warm_check": warm_check,
        "vmhwm_kb_max": max(vm) if vm else None,
        "vmhwm_kb_per_process": [f.get("vmhwm_kb") for f in footers],
        "sampler_max_hwm_kb_per_process": [f.get("sampler_max_hwm_kb") for f in footers],
        "sampler_log_by_pid": sampler,
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
        "model_sha256": [f.get("model_sha256") for f in footers],
        "native_libs_loaded": [f.get("native_libs_loaded") for f in footers],
        "native_libs": footers[-1].get("native_libs") if footers else None,
        "text_checks": [text_check(final, *split_ref(a)) for a in args.text_ref if split_ref(a)[0].exists()],
        "text_refs_missing": [a for a in args.text_ref if not split_ref(a)[0].exists()],
        "compare": compares,
    }
    (out / f"{tag}.summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    brief = {k: summary[k] for k in ("tag", "set", "rows_covered", "rows_ok", "wer_percent", "substitutions", "deletions",
                                     "insertions", "empty_hypotheses", "vmhwm_kb_max", "chain_matches")}
    brief["errors"] = len(errors)
    brief["loads_ms"] = [(p["load_label"], p["load_ms"]) for p in summary["processes"]]
    brief["time_limit_mean"] = decoder["time_limit_mean"]
    brief["windows_with_a_token_at_or_past_the_limit"] = len(decoder["windows_with_a_token_at_or_past_the_limit"])
    if sustained:
        brief.update({k: sustained[k] for k in ("rtf", "engine_ceiling_drop_max_pct", "rtf_counts")})
    if burst:
        brief.update({k: burst[k] for k in ("rows_counted", "rows_excluded", "rtf_burst", "median_utterance_rtf_burst",
                                            "wait_median_s", "wait_timeouts")})
    if warm_check:
        brief["warm_check"] = {g: {k: warm_check[g][k] for k in ("mel_ms_per_window_median", "encode_ms_per_window_median",
                                                                 "decode_ms_per_window_median")} for g in ("first10", "last10")}
    for tc in summary["text_checks"]:
        brief.setdefault("text_checks", []).append(
            f'{tc["identical"]}+{tc["identical_after_strip"]} of {tc["compared"]} same, {tc["different"]} differ ({tc["ref"]})')
    for c in compares:
        if not c.get("missing"):
            brief.setdefault("compare", []).append(
                f'{c["ref"]} over {c["ids_in_both"]} ids: this {c["this"]["wer_percent"]} % / empty {c["this"]["empty_hypotheses"]}'
                f' vs {c["ref_scores"]["wer_percent"]} % / empty {c["ref_scores"]["empty_hypotheses"]}')
    print(json.dumps(brief, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
