#!/bin/bash
# Put the three model files of the asr-fix-v1 arms (docs/asr-fix-v1.md: the 30 s export, the card's
# 5 s SM8850 AOT file for the NPU arm, the tokenizer) into .build/asr-fix/models/ as hardlinks of
# the copies asr-litert-app-v1 downloaded and
# verified (nothing is downloaded, the sources are only read), and write models.lock.json with each
# file's expected sha256 from that round's record (bytes hashed there = the Hub's LFS sha256 / git
# blob id, asr-litert-app-v1 stage.sh). A link is the source's own inode: the check here is that
# the size matches the record and the file was not modified after the record was written; HASH=1
# also hashes the files (1.9 GB: keep it out of a Mac measurement window). The phone checks the
# pushed bytes against the expected sha256 (setup).
#
#   tools/asr-fix/stage_models.sh          # link and check; exit 1 on a missing file or a mismatch
#   HASH=1 tools/asr-fix/stage_models.sh   # the same, plus sha256 of the bytes
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${OUT:-$ROOT/.build/asr-fix/models}"
LITERT_SRC="${LITERT_SRC:-$HOME/code/edge-llm-bench-wt-asr-litert/.build/asr-litert-app/models}"
mkdir -p "$OUT"

python3 - "$OUT" "$LITERT_SRC" "${HASH:-0}" <<'PY'
import hashlib, json, os, pathlib, sys
out, litert_src = (pathlib.Path(a) for a in sys.argv[1:3])
do_hash = sys.argv[3] == "1"
WANT = {"parakeet_tdt_0.6b_v3_30s_i8_stateful.tflite", "parakeet_tdt_0.6b_v3_5s_f32_stateful_Qualcomm_SM8850.tflite",
        "tokenizer.json"}

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()

litert_lock = litert_src / "models.lock.json"
wanted = [(litert_src / r["local"], out / r["local"], r["sha256"], r["bytes"], litert_lock,
           f'{r["repo"]}@{r["revision"][:8]} {r["file"]} (asr-litert-app-v1 stage.sh)')
          for r in json.load(open(litert_lock)) if r["local"] in WANT]
if {w[1].name for w in wanted} != WANT:
    print(f"[stage] MISSING in {litert_lock}: {WANT - {w[1].name for w in wanted}}", file=sys.stderr)
    sys.exit(1)
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
