#!/bin/bash
# The two files of arm B-L6 (parakeet-ctc-0.6b on the NPU, the app's own `parakeet-ctc-0.6b` entry) at
# pinned Hub revisions into .build/asr-burst/download-ctc/, checked against the Hub: the LFS sha256 for
# the .tflite, the git blob id for tokenizer.json (not an LFS file). Writes ctc.lock.json beside them;
# stage_models.sh links them into .build/asr-burst/models/ with those hashes.
#
#   tools/asr-burst/fetch_ctc.sh fetch     # download what is missing (network only; sizes checked)
#   tools/asr-burst/fetch_ctc.sh verify    # hash the bytes (1.2 GB: keep it out of a Mac measurement window)
#
# Exit: 0 = done; 1 = a download failed, a size or a hash differs, or the Hub says otherwise.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${OUT:-$ROOT/.build/asr-burst/download-ctc}"
mkdir -p "$OUT"

# repo  revision  file-in-repo  local-name  expected (Hub LFS sha256, or git blob id)  bytes
FILES=(
  "litert-community/parakeet-ctc-0.6b e3c5b655c0159f79bc90be2d6769fa7cc6386856 parakeet_ctc_0.6b_5s_f32_Qualcomm_SM8850.tflite parakeet_ctc_0.6b_5s_f32_Qualcomm_SM8850.tflite sha256:30e431db44f40f7de869776ad37869e0e3847a30717232b3667e9ce4688352fb 1210738160"
  "nvidia/parakeet-ctc-0.6b ad09ba1cc62743fbc9814de5d2016fca9096485a tokenizer.json tokenizer-ctc.json gitblob:80af47728aab88c918efe5ce9fa5e2d2ceec7511 412363"
)

hub_hash() {  # repo rev path -> "<kind>:<hash> <size>" from the Hub's tree API
  curl -fsS "https://huggingface.co/api/models/$1/tree/$2" | python3 -c '
import json, sys
for e in json.load(sys.stdin):
    if e.get("path") == sys.argv[1]:
        lfs = e.get("lfs") or {}
        print(("sha256:" + lfs["oid"]) if lfs.get("oid") else ("gitblob:" + e["oid"]), e.get("size"))
        break' "$3"
}

rc=0
case "${1:-}" in
  fetch)
    for row in "${FILES[@]}"; do
      read -r repo rev path name want bytes <<<"$row"
      read -r hub size <<<"$(hub_hash "$repo" "$rev" "$path")"
      if [ "$hub" != "$want" ] || [ "$size" != "$bytes" ]; then
        echo "[ctc] $repo@${rev:0:8} $path: the Hub says $hub $size, expected $want $bytes" >&2; rc=1; continue
      fi
      dest="$OUT/$name"
      if [ -f "$dest" ] && [ "$(stat -f %z "$dest")" = "$bytes" ]; then echo "[ctc] have $name ($bytes B)"; continue; fi
      echo "[ctc] fetch $repo@${rev:0:8} $path ($bytes B)"
      if ! curl -fL --retry 3 -sS -o "$dest.part" "https://huggingface.co/$repo/resolve/$rev/$path"; then
        echo "[ctc] download failed: $path" >&2; rm -f "$dest.part"; rc=1; continue
      fi
      [ "$(stat -f %z "$dest.part")" = "$bytes" ] || { echo "[ctc] size differs: $name" >&2; mv "$dest.part" "$dest.bad"; rc=1; continue; }
      mv "$dest.part" "$dest"
      echo "[ctc] got $name"
    done ;;
  verify)
    rows=()
    for row in "${FILES[@]}"; do
      read -r repo rev path name want bytes <<<"$row"
      dest="$OUT/$name"
      case "$want" in
        sha256:*) got="sha256:$(shasum -a 256 "$dest" | cut -c1-64)" ;;
        gitblob:*) got="gitblob:$(git hash-object "$dest")" ;;
      esac
      sha=$( [ "${want%%:*}" = sha256 ] && echo "${got#sha256:}" || shasum -a 256 "$dest" | cut -c1-64)
      if [ "$got" != "$want" ]; then echo "[ctc] HASH MISMATCH $name: $got, the Hub $want" >&2; rc=1; continue; fi
      echo "[ctc] ok $name $got"
      rows+=("{\"repo\": \"$repo\", \"revision\": \"$rev\", \"file\": \"$path\", \"local\": \"$name\", \"bytes\": $(stat -f %z "$dest"), \"sha256\": \"$sha\", \"hub_hash\": \"$want\"}")
    done
    if [ $rc = 0 ]; then
      { echo "["; for i in "${!rows[@]}"; do sep=","; [ "$i" -eq $((${#rows[@]} - 1)) ] && sep=""; echo "  ${rows[$i]}$sep"; done; echo "]"; } > "$OUT/ctc.lock.json"
      echo "[ctc] verified ${#rows[@]} files -> $OUT/ctc.lock.json"
    fi ;;
  *) sed -n 2,10p "$0"; exit 2 ;;
esac
exit $rc
