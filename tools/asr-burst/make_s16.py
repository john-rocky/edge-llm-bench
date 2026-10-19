#!/usr/bin/env python3
"""Cut S16, S32 and the warm-up utterance W out of a prep_librispeech.py set and pack them for the phone
(asr-burst-v1, docs/asr-burst-v1.md). Reads the set; writes only under <out_dir> (and --record).

S32 (LANE §0 revision 5, the burst set from then on) = the rows at index 0, 32, 64, ... = 82 utterances,
every other row of S16, so the S16 tar holds its WAVs: manifest-S32.tsv / .jsonl and SET-S32.json.

S16 = the rows of <set>/manifest.tsv at index 0, 16, 32, ... in the file's order (= the parquet's row
order, longest first): 164 of LibriSpeech test-clean's 2620, every fourth row of S4. W = the row with
--warmup-id (default 1995-1836-0004 = row 1, outside S4 and S16), transcribed once per process
outside the timing.

Writes:
  <out>/manifest-S16.tsv, manifest-S16.jsonl   the S16 rows in order (score.py's --manifest)
  <out>/SET-S16.json                           utterances, total_seconds, wav_sha256_chain over the
                                               S16 WAVs in order (make_subset.py's computation), W,
                                               and the full set recomputed from the WAVs
  <out>/manifest-device.tsv                    every row of the set, `id<TAB><id>.wav<TAB>seconds`
                                               (seconds = seconds_written), as asr-litert-app-v1's
  <out>/test-clean-S16W.tar (+ .tar.json)      manifest-device.tsv + the 164 S16 WAVs + W; the test
                                               selects S16 itself (every=16) and finds W by id

Usage: make_s16.py <set_dir> <out_dir> [--warmup-id ID] [--record <dir for a copy of SET-S16.json>]
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

EVERY = 16


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

    s16 = rows[::EVERY]
    s4_ids = {i for i, _ in rows[::4]}
    ids16 = [i for i, _ in s16]
    if not set(ids16) <= s4_ids:
        raise SystemExit("S16 is not a subset of S4")
    w_index = next((n for n, (i, _) in enumerate(rows) if i == args.warmup_id), None)
    if w_index is None:
        raise SystemExit(f"warm-up id {args.warmup_id} is not in the set")
    if args.warmup_id in s4_ids:
        raise SystemExit(f"warm-up id {args.warmup_id} is inside S4")
    w_path = dict(rows)[args.warmup_id]

    with open(out / "manifest-S16.tsv", "w") as f:
        for i, p in s16:
            f.write(f"{i}\t{p}\n")
    with open(out / "manifest-S16.jsonl", "w") as f:
        for i in ids16:
            f.write(json.dumps(by_id[i], ensure_ascii=False) + "\n")

    rec = {
        "set": "librispeech-test-clean-S16",
        "rule": f"manifest.tsv rows at index 0, {EVERY}, {2 * EVERY}, ... (every {EVERY}th row from the first, file order; every 4th row of S4)",
        **chain([p for _, p in s16]),
        "first_ids": ids16[:3],
        "last_id": ids16[-1],
        "warmup": {
            "id": args.warmup_id,
            "row_index": w_index,
            "seconds": wav_seconds(w_path),
            "wav_sha256": sha256_file(w_path),
            "in_s4": False,
            "in_s16": False,
        },
        "full": chain([p for _, p in rows]),
        "source_set_dir": str(d),
    }
    set_json = out / "SET-S16.json"
    set_json.write_text(json.dumps(rec, indent=2) + "\n")

    s32 = rows[::32]
    ids32 = [i for i, _ in s32]
    if not set(ids32) <= set(ids16):
        raise SystemExit("S32 is not a subset of S16")
    with open(out / "manifest-S32.tsv", "w") as f:
        for i, p in s32:
            f.write(f"{i}\t{p}\n")
    with open(out / "manifest-S32.jsonl", "w") as f:
        for i in ids32:
            f.write(json.dumps(by_id[i], ensure_ascii=False) + "\n")
    rec32 = {
        "set": "librispeech-test-clean-S32",
        "rule": "manifest.tsv rows at index 0, 32, 64, ... (every 32nd row from the first, file order; every other row of S16)",
        **chain([p for _, p in s32]),
        "first_ids": ids32[:3],
        "last_id": ids32[-1],
        "warmup": rec["warmup"],
        "s16_wav_sha256_chain": rec["wav_sha256_chain"],
        "full_wav_sha256_chain": rec["full"]["wav_sha256_chain"],
        "source_set_dir": str(d),
    }
    set32 = out / "SET-S32.json"
    set32.write_text(json.dumps(rec32, indent=2) + "\n")
    if args.record:
        pathlib.Path(args.record).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(set_json, pathlib.Path(args.record) / "SET-S16.json")
        shutil.copyfile(set32, pathlib.Path(args.record) / "SET-S32.json")

    lines = [f"{m['id']}\t{m['id']}.wav\t{m['seconds_written']!r}\n" for m in meta]
    manifest = "".join(lines).encode()
    (out / "manifest-device.tsv").write_bytes(manifest)
    tar_path = out / "test-clean-S16W.tar"
    packed = ids16 + [args.warmup_id]
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
        "s16": {k: rec[k] for k in ("utterances", "total_seconds", "wav_sha256_chain")},
        "warmup": rec["warmup"],
    }
    (out / f"{tar_path.name}.json").write_text(json.dumps(tar_rec, indent=2) + "\n")
    print(json.dumps({"S16": {k: rec[k] for k in ("utterances", "total_seconds", "wav_sha256_chain", "first_ids", "last_id")},
                      "S32": {k: rec32[k] for k in ("utterances", "total_seconds", "wav_sha256_chain", "first_ids", "last_id")},
                      "warmup": rec["warmup"], "full_chain": rec["full"]["wav_sha256_chain"],
                      "tar": {k: tar_rec[k] for k in ("tar_bytes", "tar_sha256", "manifest_sha256", "wavs")}}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
