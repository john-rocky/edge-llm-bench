#!/bin/bash
# The files of the asr-sigbuf-v1 checks (docs/asr-sigbuf-v1.md) at pinned Hub revisions, into
# .build/asr-sigbuf/models/ (models) and .build/asr-sigbuf/data/ (the LibriSpeech test-clean parquet),
# each checked against the Hub's own hash: the LFS sha256 for LFS files, the git blob id for
# tokenizer.json (not an LFS file). asr-npu-v1's stage_models.sh with this round's files.
#
#   tools/asr-sigbuf/stage_models.sh fetch     # download what is missing (network only, no hashing)
#   tools/asr-sigbuf/stage_models.sh verify    # hash every file, compare with the Hub, write models.lock.json
#   DRY=1 tools/asr-sigbuf/stage_models.sh fetch
#
# verify reads about 5.3 GB: run it inside a Mac measurement window (quiet_hold.py).
# Exit: 0 = done / all verified; 1 = a download failed, the Hub's hash differs from the pin here, or
# a file's bytes differ (the file is renamed *.bad).
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${OUT:-$ROOT/.build/asr-sigbuf}"
DRY="${DRY:-0}"
MODE="${1:-}"
mkdir -p "$OUT/models" "$OUT/data"

# kind  repo  revision  file-in-repo  local path under $OUT  expected (Hub LFS sha256 or git blob id)
# The app's entries (model_metadata.json at litert-samples 367816da): parakeet-tdt-0.6b-v3 = the 5 s i8
# stateful file on the CPU / GPU and the stateful SM8850 file on the NPU; parakeet-tdt_ctc-0.6b-ja = its
# 5 s i8 file and tokenizer. The 5 s f32 stateful file is the CPU side of the decoder-only NPU check.
FILES=(
  "models nvidia/parakeet-tdt-0.6b-v3 541d1f99c6b0c3cd0b11a95167540bb8edefd82b tokenizer.json models/tdt-tokenizer.json gitblob:a10a554cf61e38108756650018d5781ae9675c1d"
  "models litert-community/parakeet-tdt_ctc-0.6b-ja 1a2b23becb829520b8d7eda2833f26b14e5fcd32 tokenizer.json models/ja-tokenizer.json gitblob:088d599cbfe051e4d9acd45513dca08d75b8151b"
  "datasets hf-audio/open-asr-leaderboard de79e57adf9983993bcc72586d7313460825f5eb librispeech/test.clean-00000-of-00001.parquet data/test.clean-00000-of-00001.parquet sha256:e576cf31312bf67d5ab714ac1dd93fb52d60d62659b76402ba1f97484464ddc3"
  "models litert-community/parakeet-tdt-0.6b-v3 3ce205aa928f443f423214195cfe83ebe4802826 parakeet_tdt_0.6b_v3_5s_i8_stateful.tflite models/parakeet_tdt_0.6b_v3_5s_i8_stateful.tflite sha256:334745b8bc7fd372b1c213516f0b6338bb827b1a2abb3e77ad35fe6fea5cd16b"
  "models litert-community/parakeet-tdt_ctc-0.6b-ja 1a2b23becb829520b8d7eda2833f26b14e5fcd32 parakeet_tdt_ctc_0.6b_ja_5s_i8.tflite models/parakeet_tdt_ctc_0.6b_ja_5s_i8.tflite sha256:6ab11f31e97f21b8bc5454be6ed59c66413ce7329ba14f9fd2930398587229c8"
  "models litert-community/parakeet-tdt-0.6b-v3 3ce205aa928f443f423214195cfe83ebe4802826 parakeet_tdt_0.6b_v3_5s_f32_stateful_Qualcomm_SM8850.tflite models/parakeet_tdt_0.6b_v3_5s_f32_stateful_Qualcomm_SM8850.tflite sha256:e9edabe48ffd853ddebac6c83804752edf0e1e567b26954aae0d3e964f72a486"
  "models litert-community/parakeet-tdt-0.6b-v3 3ce205aa928f443f423214195cfe83ebe4802826 parakeet_tdt_0.6b_v3_5s_f32_stateful.tflite models/parakeet_tdt_0.6b_v3_5s_f32_stateful.tflite sha256:8c1f06a9e1682ab2f4d95f65d413055c8f83d64a7b3daab3185b5e0e91e9f4ab"
)

