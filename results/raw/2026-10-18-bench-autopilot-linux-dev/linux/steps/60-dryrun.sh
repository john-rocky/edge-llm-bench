# README.md "One command: the autopilot": its bash block as the clone's README prints it, verbatim, with its two
# placeholders filled; as dev, from the clone, in step 1's venv. Before and after: gcloud's own log files (one per
# gcloud command), the entries of results/raw, the files under logs/, git status.
. ~/elb-venv/bin/activate
cd ~/edge-llm-bench || exit 1
line=$(awk '/^\*\*One command: the autopilot\.\*\*/{s=1} s && /^```bash$/{f=1; next} s && f && /^```$/{exit} s && f' README.md)
printf '## README.md, the autopilot block as written:\n%s\n' "$line"
[ -n "$line" ] && [ "$(printf '%s\n' "$line" | wc -l)" = 1 ] || { echo '## the block is not one line'; exit 1; }
run=$(printf '%s' "$line" | sed -e 's/<your project>/litert-edge-portal/' -e 's|gs://<your bucket>|gs://litert-edge-portal-devicerun|')
printf '## run, the two placeholders filled:\n%s\n' "$run"
g0=$(find ~/.config/gcloud/logs -type f 2>/dev/null | wc -l); r0=$(ls results/raw | wc -l)
l0=$(find logs -type f 2>/dev/null | wc -l); s0=$(git status --porcelain | wc -l)
eval "$run"
rc=$?
g1=$(find ~/.config/gcloud/logs -type f 2>/dev/null | wc -l); r1=$(ls results/raw | wc -l)
l1=$(find logs -type f 2>/dev/null | wc -l); s1=$(git status --porcelain | wc -l)
printf '## dry run exit=%s; gcloud log files before/after %s/%s; results/raw entries %s/%s; files under logs/ %s/%s; git status --porcelain lines %s/%s\n' \
  "$rc" "$g0" "$g1" "$r0" "$r1" "$l0" "$l1" "$s0" "$s1"
exit "$rc"
