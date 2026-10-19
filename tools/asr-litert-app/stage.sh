#!/bin/bash
# Download the four model files the LiteRT ASR app arms use (L1–L5, docs/asr-litert-app-v1.md) into
# .build/asr-litert-app/models/ at pinned Hub revisions, and check each file's bytes against the Hub:
# the LFS sha256 for the .tflite files, the git blob id for tokenizer.json (it is not an LFS file).
# A file already there with the right hash is kept (no download). Writes models.lock.json beside the
# files (repo, revision, file, bytes, sha256, the Hub's hash) — run_app_s26.sh and LOCK.json read it.
#
#   tools/asr-litert-app/stage.sh            # download what is missing, verify all
#   DRY=1 tools/asr-litert-app/stage.sh      # print what would be fetched, touch nothing
#
# Exit: 0 = all four verified; 1 = a download failed or a hash differs (the bad file is left as *.bad).
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${OUT:-$ROOT/.build/asr-litert-app/models}"
DRY="${DRY:-0}"
mkdir -p "$OUT"

# repo  revision  file-in-repo  local-name  expected (Hub LFS sha256, or git blob id for a non-LFS file)
FILES=(
  "litert-community/parakeet-tdt-0.6b-v3 3ce205aa928f443f423214195cfe83ebe4802826 parakeet_tdt_0.6b_v3_5s_i8_stateful.tflite parakeet_tdt_0.6b_v3_5s_i8_stateful.tflite sha256:334745b8bc7fd372b1c213516f0b6338bb827b1a2abb3e77ad35fe6fea5cd16b"
  "litert-community/parakeet-tdt-0.6b-v3 3ce205aa928f443f423214195cfe83ebe4802826 parakeet_tdt_0.6b_v3_5s_f32_stateful_Qualcomm_SM8850.tflite parakeet_tdt_0.6b_v3_5s_f32_stateful_Qualcomm_SM8850.tflite sha256:e9edabe48ffd853ddebac6c83804752edf0e1e567b26954aae0d3e964f72a486"
  "mlboydaisuke/Parakeet-TDT-0.6B-v3-LiteRT af580dff28a80150057d54bb33a0e01025ce4bce parakeet_tdt_0.6b_v3_30s_i8_stateful.tflite parakeet_tdt_0.6b_v3_30s_i8_stateful.tflite sha256:378935f8897f0c713ad2aa97d939c73c44e9f26546e12c1cd6af9c76f386f06a"
  "nvidia/parakeet-tdt-0.6b-v3 541d1f99c6b0c3cd0b11a95167540bb8edefd82b tokenizer.json tokenizer.json gitblob:a10a554cf61e38108756650018d5781ae9675c1d"
)

# The Hub's own hash for one file at one revision (tree API): lfs.oid for LFS files, oid otherwise.
hub_hash() {  # repo rev path
  curl -fsS "https://huggingface.co/api/models/$1/tree/$2" | python3 -c '
import json, sys
path = sys.argv[1]
for e in json.load(sys.stdin):
    if e.get("path") == path:
        lfs = e.get("lfs") or {}
        print(("sha256:" + lfs["oid"]) if lfs.get("oid") else ("gitblob:" + e["oid"]), e.get("size"))
        break
' "$3"
}

local_hash() {  # kind file
  case "$1" in
    sha256) echo "sha256:$(shasum -a 256 "$2" | awk '{print $1}')" ;;
    gitblob) echo "gitblob:$(git hash-object "$2")" ;;
  esac
}

rc=0
rows=()
for row in "${FILES[@]}"; do
  read -r repo rev path name want <<<"$row"
  kind="${want%%:*}"
  read -r hub size <<<"$(hub_hash "$repo" "$rev" "$path")"
  if [ "$hub" != "$want" ]; then
    echo "[stage] $repo@${rev:0:8} $path: the Hub says $hub, this script expects $want" >&2; rc=1; continue
  fi
  dest="$OUT/$name"
  if [ -f "$dest" ] && [ "$(local_hash "$kind" "$dest")" = "$want" ]; then
    echo "[stage] have $name ($size B, ${want:0:20}…)"
  elif [ "$DRY" = 1 ]; then
    echo "[stage] DRY would fetch https://huggingface.co/$repo/resolve/$rev/$path -> $dest ($size B)"
    continue
  else
    echo "[stage] fetch $repo@${rev:0:8} $path ($size B)"
    if ! curl -fL --retry 3 -sS -o "$dest.part" "https://huggingface.co/$repo/resolve/$rev/$path"; then
      echo "[stage] download failed: $path" >&2; rm -f "$dest.part"; rc=1; continue
    fi
    got="$(local_hash "$kind" "$dest.part")"
    if [ "$got" != "$want" ]; then
      echo "[stage] HASH MISMATCH $name: got $got want $want (kept as $dest.bad)" >&2; mv "$dest.part" "$dest.bad"; rc=1; continue
    fi
    mv "$dest.part" "$dest"
  fi
  bytes=$(stat -f %z "$dest")
  sha=$(shasum -a 256 "$dest" | awk '{print $1}')
  rows+=("{\"repo\": \"$repo\", \"revision\": \"$rev\", \"file\": \"$path\", \"local\": \"$name\", \"bytes\": $bytes, \"sha256\": \"$sha\", \"hub_hash\": \"$want\"}")
done
if [ "$DRY" != 1 ] && [ $rc = 0 ]; then
  { echo "["; for i in "${!rows[@]}"; do sep=","; [ "$i" -eq $((${#rows[@]} - 1)) ] && sep=""; echo "  ${rows[$i]}$sep"; done; echo "]"; } > "$OUT/models.lock.json"
  echo "[stage] verified ${#rows[@]} files -> $OUT/models.lock.json"
fi
exit $rc
