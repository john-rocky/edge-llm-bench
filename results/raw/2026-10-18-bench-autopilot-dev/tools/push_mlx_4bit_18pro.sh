#!/bin/bash
# Round 16 (2026-10-19): copy the MLX Gemma 4 PTQ bundles mlx-community/gemma-4-{e2b,e4b}-it-4bit from this Mac's
# Hub cache into the iPhone 18 Pro bench app's own Hub cache, in the layout the app's MLX loader reads
# (swift-huggingface HubCache, the app's HubClient.default):
#   Library/Caches/huggingface/hub/models--mlx-community--<repo>/snapshots/<rev>/<file>   (regular files)
#   Library/Caches/huggingface/hub/models--mlx-community--<repo>/refs/main                 (<rev>, 40 bytes)
# With every file of the snapshot there, downloadSnapshot(revision: "main") resolves each file through refs/main
# (HubCache.cachedFilePath) and downloads nothing, so no cell of matrices/mlx-gemma4-file-ios.cells waits on
# Wi-Fi. The app's E2B OptiQ bundle is only listed (the weekly sittings put it there).
#
#   push_mlx_4bit_18pro.sh --dry-run          host-side checks and the copy plan; no device call
#   push_mlx_4bit_18pro.sh --keeper <pid>     the copy, inside the hold <pid> owns (queue_cli.py wait <hold> <name> <pid>)
#
# Host-side checks: the cache's refs/main is the Hub's main today, and the snapshot holds every Hub file the app's
# patterns (*.safetensors *.json *.jinja) match, at the Hub's size. Device side (--keeper only): the phone is
# attached and unlocked, the hold names <pid>; list the app's hub dir, copy each snapshot dir and then its
# refs/main, list again and compare every file's size with the Mac's.
# Exit: 0 = every file on the phone at the Mac's size (or, --dry-run, the host checks passed); 1 = a check failed
# (the line says which); 2 = usage.
set -u
set -f                                     # the patterns below are passed on, never expanded here
UDID=00008160-000038CA02C00036
APP=com.example.CoreMLLLMChat
HOLD=$HOME/code/coreai/ondevice/.device_hold
CACHE=$HOME/.cache/huggingface/hub
DEST=Library/Caches/huggingface/hub
REPOS="gemma-4-e2b-it-4bit gemma-4-e4b-it-4bit"
LISTED="gemma-4-e2b-it-qat-OptiQ-4bit"
PATTERNS="*.safetensors *.json *.jinja"     # mlx-swift-lm 60bd0d7 modelDownloadPatterns
COPY_TIMEOUT=1800                          # seconds per devicectl copy (the hold's window is 45 min)

usage() { sed -n 2,20p "$0" >&2; exit 2; }
DRY=0; KEEPER=""
case "${1:-}" in
  --dry-run) DRY=1 ;;
  --keeper) KEEPER="${2:-}"; [ -n "$KEEPER" ] || usage ;;
  *) usage ;;
esac
OUT=${OUT:-${TMPDIR:-/tmp}/push_mlx_4bit_18pro.$(date +%Y%m%d-%H%M%S)}
mkdir -p "$OUT" || exit 1
say() { echo "$(date +%H:%M:%S) $*"; }
fail() { say "FAIL $*"; exit 1; }
say "out dir: $OUT"

