#!/usr/bin/env python3
"""K/r2/reply_tokens.py <name>=<ddp-out dir> ... — for each run: the printed reply (run<i>.engine.txt between the
input_prompt line and BenchmarkInfo) counted in Qwen3 tokens (Qwen/Qwen3-1.7B tokenizer.json from the local HF
cache, offline), beside the BenchmarkInfo prefill turns and decode tokens of the same run. Read only; tests
whether main@HEAD's second prefill turn has the size of the printed reply (a guess until counted)."""
import glob
import os
import re
import sys

from tokenizers import Tokenizer

LOG = re.compile(r"^(INFO|WARNING|ERROR|VERBOSE|DEBUG): |^[IWEF][0-9]{4} ")


def tokenizer():
    snaps = glob.glob(os.path.expanduser("~/.cache/huggingface/hub/models--Qwen--Qwen3-1.7B/snapshots/*/tokenizer.json"))
    if not snaps:
        sys.exit("no cached Qwen/Qwen3-1.7B tokenizer.json")
    return Tokenizer.from_file(sorted(snaps)[0])


def main(pairs):
    tok = tokenizer()
    for p in pairs:
        name, _, d = p.partition("=")
        for i in (1, 2, 3):
            path = os.path.join(d, f"run{i}.engine.txt")
            if not os.path.isfile(path):
                continue
            lines = open(path, errors="replace").read().splitlines()
            start = next(k for k, l in enumerate(lines) if l.startswith("input_prompt:"))
            end = next(k for k, l in enumerate(lines) if l.startswith("BenchmarkInfo:"))
            reply = "\n".join(l for l in lines[start + 1:end] if not LOG.match(l)).strip()
            text = "\n".join(lines[end:])
            turns = re.findall(r"Prefill Turn (\d+): Processed (\d+) tokens", text)
            decode = re.findall(r"Decode Turn \d+: Processed (\d+) tokens", text)
            n = len(tok.encode(reply, add_special_tokens=False).ids)
            wrapped = len(tok.encode(f"<|im_start|>assistant\n{reply}<|im_end|>\n", add_special_tokens=False).ids)
            print(f"{name} run{i}: printed reply {len(reply)} chars = {n} tokens ({wrapped} as an assistant turn "
                  f"<|im_start|>assistant ... <|im_end|>); prefill turns {[(int(a), int(b)) for a, b in turns]}; "
                  f"decode tokens {decode}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
