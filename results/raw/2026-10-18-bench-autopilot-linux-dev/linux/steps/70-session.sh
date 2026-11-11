# The billed run (after the supervisor's go): one Device Run session, one job, two runs on akita-35, billed to
# litert-edge-portal, as the launch names it; as dev, from the clone, in step 1's venv. Every input is expected in the
# bucket already (the model under models/2a72330b.../ since 2026-10-15), so nothing is uploaded. After the run: the
# gcloud commands of the run read from gcloud's own log files written during it (command names; the arguments of
# storage cp only; nothing of the auth commands).
. ~/elb-venv/bin/activate
cd ~/edge-llm-bench || exit 1
G=~/.config/gcloud/logs
find "$G" -type f -name '*.log' 2>/dev/null | sort > /tmp/g-before.txt
date -u '+## start %F %T UTC'
./bench autopilot --ddp akita-35 --cells matrices/ddp-first-run.cells --project litert-edge-portal --bucket gs://litert-edge-portal-devicerun
rc=$?
date -u '+## end %F %T UTC'
printf '## ./bench autopilot exit=%s\n' "$rc"
find "$G" -type f -name '*.log' 2>/dev/null | sort > /tmp/g-after.txt
comm -13 /tmp/g-before.txt /tmp/g-after.txt > /tmp/g-new.txt
printf '## gcloud log files written during the run: %s; the commands they ran, by name:\n' "$(wc -l < /tmp/g-new.txt)"
xargs -r grep -h -o 'Running \[gcloud\.[a-z.-]*\]' < /tmp/g-new.txt | sort | uniq -c
printf '## every gcloud storage cp of the run, with its arguments:\n'
xargs -r grep -h 'Running \[gcloud\.storage\.cp\]' < /tmp/g-new.txt | sed -E 's/^.*(Running )/\1/'
exit "$rc"
