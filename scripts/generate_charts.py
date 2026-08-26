#!/usr/bin/env python3
"""Generate docs/charts/*.png from the accumulation layer — never from literals.

Reads results/summary/device-runs.csv and results/regression-reports/*/verdicts.json;
if a number here disagrees with the leaderboard, the bug is here, not there.

Palette: dataviz-validated defaults (categorical #2a78d6/#eb6834/#1baf7a passes
CVD+normal-vision checks on the #fcfcfb surface; the contrast WARN on aqua is
relieved by direct value labels on every mark). Diverging = blue/red with a
gray near-zero band. Identity is never color-alone: every bar carries its label.
"""
import csv
import json
import glob
import os
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "charts")
os.makedirs(OUT, exist_ok=True)

SURFACE = "#fcfcfb"
INK = "#333330"
MUTED = "#6f6e6a"
GRID = "#e8e7e4"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
RED, NEUTRAL = "#e34948", "#b0afac"

ARM_COLOR = {  # fixed categorical order — color follows the entity
    "litert-lm": BLUE, "litert-lm-cpu": BLUE, "litert-lm-gpu": BLUE,
    "llama.cpp": ORANGE, "mlx-swift": AQUA,
}


def style_ax(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


# Every table in this file is a per-DEVICE view (its column headers name the
# device), so every filter must pin the device, not just the platform — the
# Galaxy S26's first session (platform=android) silently pooled into the
# "Pixel 8a" columns the day it landed. Same-device-class rule.
DEV = {"mac": "Mac16,9", "ios": "iPhone18,1", "android": "Pixel 8a"}



def ios_admissible_campaigns(rows, tol=0.05):
    """iPhone chart admission: nominal starts, plus fair-start sessions whose
    in-session mlx anchor matches the newest all-nominal anchor within tol.

    Why: plugged + warm ambient pins this device's reported thermal state at
    'fair' regardless of load (2026-08-26: powered off, it would not cool
    below 'fair'), so the state label cannot discriminate suppression there.
    The anchor can: the same day produced fair-at-full-speed (mlx 177 vs the
    nominal-era 171.6, litert/LFM matching their nominal-session values
    exactly) AND fair-with-suppression (mlx 127-159, rejected by this gate).
    Sessions without an anchor fall back to nominal-only.
    """
    import collections
    anchors = collections.defaultdict(list)      # campaign -> warm anchor vals
    anchor_nominal = collections.defaultdict(lambda: True)
    for r in rows:
        if (r["platform"] == "ios" and r["device"] == DEV["ios"]
                and r["runtime"] == "mlx-swift" and "Qwen3-0.6B" in r["model_id"]
                and r["task"] == "short-chat" and r["cold_run"] == "False"
                and r["decode_tps"]):
            anchors[r["campaign"]].append(float(r["decode_tps"]))
            if (r["thermal_initial"] or "nominal") != "nominal":
                anchor_nominal[r["campaign"]] = False
    ref = None
    for c in sorted(anchors, reverse=True):      # newest campaign dirs sort last; reverse -> newest first
        if anchor_nominal[c]:
            ref = statistics.median(anchors[c]); break
    if ref is None:
        return set()
    return {c for c, vals in anchors.items()
            if abs(statistics.median(vals) / ref - 1) <= tol}


def ios_row_ok(r, admissible):
    t = r["thermal_initial"] or ""
    return t in ("nominal", "") or (t == "fair" and r["campaign"] in admissible)

def load_rows():
    with open(os.path.join(ROOT, "results", "summary", "device-runs.csv")) as fh:
        return list(csv.DictReader(fh))


def nominal_median(rows, campaign_sub, runtime, model_sub, task, cold):
    vals = [float(r["decode_tps"]) for r in rows
            if campaign_sub in r["campaign"] and r["runtime"] == runtime
            and model_sub in r["model_id"] and r["task"] == task
            and r["cold_run"] == cold and r["decode_tps"]
            and (r["thermal_initial"] or "nominal") == "nominal"]
    return statistics.median(vals) if vals else None


def chart_regression():
    """v0.15/v0.13-era -> v0.16.0 scored verdicts, one bar per cell (diverging)."""
    cells = []
    for f in sorted(glob.glob(os.path.join(ROOT, "results", "regression-reports",
                                           "*litert-lm-v0.16.0*", "verdicts.json"))):
        d = json.load(open(f))
        plat = ("iPhone 17 Pro" if "ios" in os.path.basename(os.path.dirname(f))
                else "Mac Studio M4 Max" if "mac" in os.path.basename(os.path.dirname(f))
                else "Pixel 8a")
        for v in d["verdicts"]:
            if v["verdict"] not in ("OK", "IMPROVED", "REGRESSION"):
                continue
            delta = (v.get("anchor") or {}).get("normalized_delta_pct",
                                                v.get("raw_delta_pct"))
            model = v["cell"].split()[2].split("/")[-1].replace("-litert-lm", "")
            label = f"{plat} · {model} · {v['metric'].replace('_', ' ')}"
            cells.append((label, delta, v["verdict"]))
    cells.sort(key=lambda c: c[1])
    fig, ax = plt.subplots(figsize=(8.6, 0.52 * len(cells) + 1.6), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    style_ax(ax)
    ys = range(len(cells))
    colors = [RED if v == "REGRESSION" else BLUE if abs(d) > 3 else NEUTRAL
              for _, d, v in cells]
    ax.barh(ys, [d for _, d, _ in cells], height=0.55, color=colors,
            edgecolor=SURFACE, linewidth=2)
    ax.axvline(0, color=MUTED, linewidth=1)
    for y, (label, d, verdict) in zip(ys, cells):
        # negative bars are tiny here — putting their label left of the bar
        # collides with the y tick labels; the region right of the zero line
        # is free, so all labels sit on the right side
        ax.text(max(d, 0) + 0.4, y, f"{d:+.1f}%  {verdict}",
                va="center", ha="left", fontsize=9, color=INK)
    lo = min(d for _, d, _ in cells)
    ax.set_xlim(min(lo * 1.5, -2.5), None)
    ax.set_yticks(list(ys))
    ax.set_yticklabels([c[0] for c in cells], fontsize=9, color=INK)
    ax.set_xlabel("decode / prefill / TTFT delta vs previous capture (%, anchor-normalized "
                  "where cross-session)", fontsize=9, color=MUTED)
    ax.set_title("LiteRT-LM v0.16.0 — release regression verdicts (scored cells only; "
                 "spread- or n-gated cells not shown)", fontsize=11, color=INK,
                 loc="left", pad=12)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "v0160_regression_verdicts.png"),
                facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    return len(cells)


def chart_pixel_demo():
    """Pixel 8a — one panel per model, arms compared WITHIN each model only.
    A single sorted axis across models implied a cross-model race (a 1B and a
    1.5B are not competitors); small multiples remove that reading."""
    rows = load_rows()
    models = [  # (panel title, [(arm label, runtime, model substring, quant)])
        ("DeepSeek-R1-Distill-1.5B", [
            ("llama.cpp (Q4_K_M)", "llama.cpp", "DeepSeek-R1-Distill-Qwen-1.5B-GGUF", None),
            ("LiteRT-LM cpu (INT8)", "litert-lm-cpu", "DeepSeek-R1-Distill-Qwen-1.5B", None),
            ("LiteRT-LM gpu (INT8)", "litert-lm-gpu", "DeepSeek-R1-Distill-Qwen-1.5B", None),
        ]),
        ("LFM2.5-1.2B-Instruct", [
            ("LiteRT-LM cpu (int4)", "litert-lm-cpu", "LFM2.5-1.2B", None),
            ("LiteRT-LM gpu (int4_gpu)", "litert-lm-gpu", "LFM2.5-1.2B", None),
        ]),
        ("MiniCPM5-1B", [
            ("LiteRT-LM cpu (wi4b32_wi8)", "litert-lm-cpu", "MiniCPM5-1B", None),
            ("LiteRT-LM gpu (gpu-opt)", "litert-lm-gpu", "MiniCPM5-1B", None),
        ]),
    ]

    def med(rt, msub):
        vals = [float(r["decode_tps"]) for r in rows
                if r["platform"] == "android" and r["device"] == DEV["android"]
                and r["runtime"] == rt
                and msub in r["model_id"] and r["task"] == "short-chat"
                and r["decode_tps"]
                and (r["thermal_initial"] or "") in ("nominal", "light", "")]
        return statistics.median(vals) if vals else None

    heights = [len(arms) for _, arms in models]
    fig, axes = plt.subplots(len(models), 1, figsize=(8.6, 0.62 * sum(heights) + 2.4),
                             dpi=200, sharex=True,
                             gridspec_kw={"height_ratios": heights, "hspace": 0.75})
    fig.patch.set_facecolor(SURFACE)
    xmax = 0
    for ax, (title, arms) in zip(axes, models):
        style_ax(ax)
        labels, vals, colors = [], [], []
        for label, rt, msub, _ in arms:
            v = med(rt, msub)
            if v:
                labels.append(label); vals.append(v); colors.append(ARM_COLOR[rt])
        ys = range(len(vals))
        ax.barh(ys, vals, height=0.6, color=colors, edgecolor=SURFACE, linewidth=2)
        for y, v in zip(ys, vals):
            ax.text(v + 0.3, y, f"{v:.1f}", va="center", fontsize=9, color=INK)
            xmax = max(xmax, v)
        ax.set_yticks(list(ys))
        ax.set_yticklabels(labels, fontsize=9, color=INK)
        ax.invert_yaxis()
        ax.set_title(title, fontsize=10, color=INK, loc="left", pad=4)
    for ax in axes:
        ax.set_xlim(0, xmax * 1.12)
    axes[-1].set_xlabel("decode tok/s — short-chat, fresh process (cold), median of runs; "
                        "runs starting past Android thermal 'light' excluded",
                        fontsize=9, color=MUTED)
    fig.suptitle("Pixel 8a — arms compared within each model (each model = one "
                 "config line; recipes stated per arm)", fontsize=11, color=INK,
                 x=0.02, ha="left")
    fig.savefig(os.path.join(OUT, "pixel8a_model_demo.png"),
                facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    return sum(heights)


def chart_crossarm_table():
    """The cross-platform demo table as an image (for chat posts)."""
    rows = load_rows()
    # iOS/Mac: nominal-start only (4-level scale; fairness §2). Android's
    # 7-level scale is finer — 'light' starts are accepted and DISCLOSED in
    # the caption; anything hotter is excluded.
    OK_THERMAL = {"mac": {"nominal", ""}, "ios": {"nominal", ""},
                  "android": {"nominal", "light", ""}}

    def med(plat, rt, msub, cold="True"):
        vals = [float(r["decode_tps"]) for r in rows
                if r["platform"] == plat and r["device"] == DEV[plat]
                and r["runtime"] == rt
                and msub in r["model_id"] and r["task"] == "short-chat"
                and r["cold_run"] == cold and r["decode_tps"]
                and (r["thermal_initial"] or "") in OK_THERMAL[plat]]
        return f"{statistics.median(vals):.1f}" if vals else "—"

    def ios_warm(msub, label, suffix="", runtime="litert-lm"):
        # "—" must not conflate "not measured" with "measured, excluded by the
        # nominal-start filter" — disclose which one it is, from the data.
        # `suffix` states a per-cell budget deviation (e.g. LFM2.5's ctx 1024,
        # LiteRT-LM#3129) and only appears once a number exists to qualify.
        # Same gated pool as the demo table (nominal + anchor-matched fair) —
        # two published images must never show two numbers for one cell.
        adm = ios_admissible_campaigns(rows)
        vals = [float(r["decode_tps"]) for r in rows
                if r["platform"] == "ios" and r["device"] == DEV["ios"]
                and r["runtime"] == runtime and msub in r["model_id"]
                and r["task"] == "short-chat" and r["cold_run"] == "False"
                and r["decode_tps"] and ios_row_ok(r, adm)]
        v = f"{statistics.median(vals):.1f}" if vals else "—"
        if v != "—":
            return (label + " " + v + (" " + suffix if suffix else "")).strip()
        captured = any(r["platform"] == "ios" and r["device"] == DEV["ios"] and r["runtime"] == runtime
                       and msub in r["model_id"] and r["task"] == "short-chat"
                       and r["decode_tps"] for r in rows)
        return label + " — (fair starts only)" if captured else "—"
    data = [
        ["DeepSeek-R1-1.5B", "mlx 4bit " + med("mac", "mlx-swift", "DeepSeek"),
         ios_warm("DeepSeek", "LiteRT INT8"),
         "llama Q4_K_M " + med("android", "llama.cpp", "DeepSeek"),
         "LiteRT INT8 " + med("android", "litert-lm-cpu", "DeepSeek")],
        ["", "LiteRT INT8 " + med("mac", "litert-lm", "DeepSeek"), "", "",
         "LiteRT gpu " + med("android", "litert-lm-gpu", "DeepSeek")],
        # LFM2.5 iPhone runs at context-tokens=1024 (the file's exported prefill
        # plan; the 08-24 engine-create failure was this harness's own
        # max_num_tokens config, not the runtime — LiteRT-LM#3129, corrected
        # in matrices/lu-focus-litert-ios.cells).
        ["LFM2.5-1.2B", "—",
         ios_warm("LFM2.5", "LiteRT int4_gpu", "(ctx 1024)") + "\n" +
         ios_warm("lfm2.5-1.2b", "Core AI", "(S=1 export)", runtime="core-ai"), "—",
         "LiteRT int4 cpu " + med("android", "litert-lm-cpu", "LFM2.5") +
         " / gpu " + med("android", "litert-lm-gpu", "LFM2.5")],
        ["MiniCPM5-1B", "—",
         ios_warm("MiniCPM", "LiteRT gpu-opt") + "\n" +
         ios_warm("minicpm5-1b", "Core AI", runtime="core-ai"), "—",
         "LiteRT cpu " + med("android", "litert-lm-cpu", "MiniCPM") +
         " / gpu-opt " + med("android", "litert-lm-gpu", "MiniCPM")],
        ["Gemma-4-E2B", "LiteRT wNa8o8 " + med("mac", "litert-lm", "gemma-4-E2B", "False"),
         ios_warm("gemma-4-E2B", "LiteRT wNa8o8"), "—", "—"],
        ["Qwen3-0.6B", "mlx " + med("mac", "mlx-swift", "Qwen3-0.6B", "False"),
         ios_warm("Qwen3-0.6B", "LiteRT"),
         "llama " + med("android", "llama.cpp", "Qwen3-0.6B"),
         "LiteRT gpu " + med("android", "litert-lm-gpu", "Qwen3-0.6B")],
        ["", "", ios_warm("qwen3-0.6b", "Core AI", runtime="core-ai"), "", ""],
    ]
    cols = ["model", "Mac Studio M4 Max", "iPhone 17 Pro", "Pixel 8a (llama.cpp)",
            "Pixel 8a (LiteRT-LM)"]
    fig, ax = plt.subplots(figsize=(12.5, 0.55 * len(data) + 1.6), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.axis("off")
    t = ax.table(cellText=data, colLabels=cols, loc="center", cellLoc="left")
    t.auto_set_font_size(False)
    t.set_fontsize(9)
    t.scale(1, 1.6)
    for (r, c), cell in t.get_celld().items():
        cell.set_edgecolor(GRID)
        cell.set_text_props(color=INK)
        if r == 0:
            cell.set_text_props(color=MUTED, fontweight="bold")
            cell.set_facecolor("#f0efec")
        else:
            cell.set_facecolor(SURFACE)
    ax.set_title("decode tok/s per arm (warm where the protocol defines it, else cold; "
                 "each cell states its recipe — cross-recipe cells are different\n"
                 "deployment profiles, not one race. iPhone: nominal starts, plus fair-start "
                 "sessions whose in-session anchor matches the nominal-era anchor "
                 "within 5% (see devices/iphone-17-pro.md). Pixel cells include runs starting "
                 "at Android thermal 'light'; hotter starts excluded)",
                 fontsize=10, color=INK, loc="left", pad=14)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "crossarm_table.png"),
                facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)


def chart_demo_models_table():
    """Just the three demo models, every arm that has a number (for chat posts)."""
    rows = load_rows()
    OK = {"mac": ("nominal", ""), "ios": ("nominal", ""),
          "android": ("nominal", "light", "")}

    def med(plat, rt, msub):
        # cold (fresh-process) only — the same basis as the crossarm table's
        # Mac/Pixel cells, so the two published images never disagree on a
        # number (pooling warm runs skewed Mac cells by a few tenths).
        vals = [float(r["decode_tps"]) for r in rows
                if r["platform"] == plat and r["device"] == DEV[plat]
                and r["runtime"] == rt
                and msub in r["model_id"] and r["task"] == "short-chat"
                and r["cold_run"] == "True"
                and r["decode_tps"] and (r["thermal_initial"] or "") in OK[plat]]
        return f"{statistics.median(vals):.1f}" if vals else "—"

    def ios_warm(msub, suffix="", runtime="litert-lm"):
        # Same definition as the crossarm table's iPhone cells (warm, nominal
        # start) so the two published images never disagree on a number; "—"
        # discloses whether runs exist that the thermal filter excluded.
        # `suffix` states a per-cell budget deviation and only appears with a
        # number (LFM2.5's ctx 1024 — LiteRT-LM#3129).
        adm = ios_admissible_campaigns(rows)
        vals = [float(r["decode_tps"]) for r in rows
                if r["platform"] == "ios" and r["device"] == DEV["ios"] and r["runtime"] == runtime
                and msub in r["model_id"] and r["task"] == "short-chat"
                and r["cold_run"] == "False" and r["decode_tps"]
                and ios_row_ok(r, adm)]
        if vals:
            return f"{statistics.median(vals):.1f}" + (" " + suffix if suffix else "")
        captured = any(r["platform"] == "ios" and r["device"] == DEV["ios"] and r["runtime"] == runtime
                       and msub in r["model_id"] and r["task"] == "short-chat"
                       and r["decode_tps"] for r in rows)
        return "— (fair-start runs only)" if captured else "—"

    data = [
        ["DeepSeek-R1-Distill-1.5B",
         "mlx 4bit " + med("mac", "mlx-swift", "DeepSeek") +
         "\nLiteRT INT8 " + med("mac", "litert-lm", "DeepSeek"),
         "LiteRT INT8 " + ios_warm("DeepSeek") + "\nCore AI — (bundle pending export)",
         "llama.cpp Q4_K_M " + med("android", "llama.cpp", "DeepSeek"),
         "cpu " + med("android", "litert-lm-cpu", "DeepSeek") +
         " / gpu " + med("android", "litert-lm-gpu", "DeepSeek") + "  (INT8)"],
        # LFM2.5 iPhone runs at context-tokens=1024 (exported prefill plan;
        # 08-24's failure was the harness's own max_num_tokens config —
        # LiteRT-LM#3129, corrected in matrices/lu-focus-litert-ios.cells).
        # LFM Core AI: our adapter's ShortConv-hybrid binding limitation
        # (exclude row in matrices/lu-focus-litert-ios.cells), not the runtime's.
        ["LFM2.5-1.2B-Instruct", "—",
         "LiteRT int4_gpu " + ios_warm("LFM2.5", "(ctx 1024)") +
         "\nCore AI " + ios_warm("lfm2.5-1.2b", "(S=1 export)", runtime="core-ai"), "—",
         "cpu " + med("android", "litert-lm-cpu", "LFM2.5") + " (int4) / gpu " +
         med("android", "litert-lm-gpu", "LFM2.5") + " (int4_gpu)"],
        ["MiniCPM5-1B", "—",
         "LiteRT gpu-opt " + ios_warm("MiniCPM") +
         "\nCore AI INT8 " + ios_warm("minicpm5-1b", runtime="core-ai"), "—",
         "cpu " + med("android", "litert-lm-cpu", "MiniCPM") +
         " (wi4b32_wi8) / gpu " + med("android", "litert-lm-gpu", "MiniCPM") +
         " (gpu-opt)"],
    ]
    cols = ["model", "Mac Studio M4 Max", "iPhone 17 Pro",
            "Pixel 8a — llama.cpp", "Pixel 8a — LiteRT-LM"]
    fig, ax = plt.subplots(figsize=(14.8, 3.4), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.axis("off")
    t = ax.table(cellText=data, colLabels=cols, loc="center", cellLoc="left",
                 colWidths=[0.15, 0.19, 0.18, 0.16, 0.32])
    t.auto_set_font_size(False)
    t.set_fontsize(9.5)
    t.scale(1, 2.4)
    for (r, c), cell in t.get_celld().items():
        cell.set_edgecolor(GRID)
        cell.set_text_props(color=INK)
        if r == 0:
            cell.set_text_props(color=MUTED, fontweight="bold")
            cell.set_facecolor("#f0efec")
        else:
            cell.set_facecolor(SURFACE)
    ax.set_title("Three models added by one config line each — decode tok/s, short-chat, "
                 "fresh process (iPhone: warm in-process runs).\nRecipes differ per cell "
                 "and are stated in it; cross-recipe cells are deployment profiles, not "
                 "one race. iPhone: nominal starts + anchor-matched fair sessions (5%; devices/iphone-17-pro.md); "
                 "Pixel: runs starting past Android thermal 'light' excluded.",
                 fontsize=10, color=INK, loc="left", pad=14)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "demo_models_table.png"),
                facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    n1 = chart_regression()
    n2 = chart_pixel_demo()
    chart_crossarm_table()
    chart_demo_models_table()
    print(f"wrote {OUT}: v0160_regression_verdicts.png ({n1} cells), "
          f"pixel8a_model_demo.png ({n2} bars), crossarm_table.png")
