#!/usr/bin/env python3
"""Render LEADERBOARD.md from results/summary/*.csv (continuous-bench
condition 6: an always-current standings view over the accumulation layer).

  python3 scripts/render_leaderboard.py          # rewrite the generated block
  python3 scripts/render_leaderboard.py --check  # CI: fail if stale

Neutrality invariants (why cells look the way they do):
  - quantization and engine version sit NEXT TO every number
    (quant-per-arm-rule; the 2026-07-17 trophy audit).
  - structural exclusions render as "— (<reason>)" from matrices/*.cells
    (failed-runs-stay).
  - no trophy marks; rows sort by warm decode but the recipe is visible.
  - cold and warm are separate columns, never pooled (cold-warm-split);
    the headline is the SHORT-CHAT task; other tasks live in RESULTS.md.
  - a warm median whose trial spread exceeds SPREAD_FLAG carries ⚠
    (spread-rule).
  - a run whose decoded text failed the text check (summary text_check
    FAIL:…) pools into no number, like a firstEver run (text-check-rule).
  - a run during which the phone capped the clock of a CPU the engine ran
    on (summary cpu_capped true) pools into no number either when the
    ceiling fell by more than CPU_CAP_MAX_DROP_PCT (summary
    cpu_cap_drop_pct); a run whose ceiling fell by less pools, counted, so
    the surfaces can mark the number (cpu-cap-rule). On an Android NPU or
    GPU arm (CPU_CAP_EXEMPT_ARMS) a capped run pools, counted, however far
    the ceiling fell, and the surfaces mark the number with the largest fall.
  - nor does a llama.cpp side-build run whose own device lines did not show
    the cell's npu / gpu device (summary backend_registered false).
  - GSM8K joins on (model_id, runtime); pre-v1 quality rows have no
    model_id and deliberately do not join (tag prose is not decoded).
"""
import argparse
import csv
import glob
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench_common import (DEVICE_DISPLAY, atomic_write, bandwidth_utilization,  # noqa: E402
                          corrected_quant, fmt_bw, logical_model)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUMMARY = os.path.join(ROOT, "results", "summary")
TARGET = os.path.join(ROOT, "LEADERBOARD.md")
BEGIN = "<!-- BEGIN GENERATED: scripts/render_leaderboard.py -->"
END = "<!-- END GENERATED: scripts/render_leaderboard.py -->"
HEADLINE_TASK = "short-chat"
SPREAD_FLAG = 5.0  # % — same bar the regression differ uses
# cpu-cap-rule line (owner decision 2026-10-08, methodology/fairness-rules.md §13): a run
# flagged cpu-capped still pools, counted and marked, while the clock ceiling of the CPUs
# the engine ran on fell by at most this many percent (summary cpu_cap_drop_pct: the
# largest (1 - min / hw) x 100 over their cpufreq policies); a deeper cap keeps it out of
# every pool. Material, the Galaxy S26 of 2026-10-08 (results/raw/2026-10-08-dashboard-
# ortgenai-v1-s26-*-android): the largest fall of a run was 3-14 % in the LiteRT-LM GPU
# anchor's run 1 and the ONNX Runtime GenAI Qwen3 1.7B short-chat runs, 19 % in its 4B
# short-chat runs and 49-58 % in every 1K launch (the prime cluster, policy6, fell
# furthest in each).
CPU_CAP_MAX_DROP_PCT = 15
# cpu-cap-rule, the accelerator arms (owner decision 2026-10-08, methodology/fairness-rules.md
# §13): the Android arms whose engine places the model on the NPU or the GPU. A run of theirs
# flagged cpu-capped pools, counted and marked with its fall, whatever the fall; the line above
# holds for every other arm (the CPU arms llama.cpp, litert-lm-cpu, executorch-xnnpack,
# onnxruntime-genai-cpu, litert-cpu). On these arms the capped CPUs carry the engine's host
# side. Material, the Galaxy S26 (standup ROUND-r1, -r3 and -r6 of the NPU rows lane,
# 2026-10-07/08): five llama-bench tg256 repetitions under a cap that set in during the test
# spread 1.2 % with no trend on the NPU arm and fell 3.4 % from the first to the last on the
# GPU arm (the cap's direction; the cause not established); the cap follows the SoC's
# temperature, not the skin sensor or charging, so no phone setting removes it; with the line
# alone the Qwen3 1.7B 1K cells of both llama.cpp arms (28-44 %) and every protocol cell
# (53-63 %) had no valid run. Only the Android runner reads the caps: the same arm names on
# the Mac and the iPhone carry no flag. Revert: an empty set — every arm follows the line
# again (the summary does not read it; re-render the surfaces).
CPU_CAP_EXEMPT_ARMS = frozenset({
    "llama.cpp-npu",      # llama.cpp side build, Hexagon NPU (--device HTP0)
    "llama.cpp-gpu",      # llama.cpp side build, Adreno GPU through OpenCL (--device GPUOpenCL)
    "litert-lm-npu",      # LiteRT-LM, NPU through the Qualcomm dispatch
    "litert-lm-gpu",      # LiteRT-LM, GPU
    "executorch-vulkan",  # ExecuTorch, Vulkan delegate (GPU)
    "executorch-qnn",     # ExecuTorch, QNN delegate (Hexagon NPU)
})


