#!/bin/bash
# Put the ten model files of the asr-burst-v1 arms (docs/asr-burst-v1.md) into .build/asr-burst/models/
# as hardlinks of the copies the lane's earlier rounds downloaded and verified (nothing is downloaded,
# the sources are only read), and write models.lock.json with each file's expected sha256 from the
# record of that round:
#   LiteRT (B-L1..B-L5): ../edge-llm-bench-wt-asr-litert/.build/asr-litert-app/models/ + models.lock.json
#     (bytes hashed there = the Hub's LFS sha256 / git blob id, asr-litert-app-v1 stage.sh)
#   sherpa-onnx (B-A1): the k2-fsa model tar unpacked by asr-sherpa-v1 fetch.sh, files listed with their
#     sha256 in ../edge-llm-bench-wt-asr-sherpa/.build/sherpa-onnx/LOCK.json (model_files)
#   parakeet-ctc-0.6b (B-L6): this round's fetch_ctc.sh download + ctc.lock.json (Hub LFS sha256 / git blob id)
# A link is the source's own inode: the check here is that the size matches the record and the file
# was not modified after the record was written; HASH=1 also hashes every file (a few GB: keep it out
# of a Mac measurement window). The phone checks the pushed bytes against the expected sha256 (setup).
#
#   tools/asr-burst/stage_models.sh          # link and check; exit 1 on a missing file or a mismatch
#   HASH=1 tools/asr-burst/stage_models.sh   # the same, plus sha256 of the bytes
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${OUT:-$ROOT/.build/asr-burst/models}"
LITERT_SRC="${LITERT_SRC:-$HOME/code/edge-llm-bench-wt-asr-litert/.build/asr-litert-app/models}"
SHERPA_LOCK="${SHERPA_LOCK:-$HOME/code/edge-llm-bench-wt-asr-sherpa/.build/sherpa-onnx/LOCK.json}"
SHERPA_SRC="${SHERPA_SRC:-$HOME/code/edge-llm-bench-wt-asr-sherpa/.build/sherpa-onnx/extract/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2}"
CTC_SRC="${CTC_SRC:-$ROOT/.build/asr-burst/download-ctc}"
mkdir -p "$OUT/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"

python3 - "$OUT" "$LITERT_SRC" "$SHERPA_LOCK" "$SHERPA_SRC" "${HASH:-0}" "$CTC_SRC" <<'PY'
import hashlib, json, os, pathlib, sys
out, litert_src, sherpa_lock, sherpa_src = (pathlib.Path(a) for a in sys.argv[1:5])
do_hash = sys.argv[5] == "1"
ctc_src = pathlib.Path(sys.argv[6])

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()

wanted = []
litert_lock = litert_src / "models.lock.json"
for r in json.load(open(litert_lock)):
    wanted.append((litert_src / r["local"], out / r["local"], r["sha256"], r["bytes"], litert_lock,
                   f'{r["repo"]}@{r["revision"][:8]} {r["file"]} (asr-litert-app-v1 stage.sh)'))
for r in json.load(open(sherpa_lock))["model_files"]:
    if "/test_wavs/" in r["path"]:
        continue
    wanted.append((sherpa_src / r["path"], out / r["path"], r["sha256"], r["size"], sherpa_lock,
                   f'k2-fsa/sherpa-onnx asr-models sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2: {r["path"]} (asr-sherpa-v1 fetch.sh)'))
ctc_lock = ctc_src / "ctc.lock.json"
if not ctc_lock.exists():
    print(f"[stage] MISSING {ctc_lock} (run fetch_ctc.sh fetch, then verify)", file=sys.stderr)
    sys.exit(1)
for r in json.load(open(ctc_lock)):
    wanted.append((ctc_src / r["local"], out / r["local"], r["sha256"], r["bytes"], ctc_lock,
                   f'{r["repo"]}@{r["revision"][:8]} {r["file"]} (asr-burst-v1 fetch_ctc.sh)'))
rows, bad = [], 0
for src, dst, want, size, lock, origin in wanted:
    if not src.is_file():
        print(f"[stage] MISSING {src}", file=sys.stderr); bad += 1; continue
    if dst.exists() and not os.path.samefile(src, dst):
        dst.unlink()
    if not dst.exists():
        os.link(src, dst)
    st = dst.stat()
    checks = {"same_inode_as_source": os.path.samefile(src, dst), "size_matches_record": st.st_size == size,
              "unmodified_since_record": st.st_mtime <= lock.stat().st_mtime}
    got = sha256(dst) if do_hash else None
    if do_hash:
        checks["sha256_matches_record"] = got == want
    ok = all(checks.values())
    bad += 0 if ok else 1
    print(f"[stage] {'ok ' if ok else 'BAD'} {dst.relative_to(out)} {st.st_size} B {'sha256 ' + got[:16] if got else 'expected ' + want[:16]}… {'' if ok else checks}")
    rows.append({"local": str(dst.relative_to(out)), "bytes": st.st_size, "expected_sha256": want,
                 "sha256": got, "checks": checks, "source": origin, "linked_from": str(src), "record": str(lock)})
if bad:
    sys.exit(1)
(out / "models.lock.json").write_text(json.dumps(rows, indent=1) + "\n")
print(f"[stage] {len(rows)} files {'hashed and ' if do_hash else ''}checked -> {out / 'models.lock.json'}")
PY
