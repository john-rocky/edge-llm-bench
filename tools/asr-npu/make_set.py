#!/usr/bin/env python3
"""Cut S32, its first 20 rows (F20) and the warm-up utterance W out of a prep_librispeech.py set and
pack F20 + W for the phone (asr-npu-v1, docs/asr-npu-v1.md; asr-fix-v1's make_set.py with the
smaller pack). Reads the set; writes only under <out_dir> (and --record).

S32 = the rows of <set>/manifest.tsv at index 0, 32, 64, ... in the file's order (the parquet's
order, longest first): 82 of LibriSpeech test-clean's 2620, asr-burst-v1 / asr-fix-v1's S32 (its
chain is checked against --expect-s32-chain). F20 = the first 20 rows of S32 (the CTC CPU runs);
F10 = its first 10 (the TDT NPU smoke runs). W = the row with --warmup-id (default
1995-1836-0004, outside S32), transcribed once per process outside the scoring.

Writes:
  <out>/manifest-S32.jsonl, manifest-F20.jsonl, manifest-F10.jsonl   rows in order (score.py's --manifest)
  <out>/SET-S32.json, SET-F20.json, SET-F10.json   utterances, total_seconds, wav_sha256_chain over the
                                                    WAVs in order, W, and the full set recomputed
  <out>/manifest-device.tsv                         every row of the set, `id<TAB><id>.wav<TAB>seconds`
  <out>/test-clean-F20W.tar (+ .tar.json)           manifest-device.tsv + the 20 F20 WAVs + W; the test
                                                    selects them itself (every=32, limit=20 / 10)

Usage: make_set.py <set_dir> <out_dir> [--warmup-id ID] [--expect-s32-chain SHA] [--record DIR]
"""
import argparse
import hashlib
import io
import json
import pathlib
import shutil
import sys
import tarfile
import wave


def wav_seconds(path):
    with wave.open(str(path), "rb") as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, 16000):
            raise SystemExit(f"{path}: not 16 kHz mono PCM16")
        return w.getnframes() / 16000.0


def chain(paths):
    sha = hashlib.sha256()
    total = 0.0
    for p in paths:
        sha.update(pathlib.Path(p).read_bytes())
        total += wav_seconds(p)
    return {"utterances": len(paths), "total_seconds": total, "wav_sha256_chain": sha.hexdigest()}


def sha256_file(path):
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            sha.update(block)
    return sha.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("set_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--warmup-id", default="1995-1836-0004")
    ap.add_argument("--expect-s32-chain", default="6ccb9d3c271b966a7c7cdaa02417b360a1319a858542fab92dc8407e3332f8f4")
    ap.add_argument("--record", default="")
    args = ap.parse_args()

    d = pathlib.Path(args.set_dir)
    out = pathlib.Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = [line.rstrip("\n").split("\t") for line in open(d / "manifest.tsv") if line.strip()]
    meta = [json.loads(line) for line in open(d / "manifest.jsonl") if line.strip()]
    if [i for i, _ in rows] != [m["id"] for m in meta]:
        raise SystemExit("manifest.tsv and manifest.jsonl disagree on ids or order")
    by_id = {m["id"]: m for m in meta}
    s32 = rows[::32]
    if args.warmup_id in {i for i, _ in s32}:
        raise SystemExit(f"warm-up id {args.warmup_id} is inside S32")
    w_index = next((n for n, (i, _) in enumerate(rows) if i == args.warmup_id), None)
    if w_index is None:
        raise SystemExit(f"warm-up id {args.warmup_id} is not in the set")
    w_path = dict(rows)[args.warmup_id]
    full = chain([p for _, p in rows])
    warmup = {"id": args.warmup_id, "row_index": w_index, "seconds": wav_seconds(w_path),
              "wav_sha256": sha256_file(w_path), "in_s32": False}

    recs = {}
    for name, sel, rule in (
        ("S32", s32, "manifest.tsv rows at index 0, 32, 64, ... (every 32th row from the first, file order)"),
        ("F20", s32[:20], "the first 20 rows of S32"),
        ("F10", s32[:10], "the first 10 rows of S32"),
    ):
        ids = [i for i, _ in sel]
        with open(out / f"manifest-{name}.jsonl", "w") as f:
            for i in ids:
                f.write(json.dumps(by_id[i], ensure_ascii=False) + "\n")
        rec = {"set": f"librispeech-test-clean-{name}", "rule": rule, **chain([p for _, p in sel]),
               "ids": ids if len(ids) <= 20 else ids[:3], "last_id": ids[-1], "warmup": warmup, "full": full,
               "source_set_dir": str(d)}
        set_json = out / f"SET-{name}.json"
        set_json.write_text(json.dumps(rec, indent=2) + "\n")
        if args.record:
            pathlib.Path(args.record).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(set_json, pathlib.Path(args.record) / set_json.name)
        recs[name] = rec
    s32_ok = recs["S32"]["wav_sha256_chain"] == args.expect_s32_chain

    lines = [f"{m['id']}\t{m['id']}.wav\t{m['seconds_written']!r}\n" for m in meta]
    manifest = "".join(lines).encode()
    (out / "manifest-device.tsv").write_bytes(manifest)
    tar_path = out / "test-clean-F20W.tar"
    packed = recs["F20"]["ids"] + [args.warmup_id]
    with tarfile.open(tar_path, "w", format=tarfile.USTAR_FORMAT) as tar:
        info = tarfile.TarInfo("manifest-device.tsv")
        info.size, info.mode, info.mtime = len(manifest), 0o644, 0
        tar.addfile(info, io.BytesIO(manifest))
        for i in packed:
            wav = d / f"{i}.wav"
            info = tarfile.TarInfo(wav.name)
            info.size, info.mode, info.mtime = wav.stat().st_size, 0o644, 0
            with open(wav, "rb") as f:
                tar.addfile(info, f)
    tar_rec = {"tar": tar_path.name, "tar_bytes": tar_path.stat().st_size, "tar_sha256": sha256_file(tar_path),
               "manifest": "manifest-device.tsv", "manifest_rows": len(lines),
               "manifest_sha256": hashlib.sha256(manifest).hexdigest(), "wavs": len(packed),
               **{n.lower(): {k: r[k] for k in ("utterances", "total_seconds", "wav_sha256_chain")} for n, r in recs.items()},
               "s32_chain_matches_asr_fix_v1": s32_ok, "warmup": warmup}
    (out / f"{tar_path.name}.json").write_text(json.dumps(tar_rec, indent=2) + "\n")
    print(json.dumps({**{n: {k: r[k] for k in ("utterances", "total_seconds", "wav_sha256_chain", "last_id")}
                         for n, r in recs.items()},
                      "s32_chain_matches_asr_fix_v1": s32_ok, "warmup": warmup, "full_chain": full["wav_sha256_chain"],
                      "tar": {k: tar_rec[k] for k in ("tar_bytes", "tar_sha256", "manifest_sha256", "wavs")}}, indent=2))
    return 0 if s32_ok else 1


if __name__ == "__main__":
    sys.exit(main())
