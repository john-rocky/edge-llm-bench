#!/bin/bash
# The files asr-pr-v1 needs from the Hugging Face Hub (docs/asr-pr-v1.md), each at the revision the
# earlier rounds of the lane pinned, downloaded by fetch (curl, no Python) and checked by check: the
# 30 s export and the tokenizer (asr-litert-app-v1 LOCK.json `models`) and the LibriSpeech test-clean
# parquet (asr-sherpa-v1 SET-S4.json `parquet`). check hashes the bytes and compares them with both
# the earlier record and what the Hub reports for that revision now (paths-info: the LFS sha256, or
# the git blob id for a file outside LFS), then hardlinks the model files into .build/asr-pr/models/
# and writes models.lock.json (the driver's setup reads the sha256 from it).
#
#   tools/asr-pr/stage_models.sh fetch    # network only
#   tools/asr-pr/stage_models.sh check    # hashing (keep it inside a Mac quiet window); exit 1 on a mismatch
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
B="${B:-$ROOT/.build/asr-pr}"
DL="$B/download"
# repo-type repo revision file local-dir expected-bytes expected-sha256 (the earlier record's)
FILES="model mlboydaisuke/Parakeet-TDT-0.6B-v3-LiteRT af580dff28a80150057d54bb33a0e01025ce4bce parakeet_tdt_0.6b_v3_30s_i8_stateful.tflite model30s 629689824 378935f8897f0c713ad2aa97d939c73c44e9f26546e12c1cd6af9c76f386f06a
model nvidia/parakeet-tdt-0.6b-v3 541d1f99c6b0c3cd0b11a95167540bb8edefd82b tokenizer.json tokenizer 1159960 bd321b096832a3f270bd3b2a88823957920f1a5c5ada71114a26ea729d0cbe91
dataset hf-audio/open-asr-leaderboard de79e57adf9983993bcc72586d7313460825f5eb librispeech/test.clean-00000-of-00001.parquet parquet 350475095 e576cf31312bf67d5ab714ac1dd93fb52d60d62659b76402ba1f97484464ddc3"

url_of() {  # repo-type repo revision file
  if [ "$1" = dataset ]; then echo "https://huggingface.co/datasets/$2/resolve/$3/$4"; else echo "https://huggingface.co/$2/resolve/$3/$4"; fi
}

case "${1:-}" in
  fetch)
    echo "$FILES" | while read -r type repo rev file dir bytes sha; do
      mkdir -p "$DL/$dir"
      out="$DL/$dir/${file##*/}"
      if [ -f "$out" ] && [ "$(stat -f %z "$out")" = "$bytes" ]; then echo "have $out"; continue; fi
      curl -sS -L --fail --retry 3 -o "$out" "$(url_of "$type" "$repo" "$rev" "$file")" || { echo "fetch failed: $file"; exit 1; }
      echo "fetched $out $(stat -f %z "$out") B"
    done
    ;;
  check)
    mkdir -p "$B/models"
    tmp=$(mktemp -d)
    echo "$FILES" | while read -r type repo rev file dir bytes sha; do
      api="https://huggingface.co/api/${type}s/$repo/paths-info/$rev"
      curl -sS --fail --retry 3 -X POST "$api" --data-urlencode "paths=$file" > "$tmp/${file##*/}.hub.json" || { echo "paths-info failed: $file"; exit 1; }
      out="$DL/$dir/${file##*/}"
      printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$type" "$repo" "$rev" "$file" "$out" "$bytes" "$sha" \
        "$(shasum -a 256 "$out" | cut -c1-64)" "$(git hash-object "$out")" >> "$tmp/rows.tsv"
    done || exit 1
    python3 - "$tmp" "$B/models" "$ROOT" <<'PY'
import json, os, pathlib, sys
tmp, models, root = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
rows, bad = [], 0
for line in open(tmp / "rows.tsv"):
    typ, repo, rev, file, path, want_bytes, want_sha, sha, blob = line.rstrip("\n").split("\t")
    hub = json.load(open(tmp / (os.path.basename(file) + ".hub.json")))[0]
    lfs = hub.get("lfs") or {}
    hub_hash = ("sha256:" + lfs["oid"]) if lfs.get("oid") else ("gitblob:" + hub.get("oid", ""))
    size = os.path.getsize(path)
    checks = {
        "bytes_match_record": size == int(want_bytes),
        "sha256_matches_record": sha == want_sha,
        "matches_hub_now": (lfs.get("oid") == sha) if lfs.get("oid") else (hub.get("oid") == blob),
        "hub_size_matches": (lfs.get("size") or hub.get("size")) == size,
    }
    ok = all(checks.values())
    bad += 0 if ok else 1
    rec = {"repo": repo, "repo_type": typ, "revision": rev, "file": file, "local": os.path.basename(file),
           "bytes": size, "sha256": sha, "git_blob": blob, "hub_hash": hub_hash, "checks": checks,
           "downloaded_to": str(pathlib.Path(path).relative_to(root))}
    if typ == "model":
        dst = models / os.path.basename(file)
        if dst.exists() and not os.path.samefile(path, dst):
            dst.unlink()
        if not dst.exists():
            os.link(path, dst)
        rec["staged_as"] = str(dst.relative_to(root))
    rows.append(rec)
    print(f"[stage] {'ok ' if ok else 'BAD'} {file} {size} B sha256 {sha[:16]}… hub {hub_hash[:24]}… {'' if ok else checks}")
(models / "models.lock.json").write_text(json.dumps([r for r in rows if r["repo_type"] == "model"], indent=1) + "\n")
(models.parent / "download" / "PARQUET.json").write_text(json.dumps([r for r in rows if r["repo_type"] == "dataset"][0], indent=1) + "\n")
print(f"[stage] {len(rows)} files checked -> {models / 'models.lock.json'}, download/PARQUET.json")
sys.exit(1 if bad else 0)
PY
    rc=$?
    rm -rf "$tmp"
    exit $rc
    ;;
  *) sed -n 2,13p "$0"; exit 2 ;;
esac
