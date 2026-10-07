#!/usr/bin/env python3
"""Markdown table of a smoke_mac.py run, recomputed from each launch's stats JSON.

Reads <dir>/runs.jsonl for the launch list and <dir>/<stem>.json for the
numbers (the PyTorchObserver object as llama_main printed it), so every rate in
the table can be checked against the stored file:
  prefill tok/s = prompt_tokens / (prompt_eval_end_ms - inference_start_ms) * 1000
  decode tok/s  = generated_tokens / (inference_end_ms - prompt_eval_end_ms) * 1000
  TTFT ms       = first_token_ms - inference_start_ms
RSS MB = /usr/bin/time -l "maximum resident set size" bytes / 2^20 (MiB).
Medians per task x regime follow the table (no pooling across runs of
different regimes).
"""
import argparse
import json
from pathlib import Path
import statistics


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir", type=Path)
    args = ap.parse_args()
    runs = [json.loads(line) for line in (args.dir / "runs.jsonl").read_text().splitlines() if line.strip()]
    print("| task | regime | n | prompt tok | gen tok | prefill tok/s | decode tok/s | TTFT ms | RSS MB | status | text check | text (first 60 chars) |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    groups = {}
    for r in runs:
        stem = r["stem"]
        jp = args.dir / f"{stem}.json"
        s = json.loads(jp.read_text()) if jp.exists() else None
        if s:
            pre = s["prompt_eval_end_ms"] - s["inference_start_ms"]
            dec = s["inference_end_ms"] - s["prompt_eval_end_ms"]
            prefill = s["prompt_tokens"] / pre * 1000 if pre > 0 else None
            decode = s["generated_tokens"] / dec * 1000 if dec > 0 else None
            ttft = s["first_token_ms"] - s["inference_start_ms"]
            groups.setdefault((r["task"], r["regime"]), []).append((prefill, decode, ttft))
        rss = r.get("time", {}).get("maxRSSBytes")
        tc = r.get("textIntegrity") or {}
        head = (r.get("textHead60") or "").replace("\n", "\\n").replace("|", "\\|")
        fmt = lambda v, p=1: "—" if v is None else f"{v:.{p}f}"
        print(f"| {r['task']} | {r['regime']} | {r['n']} | {s['prompt_tokens'] if s else '—'} | "
              f"{s['generated_tokens'] if s else '—'} | {fmt(prefill if s else None)} | {fmt(decode if s else None)} | "
              f"{ttft if s else '—'} | {fmt(rss / 2**20 if rss else None, 0)} | {r['status']} | "
              f"{tc.get('status', '—')}{(':' + ','.join(tc['flags'])) if tc.get('flags') else ''} | `{head}` |")
    print()
    print("| task | regime | runs | median prefill tok/s | median decode tok/s | median TTFT ms | decode spread % |")
    print("|---|---|---|---|---|---|---|")
    for (task, regime), vals in groups.items():
        pre = [v[0] for v in vals if v[0] is not None]
        dec = [v[1] for v in vals if v[1] is not None]
        ttf = [v[2] for v in vals]
        med = lambda xs, p: f"{statistics.median(xs):.{p}f}" if xs else "—"
        md = statistics.median(dec) if dec else None
        spread = f"{(max(dec) - min(dec)) / md * 100:.1f}" if md and len(dec) > 1 else "—"
        print(f"| {task} | {regime} | {len(vals)} | {med(pre, 1)} | {med(dec, 1)} | {med(ttf, 0)} | {spread} |")


if __name__ == "__main__":
    main()
