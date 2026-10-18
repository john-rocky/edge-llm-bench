# Before the billed run, as dev, from the clone: the clone's branch put on the host branch's new tip (the bundle copied
# in again; the clone holds no work of its own, a run of this step before it may have left r5's commit on top), then
# r5's 63ec5615 applied on top in this clone only (the supervisor's go, 23:4x JST: the allow-list line for the DDP
# route's gen-budget is on bench-autopilot; the host branch is not changed), then the autopilot selftest on the result
# with the system python3.
cd ~/edge-llm-bench || exit 1
[ -z "$(git status --porcelain)" ] || { echo '## the clone has changes: not moved'; git status --short; exit 1; }
git fetch -q origin bench-autopilot-googler || exit 1
git checkout -q -B bench-autopilot-googler FETCH_HEAD || exit 1
[ "$(git rev-parse HEAD)" = "$(cat /opt/elb/base-commit)" ] && echo '## HEAD = the new base' || { echo '## HEAD is not the new base'; exit 1; }
git am -q /opt/elb/63ec5615.patch || { git am --abort; exit 1; }
git log --format='## %h author %an, committer %cn: %s' -4 | cut -c1-170
printf '## the allow-list line now in the clone:\n'; grep '^gen-budget' ops/session-check/allow-list.tsv | cut -c1-160
printf '## git status --short: %s line(s)\n' "$(git status --short | wc -l)"
export BENCH_ANDROID_BIN_DIR="$HOME/edge-llm-bench/android/bin"
python3 scripts/autopilot_selftest.py > /tmp/selftest.out 2>&1
rc=$?
printf '## scripts/autopilot_selftest.py exit=%s | %s\n' "$rc" "$(tail -1 /tmp/selftest.out)"
exit "$rc"
