# Probe (not a README step), as dev, while the driver holds the container off its network: the selftest and the
# two dry runs again, to back "no network" with a run instead of a reading of the code.
. ~/elb-venv/bin/activate
cd ~/edge-llm-bench || exit 1
getent hosts github.com > /dev/null && echo '## DNS answers: NOT offline' || echo '## no DNS answer for github.com'
curl -sS -m 10 -o /dev/null https://github.com && echo '## HTTPS reached github.com: NOT offline' || echo '## no HTTPS to github.com'
./android/ddp/selftest.py; s=$?
./bench matrix matrices/ddp-first-run.cells --ddp akita-35 --dry-run \
    --project litert-edge-portal --bucket gs://litert-edge-portal-devicerun; d1=$?
./bench matrix matrices/dashboard-text-v1.cells --ddp akita-35 --dry-run \
    --project litert-edge-portal --bucket gs://litert-edge-portal-devicerun; d2=$?
printf '## offline: selftest exit=%s, first-run dry run exit=%s, dashboard dry run exit=%s\n' "$s" "$d1" "$d2"
[ "$s" = 0 ] && [ "$d1" = 0 ] && [ "$d2" = 0 ]
