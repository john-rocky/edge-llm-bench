# r2b: the second billed session, README step 4 on matrices/ddp-first-run.cells with the fixed android/ddp/run_ddp.py
# (the model keyed by the sha256 of its bytes): one Device Run session, one job, two runs on akita-35, billed to
# litert-edge-portal; as dev, from the clone, in step 1's venv. Every input is expected in the bucket already (the
# model under models/2a72330b…/ since 2026-10-15), so nothing is uploaded. After the run: the driver's "in bucket" /
# "uploading" lines counted, and the gcloud commands of the run read from gcloud's own log files written during it
# (command names; the arguments of storage cp only; nothing of the auth commands).
. ~/elb-venv/bin/activate
cd ~/edge-llm-bench || exit 1
G=~/.config/gcloud/logs
find "$G" -type f -name '*.log' 2>/dev/null | sort > /tmp/r2b-gcloud-before.txt
date -u '+## start %F %T UTC'
./bench matrix matrices/ddp-first-run.cells --ddp akita-35 --campaign 2026-10-16-ddp-linux-first-run-b-akita-35 --project litert-edge-portal --bucket gs://litert-edge-portal-devicerun 2>&1 | tee /tmp/r2b-session.out
rc=${PIPESTATUS[0]}
date -u '+## end %F %T UTC'
printf '## ./bench matrix --ddp exit=%s\n' "$rc"
printf '## driver lines: "in bucket:" %s, "uploading" %s\n' "$(grep -c '^in bucket: ' /tmp/r2b-session.out)" \
    "$(grep -c '^uploading ' /tmp/r2b-session.out)"
find "$G" -type f -name '*.log' 2>/dev/null | sort > /tmp/r2b-gcloud-after.txt
comm -13 /tmp/r2b-gcloud-before.txt /tmp/r2b-gcloud-after.txt > /tmp/r2b-gcloud-new.txt
printf '## gcloud log files written during the run: %s; the commands they ran, by name:\n' "$(wc -l < /tmp/r2b-gcloud-new.txt)"
xargs -r grep -h -o 'Running \[gcloud\.[a-z.-]*\]' < /tmp/r2b-gcloud-new.txt | sort | uniq -c
printf '## every gcloud storage cp of the run, with its arguments:\n'
xargs -r grep -h 'Running \[gcloud\.storage\.cp\]' < /tmp/r2b-gcloud-new.txt | sed -E 's/^.*(Running )/\1/'
ls -la results/raw/2026-10-16-ddp-linux-first-run-b-akita-35-android/app-path-android/ 2>&1
exit "$rc"
