#!/usr/bin/env python3
"""Cut S4, S16 and the warm-up utterance W out of a prep_librispeech.py set and pack them for the
phone (asr-fix-v1, docs/asr-fix-v1.md; asr-burst-v1's make_s16.py with S4 added). Reads the set;
writes only under <out_dir> (and --record).

S4 = the rows of <set>/manifest.tsv at index 0, 4, 8, ... in the file's order (= the parquet's row
order, longest first): 655 of LibriSpeech test-clean's 2620 (asr-litert-app-v1 / asr-sherpa-v1's S4).
S16 = the rows at index 0, 16, 32, ...: 164, every fourth row of S4 (asr-burst-v1's S16). S32 = the
rows at index 0, 32, 64, ...: 82, every other row of S16 (the burst set since LANE §0 amendment 5). W = the row
with --warmup-id (default 1995-1836-0004 = row 1, outside S4 and S16), transcribed once per process
outside the timing.

Writes:
  <out>/manifest-S4.tsv, manifest-S4.jsonl     the S4 rows in order (score.py's --manifest)
  <out>/manifest-S16.tsv, manifest-S16.jsonl   the S16 rows in order (and S32)
  <out>/SET-S4.json, SET-S16.json, SET-S32.json utterances, total_seconds, wav_sha256_chain over the
                                               set's WAVs in order (make_subset.py's computation), W,
                                               and the full set recomputed from the WAVs
  <out>/manifest-device.tsv                    every row of the set, `id<TAB><id>.wav<TAB>seconds`
                                               (seconds = seconds_written), as asr-litert-app-v1's
  <out>/test-clean-S4W.tar (+ .tar.json)       manifest-device.tsv + the 655 S4 WAVs + W; the test
                                               selects S4 / S16 itself (every=4 / 16) and finds W by id

Usage: make_set.py <set_dir> <out_dir> [--warmup-id ID] [--record <dir for copies of SET-S4.json / SET-S16.json>]
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

SETS = {"S4": 4, "S16": 16, "S32": 32}


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

    s4_ids = [i for i, _ in rows[::4]]
    if not {i for i, _ in rows[::32]} <= {i for i, _ in rows[::16]} <= set(s4_ids):
        raise SystemExit("S32 / S16 is not a subset of S16 / S4")
    w_index = next((n for n, (i, _) in enumerate(rows) if i == args.warmup_id), None)
    if w_index is None:
        raise SystemExit(f"warm-up id {args.warmup_id} is not in the set")
    if args.warmup_id in set(s4_ids):
        raise SystemExit(f"warm-up id {args.warmup_id} is inside S4")
    w_path = dict(rows)[args.warmup_id]
    full = chain([p for _, p in rows])
    warmup = {
        "id": args.warmup_id,
        "row_index": w_index,
        "seconds": wav_seconds(w_path),
        "wav_sha256": sha256_file(w_path),
        "in_s4": False,
        "in_s16": False,
    }

    recs = {}
    for name, every in SETS.items():
        sel = rows[::every]
        ids = [i for i, _ in sel]
        with open(out / f"manifest-{name}.tsv", "w") as f:
            for i, p in sel:
                f.write(f"{i}\t{p}\n")
        with open(out / f"manifest-{name}.jsonl", "w") as f:
            for i in ids:
                f.write(json.dumps(by_id[i], ensure_ascii=False) + "\n")
        rule = f"manifest.tsv rows at index 0, {every}, {2 * every}, ... (every {every}th row from the first, file order)"
        if every == 16:
            rule = rule[:-1] + "; every 4th row of S4)"
        if every == 32:
            rule = rule[:-1] + "; every 2nd row of S16, every 8th row of S4)"
        rec = {
            "set": f"librispeech-test-clean-{name}",
            "rule": rule,
            **chain([p for _, p in sel]),
            "first_ids": ids[:3],
            "last_id": ids[-1],
            "warmup": warmup,
            "full": full,
            "source_set_dir": str(d),
        }
        set_json = out / f"SET-{name}.json"
        set_json.write_text(json.dumps(rec, indent=2) + "\n")
        if args.record:
            pathlib.Path(args.record).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(set_json, pathlib.Path(args.record) / set_json.name)
        recs[name] = rec

    lines = [f"{m['id']}\t{m['id']}.wav\t{m['seconds_written']!r}\n" for m in meta]
    manifest = "".join(lines).encode()
    (out / "manifest-device.tsv").write_bytes(manifest)
    tar_path = out / "test-clean-S4W.tar"
    packed = s4_ids + [args.warmup_id]
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
    tar_rec = {
        "tar": tar_path.name,
        "tar_bytes": tar_path.stat().st_size,
        "tar_sha256": sha256_file(tar_path),
        "manifest": "manifest-device.tsv",
        "manifest_rows": len(lines),
        "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
        "wavs": len(packed),
        **{name.lower(): {k: rec[k] for k in ("utterances", "total_seconds", "wav_sha256_chain")} for name, rec in recs.items()},
        "warmup": warmup,
    }
    (out / f"{tar_path.name}.json").write_text(json.dumps(tar_rec, indent=2) + "\n")
    print(json.dumps({**{name: {k: rec[k] for k in ("utterances", "total_seconds", "wav_sha256_chain", "first_ids", "last_id")}
                         for name, rec in recs.items()},
                      "warmup": warmup, "full_chain": full["wav_sha256_chain"],
                      "tar": {k: tar_rec[k] for k in ("tar_bytes", "tar_sha256", "manifest_sha256", "wavs")}}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
