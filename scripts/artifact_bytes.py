#!/usr/bin/env python3
"""Maintain models/artifact-bytes.json — the byte size of the artifact each arm
loads for each dashboard model id, with its source. Feeds the "bw util" column
(scripts/bench_common.py bandwidth_utilization): decode tok/s x artifact bytes /
the device's memory-bandwidth ceiling (devices/memory-bandwidth.json).

  python3 scripts/artifact_bytes.py                 # print the registry as a table
  python3 scripts/artifact_bytes.py --refresh       # re-read every size from its source
  python3 scripts/artifact_bytes.py --check         # exit 1 if a source disagrees with the file

Each entry names the arm (the device-runs.csv runtime string, so Android
LiteRT is litert-lm-cpu / litert-lm-gpu), the model id as the records carry it,
the files that make up the artifact, and where the size comes from:

  source "hf:<repo>"     sizes from the Hub API (GET /api/models/<repo>?blobs=true)
                         at `revision` (pinned on the first refresh, so a later
                         re-upload shows as a --check disagreement, not a silent
                         change); `files` are exact paths in the repo
  source "local:<path>"  a side-loaded bundle (Core AI): the size of the weight
                         file(s) under that path, plus the bundle's main.hash so
                         the entry names one export, not a folder name

`bytes` is the sum over `files`. Vision towers and tokenizers are excluded where
they are separate files (the MLX Gemma-4 optiq_vision.safetensors); a .litertlm
or .gguf is one file and counts whole — the column is a proxy, and the
one-pager says so. Stdlib only; no network without --refresh/--check.
"""
import argparse
import datetime
import fnmatch
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join(ROOT, "models", "artifact-bytes.json")


def hf_sizes(repo, revision=None):
    """-> (sha, {rfilename: size}) from the Hub API."""
    url = f"https://huggingface.co/api/models/{repo}?blobs=true"
    if revision:
        url = f"https://huggingface.co/api/models/{repo}/revision/{revision}?blobs=true"
    req = urllib.request.Request(url, headers={"User-Agent": "edge-llm-bench/artifact_bytes"})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.load(r)
    return d.get("sha"), {s["rfilename"]: s.get("size") for s in d.get("siblings", [])}


def local_sizes(path, files):
    """-> (main_hash_hex or None, {file: size}) for a side-loaded bundle."""
    out = {}
    for f in files:
        p = os.path.realpath(os.path.join(os.path.expanduser(path), f))
        out[f] = os.path.getsize(p) if os.path.exists(p) else None
    h = None
    for f in files:
        hp = os.path.join(os.path.expanduser(path), os.path.dirname(f), "main.hash")
        if os.path.exists(hp):
            h = open(hp, "rb").read().hex()
            break
    return h, out


def select(names, files, exclude=()):
    """Repo paths matched by the entry's `files` (exact names or globs) minus
    `exclude` globs, in repo order. Every pattern must match at least once."""
    out = []
    for pat in files:
        hits = [n for n in names if fnmatch.fnmatchcase(n, pat)] if any(c in pat for c in "*?[") \
            else [n for n in names if n == pat]
        if not hits:
            raise RuntimeError(f"pattern {pat!r} matches nothing")
        out += [h for h in hits if h not in out]
    return [n for n in out if not any(fnmatch.fnmatchcase(n, x) for x in exclude)]


def resolve(entry):
    """-> (bytes, detail dict) for one entry, reading its source."""
    src = entry["source"]
    if src.startswith("hf:"):
        repo = src[3:]
        sha, sizes = hf_sizes(repo, entry.get("revision"))
        chosen = select(sizes, entry["files"], entry.get("exclude", ()))
        missing = [f for f in chosen if sizes.get(f) is None]
        if missing:
            raise RuntimeError(f"{repo}: no size for {missing} at {entry.get('revision') or 'main'}")
        return sum(sizes[f] for f in chosen), {"revision": sha, "resolved_files": chosen}
    if src.startswith("local:"):
        h, sizes = local_sizes(src[6:], entry["files"])
        missing = [f for f, s in sizes.items() if s is None]
        if missing:
            raise RuntimeError(f"{src}: missing {missing}")
        return sum(sizes.values()), {"main_hash": h}
    raise RuntimeError(f"unknown source {src!r}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    reg = json.load(open(REGISTRY))
    today = datetime.date.today().isoformat()
    rc = 0
    for e in reg["artifacts"]:
        if args.refresh or args.check:
            try:
                n, detail = resolve(e)
            except Exception as ex:  # network, missing file — say which entry
                print(f"ERROR {e['arm']} {e['model_id']}: {ex}", file=sys.stderr)
                rc = 1
                continue
            if args.check:
                if n != e.get("bytes"):
                    print(f"DIFF {e['arm']} {e['model_id']}: registry {e.get('bytes')} vs source {n}")
                    rc = 1
                for k, v in detail.items():
                    if v and e.get(k) and v != e.get(k):
                        print(f"DIFF {e['arm']} {e['model_id']}: {k} registry {e.get(k)} vs source {v}")
                        rc = 1
            else:
                e["bytes"] = n
                e["checked"] = today
                for k, v in detail.items():
                    if v:
                        e[k] = v
        b = e.get("bytes")
        print(f"{e['arm']:<14} {e.get('platform') or '*':<8} {e['model_id']:<52} "
              f"{(b / 1e6) if b else 0:>9.1f} MB  {e['source']}")
    if args.refresh:
        with open(REGISTRY, "w") as fh:
            json.dump(reg, fh, indent=1, ensure_ascii=False)
            fh.write("\n")
        print(f"wrote {os.path.relpath(REGISTRY, ROOT)}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
