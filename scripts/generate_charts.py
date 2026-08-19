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
    """Pixel 8a decode by model x arm (the model-agnostic demo), recipes labeled."""
    rows = load_rows()
    spec = [  # (display, runtime, model substring, quant label)
        ("DeepSeek-R1-1.5B", "llama.cpp", "DeepSeek-R1-Distill-Qwen-1.5B-GGUF", "Q4_K_M"),
        ("DeepSeek-R1-1.5B", "litert-lm-cpu", "DeepSeek-R1-Distill-Qwen-1.5B", "INT8"),
        ("DeepSeek-R1-1.5B", "litert-lm-gpu", "DeepSeek-R1-Distill-Qwen-1.5B", "INT8"),
        ("LFM2.5-1.2B", "litert-lm-cpu", "LFM2.5-1.2B", "int4"),
        ("LFM2.5-1.2B", "litert-lm-gpu", "LFM2.5-1.2B", "int4_gpu"),
        ("MiniCPM5-1B", "litert-lm-cpu", "MiniCPM5-1B", "wi4b32_wi8_afp32"),
        ("MiniCPM5-1B", "litert-lm-gpu", "MiniCPM5-1B", "wi4b32 gpu-opt"),
    ]
    bars = []
    for disp, rt, msub, quant in spec:
        med = None
        for cold in ("True", "False"):
            vals = [float(r["decode_tps"]) for r in load_rows()
                    if r["platform"] == "android" and r["runtime"] == rt
                    and msub in r["model_id"] and r["task"] == "short-chat"
                    and r["cold_run"] == cold and r["decode_tps"]]
            if vals:
                med = statistics.median(vals + ([med] if med else []))
        if med:
            arm = rt.replace("litert-lm-", "LiteRT-LM ") if rt.startswith("litert") else rt
            bars.append((f"{disp} — {arm} ({quant})", med, ARM_COLOR[rt]))
    bars.sort(key=lambda b: b[1])
    fig, ax = plt.subplots(figsize=(8.6, 0.52 * len(bars) + 1.8), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    style_ax(ax)
    ys = range(len(bars))
    ax.barh(ys, [b[1] for b in bars], height=0.55,
            color=[b[2] for b in bars], edgecolor=SURFACE, linewidth=2)
    for y, (label, v, _) in zip(ys, bars):
        ax.text(v + 0.3, y, f"{v:.1f}", va="center", fontsize=9, color=INK)
    ax.set_yticks(list(ys))
    ax.set_yticklabels([b[0] for b in bars], fontsize=9, color=INK)
    ax.set_xlabel("decode tok/s — short-chat, fresh process (cold), median of runs",
                  fontsize=9, color=MUTED)
    ax.set_title("Pixel 8a — models added by one cells line each (recipes differ per "
                 "row and are part of the label)", fontsize=11, color=INK,
                 loc="left", pad=12)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (BLUE, ORANGE)]
    ax.legend(handles, ["LiteRT-LM", "llama.cpp"], loc="lower right", frameon=False,
              fontsize=9, labelcolor=INK)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "pixel8a_model_demo.png"),
                facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    return len(bars)


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
                if r["platform"] == plat and r["runtime"] == rt
                and msub in r["model_id"] and r["task"] == "short-chat"
                and r["cold_run"] == cold and r["decode_tps"]
                and (r["thermal_initial"] or "") in OK_THERMAL[plat]]
        return f"{statistics.median(vals):.1f}" if vals else "—"
    data = [
        ["DeepSeek-R1-1.5B", "mlx 4bit " + med("mac", "mlx-swift", "DeepSeek"),
         "—", "llama Q4_K_M " + med("android", "llama.cpp", "DeepSeek"),
         "LiteRT INT8 " + med("android", "litert-lm-cpu", "DeepSeek")],
        ["", "LiteRT INT8 " + med("mac", "litert-lm", "DeepSeek"), "", "",
         "LiteRT gpu " + med("android", "litert-lm-gpu", "DeepSeek")],
        ["LFM2.5-1.2B", "—", "—", "—",
         "LiteRT int4 cpu " + med("android", "litert-lm-cpu", "LFM2.5") +
         " / gpu " + med("android", "litert-lm-gpu", "LFM2.5")],
        ["MiniCPM5-1B", "—", "—", "—",
         "LiteRT cpu " + med("android", "litert-lm-cpu", "MiniCPM") +
         " / gpu-opt " + med("android", "litert-lm-gpu", "MiniCPM")],
        ["Gemma-4-E2B", "LiteRT wNa8o8 " + med("mac", "litert-lm", "gemma-4-E2B", "False"),
         "LiteRT wNa8o8 " + med("ios", "litert-lm", "gemma-4-E2B", "False"), "—", "—"],
        ["Qwen3-0.6B", "mlx " + med("mac", "mlx-swift", "Qwen3-0.6B", "False"),
         "LiteRT " + med("ios", "litert-lm", "Qwen3-0.6B", "False"),
         "llama " + med("android", "llama.cpp", "Qwen3-0.6B"),
         "LiteRT gpu " + med("android", "litert-lm-gpu", "Qwen3-0.6B")],
    ]
    cols = ["model", "Mac Studio M4 Max", "iPhone 17 Pro", "Pixel 8a (llama.cpp)",
            "Pixel 8a (LiteRT-LM)"]
    fig, ax = plt.subplots(figsize=(11.5, 0.55 * len(data) + 1.6), dpi=200)
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
                 "deployment profiles, not one race. Pixel cells include runs starting "
                 "at Android thermal 'light'; hotter starts excluded)",
                 fontsize=10, color=INK, loc="left", pad=14)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "crossarm_table.png"),
                facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    n1 = chart_regression()
    n2 = chart_pixel_demo()
    chart_crossarm_table()
    print(f"wrote {OUT}: v0160_regression_verdicts.png ({n1} cells), "
          f"pixel8a_model_demo.png ({n2} bars), crossarm_table.png")