def load(name):
    path = os.path.join(SUMMARY, name)
    if not os.path.exists(path):
        return []
    with open(path) as fh:
        return list(csv.DictReader(fh))


def fnum(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def device_name(model_identifier):
    # modelIdentifier ("iPhone18,1") is the join key; DEVICE_DISPLAY keys are
    # filename labels — show the identifier as-is when no mapping applies.
    return DEVICE_DISPLAY.get(model_identifier, model_identifier)


_VERSION_TAG = re.compile(r"^v?\d+(\.\d+)+$")


def latest_session(rows):
    """Rows of the newest capture SESSION for one (device, runtime, model) cell —
    cross-session pooling is invalid (iphone-session-variance). A session is a
    campaign dir (one sitting), not a calendar date: two sittings on one day
    must not pool (2026-08-24, a fair-thermal morning + a nominal evening
    retake of MiniCPM produced a fictitious pooled warm median under the old
    date key). Date remains the key for legacy flat rows with no campaign.

    Engine first, then time: a regression pair re-measures the OLD engine
    after the new one (the v0.15.0 baseline rehearsal ran after the v0.16.0
    capture), so pure timestamp order would crown the baseline. When every
    engine string in the cell is a comparable version tag, the newest engine
    wins before the newest session; hash/opaque engines keep timestamp order."""
    engines = {r["engine_version"] or "" for r in rows}
    if len(engines) > 1 and all(_VERSION_TAG.match(e) for e in engines):
        top = max(engines, key=lambda e: [int(x) for x in re.findall(r"\d+", e)])
        rows = [r for r in rows if (r["engine_version"] or "") == top]

    def skey(r):
        return r["campaign"] or (r["timestamp"] or "")[:10]
    newest = max(rows, key=lambda r: r["timestamp"] or "")
    sess = [r for r in rows if skey(r) == skey(newest)]
    return sess, max((r["timestamp"] or "")[:10] for r in sess)


def shallow_cap(r, arm=None):
    """A row flagged cpu-capped that pools, counted (cpu-cap-rule): on an arm of
    CPU_CAP_EXEMPT_ARMS whatever its fall, on every other arm when its engine CPUs' clock
    ceiling fell by at most CPU_CAP_MAX_DROP_PCT (summary cpu_cap_drop_pct, read as the
    column shows it). arm = the row's arm, by default its runtime column. A CPU arm's
    flagged row without the column (a summary built before 2026-10-08) is not shallow and
    stays out, as every flagged run did then."""
    if r.get("cpu_capped") != "true":
        return False
    if (r.get("runtime") if arm is None else arm) in CPU_CAP_EXEMPT_ARMS:
        return True
    drop = fnum(r.get("cpu_cap_drop_pct"))
    return drop is not None and drop <= CPU_CAP_MAX_DROP_PCT


def arm_row(rows):
    """One leaderboard line from one cell's latest-session rows."""
    sess, date = latest_session(rows)
    # firstEver rows are the engine-cache build (cold-warm-split: reported
    # separately, never as the engine's speed) — they stay in the session for
    # quant/engine identity but contribute to no metric pool
    meas = [r for r in sess if r.get("first_ever") != "True"]
    # text-check-rule: a run whose decoded text failed the text check is not a
    # measurement either — same treatment, counted so the surfaces can say why
    # a pool shrank or emptied; .get: summaries built before 2026-10-06 have no
    # text_check column
    text_fail = [r for r in meas if (r.get("text_check") or "").startswith("FAIL")]
    text_checked = sum(1 for r in meas if r.get("text_check"))
    meas = [r for r in meas if not (r.get("text_check") or "").startswith("FAIL")]
    # cpu-cap-rule: a run during which the ceiling of a CPU the engine ran on fell
    # more than CPU_CAP_MAX_DROP_PCT below its hardware maximum measured the phone's
    # cap, not the engine — same treatment again, after the text check (a run that
    # failed both counts as a text failure); a shallower cap pools, counted below, and
    # so does any cap on an accelerator arm (CPU_CAP_EXEMPT_ARMS, shallow_cap);
    # .get: summaries built before 2026-10-07 have no cpu_capped
    cpu_capped = [r for r in meas if r.get("cpu_capped") == "true" and not shallow_cap(r)]
    cpu_read = sum(1 for r in meas if r.get("cpu_capped"))
    meas = [r for r in meas if r.get("cpu_capped") != "true" or shallow_cap(r)]
    # a llama.cpp side build's run whose own device lines did not show the cell's
    # device (npu / gpu) measured another device — same treatment, last; .get:
    # summaries built before 2026-10-07 have no backend_registered column
    backend_off = [r for r in meas if r.get("backend_registered") == "false"]
    meas = [r for r in meas if r.get("backend_registered") != "false"]
    # the pool's runs that ran under a cap within the line (any cap on an accelerator
    # arm): they count, and the surfaces mark the number with how many there were and,
    # on an accelerator arm, the largest fall among them
    capped_counted = [r for r in meas if shallow_cap(r)]
    counted_drops = [fnum(r.get("cpu_cap_drop_pct")) for r in capped_counted]
    counted_drops = [v for v in counted_drops if v is not None]
    warm = [fnum(r["decode_tps"]) for r in meas if r["cold_run"] == "False"]
    warm = [v for v in warm if v]
    cold = [fnum(r["decode_tps"]) for r in meas if r["cold_run"] == "True"]
    cold = [v for v in cold if v]
    wmed = statistics.median(warm) if warm else None
    spread = ((max(warm) - min(warm)) / wmed * 100) if wmed and len(warm) > 1 else 0.0
    # Cold median + spread for the regimes that have no warm runs (Android
    # v1: every run is a fresh process). `cold` below stays the session's
    # last cold run — the leaderboard's historical column — so nothing that
    # renders from it moves; the dashboard reads cold_median where the
    # platform's headline regime is cold (no-cherry-pick: the median of the
    # session's runs, with its spread, never a single trial).
    cmed = statistics.median(cold) if cold else None
    cspread = ((max(cold) - min(cold)) / cmed * 100) if cmed and len(cold) > 1 else 0.0
    prefill = [fnum(r["prefill_tps"]) for r in meas]
    prefill = [v for v in prefill if v]
    ttft = [fnum(r["ttft_ms"]) for r in meas]
    ttft = [v for v in ttft if v]
    # iOS rows carry phys_footprint; android rows only RSS (no Android
    # equivalent of footprint — never fabricated). Same column, semantics
    # disclosed in the header note.
    mem = [fnum(r["mem_footprint_median_mb"]) or fnum(r["mem_resident_median_mb"])
           for r in meas]
    mem = [v for v in mem if v]
    # per-run high-water, same basis choice as mem; .get: summaries built
    # before 2026-10-06 have no peak columns
    mem_peak = [fnum(r.get("mem_footprint_peak_mb")) or fnum(r.get("mem_resident_peak_mb"))
                for r in meas]
    mem_peak = [v for v in mem_peak if v]
    quants, qcorr = set(), False
    for r in sess:
        # corrected_quant also restores an audited label for rows recorded
        # without one (the Android Qwen3-4B LiteRT case), so it runs on every row
        q, c = corrected_quant(r["runtime"], r["model_id"], r["quantization"] or "")
        if q:
            quants.add(q)
            qcorr = qcorr or c
    quants = sorted(quants)
    engines = sorted({r["engine_version"] for r in sess if r["engine_version"]})
    return {
        "warm": wmed, "warm_n": len(warm), "spread": spread,
        "cold": cold[-1] if cold else None,
        "cold_median": cmed, "cold_n": len(cold), "cold_spread": cspread,
        "campaign": sess[0]["campaign"] if sess else "",
        "thermal_initial": sorted({r.get("thermal_initial") or "" for r in meas}),
        "prefill": statistics.median(prefill) if prefill else None,
        "ttft": statistics.median(ttft) if ttft else None,
        "mem": statistics.median(mem) if mem else None,
        "mem_peak": statistics.median(mem_peak) if mem_peak else None,
        "mem_peak_n": len(mem_peak),
        "quant": (" / ".join(quants) or "unrecorded") + ("†" if qcorr else ""),
        "engine": " / ".join(engines) or "pre-stamp",
        "date": date, "n": len(meas),
        # runs the text check kept out of the pool, the flags they raised, and
        # how many of the would-be pool were checked at all (0 = no text check)
        "text_fail_n": len(text_fail),
        "text_fail_flags": ", ".join(sorted({f for r in text_fail
                                             for f in r["text_check"][len("FAIL:"):].split(",") if f})),
        "text_checked_n": text_checked,
        # runs the CPU cap kept out of the pool (a fall past CPU_CAP_MAX_DROP_PCT), the
        # pool's runs under a cap within it (any cap on an accelerator arm) with the
        # largest fall among them (None: none, or no fall recorded), and the runs past the
        # text check whose caps were read, capped or not (0 = not read: no cpu-cap-rule
        # verdict)
        "cpu_capped_n": len(cpu_capped),
        "cpu_capped_counted_n": len(capped_counted),
        "cpu_capped_counted_max_drop": max(counted_drops) if counted_drops else None,
        "cpu_read_n": cpu_read,
        # runs a side build's device lines kept out of the pool (backend-not-registered)
        "backend_off_n": len(backend_off),
    }


def quality_lookup(quality_rows):
    out = {}
    for r in quality_rows:
        if r.get("model_id") and r.get("runtime"):
            key = (r["model_id"], r["runtime"])
            out.setdefault(key, []).append(r)
    return out


def structural_exclusions():
    """exclude= cells from matrices/*.cells, grouped by platform."""
    out = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "matrices", "*.cells"))):
        for raw in open(path):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            reason = next((p.split("=", 1)[1] for p in parts[4:]
                           if p.startswith("exclude=")), None)
            if reason:
                out.setdefault(parts[0], set()).add(
                    (parts[1], parts[2], parts[3], reason))
    return out


