# The clone, as dev: branch bench-autopilot-googler from the host checkout's bundle (/opt/elb/repo.bundle, copied in by
# the driver; GitHub does not hold this branch, so README step 2's `git clone https://github.com/...` line is not run),
# in step 1's venv. The bundle's commit is the base the post's commit is measured from (/opt/elb/base-commit).
. ~/elb-venv/bin/activate
cd ~ || exit 1
git clone -b bench-autopilot-googler /opt/elb/repo.bundle edge-llm-bench || exit 1
cd edge-llm-bench || exit 1
git log -1 --format='## HEAD %H %cI' && git log -1 --format='## %s' | cut -c1-120
[ "$(git rev-parse HEAD)" = "$(cat /opt/elb/base-commit)" ] && echo '## HEAD = the bundle base' || { echo '## HEAD differs from the bundle base'; exit 1; }
printf '## git status --short: %s line(s)\n' "$(git status --short | wc -l)"
printf '## remote: %s\n' "$(git remote get-url origin)"
du -sh .git
