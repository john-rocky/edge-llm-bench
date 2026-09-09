#!/usr/bin/env python3
"""Post-capture gate for one cell: SHORT / DEAD / DEGENERATE / HOT / SPREAD / COLLAPSE / LEVEL / OK.

Automates the two flags the protocol already defines, instead of leaving them
to the operator's eye between cells (fairness cold-warm-split thermal guard;
spread-rule, same 5% bar as render_leaderboard and regression_diff):

  SHORT <n>        fewer records than --runs (crash/timeout — do NOT retry
                   here; failed-runs-stay owns that path)
  DEAD <n>         a judged record has no decode number (missing key or 0) —
                   the run completed as a record but not as a measurement
                   (audited 2026-08-27: zero-decode runs silently passed and
                   vanished from the spread list)
  DEGENERATE <n>   a judged record's outputSample is a repetition loop
                   (distinct character 6-grams under --degenerate-ratio of
                   the sample's 6-grams). The engine ran and reported a rate,
                   but it was generating garbage: the Core AI Qwen3-0.6B
                   macOS-26-era export decoded "[nodeelehandlinghandling…"
                   at 148 tok/s on the phone (2026-08-26) and 1127 tok/s on
                   the Mac (2026-09-08) and both passed every other check.
                   Never retried — a re-run reproduces it; the runner flags
                   the cell and the number must not be read as a speed.
  HOT <states>     an initialThermalState outside --ok-thermal
  SPREAD <pct>     warm decode (max-min)/median exceeded --spread-flag
  COLLAPSE <pct>   cold-only capture (Android regime has no warm runs, so
                   SPREAD can never fire) with the contended-device
                   signature: the slowest cold decode under half the median
                   (measured 2026-08-27 Pixel: 0.3-1.4 tok/s junk beside
                   22-26 clean in one session) OR the median under half the
                   fastest run (2026-09-09 Pixel 8a: 4.9 then 1.6 / 1.4 —
                   two slow runs move the median itself, and the
                   slowest/median test read 87%). <pct> is the lower of the
                   two ratios. The bar is 50%, not --spread-flag: Android
                   cold trials legitimately spread 15-30% and a 5% bar would
                   flag every capture.
  LEVEL <pct>      only with --previous (the quarantined capture this retry
                   replaces): the retry's judged median under half the
                   median of the previous capture's un-collapsed runs (those
                   at or above half its fastest). A block re-run that is
                   uniformly slow passes every within-capture test
                   (2026-09-08 Pixel 8a: 1.3 / 0.9 / 1.3 after 5.2 / 5.3 /
                   2.5, slowest/median 69%) and stood at 26% of the cell's
                   previous week; this is the cross-capture check the
                   within-capture rules cannot make. <pct> = retry median /
                   reference x 100. Same basis as the retry (warm runs when
                   the regime has them, else cold).
  OK

Input: schema-v1 records — --jsonl <cell.jsonl> (mac runner) or positional
per-run .json files (iPhone device-jsonl pulls). Only the newest --runs
records are judged: a retried cell is judged on its retry, not its history.

Runners act on the verdict by quarantining the flagged capture (mac:
<cell>.jsonl.attempt1, outside build_summary's *.jsonl glob; iPhone:
device-jsonl-flagged/; Android: <run>.json.attempt1) and re-running ONCE. The
flagged capture always stays on disk in raw — replaced wholesale, never mixed
run-by-run (no-cherry-pick). A runner judging the retry passes the quarantined
records as --previous so LEVEL can fire; a LEVEL retry stands, flagged.
Exit: 0 = OK, 1 = flagged.
"""
import argparse
import json
import statistics
import sys

DEGENERATE_MIN_CHARS = 60   # shorter samples are not judged (too few n-grams)


def degenerate(sample, ratio):
    """True when the sample is a repetition loop: fewer distinct character
    6-grams than `ratio` of all its 6-grams. Coherent prose of 200 chars sits
    near 0.95; "handlinghandling…" sits near 0.05."""
    s = (sample or "").strip()
    if len(s) < DEGENERATE_MIN_CHARS:
        return False
    grams = [s[i:i + 6] for i in range(len(s) - 5)]
    return len(set(grams)) / len(grams) < ratio


