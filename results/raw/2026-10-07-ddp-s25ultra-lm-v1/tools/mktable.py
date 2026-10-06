#!/usr/bin/env python3
"""table.md from collect_lm.py's measurements-lm.jsonl plus each job's provenance.txt and logcat.txt.

Usage: mktable.py <measurements-lm.jsonl> <sessions root> <cli version> > table.md
"""
import json
import pathlib
import re
import sys

ORDER = ["Qwen3-0.6B", "Qwen3-1.7B", "Qwen3-4B", "gemma-4-E2B-it-litert-lm", "gemma-4-E4B-it-litert-lm"]
rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
root = pathlib.Path(sys.argv[2])
cli = sys.argv[3]
rows.sort(key=lambda r: (ORDER.index(r["model"].split("/")[1]), r["accelerator"]))


def spread(r, key):
    vals = [i[key] for i in r["iterations"][r["conditions"]["warmup_iterations"]:] if i[key] is not None]
    return (max(vals) / min(vals) - 1) * 100 if vals and min(vals) > 0 else None


def prov(r):
    text = (root / r["session"] / r["job"] / "provenance.txt").read_text(errors="replace")
    build = re.search(r"^build: (.+)$", text, re.M)
    date = re.search(r"^date: (.+)$", text, re.M)
    product = re.search(r"^product: (.+)$", text, re.M)
    exits = re.findall(r"^(warm-up|measured) process: exit (\d+)$", text, re.M)
    return {"build": build.group(1) if build else None, "date": date.group(1) if date else None,
            "product": product.group(1) if product else None, "exits": exits}


print("| model | file | backend | prefill tok/s | decode tok/s | TTFT s | init ms | peak mem MB | tokens (prefill / decode / max) | iterations | session |")
print("|---|---|---|---:|---:|---:|---:|---:|---|---|---|")
for r in rows:
    m, c = r["metrics"], r["conditions"]
    backend = r["accelerator"] + (f" ({r['delegate']})" if r["delegate"] else "")
    print(f"| {r['model']} | {r['file']} | {backend} | {m['prefill_tok_s']:.1f} | {m['decode_tok_s']:.2f} | {m['ttft_s']:.3f} |"
          f" {m['init_total_ms']:.0f} | {m['peak_mem_mb'] if m['peak_mem_mb'] is not None else 'n/a'} |"
          f" {c['prefill_tokens']} / {c['decode_tokens']} / {c['max_num_tokens']} | {c['iterations']} ({c['warmup_iterations']} warm-up) | {r['session']} |")

print()
print("Per-iteration values and spread (max/min - 1 over the iterations after the warm-up one):")
print()
print("| model | backend | prefill tok/s per iteration | spread | decode tok/s per iteration | spread | session date (device clock) | device build |")
print("|---|---|---|---:|---|---:|---|---|")
for r in rows:
    p = prov(r)
    pre = ", ".join(f"{i['prefill_tok_s']:.1f}" for i in r["iterations"])
    dec = ", ".join(f"{i['decode_tok_s']:.2f}" for i in r["iterations"])
    parts = (p["build"] or "").split("/")
    build = parts[4].split(":")[0] if len(parts) > 4 else (p["build"] or "?")
    print(f"| {r['model'].split('/')[1]} | {r['accelerator']} | {pre} | {spread(r, 'prefill_tok_s'):.1f}% | {dec} |"
          f" {spread(r, 'decode_tok_s'):.1f}% | {p['date']} | {p['product']}, {build} |")

print()
bins = sorted({r["binary"] for r in rows})
shas = sorted({r["file"] + " " + (r["file_sha256"] or "?") for r in rows})
print("Binary: " + "; ".join(bins))
print()
print(f"CLI: litert-cli-nightly {cli}")
print()
print("Bundles (sha256 from each session's provenance.txt):")
print()
for s in shas:
    print(f"- {s}")

# --- the first (cache-writing) process of each session, read from the log by gather.py ---
if len(sys.argv) > 4:
    first = {(f["session"], f["job"]): f for f in (json.loads(l) for l in open(sys.argv[4]) if l.strip())}
    print()
    print("The first process of each session (it starts without cache files, runs one prefill and one decode, and writes the caches;")
    print("read from the log, not from metrics.pb) beside the measured process:")
    print()
    print("| model | backend | first process: init ms (no caches) | prefill tok/s | decode tok/s | measured process: init ms (caches present) | median prefill tok/s | median decode tok/s |")
    print("|---|---|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        f = first.get((r["session"], r["job"]))
        if not f:
            continue
        m = r["metrics"]
        print(f"| {r['model'].split('/')[1]} ({r['file']}) | {r['accelerator']} | {f['cold_init_total_ms']:.0f} | {f['first_prefill_tok_s']:.1f} |"
              f" {f['first_decode_tok_s']:.2f} | {m['init_total_ms']:.0f} | {m['prefill_tok_s']:.1f} | {m['decode_tok_s']:.2f} |")
