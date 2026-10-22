#!/usr/bin/env python3
"""asr-sigbuf-v1 (docs/asr-sigbuf-v1.md): the runs of one sitting against the pre-registered lines.

  compare.py pair <record dir> <fix tag>   one line: the fix run's windows against its main run (the same
                                           pair: <model>-<accel>-main-r<N>); MISMATCH on any token id or time
                                           index that differs, a window missing on one side, or an error
  compare.py summary <record dir> [prefix]  the runs whose tags start with prefix (f1- = the first form of the change,
                                           f2- = the second): the facts per build into <record dir>/compare-f1.json /
                                           compare-f2.json (no ratio between the builds there); the cost ratio and
                                           every line's verdict into .build/asr-sigbuf/verdicts-f1.json / -f2.json
                                           (not in the record), printed

Lines (copied from the round's 線 before any number):
- identity: per entry and backend, every window's token ids equal between the main and the fix APKs (every
  run of the sitting, the warm-up row left out).
- cost: the median of the windows' decode times of each build's v3 runs (CPU and GPU each, the warm-up
  row left out); the round's limit (COST_LIMIT_PCT) is applied in verdicts.json only.
- NPU decoder only: dec-npu-fix has 0 of 12 windows failing, no `Failed to find memHandle` line in its log
  tap, and every window's token ids equal to dec-cpu-f32-fix's.
- NPU app path: v3-npu-app-fix has no `Failed to find memHandle` / err 6004 line in its log tap and the
  test process did not crash (a done marker, no crash buffer); its text is recorded as it is.
Plain python3, no third-party package.
"""
import json
import os
import pathlib
import statistics
import sys

COST_LIMIT_PCT = 3.0


def load_jsonl(path):
    rows, header, end = [], None, None
    for line in open(path):
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("type") == "header":
            header = r
        elif r.get("type") == "utterance":
            rows.append(r)
        elif r.get("type") == "end":
            end = r
    return header, rows, end


def windows_of(rows):
    """(row id, window index) -> window, the warm-up row left out."""
    out = {}
    for r in rows:
        if r.get("warmup"):
            continue
        for k, w in enumerate(r.get("windows", [])):
            out[(r["id"], k)] = w
    return out


def decode_ms(rows):
    return [w["decode_ms"] for r in rows if not r.get("warmup") for w in r.get("windows", [])]


def compare_runs(a_rows, b_rows):
    wa, wb = windows_of(a_rows), windows_of(b_rows)
    diffs = []
    for key in sorted(set(wa) | set(wb)):
        x, y = wa.get(key), wb.get(key)
        if x is None or y is None:
            diffs.append({"row": key[0], "window": key[1], "what": "missing in " + ("main" if x is None else "fix")})
        elif x["tokens"] != y["tokens"]:
            diffs.append({"row": key[0], "window": key[1], "what": "token ids", "main": x["tokens"], "fix": y["tokens"]})
        elif x["time_indices"] != y["time_indices"]:
            diffs.append({"row": key[0], "window": key[1], "what": "time indices"})
    # A row with an error counts as identical in both builds only when both stop at the same window with the
    # same message and every window before it has the same token ids (the supervisor's rule of 14:3x, written
    # into the round's lines before the ja GPU pair ran); any other error is a difference.
    ra = {r["id"]: r for r in a_rows if r.get("error")}
    rb = {r["id"]: r for r in b_rows if r.get("error")}
    def same_stop(i):
        x, y = ra.get(i), rb.get(i)
        return (x is not None and y is not None and x["error"] == y["error"]
                and [w["tokens"] for w in x.get("windows", [])] == [w["tokens"] for w in y.get("windows", [])])
    matched = sorted(i for i in set(ra) | set(rb) if same_stop(i))
    errors = [(r["id"], r["error"]) for r in a_rows + b_rows if r.get("error") and r["id"] not in matched]
    return {"windows_main": len(wa), "windows_fix": len(wb), "identical": len(wa) - len([d for d in diffs if d["what"] != "missing in main"]),
            "diffs": diffs[:5], "diff_count": len(diffs), "errors": errors[:5], "error_count": len(errors),
            "same_error_in_both_builds": [(i, ra[i]["error"], len(ra[i].get("windows", []))) for i in matched],
            "tokens_main": sum(len(w["tokens"]) for w in wa.values()),
            "capped_main": sum(1 for w in wa.values() if w.get("capped")),
            "capped_fix": sum(1 for w in wb.values() if w.get("capped"))}