def load_records(jsonl, files):
    """Schema-v1 records from one .jsonl or positional .json files, oldest first."""
    recs = []
    if jsonl:
        with open(jsonl) as fh:
            recs = [json.loads(ln) for ln in fh if ln.strip()]
    else:
        for f in files:
            with open(f) as fh:
                recs.append(json.load(fh))
    recs.sort(key=lambda d: d.get("timestamp") or "")
    return recs


def decodes(recs, warm_only):
    return [m["decodeTokensPerSecond"] for r in recs for m in [r.get("metrics", {})]
            if m.get("decodeTokensPerSecond") and (not warm_only or not m.get("coldRun"))]


def reference_level(previous, warm_basis):
    """Median of the previous capture's un-collapsed runs (at or above half
    its fastest) on the retry's basis, or None when nothing is judgeable."""
    vals = decodes(previous, warm_basis) or (decodes(previous, False) if warm_basis else [])
    if not vals:
        return None
    top = max(vals)
    return statistics.median([v for v in vals if v >= top / 2])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, required=True)
    ap.add_argument("--spread-flag", type=float, default=5.0)
    ap.add_argument("--ok-thermal", default="nominal",
                    help="comma list; empty/missing states always pass")
    ap.add_argument("--degenerate-ratio", type=float, default=0.5,
                    help="distinct/total character 6-grams of outputSample below this = DEGENERATE")
    ap.add_argument("--jsonl")
    ap.add_argument("--previous", nargs="*", default=[],
                    help="records of the quarantined capture this retry replaces "
                         "(.json files, or one .jsonl); enables LEVEL")
    ap.add_argument("files", nargs="*")
    a = ap.parse_args()

    try:
        recs = load_records(a.jsonl, a.files)
    except (OSError, json.JSONDecodeError) as e:
        print(f"SHORT 0 ({e.__class__.__name__})")
        return 1
    recs = recs[-a.runs:]
    if len(recs) < a.runs:
        print(f"SHORT {len(recs)}")
        return 1

    dead = sum(1 for r in recs
               if not r.get("metrics", {}).get("decodeTokensPerSecond"))
    if dead:
        print(f"DEAD {dead}")
        return 1

    degen = sum(1 for r in recs if degenerate(r.get("outputSample"), a.degenerate_ratio))
    if degen:
        print(f"DEGENERATE {degen}")
        return 1

    ok = set(a.ok_thermal.split(",")) | {"", None}
    states = [r.get("metrics", {}).get("initialThermalState") for r in recs]
    if any(s not in ok for s in states):
        print("HOT " + ",".join(str(s) for s in states))
        return 1

    warm = [m["decodeTokensPerSecond"] for r in recs
            for m in [r.get("metrics", {})]
            if not m.get("coldRun")]
    if len(warm) > 1:
        med = statistics.median(warm)
        spread = (max(warm) - min(warm)) / med * 100 if med else 0.0
        if spread > a.spread_flag:
            print(f"SPREAD {spread:.1f}")
            return 1
    if not warm:
        cold = [r["metrics"]["decodeTokensPerSecond"] for r in recs]
        if len(cold) > 1:
            med = statistics.median(cold)
            if med:
                # slowest under half the median, or the median under half the
                # fastest: the same signature seen from either side
                low = min(min(cold) / med, med / max(cold))
                if low < 0.5:
                    print(f"COLLAPSE {low * 100:.0f}")
                    return 1
    if a.previous:
        # a retry judged on its own runs passes when it is uniformly slow;
        # its level is judged once, here, on the capture it replaces
        try:
            previous = load_records(a.previous[0] if len(a.previous) == 1 and
                                    a.previous[0].endswith(".jsonl") else None,
                                    a.previous if not (len(a.previous) == 1 and
                                                       a.previous[0].endswith(".jsonl")) else [])
        except (OSError, json.JSONDecodeError):
            previous = []
        ref = reference_level(previous, bool(warm))
        cur = warm if warm else [r["metrics"]["decodeTokensPerSecond"] for r in recs]
        if ref and cur:
            cur_med = statistics.median(cur)
            if cur_med < ref / 2:
                print(f"LEVEL {cur_med / ref * 100:.0f}")
                return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
