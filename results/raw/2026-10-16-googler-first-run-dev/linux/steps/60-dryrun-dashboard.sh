# README step 3 (README.md lines 145-146 with this lane's project and bucket for the placeholders), as dev, from the
# clone, in step 1's venv. Around it: the count of gcloud's own log files (one per gcloud invocation) and of
# results/raw entries, before and after.
. ~/elb-venv/bin/activate
cd ~/edge-llm-bench || exit 1
g0=$(find ~/.config/gcloud/logs -type f 2>/dev/null | wc -l)
r0=$(ls results/raw | wc -l)
./bench matrix matrices/dashboard-text-v1.cells --ddp akita-35 --dry-run \
    --project litert-edge-portal --bucket gs://litert-edge-portal-devicerun
rc=$?
g1=$(find ~/.config/gcloud/logs -type f 2>/dev/null | wc -l)
r1=$(ls results/raw | wc -l)
printf '## dry run exit=%s; gcloud log files before/after %s/%s; results/raw entries before/after %s/%s; git status --short %s line(s)\n' \
    "$rc" "$g0" "$g1" "$r0" "$r1" "$(git status --short | wc -l)"
exit "$rc"