def cmd_pair(rec, fix_tag):
    main_tag = fix_tag.replace("-fix-", "-main-")
    missing = [t for t in (main_tag, fix_tag) if not (rec / f"{t}.done").exists()]
    if missing:
        # A run stopped before its done marker (the sitting's end, a crash): not a token comparison.
        print(f"INCOMPLETE {fix_tag}: no done marker for {', '.join(missing)}")
        return 2
    try:
        _, a, _ = load_jsonl(rec / f"{main_tag}.jsonl")
        _, b, _ = load_jsonl(rec / f"{fix_tag}.jsonl")
    except FileNotFoundError as e:
        print(f"MISMATCH {fix_tag}: a run is missing ({e.filename})")
        return 1
    c = compare_runs(a, b)
    ok = c["diff_count"] == 0 and c["error_count"] == 0 and c["windows_main"] > 0
    da, db = decode_ms(a), decode_ms(b)
    med = (f"decode median main {statistics.median(da):.2f} ms / fix {statistics.median(db):.2f} ms"
           if da and db else "no decode times")
    print(f"{'OK' if ok else 'MISMATCH'} {fix_tag} against {main_tag}: {c['identical']} / {c['windows_main']} windows identical "
          f"({c['tokens_main']} tokens), diffs {c['diff_count']} {c['diffs'][:1]}, errors {c['error_count']} {c['errors'][:1]}, "
          f"same error in both builds {c['same_error_in_both_builds']}, capped {c['capped_main']} / {c['capped_fix']}; {med}")
    return 0 if ok else 1


def pct(b, a):
    return (b / a - 1.0) * 100.0


