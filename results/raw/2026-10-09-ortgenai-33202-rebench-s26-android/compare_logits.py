"""Logits of round r8-33202's dump launches compared pairwise (ORT GenAI,
Galaxy S26, 2026-10-09): ortgenai_run_dl --dump-logits on the 1K task prompt,
greedy, budget 8, with the release libonnxruntime.so ("old", Maven 1.30.0)
or v1.30.0 + microsoft/onnxruntime PR #33202 ("new"), GroupQueryAttention
flash path on (default) or off (ORT_GQA_DISABLE_FLASH_ATTENTION=1).

Inputs: <dumps>/r8-B*-dl-<lib>-<flash>.d/logits.f32 (step 0 = the prompt's
last position) and logits.f32.decode (steps 1.., one forward pass each), vocab
float32 values per step in the phone's byte order (little-endian), and the
LOGITS_DUMP lines of device/<tag>.engine.txt (the token sampled from each
step). The raw files stay outside the repo; this script's JSON goes next to it.

Pairs: new on vs new off (the PR's flash path against the non-flash path, one
library), old off vs new off (the non-flash path, which the PR does not touch,
across the two builds), old on vs old off, new on vs old on.
Per step: max |a - b|, mean |a - b|, the largest |logit| (scale), argmax of
each, the top-5 ids of each (same set, same order), and the softmax
probability of each run's argmax. A decode step k is compared only while both
runs fed the same tokens before it (sampled tokens of steps 0..k-1 equal).

usage: python3 -I compare_logits.py <dumps dir> [<repo results dir>]
"""
import array
import json
import math
import os
import re
import sys

PAIRS = [("new-on", "new-off"), ("old-off", "new-off"), ("old-on", "old-off"), ("new-on", "old-on")]


