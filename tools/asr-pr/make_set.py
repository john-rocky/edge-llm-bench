#!/usr/bin/env python3
"""Cut S32 and the warm-up utterance W out of a prep_librispeech.py set, add the two edge inputs and
pack them for the phone (asr-pr-v1, docs/asr-pr-v1.md; asr-fix-v1's make_set.py cut to S32). Reads
the set; writes only under <out_dir> (and --record).

S32 = the rows of <set>/manifest.tsv at index 0, 32, 64, ... in the file's order (= the parquet's row
order, longest first): 82 of LibriSpeech test-clean's 2620 (asr-burst-v1 / asr-fix-v1's burst set).
W = the row with --warmup-id (default 1995-1836-0004 = row 1, outside S32), transcribed once per
process outside the timing.
The edge inputs (not LibriSpeech rows, no reference text): silence-2s = 32,000 zero samples (2 s);
clip-0p8s = W's first 12,800 samples (0.8 s), a clip shorter than a second.

Writes:
  <out>/manifest-S32.tsv, manifest-S32.jsonl    the S32 rows in order (score.py's --manifest)
  <out>/SET-S32.json                            utterances, total_seconds, wav_sha256_chain over the
                                                set's WAVs in order (make_subset.py's computation), W,
                                                and the full set recomputed from the WAVs
  <out>/silence-2s.wav, clip-0p8s.wav           16 kHz mono PCM16
  <out>/manifest-device.tsv                     every row of the set, `id<TAB><id>.wav<TAB>seconds`
                                                (seconds = seconds_written), as asr-litert-app-v1's
  <out>/manifest-edge.tsv                       silence-2s, clip-0p8s, then W (the test takes the first
                                                two with limit=2 and finds W by id)
  <out>/SET-edge.json                           the edge WAVs' sha256 and how they were made
  <out>/test-clean-S32WE.tar (+ .tar.json)      the two manifests + the 82 S32 WAVs + W + the edge WAVs

Usage: make_set.py <set_dir> <out_dir> [--warmup-id ID] [--record <dir for copies of SET-S32.json / SET-edge.json>]
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

EVERY = 32
S32_CHAIN = "6ccb9d3c271b966a7c7cdaa02417b360a1319a858542fab92dc8407e3332f8f4"  # asr-fix-v1 SET-S32.json
FULL_CHAIN = "c703709c50680769d7398f5daee2691fb6ddd81675969ff31d44bd20508b888a"  # 2026-09-25 SET-test-clean.json
CLIP_SAMPLES = 12_800


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


def write_wav(path, frames):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(frames)


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
    sel = rows[::EVERY]
    ids = [i for i, _ in sel]
    w_index = next((n for n, (i, _) in enumerate(rows) if i == args.warmup_id), None)
    if w_index is None:
        raise SystemExit(f"warm-up id {args.warmup_id} is not in the set")
    if args.warmup_id in set(ids):
        raise SystemExit(f"warm-up id {args.warmup_id} is inside S32")
    w_path = pathlib.Path(dict(rows)[args.warmup_id])
    full = chain([p for _, p in rows])
    warmup = {"id": args.warmup_id, "row_index": w_index, "seconds": wav_seconds(w_path),
              "wav_sha256": sha256_file(w_path), "in_s32": False}

    with open(out / "manifest-S32.tsv", "w") as f:
        for i, p in sel:
            f.write(f"{i}\t{p}\n")
    with open(out / "manifest-S32.jsonl", "w") as f:
        for i in ids:
            f.write(json.dumps(by_id[i], ensure_ascii=False) + "\n")
    s32 = {
        "set": "librispeech-test-clean-S32",
        "rule": f"manifest.tsv rows at index 0, {EVERY}, {2 * EVERY}, ... (every {EVERY}th row from the first, file order)",
        **chain([p for _, p in sel]),
        "first_ids": ids[:3],
        "last_id": ids[-1],
        "warmup": warmup,
        "full": full,
        "source_set_dir": str(d),
        "matches_asr_fix_v1": None,
    }
    s32["matches_asr_fix_v1"] = s32["wav_sha256_chain"] == S32_CHAIN and full["wav_sha256_chain"] == FULL_CHAIN
    (out / "SET-S32.json").write_text(json.dumps(s32, indent=2) + "\n")

    # The edge inputs.
    write_wav(out / "silence-2s.wav", bytes(2 * 32_000))
    with wave.open(str(w_path), "rb") as w:
        clip = w.readframes(CLIP_SAMPLES)
    write_wav(out / "clip-0p8s.wav", clip)
    last_nonzero = max((k for k in range(CLIP_SAMPLES) if clip[2 * k:2 * k + 2] != b"\0\0"), default=-1)
    edge = {
        "set": "edge2",
        "rows": [
            {"id": "silence-2s", "wav": "silence-2s.wav", "seconds": 2.0, "made": "32,000 zero samples (16 kHz mono PCM16)",
             "wav_sha256": sha256_file(out / "silence-2s.wav"), "last_nonzero_sample": -1},
            {"id": "clip-0p8s", "wav": "clip-0p8s.wav", "seconds": CLIP_SAMPLES / 16000,
             "made": f"the first {CLIP_SAMPLES} samples of {args.warmup_id}.wav (W)",
             "wav_sha256": sha256_file(out / "clip-0p8s.wav"), "last_nonzero_sample": last_nonzero},
        ],
        "warmup": warmup,
    }
    (out / "SET-edge.json").write_text(json.dumps(edge, indent=2) + "\n")
    if args.record:
        pathlib.Path(args.record).mkdir(parents=True, exist_ok=True)
        for name in ("SET-S32.json", "SET-edge.json"):
            shutil.copyfile(out / name, pathlib.Path(args.record) / name)

    device = "".join(f"{m['id']}\t{m['id']}.wav\t{m['seconds_written']!r}\n" for m in meta).encode()
    (out / "manifest-device.tsv").write_bytes(device)
    edge_manifest = (f"silence-2s\tsilence-2s.wav\t2.0\nclip-0p8s\tclip-0p8s.wav\t{CLIP_SAMPLES / 16000!r}\n"
                     f"{args.warmup_id}\t{args.warmup_id}.wav\t{by_id[args.warmup_id]['seconds_written']!r}\n").encode()
    (out / "manifest-edge.tsv").write_bytes(edge_manifest)
    tar_path = out / "test-clean-S32WE.tar"
    wavs = [d / f"{i}.wav" for i in ids + [args.warmup_id]] + [out / "silence-2s.wav", out / "clip-0p8s.wav"]
    with tarfile.open(tar_path, "w", format=tarfile.USTAR_FORMAT) as tar:
        for name, data in (("manifest-device.tsv", device), ("manifest-edge.tsv", edge_manifest)):
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(data), 0o644, 0
            tar.addfile(info, io.BytesIO(data))
        for wav in wavs:
            info = tarfile.TarInfo(wav.name)
            info.size, info.mode, info.mtime = wav.stat().st_size, 0o644, 0
            with open(wav, "rb") as f:
                tar.addfile(info, f)
    tar_rec = {
        "tar": tar_path.name,
        "tar_bytes": tar_path.stat().st_size,
        "tar_sha256": sha256_file(tar_path),
        "manifests": {"manifest-device.tsv": hashlib.sha256(device).hexdigest(),
                      "manifest-edge.tsv": hashlib.sha256(edge_manifest).hexdigest()},
        "manifest_rows": len(meta),
        "wavs": len(wavs),
        "s32": {k: s32[k] for k in ("utterances", "total_seconds", "wav_sha256_chain")},
        "warmup": warmup,
        "edge": [{k: r[k] for k in ("id", "wav_sha256")} for r in edge["rows"]],
    }
    (out / f"{tar_path.name}.json").write_text(json.dumps(tar_rec, indent=2) + "\n")
    print(json.dumps({"S32": {k: s32[k] for k in ("utterances", "total_seconds", "wav_sha256_chain", "first_ids", "last_id",
                                                  "matches_asr_fix_v1")},
                      "full_chain": full["wav_sha256_chain"], "warmup": warmup, "edge": edge["rows"],
                      "tar": {k: tar_rec[k] for k in ("tar_bytes", "tar_sha256", "wavs")}}, indent=2))
    return 0 if s32["matches_asr_fix_v1"] else 1


if __name__ == "__main__":
    sys.exit(main())