def cmd_summary(rec, private_path, prefix=""):
    out = {"lines": {}, "identity": {}, "cost": {}, "npu_decoder": {}, "npu_app": {}}
    private = {"cost": {}}
    # identity and cost, per entry and backend
    for model in ("v3", "ja"):
        for accel in ("cpu", "gpu"):
            runs = {}
            for arm in ("main", "fix"):
                for n in (1, 2, 3):
                    p = rec / f"{prefix}{model}-{accel}-{arm}-r{n}.jsonl"
                    if p.exists():
                        runs[(arm, n)] = load_jsonl(p)
            if not runs:
                continue
            key = f"{model}-{accel}"
            mains = [runs[k][1] for k in sorted(runs) if k[0] == "main"]
            fixes = [runs[k][1] for k in sorted(runs) if k[0] == "fix"]
            ref = mains[0] if mains else None
            comps = {}
            for (arm, n), (_, rows, _) in sorted(runs.items()):
                if ref is not None and rows is not ref:
                    comps[f"{arm}-r{n} against main-r1"] = compare_runs(ref, rows)
            all_ok = bool(mains) and bool(fixes) and all(c["diff_count"] == 0 and c["error_count"] == 0 for c in comps.values())
            out["identity"][key] = {"runs": [f"{a}-r{n}" for a, n in sorted(runs)], "windows": len(windows_of(ref)) if ref else 0,
                                    "tokens": sum(len(w["tokens"]) for w in windows_of(ref).values()) if ref else 0,
                                    "comparisons": comps, "pass": all_ok}
            if model == "v3":
                da = [x for rows in mains for x in decode_ms(rows)]
                db = [x for rows in fixes for x in decode_ms(rows)]
                per_run = {f"{a}-r{n}": {"windows": len(decode_ms(rows)), "decode_median_ms": statistics.median(decode_ms(rows)) if decode_ms(rows) else None,
                                         "encode_median_ms": statistics.median([w["encode_ms"] for r in rows if not r.get("warmup") for w in r["windows"]] or [0]),
                                         "pace_timeouts": sum(1 for r in rows if (r.get("pace_wait") or {}).get("timed_out")),
                                         "thermal_max": max([r.get("thermal_after", -1) for r in rows] or [-1])}
                           for (a, n), (_, rows, _) in sorted(runs.items())}
                if da and db:
                    ma, mb = statistics.median(da), statistics.median(db)
                    # paired windows (the same row and window in a main and a fix run of the same pair number)
                    ratios = []
                    for n in (1, 2, 3):
                        if ("main", n) in runs and ("fix", n) in runs:
                            wa, wb = windows_of(runs[("main", n)][1]), windows_of(runs[("fix", n)][1])
                            ratios += [wb[k]["decode_ms"] / wa[k]["decode_ms"] for k in wa if k in wb and wa[k]["decode_ms"] > 0]
                    # The public record keeps each build's own numbers; the ratio and the verdict go to the
                    # private verdict file only (no arm-to-arm ratio in public text).
                    out["cost"][key] = {"decode_median_main_runs_ms": ma, "decode_median_fix_runs_ms": mb,
                                        "windows_main": len(da), "windows_fix": len(db), "per_run": per_run}
                    private["cost"][key] = {"fix_vs_main_pct": pct(mb, ma),
                                            "paired_ratio_median_pct": (statistics.median(ratios) - 1) * 100 if ratios else None,
                                            "pass": pct(mb, ma) <= COST_LIMIT_PCT}
    # NPU decoder only
    dec = {}
    for tag in ("dec-cpu-f32-fix", "dec-npu-fix", "dec-cpu-f32-main", "dec-npu-main"):
        p = rec / f"{prefix}{tag}.json"
        if p.exists():
            dec[tag] = json.load(open(p))
    def toks(d):
        return [w["tokens"] for w in d["windows"]]
    for tag, d in dec.items():
        ref = dec.get("dec-cpu-f32-fix")
        same = None
        if ref is not None and tag != "dec-cpu-f32-fix":
            same = sum(1 for x, y in zip(toks(ref), toks(d)) if x == y)
        out["npu_decoder"][tag] = {"windows_run": d["windows_run"], "windows_failed": d["windows_failed"],
                                   "log": d.get("log"), "same_tokens_as_dec_cpu_f32_fix": same,
                                   "tokens_per_window": [len(t) for t in toks(d)],
                                   "first_error": next((w["error"] for w in d["windows"] if w.get("error")), None),
                                   "tdt_decoder_blob": d.get("tdt_decoder_blob"), "litert_version": d.get("litert_version")}
    if "dec-npu-fix" in dec and "dec-cpu-f32-fix" in dec:
        d = out["npu_decoder"]["dec-npu-fix"]
        mem = (d["log"] or {}).get("failed_to_find_memhandle")
        out["lines"]["npu_decoder"] = {"windows_failed": d["windows_failed"], "memhandle_lines": mem,
                                       "same_tokens_as_cpu": d["same_tokens_as_dec_cpu_f32_fix"], "windows": d["windows_run"],
                                       "pass": d["windows_failed"] == 0 and mem == 0 and d["same_tokens_as_dec_cpu_f32_fix"] == d["windows_run"] == 12}
    # NPU app path
    for tag in ("v3-npu-app-fix", "v3-npu-app-main"):
        p = rec / f"{prefix}{tag}.jsonl"
        if not p.exists():
            continue
        header, rows, end = load_jsonl(p)
        log = (end or {}).get("log") or {}
        crash = (rec / f"{prefix}{tag}.crash.log").exists()
        done = (rec / f"{prefix}{tag}.done").exists()
        out["npu_app"][tag] = {"rows": len(rows), "errors": [r["error"] for r in rows if r.get("error")],
                               "windows": sum(len(r["windows"]) for r in rows),
                               "capped_windows": sum(1 for r in rows for w in r["windows"] if w.get("capped")),
                               "ended_windows": sum(1 for r in rows for w in r["windows"] if w.get("ended")),
                               "texts": [r["text"][:120] for r in rows], "log": log, "crash_log": crash, "done": done,
                               "tdt_decoder_blob": (header or {}).get("tdt_decoder_blob")}
        if tag == "v3-npu-app-fix":
            out["lines"]["npu_app"] = {"memhandle_lines": log.get("failed_to_find_memhandle"), "err_6004_lines": log.get("err_6004"),
                                       "crash_log": crash, "done": done,
                                       "pass": log.get("failed_to_find_memhandle") == 0 and log.get("err_6004") == 0 and done and not crash}
    out["lines"]["identity"] = {k: v["pass"] for k, v in out["identity"].items()}
    form = prefix.rstrip("-")
    out["form"] = form or None
    (rec / (f"compare-{form}.json" if form else "compare.json")).write_text(json.dumps(out, indent=1) + "\n")
    private["lines"] = dict(out["lines"])
    private["lines"]["cost"] = {k: {"fix_vs_main_pct": round(v["fix_vs_main_pct"], 2), "pass": v["pass"]}
                                for k, v in private["cost"].items()}
    private_path.parent.mkdir(parents=True, exist_ok=True)
    private_path.write_text(json.dumps(private, indent=1) + "\n")
    print(json.dumps(private["lines"], indent=1))
    return 0


def main(argv):
    if len(argv) >= 3 and argv[0] == "pair":
        return cmd_pair(pathlib.Path(argv[1]), argv[2])
    if len(argv) >= 2 and argv[0] == "summary":
        prefix = argv[2] if len(argv) >= 3 else ""
        form = prefix.rstrip("-")
        private = pathlib.Path(__file__).resolve().parents[2] / ".build/asr-sigbuf" / (f"verdicts-{form}.json" if form else "verdicts.json")
        return cmd_summary(pathlib.Path(argv[1]), private, prefix)
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
