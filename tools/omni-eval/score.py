#!/usr/bin/env python3
"""Score an omni_eval_runner JSONL against a manifest the way the Open ASR
Leaderboard scores: the leaderboard's EnglishTextNormalizer on both sides,
corpus-level WER (total edits / total reference words), RTFx = audio / time.

Usage: score.py --manifest <dir>/manifest.jsonl --pred <run>.jsonl [--details out.jsonl]
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import jiwer  # noqa: E402
from leaderboard.normalizer import EnglishTextNormalizer  # noqa: E402

normalizer = EnglishTextNormalizer()


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--pred", required=True)
    ap.add_argument("--details", default="")
    ap.add_argument("--worst", type=int, default=0, help="print the N worst utterances")
    args = ap.parse_args()

    refs = {r["id"]: r for r in load_jsonl(args.manifest)}
    preds = load_jsonl(args.pred)
    header = next((p for p in preds if p.get("type") == "header"), {})
    footer = next((p for p in preds if p.get("type") == "footer"), {})
    utts = [p for p in preds if "id" in p]
    seen = {p["id"] for p in utts}
    hung = [i for i in refs if i not in seen]
    for i in hung:  # utterances the runner never returned from (killed by the watchdog): scored as empty
        utts.append({"id": i, "text": "", "audio_seconds": refs[i]["seconds_written"],
                     "processing_seconds": 0.0, "session_create_seconds": 0.0, "error": "hang (watchdog)"})

    norm_refs, norm_hyps, rows = [], [], []
    audio = proc = create = 0.0
    empty = errors = flush_empty = 0
    for p in utts:
        r = refs[p["id"]]
        nr = normalizer(r["text"])
        nh = normalizer(p["text"])
        if not nr.strip():
            continue  # the leaderboard drops empty references
        if p.get("error") == "NOT_FOUND: Deque has no output available.":
            flush_empty += 1  # v1 runner recorded a benign Flush() NOT_FOUND as an error
        elif p.get("error"):
            errors += 1
        if p.get("flush_empty"):
            flush_empty += 1
        if not nh.strip():
            empty += 1
        norm_refs.append(nr)
        norm_hyps.append(nh)
        audio += p["audio_seconds"]
        proc += p["processing_seconds"]
        create += p.get("session_create_seconds", 0.0)
        m = jiwer.process_words(nr, nh if nh.strip() else "")
        rows.append({
            "id": p["id"], "audio_seconds": p["audio_seconds"],
            "processing_seconds": p["processing_seconds"],
            "ref": nr, "hyp": nh, "raw_hyp": p["text"],
            "ref_words": len(nr.split()),
            "S": m.substitutions, "D": m.deletions, "I": m.insertions,
            "errors": m.substitutions + m.deletions + m.insertions,
            "wer": m.wer, "error": "" if p.get("error") == "NOT_FOUND: Deque has no output available." else p.get("error", ""),
        })

    out = jiwer.process_words(norm_refs, norm_hyps)
    total_ref_words = sum(r["ref_words"] for r in rows)
    result = {
        "model_name": header.get("model_name"), "backend": header.get("backend"),
        "num_threads": header.get("num_threads"),
        "push_chunk_ms": header.get("push_chunk_ms"),
        "reuse_session": header.get("reuse_session"),
        "utterances": len(rows), "hung_utterances": hung, "runner_failures": errors, "flush_empty": flush_empty,
        "empty_hypotheses": empty,
        "wer_percent": round(100 * out.wer, 2),
        "substitutions": out.substitutions, "deletions": out.deletions,
        "insertions": out.insertions, "reference_words": total_ref_words,
        "audio_hours": round(audio / 3600, 3),
        "processing_seconds": round(proc, 1),
        "rtfx_processing": round(audio / proc, 2) if proc else None,
        "rtfx_processing_plus_session_create": round(audio / (proc + create), 2) if proc else None,
        "load_seconds": header.get("load_seconds"),
        "peak_rss_mb": round(footer.get("peak_rss_bytes", 0) / 1e6, 1) if footer else None,
    }
    print(json.dumps(result, indent=2))
    if args.details:
        with open(args.details, "w") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    if args.worst:
        for r in sorted(rows, key=lambda x: -x["errors"])[: args.worst]:
            print(f"--- {r['id']} S{r['S']} D{r['D']} I{r['I']} / {r['ref_words']} words, {r['audio_seconds']:.1f}s")
            print("REF:", r["ref"])
            print("HYP:", r["hyp"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
