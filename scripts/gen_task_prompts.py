#!/usr/bin/env python3
"""Regenerate prompts/text/*.txt — the canonical task prompts, byte-identical to
what the Swift tasks build (same-budget rule: every arm sees the same prompt).

Sources of truth being mirrored:
  ShortChatTask.swift    prompt literal, maxTokens 128, greedy
  LongContextTask.swift  [i]-tagged lorem blocks (55 tok/block nominal) + tail;
                         long-context-1024-gen256 = 18 blocks + NOREF_TAIL, maxTokens 256
                         long-context-2048-gen256 = explicit 27 blocks, maxTokens 256

long-context-2048-gen256-noref = the same 27 blocks with a tail that calls them
filler and asks from the model's own knowledge (NOREF_TAIL), maxTokens 256; Android
drivers read the file, the Swift catalog builds it (LongContextTask.norefTail, since
2026-10-17 for catalog X2's iPhone leg). long-context-1024-gen256 takes the same tail
since 2026-10-19 (the "passage above" tail before), under the same id: versions.tsv
names the versioned texts (VERSIONS; the records' conditions.promptVersion).

The Android CLI drivers feed these files via --input_prompt_file / llama-cli -f.
If a Swift task changes, regenerate and commit; a follow-up iOS unit test can
assert the Swift-built prompts hash to the same values.
"""
import hashlib
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "prompts", "text")

LOREM = ("Lorem ipsum dolor sit amet, consectetur adipiscing elit. Phasellus bibendum velit non augue "
         "ultricies, a vestibulum ipsum porttitor. Sed at nulla a justo viverra dictum. Vivamus blandit "
         "velit at lectus pulvinar pellentesque. Mauris dictum massa ut nisi tristique consequat.")
TOKENS_PER_BLOCK = 55


def long_context(target_tokens, force_long_output, blocks=None, tail=None):
    blocks = blocks if blocks is not None else max(1, target_tokens // TOKENS_PER_BLOCK)
    pieces = [f"[{i}] {LOREM}" for i in range(blocks)]
    if tail is not None:
        pieces.append("\n\n" + tail)
    elif force_long_output:
        pieces.append("\n\nUsing the passage above as context, list 25 distinct things "
                      "on-device AI lets a phone do that a cloud model cannot. Number every item "
                      "and give each one two full sentences of explanation. Do not stop early.")
    else:
        pieces.append("\n\nFinish with one sentence: what on-device AI lets a phone do that a cloud model cannot.")
    return "\n".join(pieces)


# The 2048 task's tail asks "using the passage above": on the Galaxy S26 GPU (v0.16.0) Gemma 4
# E4B refuses the lorem blocks in 50-61 tokens and E2B stops at 93 tokens at an 8,192
# allocation (results/raw/2026-09-24-dashboard-longctx-v1-s26-android-gpu-retake/text_check.md),
# so its decode rates are taken over different answer lengths. This tail asks for the same list
# from the model's own knowledge. Since 2026-10-19 the 1K task takes it too (with the model's own chat
# template Gemma 4 on llama.cpp and MLX declined the "passage above" tail as placeholder text); a text
# change under an id that records already carry gets a version in VERSIONS (docs/dashboard-cells-v1.md
# "1K task tail (2026-10-19)").
NOREF_TAIL = ("The numbered blocks above are filler text and carry no information; do not summarize "
              "or evaluate them. From your own knowledge, list 25 distinct things on-device AI lets "
              "a phone do that a cloud model cannot. Number every item and give each one two full "
              "sentences of explanation. Do not stop early.")

PROMPTS = {
    # task id -> (text, decode budget the task pins)
    "short-chat": ("Explain what on-device AI means in simple terms.", 128),
    "long-context-1024-gen256": (long_context(1024, True, tail=NOREF_TAIL), 256),
    "long-context-2048-gen256": (long_context(2048, True, blocks=27), 256),
    "long-context-2048-gen256-noref": (long_context(2048, True, blocks=27, tail=NOREF_TAIL), 256),
}

# task id -> the version of its text (the Swift tasks' promptVersion, byte for byte): every driver
# writes it into its records as conditions.promptVersion and results/summary carries it as
# prompt_version, so a series across a text change under one id is marked, never compared
# (scripts/regression_watch.py prompt_changed). A task not here keeps the text it was born with (no
# key). The 1K text changed on 2026-10-19; the 2K noref text is unchanged since its first records
# (2026-10-12): its records before 2026-10-19 carry no version and the same text.
VERSIONS = {
    "long-context-1024-gen256": "noref-2026-10-19",
    "long-context-2048-gen256-noref": "noref-2026-10-12",
}

# EnduranceChatTask.turnPrompts mirrored verbatim (methodology/endurance.md;
# rationale prompts/endurance-chat.md). The Android endurance driver reads
# this as one prompt per line — the script is part of the measurement
# contract (same-budget), so changing a line means a new task id, not an
# edit in place. Not in PROMPTS/budgets.tsv: endurance's 256-token cap is a
# PER-TURN cap carried by the task, not a single-prompt decode budget.
ENDURANCE_TURNS = [
    "Let's talk about running language models on phones. In two or three sentences, what is the biggest engineering constraint?",
    "Which matters more for the experience you just described: prefill speed or decode speed? Answer briefly and say why.",
    "Give me a concrete example with a model around 2B parameters.",
    "Summarize our conversation so far in one short paragraph.",
    "Now switch topics: explain KV cache growth during a long chat, in a few sentences.",
    "How does quantization interact with the problem you just explained? Keep it brief.",
    "Earlier you named an engineering constraint. Does quantization help with that one too? A short answer is fine.",
    "Write a four-line rhyming poem about a phone getting warm while it thinks.",
    "In one sentence each, name three ways a chat app can shorten its context when the conversation gets long.",
    "Which of those three would you pick for a low-RAM device, and why? Two sentences.",
    "Summarize everything we have discussed in this whole conversation in one short paragraph.",
    "Ask me one good follow-up question about on-device AI, then answer it yourself in two sentences.",
]


def main():
    os.makedirs(OUT, exist_ok=True)
    for task, (text, budget) in PROMPTS.items():
        path = os.path.join(OUT, f"{task}.txt")
        with open(path, "w") as fh:
            fh.write(text)
        sha = hashlib.sha256(text.encode()).hexdigest()
        print(f"{task}: {len(text)} bytes, budget {budget}, sha256 {sha[:16]}…")
    turns = "\n".join(ENDURANCE_TURNS) + "\n"
    with open(os.path.join(OUT, "endurance-chat.turns.txt"), "w") as fh:
        fh.write(turns)
    print(f"endurance-chat.turns: {len(ENDURANCE_TURNS)} prompts, "
          f"sha256 {hashlib.sha256(turns.encode()).hexdigest()[:16]}…")
    # budgets sidecar so drivers don't hardcode them
    with open(os.path.join(OUT, "budgets.tsv"), "w") as fh:
        for task, (_, budget) in PROMPTS.items():
            fh.write(f"{task}\t{budget}\n")
    # versions sidecar: the drivers stamp conditions.promptVersion from it
    with open(os.path.join(OUT, "versions.tsv"), "w") as fh:
        for task, version in VERSIONS.items():
            fh.write(f"{task}\t{version}\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