hub_hash() {  # kind repo rev path -> "<sha256:…|gitblob:…> <size>" from the Hub's tree API
  local dir="/${4%/*}"
  [ "$dir" = "/$4" ] && dir=""
  curl -fsS "https://huggingface.co/api/$1/$2/tree/$3$dir" | python3 -c '
import json, sys
path = sys.argv[1]
for e in json.load(sys.stdin):
    if e.get("path") == path:
        lfs = e.get("lfs") or {}
        print(("sha256:" + lfs["oid"]) if lfs.get("oid") else ("gitblob:" + e["oid"]), e.get("size"))
        break
' "$4"
}

local_hash() {  # kind file
  case "$1" in
    sha256) echo "sha256:$(shasum -a 256 "$2" | awk '{print $1}')" ;;
    gitblob) echo "gitblob:$(git hash-object "$2")" ;;
  esac
}

url_of() {  # kind repo rev path
  case "$1" in
    datasets) echo "https://huggingface.co/datasets/$2/resolve/$3/$4" ;;
    *) echo "https://huggingface.co/$2/resolve/$3/$4" ;;
  esac
}

rc=0
case "$MODE" in
  fetch)
    for row in "${FILES[@]}"; do
      read -r kind repo rev path name want <<<"$row"
      read -r hub size <<<"$(hub_hash "$kind" "$repo" "$rev" "$path")"
      if [ "$hub" != "$want" ]; then
        echo "[stage] $repo@${rev:0:8} $path: the Hub says ${hub:-nothing}, this script expects $want" >&2; rc=1; continue
      fi
      dest="$OUT/$name"
      if [ -f "$dest" ] && [ "$(stat -f %z "$dest")" = "$size" ]; then
        echo "[stage] have $name ($size B; bytes checked by verify)"
      elif [ "$DRY" = 1 ]; then
        echo "[stage] DRY would fetch $(url_of "$kind" "$repo" "$rev" "$path") -> $dest ($size B)"
      else
        echo "[stage] fetch $repo@${rev:0:8} $path ($size B) $(date +%T)"
        if ! curl -fL --retry 3 -sS -o "$dest.part" "$(url_of "$kind" "$repo" "$rev" "$path")"; then
          echo "[stage] download failed: $path" >&2; rm -f "$dest.part"; rc=1; continue
        fi
        [ "$(stat -f %z "$dest.part")" = "$size" ] || { echo "[stage] size differs: $path" >&2; mv "$dest.part" "$dest.bad"; rc=1; continue; }
        mv "$dest.part" "$dest"
        echo "[stage] got $name $(date +%T)"
      fi
    done
    echo "[stage] FETCH END rc=$rc $(date +%T)"
    ;;
  verify)
    rows=()
    for row in "${FILES[@]}"; do
      read -r kind repo rev path name want <<<"$row"
      dest="$OUT/$name"
      [ -f "$dest" ] || { echo "[stage] MISSING $name" >&2; rc=1; continue; }
      hk="${want%%:*}"
      got="$(local_hash "$hk" "$dest")"
      if [ "$got" != "$want" ]; then
        echo "[stage] HASH MISMATCH $name: got $got want $want (kept as $dest.bad)" >&2; mv "$dest" "$dest.bad"; rc=1; continue
      fi
      sha=$(if [ "$hk" = sha256 ]; then echo "${got#sha256:}"; else shasum -a 256 "$dest" | awk '{print $1}'; fi)
      echo "[stage] ok $name $(stat -f %z "$dest") B sha256 ${sha:0:16}…"
      rows+=("{\"repo\": \"$repo\", \"repo_type\": \"$kind\", \"revision\": \"$rev\", \"file\": \"$path\", \"local\": \"$name\", \"bytes\": $(stat -f %z "$dest"), \"sha256\": \"$sha\", \"hub_hash\": \"$want\"}")
    done
    if [ $rc = 0 ]; then
      { echo "["; for i in "${!rows[@]}"; do sep=","; [ "$i" -eq $((${#rows[@]} - 1)) ] && sep=""; echo "  ${rows[$i]}$sep"; done; echo "]"; } > "$OUT/models/models.lock.json"
      echo "[stage] verified ${#rows[@]} files -> $OUT/models/models.lock.json"
    fi
    ;;
  *) sed -n 2,13p "$0"; exit 2 ;;
esac
exit $rc
