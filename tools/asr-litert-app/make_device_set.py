#!/usr/bin/env python3
"""Pack a prep_librispeech.py set for the phone (asr-litert-app-v1).

Writes <out>/<name>.tar holding every WAV of the set plus manifest-device.tsv, the manifest the
instrumented test reads: one line per utterance in the set's order, `id<TAB><id>.wav<TAB>seconds`
(seconds = manifest.jsonl's seconds_written). The test applies the S4 rule itself (every=4: rows
0, 4, 8, ...), so the full set goes to the phone once and S4 / full / smoke runs share it.
Also writes <out>/<name>.tar.json: the tar's sha256 and size, the row count, total seconds and the
WAV chain of the full set and of S4 (the computation of SET.json / SET-S4.json).

Usage: make_device_set.py <set_dir> <out_dir> [--name test-clean]
"""
import argparse
import hashlib
import io
import json
import pathlib
import sys
import tarfile


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("set_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--name", default="test-clean")
    args = ap.parse_args()

    d = pathlib.Path(args.set_dir)
    rows = [json.loads(line) for line in open(d / "manifest.jsonl") if line.strip()]
    ids_tsv = [line.split("\t")[0] for line in open(d / "manifest.tsv") if line.strip()]
    if [r["id"] for r in rows] != ids_tsv:
        raise SystemExit("manifest.jsonl and manifest.tsv disagree on ids or order")

    lines, chain, chain_s4, total, total_s4 = [], hashlib.sha256(), hashlib.sha256(), 0.0, 0.0
    for i, r in enumerate(rows):
        wav = d / f"{r['id']}.wav"
        data = wav.read_bytes()
        chain.update(data)
        total += r["seconds_written"]
        if i % 4 == 0:
            chain_s4.update(data)
            total_s4 += r["seconds_written"]
        lines.append(f"{r['id']}\t{r['id']}.wav\t{r['seconds_written']!r}\n")

    out = pathlib.Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tar_path = out / f"{args.name}.tar"
    manifest = "".join(lines).encode()
    (out / "manifest-device.tsv").write_bytes(manifest)  # the driver's copy (resume after a crash)
    with tarfile.open(tar_path, "w", format=tarfile.USTAR_FORMAT) as tar:
        info = tarfile.TarInfo("manifest-device.tsv")
        info.size, info.mode, info.mtime = len(manifest), 0o644, 0
        tar.addfile(info, io.BytesIO(manifest))
        for r in rows:
            wav = d / f"{r['id']}.wav"
            info = tarfile.TarInfo(wav.name)
            info.size, info.mode, info.mtime = wav.stat().st_size, 0o644, 0
            with open(wav, "rb") as f:
                tar.addfile(info, f)

    sha = hashlib.sha256()
    with open(tar_path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            sha.update(block)
    rec = {
        "tar": tar_path.name,
        "tar_bytes": tar_path.stat().st_size,
        "tar_sha256": sha.hexdigest(),
        "manifest": "manifest-device.tsv",
        "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
        "utterances": len(rows),
        "total_seconds": total,
        "wav_sha256_chain": chain.hexdigest(),
        "s4": {
            "utterances": (len(rows) + 3) // 4,
            "total_seconds": total_s4,
            "wav_sha256_chain": chain_s4.hexdigest(),
        },
    }
    (out / f"{args.name}.tar.json").write_text(json.dumps(rec, indent=2) + "\n")
    print(json.dumps(rec, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
