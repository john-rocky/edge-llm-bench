#!/usr/bin/env python3
"""Summarize the A and C runs of asr-npu-v1 (docs/asr-npu-v1.md): AsrBenchTest JSONL rows through
tools/omni-eval/score.py (the Open ASR Leaderboard normalizer, corpus WER, S/D/I).

  summarize.py --rec <REC> --set-dir .build/asr-npu/set --out <REC>/summary [--l1-ref <asr-litert-app-v1 l1 S4 jsonl>]

Per run (<tag>.jsonl in REC): the header (model, model_file, accelerator, tdt_fix, tdt_buffers,
load, foreground / cpuset), the rows, the rows with an error and their messages (first and count),
empty texts, WER / S / D / I over the rows the run covered (rows with an error score as empty text),
the decoder's network runs per window (TDT), VmHWM, the registration lines of the load log, and for
NPU runs the merger's `decode: tokenId=` lines kept in <tag>.tokens.log (how many, how many with
token 0). Pairs: c-cpu-separate's text against c-cpu-shared's (identical rows), c-npu-* against the
asr-litert-app-v1 L1 run (CPU, 5 s int8) over the same ids (--l1-ref: the WER of the same rows).
Writes <out>/<tag>.score.json and <out>/runs.json; prints one line per run.
"""
import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
REG = re.compile(r"registered|Replacing \d+ out of \d+ node|DispatchDelegate|Dispatch|NpuAccelerator|qnn_partition|"
                 r"QnnContext|fallback|Fallback")


def load(path):
    return [json.loads(line) for line in open(path) if line.strip()]


def score(manifest_lines, rows):
    """score.py over these manifest lines and rows (it imports the vendored normalizer as `leaderboard`)."""
    tmp = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
    tmp.writelines(manifest_lines)
    tmp.close()
    pred = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
    for u in rows:
        pred.write(json.dumps({k: u.get(k) for k in ("id", "text", "audio_seconds", "processing_seconds", "error")
                               if u.get(k) is not None}) + "\n")
    pred.close()
    alias = pathlib.Path(tempfile.mkdtemp())
    (alias / "leaderboard").symlink_to(ROOT / "tools/omni-eval/leaderboard_normalizer")
    env = dict(os.environ, PYTHONPATH=str(alias), PYTHONDONTWRITEBYTECODE="1")
    out = subprocess.run([sys.executable, str(ROOT / "tools/omni-eval/score.py"), "--manifest", tmp.name, "--pred", pred.name],
                         env=env, capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(out.stderr)
    return json.loads(out.stdout)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rec", required=True)
    ap.add_argument("--set-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--l1-ref", default="")
    args = ap.parse_args()
    rec, out = pathlib.Path(args.rec), pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    manifest = {json.loads(l)["id"]: l for l in open(pathlib.Path(args.set_dir) / "manifest-S32.jsonl") if l.strip()}
    runs = {}
    for path in sorted(rec.glob("[ac]-*.jsonl")):
        tag = path.stem
        rows = load(path)
        head = next((r for r in rows if r.get("type") == "header"), {})
        foot = next((r for r in reversed(rows) if r.get("type") == "footer"), {})
        utts = [r for r in rows if r.get("type") == "utterance"]
        warm = next((r for r in rows if r.get("type") == "warmup"), None)
        errors = [u for u in utts if u.get("error")]
        s = score([manifest[u["id"]] for u in utts], utts)
        (out / f"{tag}.score.json").write_text(json.dumps(s, indent=1) + "\n")
        load_log = rec / f"{tag}.load-logcat.txt"
        reg = sorted({re.sub(r"^\S+ \S+\s+\d+\s+\d+ ", "", l.strip()) for l in open(load_log, errors="replace")
                      if REG.search(l)}) if load_log.exists() else []
        tokens = rec / f"{tag}.tokens.log"
        tok = None
        if tokens.exists():
            lines = [l for l in open(tokens, errors="replace") if "decode: tokenId=" in l]
            tok = {"lines": len(lines), "token0_lines": sum("tokenId=0," in l or "tokenId=0 " in l for l in lines)}
        steps = [s_ for u in utts for s_ in (u.get("window_decode_steps") or [])]
        runs[tag] = {
            "model": head.get("model_name"), "accelerator": head.get("backend"),
            "model_file": head.get("model_file"), "model_bytes": head.get("model_bytes"),
            "model_sha256": foot.get("model_sha256"), "tdt_fix": head.get("tdt_fix"), "tdt_buffers": head.get("tdt_buffers"),
            "load_ms": head.get("load_ms"), "foreground_state": head.get("foreground_state"),
            "cpuset": (head.get("process_state") or {}).get("after_load", {}).get("cpuset"),
            "rows": len(utts), "error_rows": len(errors),
            "first_error": errors[0]["error"] if errors else None,
            "errors_distinct": sorted({e["error"] for e in errors}),
            "warmup_error": (warm or {}).get("error"), "warmup_text": (warm or {}).get("text"),
            "empty_texts": sum(1 for u in utts if not u.get("error") and not u.get("text", "").strip()),
            "wer_percent": s["wer_percent"], "S": s["substitutions"], "D": s["deletions"], "I": s["insertions"],
            "reference_words": s["reference_words"], "empty_hypotheses": s["empty_hypotheses"],
            "decode_network_runs_per_window": (sum(steps) / len(steps)) if steps else None,
            "vmhwm_kb": foot.get("vmhwm_kb"), "footer": bool(foot),
            "registration": reg[:40], "tokens_log": tok,
            "texts": {u["id"]: u.get("text", "") for u in utts},
        }
    if "c-cpu-shared-smoke10" in runs and "c-cpu-separate-smoke10" in runs:
        a, b = runs["c-cpu-shared-smoke10"]["texts"], runs["c-cpu-separate-smoke10"]["texts"]
        runs["c-cpu-separate-smoke10"]["same_text_as_c_cpu_shared"] = sum(a.get(i) == t for i, t in b.items())
    if args.l1_ref:
        l1 = {r["id"]: r for r in load(args.l1_ref) if "id" in r and r.get("type") != "warmup"}
        for tag in [t for t in runs if t.startswith("c-npu-")]:
            ids = list(runs[tag]["texts"])
            ref_rows = [l1[i] for i in ids if i in l1]
            s = score([manifest[r["id"]] for r in ref_rows], ref_rows)
            runs[tag]["l1_same_ids"] = {"rows": len(ref_rows), "wer_percent": s["wer_percent"],
                                        "S": s["substitutions"], "D": s["deletions"], "I": s["insertions"]}
    (out / "runs.json").write_text(json.dumps(runs, indent=1, ensure_ascii=False) + "\n")
    for tag, r in runs.items():
        print(f"{tag}: rows {r['rows']} errors {r['error_rows']} empty {r['empty_texts']} WER {r['wer_percent']} % "
              f"(S/D/I {r['S']}/{r['D']}/{r['I']} of {r['reference_words']}) load {r['load_ms']} ms"
              + (f" first error: {r['first_error'][:120]}" if r["first_error"] else "")
              + (f" tokens.log {r['tokens_log']}" if r["tokens_log"] else "")
              + (f" same text as c-cpu-shared {r['same_text_as_c_cpu_shared']}/{r['rows']}" if "same_text_as_c_cpu_shared" in r else "")
              + (f" L1 same ids WER {r['l1_same_ids']['wer_percent']} %" if "l1_same_ids" in r else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
