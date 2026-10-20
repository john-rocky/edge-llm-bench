#!/usr/bin/env python3
"""Pick B's three encoder inputs (asr-npu-v1, docs/asr-npu-v1.md) out of MelDumpTest's windows of
S32's first utterance, by the rule set before the runs: the first window, the middle one
(index floor(N / 2)), and among the others the one with the largest share of 10 ms frames under
-40 dBFS (the earliest on a tie). The same window indices for the TDT and the CTC features.

  pick_windows.py --mel-all .build/asr-npu/mel-all --out .build/asr-npu/mel --record <REC>/b-inputs.json

Writes <out>/<kind>-<utt>.wNN.f32 (copies), <out>/MANIFEST (`<file> <sha256>` per line, TDT first) and
the record's b-inputs.json (per window: index, start, valid samples, quiet share, sha256 per kind).
After the three windows of each kind, <kind>-zeros.f32 (all zeros, the encoder input's size): an
observation outside the line, an input a reproduction needs no file for.
"""
import argparse
import hashlib
import json
import pathlib
import shutil
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mel-all", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--record", required=True)
    ap.add_argument("--utt", default="4507-16021-0047")
    args = ap.parse_args()
    src, out = pathlib.Path(args.mel_all), pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    meta = {k: json.loads((src / f"{k}-{args.utt}.windows.json").read_text()) for k in ("tdt", "ctc")}
    wins = meta["tdt"]["windows"]
    n = len(wins)
    if [w["valid_samples"] for w in wins] != [w["valid_samples"] for w in meta["ctc"]["windows"]]:
        raise SystemExit("the TDT and CTC dumps cut different windows")
    head, mid = 0, n // 2
    rest = [w for w in wins if w["window"] not in (head, mid)]
    quiet = max(rest, key=lambda w: (w["quiet_frame_share"], -w["window"]))["window"]
    picked = [("head", head), ("middle", mid), ("quietest", quiet)]
    lines, rec = [], {"utterance": args.utt, "windows_in_utterance": n,
                      "rule": "first window, window floor(N/2), and among the rest the largest share of 10 ms frames under -40 dBFS",
                      "all_windows": [{k: w[k] for k in ("window", "start_s", "valid_samples", "quiet_frame_share")} for w in wins],
                      "picked": []}
    for kind in ("tdt", "ctc"):
        for role, k in picked:
            w = meta[kind]["windows"][k]
            name = f"{kind}-{args.utt}.w{k:02d}.f32"
            shutil.copyfile(src / w["file"], out / name)
            sha = hashlib.sha256((out / name).read_bytes()).hexdigest()
            if sha != w["sha256"]:
                raise SystemExit(f"{name}: copy differs from the dump")
            lines.append(f"{name} {sha}\n")
            rec["picked"].append({"kind": kind, "role": role, "window": k, "start_s": w["start_s"], "file": name,
                                  "floats": w["written_floats"], "feature_floats": w["feature_floats"],
                                  "valid_samples": w["valid_samples"], "quiet_frame_share": w["quiet_frame_share"],
                                  "sha256": sha})
        # Outside the line: an all-zero input of the same size, which needs no file to reproduce.
        name = f"{kind}-zeros.f32"
        (out / name).write_bytes(bytes(4 * meta[kind]["expected_floats"]))
        sha = hashlib.sha256((out / name).read_bytes()).hexdigest()
        lines.append(f"{name} {sha}\n")
        rec["picked"].append({"kind": kind, "role": "zeros (an observation outside the line)", "window": None,
                              "file": name, "floats": meta[kind]["expected_floats"], "sha256": sha})
    (out / "MANIFEST").write_text("".join(lines))
    pathlib.Path(args.record).write_text(json.dumps(rec, indent=1) + "\n")
    print("".join(lines), end="")
    print(json.dumps({"picked": picked, "windows": n}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