def fmt(v, unit=""):
    if v is None:
        return "—"
    return f"{v:.1f}{unit}"


def generate():
    device_rows = load("device-runs.csv")
    qlook = quality_lookup(load("quality.csv"))
    excl = structural_exclusions()

    # (platform, device) -> logical model -> (runtime, model_id) -> rows
    tree = {}
    latest_stamp = ""
    for r in device_rows:
        if r["task"] != HEADLINE_TASK or not r["model_id"] or not r["device"]:
            continue
        latest_stamp = max(latest_stamp, (r["timestamp"] or "")[:10])
        plat = r.get("platform") or "?"
        tree.setdefault((plat, r["device"]), {}) \
            .setdefault(logical_model(r["model_id"]), {}) \
            .setdefault((r["runtime"], r["model_id"]), []).append(r)

    lines = [
        BEGIN,
        "",
        f"Generated from `results/summary/*.csv` (latest capture {latest_stamp or 'n/a'}) "
        "by `scripts/render_leaderboard.py` — do not edit inside the markers.",
        "",
        f"Headline task: **{HEADLINE_TASK}**, warm = median of same-session warm runs "
        "(cold-warm-split); other tasks and full history: RESULTS.md. Rows sort by warm "
        "decode; the recipe (quantization, engine build) is part of every row — a faster "
        "number under a different recipe is a different deployment profile, not a win.",
        "",
        "† = quantization label carries the audited in-place correction "
        "(Gemma-4 `.litertlm` is the wNa8o8 mobile schema; early rows recorded "
        "\"INT4 (QAT)\" — quant-label-rule). mem MB = phys_footprint on Apple rows, "
        "RSS on Android rows (no footprint equivalent; methodology/android.md). "
        "bw util = the headline decode (warm on Apple, cold median on Android) × "
        "bytes per token (the artifact minus per-token-gathered tables such as Gemma 4's "
        "per-layer embeddings; `models/artifact-bytes.json`) ÷ the device's memory-bandwidth "
        "ceiling (`devices/memory-bandwidth.json`, cited per device; `~` = derived or "
        "estimated ceiling, not a vendor figure; — = no citable ceiling or unregistered "
        "artifact). A recipe-normalized estimate, never a ranking.",
        "",
    ]
    for plat in ("mac", "ios", "android"):
        keys = sorted(k for k in tree if k[0] == plat)
        if not keys and plat not in excl:
            continue
        lines.append(f"## {plat}")
        lines.append("")
        if plat == "android":
            lines.append(
                "Android decode spans are not budget-matched across arms: llama-cli "
                "caps at the 128-token task budget, while `litert_lm_main` runs to "
                "the model's own stop (441–1037 generated tokens per run in the raw "
                "records) — v0.16.0 has no working output cap on that binary. LiteRT "
                "decode rates reproduce within ~1% across sessions, so the longer "
                "span is not visibly depressing them, but the asymmetry is real and "
                "per-run token counts are in `results/raw/` "
                "(budget-mode-rule; methodology/android.md).")
            lines.append("")
        for key in keys:
            _, dev = key
            models = tree[key]
            # comparison first: models with >=2 arms, then single-arm cells compactly
            multi = {m: arms for m, arms in models.items() if len(arms) >= 2}
            single = {m: arms for m, arms in models.items() if len(arms) < 2}
            lines.append(f"### {device_name(dev)}")
            lines.append("")
            for model in sorted(multi):
                arms = multi[model]
                lines.append(f"**{model}**")
                lines.append("")
                lines.append("| runtime | artifact | quant | engine | warm tok/s | cold tok/s | bw util | prefill tok/s | TTFT ms | mem MB | GSM8K | captured |")
                lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
                entries = []
                for (rt, mid), rows in arms.items():
                    a = arm_row(rows)
                    q = qlook.get((mid, rt))
                    if q:
                        qbest = q[-1]
                        thinking = qbest.get("thinking") or "off"
                        qtxt = f"{float(qbest['acc'])*100:.1f}% (n={qbest['n']}, thinking {thinking})"
                    else:
                        qtxt = "—"
                    entries.append((a["warm"] or 0, rt, mid, a, qtxt))
                for _, rt, mid, a, qtxt in sorted(entries, reverse=True):
                    warm_txt = fmt(a["warm"])
                    if a["warm"] and a["spread"] > SPREAD_FLAG:
                        warm_txt += f" ⚠spread {a['spread']:.0f}%"
                    headline = a["warm"] if plat != "android" else a["cold_median"]
                    bw = fmt_bw(bandwidth_utilization(headline, rt, mid, dev, plat))
                    lines.append(
                        f"| {rt} | `{mid}` | {a['quant']} | {a['engine']} | {warm_txt} | "
                        f"{fmt(a['cold'])} | {bw} | {fmt(a['prefill'])} | {fmt(a['ttft'])} | "
                        f"{fmt(a['mem'])} | {qtxt} | {a['date']} |")
                lines.append("")
            if single:
                lines.append("<details><summary>single-arm cells (no cross-runtime comparison)</summary>")
                lines.append("")
                lines.append("| model | runtime | artifact | quant | engine | warm tok/s | cold tok/s | captured |")
                lines.append("|---|---|---|---|---|---|---|---|")
                for model in sorted(single):
                    for (rt, mid), rows in single[model].items():
                        a = arm_row(rows)
                        # same ⚠ as the comparison branch — a wide cell is no
                        # less wide for lacking a rival (audited 2026-08-27:
                        # three >5% cells published unmarked through this gap)
                        warm_txt = fmt(a["warm"])
                        if a["warm"] and a["spread"] > SPREAD_FLAG:
                            warm_txt += f" ⚠spread {a['spread']:.0f}%"
                        lines.append(f"| {model} | {rt} | `{mid}` | {a['quant']} | {a['engine']} | "
                                     f"{warm_txt} | {fmt(a['cold'])} | {a['date']} |")
                lines.append("")
                lines.append("</details>")
                lines.append("")
        if plat in excl:
            lines.append("**Structural exclusions** (failed-runs-stay — the row exists, the reason is the datum):")
            lines.append("")
            for rt, mid, task, reason in sorted(excl[plat]):
                lines.append(f"- `{rt} {mid} {task}` — {reason}")
            lines.append("")
    lines.append(END)
    return "\n".join(lines) + "\n"


