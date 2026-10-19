#!/usr/bin/env bash
# The asr-sherpa-v1 set: LibriSpeech test-clean from hf-audio/open-asr-leaderboard
# (the parquet the 2026-09-25 omni-asr-wer run used), its bytes checked against the
# Hub's LFS sha256, unpacked by tools/omni-eval/prep_librispeech.py, then cut to S4
# by make_subset.py.
#
#   PY=<python with huggingface_hub pyarrow soundfile numpy> tools/asr-sherpa/fetch_set.sh
#
# Writes under .build/ (gitignored):
#   .build/omni-eval/data/librispeech/test.clean-00000-of-00001.parquet (+ PARQUET.json)
#   .build/omni-eval/sets/librispeech-test-clean/  <id>.wav, manifest.{jsonl,tsv}, SET.json,
#                                                  manifest-S4.{tsv,jsonl}, SET-S4.json
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../.." && pwd)
PY=${PY:-python3}
REPO_ID=hf-audio/open-asr-leaderboard
FILE=librispeech/test.clean-00000-of-00001.parquet
CHAIN_0925=c703709c50680769d7398f5daee2691fb6ddd81675969ff31d44bd20508b888a  # SET-test-clean.json, 2026-09-25
data=$repo/.build/omni-eval/data
set_dir=$repo/.build/omni-eval/sets/librispeech-test-clean
mkdir -p "$data"

"$PY" -I - "$REPO_ID" "$FILE" "$data" > "$data/PARQUET.json" <<'EOF'
import hashlib, json, sys
from huggingface_hub import HfApi, hf_hub_download
repo_id, filename, local_dir = sys.argv[1:4]
info = HfApi().dataset_info(repo_id, files_metadata=True)
s = next(s for s in info.siblings if s.rfilename == filename)
lfs = s.lfs if isinstance(s.lfs, dict) else vars(s.lfs)
path = hf_hub_download(repo_id, filename, repo_type="dataset", revision=info.sha, local_dir=local_dir)
h = hashlib.sha256()
with open(path, "rb") as f:
    for block in iter(lambda: f.read(1 << 20), b""):
        h.update(block)
rec = {"repo": repo_id, "revision": info.sha, "file": filename, "size": s.size,
       "hub_lfs_sha256": lfs["sha256"], "sha256": h.hexdigest()}
print(json.dumps(rec))
if rec["sha256"] != rec["hub_lfs_sha256"]:
    sys.exit(f"sha256 mismatch: {rec['sha256']} != Hub {rec['hub_lfs_sha256']}")
EOF
cat "$data/PARQUET.json"

"$PY" -I "$repo/tools/omni-eval/prep_librispeech.py" "$data/$FILE" "$set_dir"
chain=$("$PY" -I -c 'import json, sys; print(json.load(open(sys.argv[1]))["wav_sha256_chain"])' "$set_dir/SET.json")
if [ "$chain" = "$CHAIN_0925" ]; then
  echo "full chain $chain = 2026-09-25"
else
  echo "full chain $chain != 2026-09-25 ($CHAIN_0925)"
fi
"$PY" -I "$here/make_subset.py" "$set_dir" --every 4 --parquet-record "$data/PARQUET.json"
