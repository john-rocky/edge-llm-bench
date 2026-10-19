#!/usr/bin/env python3
"""One line on one run, right after it (asr-fix-v1; asr-burst-v1's check_run.py): rows, errors, the
processes' load, where they ran (foreground state, cpuset, CPUs), dexopt, the waits, the falls, the
retakes and exclusions, tdt_fix and the decoder's frames per window, and the text against a reference
run of the same model (identical, identical after strip, differing). Plain python3 (no scoring): the
sitting reads it between runs; summarize.py does the full summary.

  check_run.py <REC>/<tag>.jsonl [--ref <jsonl of the reference run>]
"""
import argparse
import json
import statistics
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--ref", default="")
    args = ap.parse_args()
    try:
        rows = [json.loads(line) for line in open(args.jsonl) if line.strip()]
    except FileNotFoundError:
        print(json.dumps({"jsonl": args.jsonl, "error": "no jsonl"}))
        return 0
    heads = [r for r in rows if r.get("type") == "header"]
    foots = [r for r in rows if r.get("type") == "footer"]
    utts = {}
    for r in rows:
        if "id" in r:
            utts[r["id"]] = r
    utts = list(utts.values())
    waits = [u["wait_s"] for u in utts if u.get("wait_s") is not None]
    out = {
        "rows": len(utts),
        "errors": [(u["id"], u["error"]) for u in utts if u.get("error")],
        "loads_ms": [(h.get("load_label"), round(h.get("load_ms") or 0, 1)) for h in heads],
        "aborted": [h.get("aborted") for h in heads if h.get("aborted")],
        "foreground": [(h.get("foreground"), h.get("foreground_state"), h.get("foreground_top_app"),
                        h.get("foreground_top_app_wait_ms"), h.get("foreground_error")) for h in heads],
        "screen": [h.get("screen_start") for h in heads],
        "cpuset_after_load": [((h.get("process_state") or {}).get("after_load") or {}).get("cpuset") for h in heads],
        "cpus_after_load": [((h.get("process_state") or {}).get("after_load") or {}).get("cpus_allowed") for h in heads],
        "debuggable": [h.get("debuggable") for h in heads],
        "dexopt": [(h.get("dexopt_app"), h.get("dexopt_test"), len(h.get("oat_files_mapped") or [])) for h in heads],
        "cpuset_rows": sorted({u.get("cpuset") for u in utts if u.get("cpuset")}),
        "cpus_rows": sorted({u.get("cpus_allowed") for u in utts if u.get("cpus_allowed")}),
        "wait_median_s": statistics.median(waits) if waits else None,
        "wait_max_s": max(waits) if waits else None,
        "wait_timeouts": sum(1 for u in utts if u.get("wait_timed_out")),
        "drop_max": max([u.get("cap_drop_pct") or 0 for u in utts], default=None),
        "retaken": sum(1 for u in utts if u.get("attempts", 1) > 1),
        "excluded": sum(1 for u in utts if u.get("excluded")),
        "tdt_fix": [h.get("tdt_fix") for h in heads],
        "decode_frames_mean": (lambda xs: round(sum(xs) / len(xs), 1) if xs else None)(
            [x for u in utts for x in (u.get("window_decode_frames") or [])]),
        "capped_frames": sum(x for u in utts for x in (u.get("window_capped_frames") or [])),
        "empty_texts": sum(1 for u in utts if not u.get("error") and not u.get("text", "").strip()),
        "rtf": [f.get("rtf") for f in foots],
        "rtf_burst": [f.get("rtf_burst") for f in foots],
        "vmhwm_kb": [f.get("vmhwm_kb") for f in foots],
        "done": bool(foots),
    }
    if args.ref:
        ref = {}
        for line in open(args.ref):
            if line.strip():
                r = json.loads(line)
                if "id" in r:
                    ref[r["id"]] = r["text"]
        same = strip = diff = missing = 0
        first_diff = None
        for u in utts:
            if u["id"] not in ref:
                missing += 1
            elif u["text"] == ref[u["id"]]:
                same += 1
            elif u["text"].strip() == ref[u["id"]].strip():
                strip += 1
            else:
                diff += 1
                first_diff = first_diff or {"id": u["id"], "this": u["text"][:120], "ref": ref[u["id"]][:120]}
        out["text"] = {"identical": same, "identical_after_strip": strip, "different": diff, "missing_in_ref": missing,
                       "first_difference": first_diff}
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
