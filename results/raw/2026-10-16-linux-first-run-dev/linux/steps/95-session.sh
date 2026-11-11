# r2: README step 4 (the billed run) on matrices/ddp-first-run.cells: one Device Run session, one job, two runs on
# akita-35, billed to litert-edge-portal; as dev, from the clone, in step 1's venv. --campaign names the results
# directory (without it: <date>-ddp-akita-35-android).
. ~/elb-venv/bin/activate
cd ~/edge-llm-bench || exit 1
date -u '+## start %F %T UTC'
./bench matrix matrices/ddp-first-run.cells --ddp akita-35 --campaign 2026-10-16-ddp-linux-first-run-akita-35 --project litert-edge-portal --bucket gs://litert-edge-portal-devicerun
rc=$?
date -u '+## end %F %T UTC'
printf '## ./bench matrix --ddp exit=%s\n' "$rc"
ls -la results/raw/2026-10-16-ddp-linux-first-run-akita-35-android/app-path-android/ 2>&1
exit "$rc"
