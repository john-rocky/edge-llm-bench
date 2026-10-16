#!/usr/bin/env python3
"""K/r2/turns.py <row name>=<ddp-out dir> ... — the BenchmarkInfo turns of each run (run<i>.engine.txt) as a markdown
table for K/MATRIX.md (read only): every prefill turn (tokens, ms, tok/s), the decode turn (tokens, tok/s),
time to first token, Init Executor, and the printed reply (the text between the input_prompt line and BenchmarkInfo)
in Qwen3 tokens (Qwen/Qwen3-1.7B tokenizer.json from the local HF cache) and its first words."""
import glob
import os
import re
import sys

from tokenizers import Tokenizer

LOG = re.compile(r"^(INFO|WARNING|ERROR|VERBOSE|DEBUG): |^[IWEF][0-9]{4} ")
PREFILL = re.compile(r"Prefill Turn (\d+): Processed (\d+) tokens in ([0-9.]+)(ms|s) duration\.\s*\n\s*Prefill Speed: ([0-9.]+)")
DECODE = re.compile(r"Decode Turn (\d+): Processed (\d+) tokens in ([0-9.]+)(ms|s) duration\.\s*\n\s*Decode Speed: ([0-9.]+)")


def g(v):
    return f"{round(float(v), 2):g}"


def main(pairs):
    snaps = glob.glob(os.path.expanduser("~/.cache/huggingface/hub/models--Qwen--Qwen3-1.7B/snapshots/*/tokenizer.json"))
    tok = Tokenizer.from_file(sorted(snaps)[0])
    print("| row | run | prefill turns: tokens in ms = tok/s | decode: tokens = tok/s | TTFT s | Init Executor ms "
          "| printed reply: Qwen3 tokens, first words |")
    print("|---|---|---|---|---|---|---|")
    for p in pairs:
        name, _, d = p.partition("=")
        for i in (1, 2, 3):
            text = open(os.path.join(d, f"run{i}.engine.txt"), errors="replace").read()
            lines = text.splitlines()
            start = next(k for k, l in enumerate(lines) if l.startswith("input_prompt:"))
            end = next(k for k, l in enumerate(lines) if l.startswith("BenchmarkInfo:"))
            reply = "\n".join(l for l in lines[start + 1:end] if not LOG.match(l)).strip()
            info = "\n".join(lines[end:])
            pre = "; ".join(f"turn {t}: {n} in {g(float(x) * (1000 if u == 's' else 1))} = {g(r)}"
                            for t, n, x, u, r in PREFILL.findall(info))
            dec = "; ".join(f"{n} = {g(r)}" for _, n, _, _, r in DECODE.findall(info))
            ttft = re.search(r"Time to first token: ([0-9.]+) s", info)
            init = re.search(r"Init Executor: ([0-9.]+) ms", info)
            words = " ".join(reply.split()[:6])
            print(f"| {name} | {i} | {pre} | {dec} | {ttft.group(1) if ttft else '—'} | {init.group(1) if init else '—'} "
                  f"| {len(tok.encode(reply, add_special_tokens=False).ids)}, \"{words} …\" |")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