# --- host side: every repo's cached revision against the Hub, its files against the Hub tree
for r in $REPOS; do
  repo=$CACHE/models--mlx-community--$r
  [ -f "$repo/refs/main" ] || fail "$r: no $repo/refs/main (hf download mlx-community/$r --include $PATTERNS)"
  rev=$(cat "$repo/refs/main")
  case "$rev" in *[!0-9a-f]*|"") fail "$r: refs/main is not a commit hash: '$rev'" ;; esac
  [ ${#rev} -eq 40 ] || fail "$r: refs/main is not 40 characters: '$rev'"
  [ -d "$repo/snapshots/$rev" ] || fail "$r: no snapshot dir for $rev"
  curl -fsS "https://huggingface.co/api/models/mlx-community/$r/revision/main" -o "$OUT/$r.hub-main.json" \
    || fail "$r: Hub API revision/main unreachable"
  curl -fsS "https://huggingface.co/api/models/mlx-community/$r/tree/$rev?recursive=true" -o "$OUT/$r.hub-tree.json" \
    || fail "$r: Hub API tree unreachable"
  python3 -I - "$r" "$rev" "$repo/snapshots/$rev" "$OUT" $PATTERNS <<'EOF' || exit 1
import fnmatch, json, os, sys
r, rev, snap, out, pats = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5:]
main = json.load(open(os.path.join(out, f"{r}.hub-main.json")))["sha"]
if main != rev:
    print(f"FAIL {r}: the Hub's main is {main}, the cache holds {rev} - hf download the new revision first "
          "(the app would fetch the new main's changed files over Wi-Fi)")
    sys.exit(1)
tree = [e for e in json.load(open(os.path.join(out, f"{r}.hub-tree.json"))) if e.get("type") == "file"]
want = {e["path"]: e.get("size") for e in tree if any(fnmatch.fnmatchcase(e["path"], p) for p in pats)}
have = {}
for root, _, files in os.walk(snap, followlinks=True):
    for f in files:
        p = os.path.join(root, f)
        have[os.path.relpath(p, snap)] = os.stat(p).st_size   # follows the symlink into blobs/
bad = [f"{p}: Hub {s}, cache {have.get(p)}" for p, s in sorted(want.items()) if have.get(p) != s]
if bad:
    print(f"FAIL {r}: the snapshot differs from the Hub tree: " + "; ".join(bad))
    sys.exit(1)
extra = sorted(set(have) - set(want))
with open(os.path.join(out, f"{r}.files.tsv"), "w") as fh:
    for p in sorted(have):
        fh.write(f"{p}\t{have[p]}\n")
print(f"OK   {r} {rev}: Hub main = cache refs/main; {len(want)} files match {' '.join(pats)}, "
      f"{sum(want.values()):,} bytes, every one at the Hub's size"
      + (f"; also in the snapshot, not matched: {', '.join(extra)}" if extra else ""))
EOF
done

say "plan (devicectl copy to, device $UDID, app $APP; snapshot dir first, then refs/main):"
for r in $REPOS; do
  rev=$(cat "$CACHE/models--mlx-community--$r/refs/main")
  echo "  $CACHE/models--mlx-community--$r/snapshots/$rev/"
  echo "    -> $DEST/models--mlx-community--$r/snapshots/$rev/"
  sed 's/^/       /' "$OUT/$r.files.tsv"
  echo "  $CACHE/models--mlx-community--$r/refs/main ($rev)"
  echo "    -> $DEST/models--mlx-community--$r/refs/main"
done
echo "  listed only: $DEST/models--mlx-community--$LISTED/"
if [ $DRY -eq 1 ]; then
  say "dry run: no device call made"
  exit 0
fi

# --- device side, inside the keeper's hold
kill -0 "$KEEPER" 2>/dev/null || fail "keeper pid $KEEPER is not alive"
python3 -I - "$HOLD" "$KEEPER" <<'EOF' || exit 1
import json, sys
try:
    h = json.load(open(sys.argv[1]))
except (OSError, ValueError) as e:
    print(f"FAIL no readable hold at {sys.argv[1]} ({e}): the keeper must hold the phone first"); sys.exit(1)
if str(h.get("pid")) != sys.argv[2]:
    print(f"FAIL the hold belongs to pid {h.get('pid')} ({h.get('script')}), not to the keeper {sys.argv[2]}"); sys.exit(1)
print(f"OK   hold {sys.argv[1]}: pid {h.get('pid')} ({h.get('script')}, since {h.get('started')})")
EOF
xcrun devicectl list devices > "$OUT/devices.txt" 2>&1
grep "$UDID" "$OUT/devices.txt" | grep -q -e available -e connected || fail "$UDID not available to devicectl ($OUT/devices.txt)"
xcrun devicectl device info lockState --device "$UDID" > "$OUT/lockstate.txt" 2>&1 || fail "lockState query failed ($OUT/lockstate.txt)"
grep -q "passcodeRequired: false" "$OUT/lockstate.txt" || fail "the phone is locked ($OUT/lockstate.txt)"
say "OK   $UDID attached and unlocked"

list_hub() {   # $1 = tag; the app's whole hub dir, recursive, as JSON
  xcrun devicectl device info files --device "$UDID" --domain-type appDataContainer --domain-identifier "$APP" \
    --subdirectory "$DEST" -j "$OUT/hub-$1.json" > "$OUT/hub-$1.txt" 2>&1 || fail "listing $DEST failed ($OUT/hub-$1.txt)"
}
check_repo() {   # $1 = tag, $2 = repo, $3 = expected-files tsv ("" = list only)
  python3 -I - "$OUT/hub-$1.json" "models--mlx-community--$2" "${3:-}" "$CACHE" <<'EOF'
import json, os, sys
listing, repo, tsv, cache = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
files = {f["relativePath"]: f["metadata"]["size"] for f in json.load(open(listing))["result"]["files"]
         if not f["resources"]["isDirectory"]}
mine = {p[len(repo) + 1:]: s for p, s in files.items() if p.startswith(repo + "/")}
if not tsv:
    # list only: each snapshot on the phone, against the Mac's snapshot of the same revision where the Mac has one
    snaps = sorted({p.split("/")[1] for p in mine if p.startswith("snapshots/")})
    for s in snaps:
        sub = {p[len(f"snapshots/{s}/"):]: v for p, v in mine.items() if p.startswith(f"snapshots/{s}/")}
        line = f"     {repo} snapshots/{s}: {len(sub)} files, {sum(sub.values()):,} bytes"
        mac = os.path.join(cache, repo, "snapshots", s)
        if os.path.isdir(mac):
            ref = {}
            for root, _, fs in os.walk(mac, followlinks=True):
                for f in fs:
                    ref[os.path.relpath(os.path.join(root, f), mac)] = os.stat(os.path.join(root, f)).st_size
            diff = sorted(p for p in set(ref) | set(sub) if ref.get(p) != sub.get(p))
            line += (f"; the Mac's snapshot of {s[:8]}: {len(ref)} files, "
                     + ("every file at the same size" if not diff else "differs: " + ", ".join(diff)))
        print(line)
    print(f"     {repo} refs/main: {'present, ' + str(mine['refs/main']) + ' bytes' if 'refs/main' in mine else 'absent'}"
          + ("" if snaps else "; no snapshot"))
    sys.exit(0)
rev = open(tsv.replace(".files.tsv", ".rev")).read().strip()
want = dict(line.rstrip("\n").split("\t") for line in open(tsv))
bad = [f"{p}: Mac {s}, phone {mine.get(f'snapshots/{rev}/{p}')}" for p, s in sorted(want.items())
       if mine.get(f"snapshots/{rev}/{p}") != int(s)]
if mine.get("refs/main") != 40:
    bad.append(f"refs/main: phone {mine.get('refs/main')} bytes, want 40")
if bad:
    print(f"FAIL {repo}: " + "; ".join(bad)); sys.exit(1)
print(f"OK   {repo} snapshots/{rev}: {len(want)} files at the Mac's sizes ({sum(int(s) for s in want.values()):,} bytes); refs/main 40 bytes")
EOF
}

list_hub before
say "before the copy:"
for r in $LISTED $REPOS; do check_repo before "$r" ""; done

for r in $REPOS; do
  repo=$CACHE/models--mlx-community--$r
  rev=$(cat "$repo/refs/main")
  printf '%s\n' "$rev" > "$OUT/$r.rev"
  say "copy $r snapshots/$rev/"
  xcrun devicectl device copy to --device "$UDID" --domain-type appDataContainer --domain-identifier "$APP" \
    --source "$repo/snapshots/$rev" --destination "$DEST/models--mlx-community--$r/snapshots/$rev" \
    -t "$COPY_TIMEOUT" > "$OUT/copy-$r-snapshot.txt" 2>&1 || fail "copy of $r snapshot failed ($OUT/copy-$r-snapshot.txt)"
  say "copy $r refs/main"
  xcrun devicectl device copy to --device "$UDID" --domain-type appDataContainer --domain-identifier "$APP" \
    --source "$repo/refs/main" --destination "$DEST/models--mlx-community--$r/refs/main" \
    -t 120 > "$OUT/copy-$r-refs.txt" 2>&1 || fail "copy of $r refs/main failed ($OUT/copy-$r-refs.txt)"
done

list_hub after
say "after the copy:"
rc=0
for r in $REPOS; do check_repo after "$r" "$OUT/$r.files.tsv" || rc=1; done
check_repo after "$LISTED" ""
[ $rc -eq 0 ] && say "done: both bundles on the phone at the Mac's sizes" || say "FAIL a bundle differs (above)"
exit $rc
