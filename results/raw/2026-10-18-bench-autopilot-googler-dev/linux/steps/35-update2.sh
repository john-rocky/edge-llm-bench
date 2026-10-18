# The retake's go (the supervisor, 23:5x JST), as dev, from the clone: r5's 6e3d5908 applied in this clone only (the
# .gitignore line that keeps a Device Run execution's own logcat.txt out of every commit; on bench-autopilot; the host
# branch is not changed). The r1 sitting's dir stays on disk as evidence; the patch touches .gitignore only.
cd ~/edge-llm-bench || exit 1
git am -q /opt/elb/6e3d5908.patch || { git am --abort; exit 1; }
git log --format='## %h author %an, committer %cn: %s' -3 | cut -c1-170
printf '## .gitignore, the line:\n'; grep -n 'execution-\*/logcat.txt' .gitignore
f=$(ls -d results/raw/*-dashboard-v1-pixel8a-ddp-akita-35-android/ddp/*/*/execution-*/logcat.txt | head -1)
printf '## the r1 dir'"'"'s execution logcat: %s\n' "$(git check-ignore -v "$f" || echo 'not ignored')"
printf '## git status --short:\n'; git status --short | cut -c1-140
