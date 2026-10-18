# README step 2's bash block as the clone's README.md prints it, without its clone line (30-clone.sh cloned the
# branch from the bundle): the pinned LiteRT-LM Android files from the release asset; as dev, from the clone, in
# step 1's venv. Then the files against the asset's SHA256SUMS.
. ~/elb-venv/bin/activate
cd ~/edge-llm-bench || exit 1
blk=$(awk '/^\*\*2\. /{s=1} /^\*\*3\. /{s=0} s && /^```bash$/{n++; f=1; next} s && /^```$/{f=0; next} s && f && n==1' README.md | grep -v '^git clone ')
printf '## README.md step 2, its first bash block without the clone line:\n%s\n' "$blk"
[ -n "$blk" ] || { echo '## block not found'; exit 1; }
eval "$blk"; rc=$?
printf '## block exit=%s TAG=%s\n' "$rc" "$TAG"
[ "$rc" = 0 ] || exit "$rc"
printf '## android/bin/%s: %s entries (ls -A), %s without the ._* files\n' "$TAG" "$(ls -A "android/bin/$TAG" | wc -l)" \
  "$(ls -A "android/bin/$TAG" | grep -vc '^\._')"
if [ -f "android/bin/$TAG/SHA256SUMS" ]; then ( cd "android/bin/$TAG" && sha256sum -c SHA256SUMS ) || exit 1; else echo '## no SHA256SUMS'; fi