HEADER = """# Leaderboard — current standings per platform

Neutral, reproducible standings for local LLM runtimes on-device. Every number
carries its recipe (quantization + engine build): arms run at their own best
available build, which is only a fair comparison when the recipe is visible.
Method and rules: `methodology/fairness-rules.md`. Raw records: `results/`.
Regenerate: `python3 scripts/build_summary.py && python3 scripts/render_leaderboard.py`.

"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    block = generate()
    if os.path.exists(TARGET):
        current = open(TARGET).read()
        if BEGIN in current and END in current:
            head, _, rest = current.partition(BEGIN)
            _, _, tail = rest.partition(END)
            new = head + block.rstrip("\n").replace(BEGIN + "\n", BEGIN + "\n", 1) + tail
            new = head + block + tail.lstrip("\n")
        else:
            new = current.rstrip("\n") + "\n\n" + block
    else:
        new = HEADER + block
    if args.check:
        if not os.path.exists(TARGET) or open(TARGET).read() != new:
            print("LEADERBOARD.md is stale — run scripts/render_leaderboard.py", file=sys.stderr)
            return 1
        print("LEADERBOARD.md is up to date.")
        return 0
    with atomic_write(TARGET) as fh:
        fh.write(new)
    print(f"wrote {os.path.relpath(TARGET, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
