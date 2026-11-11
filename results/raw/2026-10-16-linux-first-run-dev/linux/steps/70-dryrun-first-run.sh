# The README step 3 command on matrices/ddp-first-run.cells (copied in by the driver), as dev, from the clone,
# in step 1's venv; the same before / after counts as 60-dryrun-dashboard.sh.
. ~/elb-venv/bin/activate
cd ~/edge-llm-bench || exit 1
python3 scripts/validate_cells.py matrices/ddp-first-run.cells || exit 1
g0=$(find ~/.config/gcloud/logs -type f 2>/dev/null | wc -l)
r0=$(ls results/raw | wc -l)
./bench matrix matrices/ddp-first-run.cells --ddp akita-35 --dry-run \
    --project litert-edge-portal --bucket gs://litert-edge-portal-devicerun
rc=$?
g1=$(find ~/.config/gcloud/logs -type f 2>/dev/null | wc -l)
r1=$(ls results/raw | wc -l)
printf '## dry run exit=%s; gcloud log files before/after %s/%s; results/raw entries before/after %s/%s; git status --short %s line(s)\n' \
    "$rc" "$g0" "$g1" "$r0" "$r1" "$(git status --short | wc -l)"
exit "$rc"
