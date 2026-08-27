#!/usr/bin/env python3
"""Generate docs/charts/*.png from the accumulation layer — never from literals.

Reads results/summary/device-runs.csv and results/regression-reports/*/verdicts.json.
Cell values come from render_leaderboard.arm_row — the same latest-session
aggregation that renders LEADERBOARD.md — so a chart and the leaderboard cannot
show two numbers for one cell. (Until 2026-08-26 charts pooled cold runs across
sessions: a few percent off the leaderboard on Pixel cells, and wrong by 2× on
any device whose history holds pre-fix sessions — the S26 mask-artifact rows.)

Palette: dataviz-validated defaults (categorical #2a78d6/#eb6834/#1baf7a passes
CVD+normal-vision checks on the #fcfcfb surface; the contrast WARN on aqua is
relieved by direct value labels on every mark). Diverging = blue/red with a
gray near-zero band. Identity is never color-alone: every bar carries its label.
"""
import csv
import json
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_leaderboard import arm_row, SPREAD_FLAG  # noqa: E402

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



def load_rows():
    with open(os.path.join(ROOT, "results", "summary", "device-runs.csv")) as fh:
        return list(csv.DictReader(fh))


def cell(rows, plat, rt, msub, dev=None):
    """One (device, runtime, model) cell on the LEADERBOARD basis: arm_row over
    the cell's full history (latest-session selection happens inside arm_row).
    A substring matching two artifacts would silently pool them — refuse."""
    sel = [r for r in rows
           if r["platform"] == plat and r["device"] == (dev or DEV[plat])
           and r["runtime"] == rt and msub in r["model_id"]
           and r["task"] == "short-chat"]
    ids = {r["model_id"] for r in sel}
    if len(ids) > 1:
        raise SystemExit(f"ambiguous cell {plat}/{rt}/{msub!r}: {sorted(ids)}")
    return arm_row(sel) if sel else None


