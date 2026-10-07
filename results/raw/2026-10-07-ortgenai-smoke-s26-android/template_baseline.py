"""Chat-template baseline for the Galaxy S26 ortgenai_run smoke (2026-10-07).

The host reference for "the model's chat template is in effect on the phone":
the same model folder's tokenizer (onnxruntime-genai Python, tokenizer only, no
model session) applies the folder's own template to each prompt as one user
message with add_generation_prompt, and encodes the result. ortgenai_run on the
phone must print the same templated text (sha256) and the same prompt_tokens.
The messages JSON is built byte-for-byte as ortgenai_run builds it.

usage: ORT_DISABLE_TELEMETRY=1 python template_baseline.py <model folder> <out.json> <prompt file>...
"""
import hashlib
import json
import os
import sys

import onnxruntime_genai as og


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main(model_dir, out_path, *prompt_files):
    if os.environ.get("ORT_DISABLE_TELEMETRY") != "1":
        raise SystemExit("set ORT_DISABLE_TELEMETRY=1 before onnxruntime_genai initializes")
    og.disable_telemetry_events()
    tokenizer = og.Tokenizer(model_dir)
    snapshot = os.path.realpath(model_dir).split("/snapshots/")
    rows = []
    for path in prompt_files:
        prompt = open(path, encoding="utf-8").read()
        messages = json.dumps([{"role": "user", "content": prompt}], ensure_ascii=False, separators=(",", ":"))
        templated = tokenizer.apply_chat_template(messages, add_generation_prompt=True)
        ids = [int(t) for t in tokenizer.encode(templated)]
        rows.append({
            "prompt_file": os.path.relpath(path),
            "prompt_sha256": sha256(prompt),
            "messages_sha256": sha256(messages),
            "templated": templated,
            "templated_sha256": sha256(templated),
            "prompt_tokens": len(ids),
            "first_ids": ids[:8],
            "last_ids": ids[-8:],
        })
    result = {
        "onnxruntime_genai": og.__version__,
        "model_snapshot": snapshot[1] if len(snapshot) == 2 else os.path.basename(model_dir),
        "chat_template_jinja_sha256": hashlib.sha256(
            open(os.path.join(model_dir, "chat_template.jinja"), "rb").read()).hexdigest(),
        "add_generation_prompt": True,
        "rows": rows,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
        f.write("\n")
    for row in rows:
        print(row["prompt_file"], "prompt_tokens", row["prompt_tokens"], "templated_sha256", row["templated_sha256"])


if __name__ == "__main__":
    main(*sys.argv[1:])
