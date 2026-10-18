# After the billed run, as dev, from the clone: the commits the post made on top of the bundle's base, `git log -1
# --stat`, git status, the campaign dir, its REVIEW.md when it was held, the one screen as written to summary.txt,
# the ledgers' last lines; the commits on top of the base (63ec5615 as applied here, then the post's) as a bundle
# (/tmp/autopilot-commit.bundle) for the driver to copy out.
cd ~/edge-llm-bench || exit 1
base=$(cat /opt/elb/base-commit)
# the clone's HEAD right before the sitting (the patches applied in the clone sit between the base and it): the post
# committed when HEAD moved past it
pre=$(cat /opt/elb/pre-session-head 2>/dev/null || echo "$base")
printf '## HEAD %s; before the sitting %s; the bundle base %s\n' "$(git rev-parse HEAD)" "$pre" "$base"
printf '## commits on top of the base:\n'; git log --format='%h %s' "$base"..HEAD | cut -c1-400
printf '## git log -1 --stat:\n'; git log -1 --stat --format='commit %H%nAuthor: %an <%ae>%nDate:   %cI%n%n    %s' | cut -c1-400
printf '## git status --short:\n'; git status --short
camp=$(ls -d results/raw/*-dashboard-v1-pixel8a-ddp-akita-35*-android 2>/dev/null | tail -1)
printf '## campaign dir: %s\n' "${camp:-none}"
[ -n "$camp" ] && find "$camp" -maxdepth 2 | sort | sed 's/^/  /'
[ -f "$camp/REVIEW.md" ] && { printf '## %s/REVIEW.md:\n' "$camp"; cat "$camp/REVIEW.md"; }
s=logs/autopilot/$(basename "${camp:-none}")/summary.txt
[ -f "$s" ] && { printf '## %s:\n' "$s"; cat "$s"; }
for f in logs/dashboard-job/ledger.tsv logs/dashboard-job/autopilot-ledger.tsv; do printf '## %s (last line):\n' "$f"; tail -1 "$f"; done
printf '## results/summary/device-runs.csv lines: %s\n' "$(wc -l < results/summary/device-runs.csv)"
rm -f /tmp/autopilot-commit.bundle
if [ "$(git rev-parse HEAD)" != "$pre" ]; then
  git bundle create /tmp/autopilot-commit.bundle "$base"..bench-autopilot-googler && git bundle verify /tmp/autopilot-commit.bundle
else
  echo '## the post made no commit (HEAD is where it was before the sitting): no bundle'
fi