def cell_num(rows, plat, rt, msub, field="cold"):
    c = cell(rows, plat, rt, msub)
    v = c and c[field]
    return f"{v:.1f}" if v else "—"


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
            ("llama.cpp (Q4_K_M)", "llama.cpp", "LFM2.5-1.2B", None),
            ("LiteRT-LM cpu (int4)", "litert-lm-cpu", "LFM2.5-1.2B", None),
            ("LiteRT-LM gpu (int4_gpu)", "litert-lm-gpu", "LFM2.5-1.2B", None),
        ]),
        ("MiniCPM5-1B", [
            ("llama.cpp (Q4_K_M)", "llama.cpp", "MiniCPM5-1B", None),
            ("LiteRT-LM cpu (wi4b32_wi8)", "litert-lm-cpu", "MiniCPM5-1B", None),
            ("LiteRT-LM gpu (gpu-opt)", "litert-lm-gpu", "MiniCPM5-1B", None),
        ]),
    ]

    def med(rt, msub):
        c = cell(rows, "android", rt, msub)
        return c and c["cold"]

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
    axes[-1].set_xlabel("decode tok/s — short-chat, fresh process (cold); latest capture "
                        "session per cell, the same numbers as LEADERBOARD.md",
                        fontsize=9, color=MUTED)
    fig.suptitle("Pixel 8a — arms compared within each model (each model = one "
                 "config line; recipes stated per arm)", fontsize=11, color=INK,
                 x=0.02, ha="left")
    fig.savefig(os.path.join(OUT, "pixel8a_model_demo.png"),
                facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    return sum(heights)


YELLOW = "#eda100"   # categorical slot 4 (dataviz palette) — the Core AI arm
ZEBRA = "#f4f3f1"
HEAD_INK = "#55544f"


def _cell_line(rows, color, label, plat, rt, msub, field="cold", note=""):
    """One arm line for a value table: (dot color, value, muted recipe label).
    A warm value whose trial spread exceeds SPREAD_FLAG carries the same ⚠ as
    its LEADERBOARD row — the chart must not look cleaner than the table."""
    c = cell(rows, plat, rt, msub)
    v = c and c[field]
    lab = label + (f" · {note}" if note else "")
    if v and field == "warm" and c["spread"] > SPREAD_FLAG:
        lab += f" · ⚠ spread {c['spread']:.0f}%"
    return (color, f"{v:.1f}" if v else "—", lab)


def draw_value_table(fname, title, subtitle, columns, widths, table_rows, footnote):
    """Typeset a value table: no cell borders, zebra row banding, and per arm
    line a colored identity dot + bold value + muted recipe label (identity is
    never color-alone — the label carries it; dots reinforce). columns[0] is
    the model column; widths are inches; table_rows: [(model, [cell, ...])]
    where cell = list of (color, value, label) lines, [] = em-dash cell."""
    LINE, PAD, MARGIN = 0.235, 0.16, 0.30
    n_lines = [max(1, max((len(c) for c in cells), default=1))
               for _, cells in table_rows]
    row_h = [n * LINE + PAD for n in n_lines]
    W = MARGIN * 2 + sum(widths)
    title_h, sub_h, head_h, foot_h = 0.40, 0.30, 0.34, 0.56
    H = 0.22 + title_h + sub_h + head_h + sum(row_h) + foot_h
    fig = plt.figure(figsize=(W, H), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    rend = fig.canvas.get_renderer()
    inv = fig.transFigure.inverted()

    def xf(x):
        return x / W

    def yf(y):          # y in inches from the top
        return 1 - y / H

    def text(x, y, s, size, color, weight="normal", va="center"):
        return fig.text(xf(x), yf(y), s, fontsize=size, color=color,
                        fontweight=weight, ha="left", va=va)

    def advance(t):
        return inv.transform((t.get_window_extent(rend).x1, 0))[0] * W

    col_x = [MARGIN]
    for w in widths[:-1]:
        col_x.append(col_x[-1] + w)

    y = 0.22 + title_h / 2
    text(MARGIN, y, title, 13, INK, "bold")
    y += title_h / 2 + sub_h / 2
    text(MARGIN, y, subtitle, 9, MUTED)
    y += sub_h / 2
    for x, label in zip(col_x, columns):
        text(x, y + head_h / 2, label, 9.5, HEAD_INK, "bold")
    y += head_h
    fig.add_artist(plt.Line2D([xf(MARGIN * 0.6), 1 - xf(MARGIN * 0.6)],
                              [yf(y)] * 2, transform=fig.transFigure,
                              color=GRID, linewidth=1))

    for i, ((model, cells), h) in enumerate(zip(table_rows, row_h)):
        if i % 2 == 1:
            fig.add_artist(plt.Rectangle(
                (xf(MARGIN * 0.5), yf(y + h)), 1 - 2 * xf(MARGIN * 0.5),
                h / H, transform=fig.transFigure, facecolor=ZEBRA,
                edgecolor="none", zorder=0))
        first_y = y + PAD / 2 + LINE / 2
        text(col_x[0], first_y, model, 10, INK, "bold")
        for x, lines in zip(col_x[1:], cells):
            if not lines:
                text(x + 0.17, first_y, "—", 10, MUTED)
                continue
            for j, (color, value, label) in enumerate(lines):
                ly = y + PAD / 2 + (j + 0.5) * LINE
                if color:
                    text(x, ly, "●", 6.5, color)
                t = text(x + 0.17, ly, value, 10.5,
                         INK if value != "—" else MUTED, "bold")
                text(advance(t) + 0.09, ly, label, 8.5, MUTED)
        y += h

    text(MARGIN, y + 0.22, footnote, 8, MUTED, va="top")
    fig.savefig(os.path.join(OUT, fname), facecolor=SURFACE)
    plt.close(fig)


def chart_crossarm_table():
    """The cross-platform standings table (README hero + chat posts)."""
    rows = load_rows()

    def L(*a, **k):
        return _cell_line(rows, *a, **k)

    table_rows = [
        ("Qwen3-0.6B", [
            [L(AQUA, "mlx · 4bit", "mac", "mlx-swift", "Qwen3-0.6B", "warm"),
             L(BLUE, "LiteRT · int4 mixed", "mac", "litert-lm", "Qwen3-0.6B", "warm")],
            [L(AQUA, "mlx · 4bit", "ios", "mlx-swift", "Qwen3-0.6B", "warm"),
             L(YELLOW, "Core AI · int4 dynamic", "ios", "core-ai", "qwen3-0.6b", "warm"),
             L(BLUE, "LiteRT · int4 mixed", "ios", "litert-lm", "Qwen3-0.6B", "warm")],
            [L(ORANGE, "llama · Q4_K_M", "android", "llama.cpp", "Qwen3-0.6B")],
            [L(BLUE, "LiteRT gpu · int4 mixed", "android", "litert-lm-gpu", "Qwen3-0.6B"),
             L(BLUE, "LiteRT cpu · int4 mixed", "android", "litert-lm-cpu", "Qwen3-0.6B")],
        ]),
        ("DeepSeek-R1-1.5B", [
            # mac lines say "warm" like every other mac line here — the
            # subtitle promises warm-where-defined, and warm exists (audit
            # 2026-08-27 caught these two on the cold field, a 0.2% cosmetic
            # inconsistency but a broken promise)
            [L(AQUA, "mlx · 4bit", "mac", "mlx-swift", "DeepSeek", "warm"),
             L(BLUE, "LiteRT · INT8", "mac", "litert-lm", "DeepSeek", "warm")],
            [L(BLUE, "LiteRT · INT8", "ios", "litert-lm", "DeepSeek", "warm")],
            [L(ORANGE, "llama · Q4_K_M", "android", "llama.cpp", "DeepSeek")],
            [L(BLUE, "LiteRT gpu · INT8", "android", "litert-lm-gpu", "DeepSeek"),
             L(BLUE, "LiteRT cpu · INT8", "android", "litert-lm-cpu", "DeepSeek")],
        ]),
        # LFM2.5 runs at context-tokens=1024 on every litert arm (the file's
        # exported prefill plan — LiteRT-LM#3129 notes in the cells files).
        ("LFM2.5-1.2B", [
            [L(BLUE, "LiteRT · int4_gpu", "mac", "litert-lm", "LFM2.5", "warm", "ctx 1024"),
             L(AQUA, "mlx · 4bit", "mac", "mlx-swift", "LFM2.5", "warm")],
            [L(BLUE, "LiteRT · int4_gpu", "ios", "litert-lm", "LFM2.5", "warm", "ctx 1024"),
             L(YELLOW, "Core AI · int8hu", "ios", "core-ai", "lfm2.5-1.2b", "warm", "S=1 export")],
            [L(ORANGE, "llama · Q4_K_M", "android", "llama.cpp", "LFM2.5")],
            [L(BLUE, "LiteRT gpu · int4_gpu", "android", "litert-lm-gpu", "LFM2.5"),
             L(BLUE, "LiteRT cpu · int4", "android", "litert-lm-cpu", "LFM2.5")],
        ]),
        ("MiniCPM5-1B", [
            [L(BLUE, "LiteRT · gpu-opt", "mac", "litert-lm", "MiniCPM", "warm"),
             L(AQUA, "mlx · 4bit", "mac", "mlx-swift", "MiniCPM", "warm")],
            [L(BLUE, "LiteRT · gpu-opt", "ios", "litert-lm", "MiniCPM", "warm"),
             L(YELLOW, "Core AI · INT8", "ios", "core-ai", "minicpm5-1b", "warm")],
            [L(ORANGE, "llama · Q4_K_M", "android", "llama.cpp", "MiniCPM")],
            [L(BLUE, "LiteRT gpu · gpu-opt", "android", "litert-lm-gpu", "MiniCPM"),
             L(BLUE, "LiteRT cpu · wi4b32_wi8", "android", "litert-lm-cpu", "MiniCPM")],
        ]),
        ("Gemma-4-E2B", [
            [L(BLUE, "LiteRT · wNa8o8", "mac", "litert-lm", "gemma-4-E2B", "warm")],
            [L(BLUE, "LiteRT · wNa8o8", "ios", "litert-lm", "gemma-4-E2B", "warm")],
            [],
            [L(BLUE, "LiteRT gpu · wNa8o8", "android", "litert-lm-gpu", "gemma-4-E2B")],
        ]),
    ]
    draw_value_table(
        "crossarm_table.png",
        "Decode speed per arm — tok/s",
        "Warm where the protocol defines it, else cold · the recipe travels with "
        "every cell · cross-recipe cells are different deployment profiles, not one race",
        ["model", "Mac Studio M4 Max", "iPhone 17 Pro",
         "Pixel 8a · llama.cpp", "Pixel 8a · LiteRT-LM"],
        [1.55, 2.55, 2.85, 1.95, 2.75],
        table_rows,
        "Values are LEADERBOARD.md's: latest capture session per cell, never pooled "
        "across sessions — warm = median of same-session warm runs, cold = the "
        "session's last cold run.\nLFM2.5 LiteRT cells run at context 1024 (the "
        "file's exported prefill plan — LiteRT-LM#3129); Android v1 has no warm "
        "regime (methodology/android.md).")


def chart_demo_models_table():
    """The three demo models, every arm with a number (for chat posts)."""
    rows = load_rows()

    def L(*a, **k):
        return _cell_line(rows, *a, **k)

    table_rows = [
        ("DeepSeek-R1-1.5B", [
            [L(AQUA, "mlx · 4bit", "mac", "mlx-swift", "DeepSeek"),
             L(BLUE, "LiteRT · INT8", "mac", "litert-lm", "DeepSeek")],
            [L(BLUE, "LiteRT · INT8", "ios", "litert-lm", "DeepSeek", "warm"),
             (YELLOW, "—", "Core AI · bundle pending export")],
            [L(ORANGE, "llama · Q4_K_M", "android", "llama.cpp", "DeepSeek")],
            [L(BLUE, "LiteRT gpu · INT8", "android", "litert-lm-gpu", "DeepSeek"),
             L(BLUE, "LiteRT cpu · INT8", "android", "litert-lm-cpu", "DeepSeek")],
        ]),
        ("LFM2.5-1.2B-Instruct", [
            [L(BLUE, "LiteRT · int4_gpu", "mac", "litert-lm", "LFM2.5", note="ctx 1024"),
             L(AQUA, "mlx · 4bit", "mac", "mlx-swift", "LFM2.5")],
            [L(BLUE, "LiteRT · int4_gpu", "ios", "litert-lm", "LFM2.5", "warm", "ctx 1024"),
             L(YELLOW, "Core AI · int8hu", "ios", "core-ai", "lfm2.5-1.2b", "warm", "S=1 export")],
            [L(ORANGE, "llama · Q4_K_M", "android", "llama.cpp", "LFM2.5")],
            [L(BLUE, "LiteRT gpu · int4_gpu", "android", "litert-lm-gpu", "LFM2.5"),
             L(BLUE, "LiteRT cpu · int4", "android", "litert-lm-cpu", "LFM2.5")],
        ]),
        ("MiniCPM5-1B", [
            [L(BLUE, "LiteRT · gpu-opt", "mac", "litert-lm", "MiniCPM"),
             L(AQUA, "mlx · 4bit", "mac", "mlx-swift", "MiniCPM")],
            [L(BLUE, "LiteRT · gpu-opt", "ios", "litert-lm", "MiniCPM", "warm"),
             L(YELLOW, "Core AI · INT8", "ios", "core-ai", "minicpm5-1b", "warm")],
            [L(ORANGE, "llama · Q4_K_M", "android", "llama.cpp", "MiniCPM")],
            [L(BLUE, "LiteRT gpu · gpu-opt", "android", "litert-lm-gpu", "MiniCPM"),
             L(BLUE, "LiteRT cpu · wi4b32_wi8", "android", "litert-lm-cpu", "MiniCPM")],
        ]),
    ]
    draw_value_table(
        "demo_models_table.png",
        "Three models, one config line each — decode tok/s",
        "short-chat, fresh process · iPhone cells are warm in-process runs · "
        "recipes differ per cell and are stated in it — different deployment "
        "profiles, not one race",
        ["model", "Mac Studio M4 Max", "iPhone 17 Pro",
         "Pixel 8a · llama.cpp", "Pixel 8a · LiteRT-LM"],
        [1.85, 2.55, 2.85, 1.95, 2.75],
        table_rows,
        "Values are LEADERBOARD.md's: latest capture session per cell, never pooled "
        "across sessions — warm = median of same-session warm runs, cold = the "
        "session's last cold run.\nLFM2.5 LiteRT cells run at context 1024 (the "
        "file's exported prefill plan — LiteRT-LM#3129).")


if __name__ == "__main__":
    n1 = chart_regression()
    n2 = chart_pixel_demo()
    chart_crossarm_table()
    chart_demo_models_table()
    print(f"wrote {OUT}: v0160_regression_verdicts.png ({n1} cells), "
          f"pixel8a_model_demo.png ({n2} bars), crossarm_table.png")