def load_run(dumps, results, tag):
    rec = []
    d = os.path.join(dumps, tag + ".d")
    for name in ("logits.f32", "logits.f32.decode"):
        raw = open(os.path.join(d, name), "rb").read()
        a = array.array("f")
        a.frombytes(raw)
        if sys.byteorder != "little":
            a.byteswap()
        rec.append(a)
    text = open(os.path.join(results, "device", tag + ".engine.txt"), encoding="utf-8", errors="replace").read()
    lines = re.findall(r"^LOGITS_DUMP step=(\d+) phase=(\w+) shape=(\S+) argmax=(\d+) sampled=(\d+) top5=(\S+)$", text, re.M)
    end = re.search(r"^LOGITS_DUMP_END steps=(\d+) vocab=(\d+)", text, re.M)
    vocab = int(end.group(2))
    steps = [rec[0]] + [rec[1][i * vocab:(i + 1) * vocab] for i in range(len(rec[1]) // vocab)]
    assert len(rec[0]) == vocab and len(rec[1]) % vocab == 0, tag
    assert len(steps) == int(end.group(1)) == len(lines), tag
    sampled = [int(x[4]) for x in lines]
    for k, (row, line) in enumerate(zip(steps, lines)):
        am = max(range(vocab), key=row.__getitem__)
        assert am == int(line[3]), (tag, k, am, line[3])  # the file and the printed line agree
    return {"tag": tag, "vocab": vocab, "steps": steps, "sampled": sampled,
            "output": (re.search(r"\[OUTPUT BEGIN\](.*?)\[OUTPUT END\]", text, re.S) or [None, None])[1]}


def top(row, n=5):
    return sorted(range(len(row)), key=lambda i: (-row[i], i))[:n]


def p_max(row):
    m = max(row)
    z = sum(math.exp(x - m) for x in row)
    return 1.0 / z


def compare(a, b):
    out = {"a": a["tag"], "b": b["tag"], "sampled_a": a["sampled"], "sampled_b": b["sampled"],
           "same_tokens": a["sampled"] == b["sampled"], "same_output_text": a["output"] == b["output"], "steps": []}
    for k in range(min(len(a["steps"]), len(b["steps"]))):
        if a["sampled"][:k] != b["sampled"][:k]:
            out["steps"].append({"step": k, "compared": False, "why": "the tokens fed before this step differ"})
            continue
        ra, rb = a["steps"][k], b["steps"][k]
        diffs = [abs(x - y) for x, y in zip(ra, rb)]
        ta, tb = top(ra), top(rb)
        out["steps"].append({
            "step": k, "compared": True,
            "max_abs_diff": max(diffs), "mean_abs_diff": sum(diffs) / len(diffs),
            "max_abs_logit": max(max(abs(x) for x in ra), max(abs(x) for x in rb)),
            "argmax_a": ta[0], "argmax_b": tb[0], "argmax_equal": ta[0] == tb[0],
            "top5_a": ta, "top5_b": tb, "top5_same_set": set(ta) == set(tb), "top5_same_order": ta == tb,
            "p_argmax_a": p_max(ra), "p_argmax_b": p_max(rb),
            "logit_argmax_a": ra[ta[0]], "logit_argmax_b": rb[tb[0]],
            "second_gap_a": ra[ta[0]] - ra[ta[1]], "second_gap_b": rb[tb[0]] - rb[tb[1]],
        })
    done = [s for s in out["steps"] if s["compared"]]
    out["compared_steps"] = len(done)
    out["max_abs_diff_all"] = max((s["max_abs_diff"] for s in done), default=None)
    out["argmax_equal_all"] = all(s["argmax_equal"] for s in done)
    out["top5_same_set_all"] = all(s["top5_same_set"] for s in done)
    return out


def main(dumps, results):
    tags = sorted(t[:-2] for t in os.listdir(dumps) if t.startswith("r8-B") and t.endswith(".d"))
    runs = {}
    for t in tags:
        m = re.match(r"^r8-B\d-dl-(old|new)-(on|off)$", t)
        if m:
            runs[f"{m.group(1)}-{m.group(2)}"] = load_run(dumps, results, t)
    res = {"runs": {k: {"tag": v["tag"], "vocab": v["vocab"], "steps": len(v["steps"]), "sampled": v["sampled"],
                        "output": v["output"]} for k, v in runs.items()}, "pairs": []}
    lines = ["Logits, 1K task prompt (1338 tokens), greedy, budget 8: pairs of launches",
             "", "| pair | steps compared | same 8 tokens | max abs diff, prompt step | max abs diff, all compared steps | argmax equal (all) | top-5 same set (all) | top-5 same order (all) |",
             "|---|---|---|---|---|---|---|---|"]
    for x, y in PAIRS:
        if x not in runs or y not in runs:
            continue
        c = compare(runs[x], runs[y])
        c["pair"] = f"{x} vs {y}"
        res["pairs"].append(c)
        p0 = c["steps"][0]
        lines.append(f"| {x} vs {y} | {c['compared_steps']} | {'yes' if c['same_tokens'] else 'no'} | {p0['max_abs_diff']:.4g} | "
                     f"{c['max_abs_diff_all']:.4g} | {'yes' if c['argmax_equal_all'] else 'no'} | {'yes' if c['top5_same_set_all'] else 'no'} | "
                     f"{'yes' if all(s['top5_same_order'] for s in c['steps'] if s['compared']) else 'no'} |")
    lines += ["", "per step (pair: step max abs diff / mean abs diff / argmax a,b / p(argmax) a,b):"]
    for c in res["pairs"]:
        lines.append(f"- {c['pair']}: " + "; ".join(
            f"{s['step']}: {s['max_abs_diff']:.3g} / {s['mean_abs_diff']:.2g} / {s['argmax_a']},{s['argmax_b']} / {s['p_argmax_a']:.4f},{s['p_argmax_b']:.4f}"
            if s["compared"] else f"{s['step']}: not compared" for s in c["steps"]))
    lines += ["", "sampled tokens: " + "; ".join(f"{k} {v['sampled']}" for k, v in runs.items())]
    print("\n".join(lines))
    with open(os.path.join(results, "logits_summary.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else here)
