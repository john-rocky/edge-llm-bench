#!/usr/bin/env python3
"""Template the repository's text prompts with the model's own chat template.

llama_main takes the prompt as raw text (README: "you have to apply the chat
template manually for the C++ runner"), so the host renders it once:
apply_chat_template([{"role": "user", "content": <prompts/text/<task>.txt>}],
tokenize=False, add_generation_prompt=True), with the template's defaults
(Qwen3: thinking on; enable_thinking is not passed). The file content goes in
unmodified, as android/bench/run_cell.py hands it to llama-cli -st.

Writes <out-dir>/<task>.<suffix>.txt and <out-dir>/prompts.json (sha256 of the
source and the rendered prompt, and the host tokenizer's token count of the
rendered prompt without added special tokens: the runner encodes with
num_bos=0, num_eos=0).
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TASKS = ("short-chat", "long-context-1024-gen256")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snapshot", type=Path, required=True, help="local HF snapshot dir (tokenizer + template)")
    ap.add_argument("--suffix", required=True, help="file tag, e.g. qwen3")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--tasks", nargs="+", default=list(TASKS))
    args = ap.parse_args()
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from transformers import AutoTokenizer
    import transformers

    tok = AutoTokenizer.from_pretrained(str(args.snapshot))
    budgets = dict(line.split() for line in (REPO / "prompts/text/budgets.tsv").read_text().splitlines()
                   if line.strip() and not line.startswith("#"))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    report = {"snapshot": str(args.snapshot), "transformers": transformers.__version__,
              "call": "apply_chat_template([{'role': 'user', 'content': <file>}], tokenize=False, "
                      "add_generation_prompt=True)", "tasks": {}}
    for task in args.tasks:
        src = REPO / f"prompts/text/{task}.txt"
        content = src.read_text(encoding="utf-8")
        rendered = tok.apply_chat_template([{"role": "user", "content": content}],
                                           tokenize=False, add_generation_prompt=True)
        ids = tok(rendered, add_special_tokens=False)["input_ids"]
        out = args.out_dir / f"{task}.{args.suffix}.txt"
        out.write_text(rendered, encoding="utf-8")
        report["tasks"][task] = {
            "source": f"prompts/text/{task}.txt", "sourceSha256": hashlib.sha256(src.read_bytes()).hexdigest(),
            "rendered": str(out), "renderedSha256": hashlib.sha256(rendered.encode()).hexdigest(),
            "renderedBytes": len(rendered.encode()), "hostPromptTokens": len(ids),
            "contentTokens": len(tok(content, add_special_tokens=False)["input_ids"]),
            "maxOutputTokens": int(budgets[task]), "head": rendered[:80], "tail": rendered[-60:]}
        print(f"{task}: {len(ids)} prompt tokens (content alone {report['tasks'][task]['contentTokens']}), "
              f"budget {budgets[task]} -> {out}")
    (args.out_dir / "prompts.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
