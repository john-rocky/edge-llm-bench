# r2: `./bench doctor` with the clone's own bench and scripts/doctor.py (main 0efecb0), as dev, in step 1's venv:
# the "before" output that 97-doctor-ddp.sh compares with the changed files' output.
. ~/elb-venv/bin/activate
cd ~/edge-llm-bench || exit 1
printf '## bench sha256 %s, scripts/doctor.py sha256 %s (git: %s)\n' "$(sha256sum bench | cut -d' ' -f1)" \
    "$(sha256sum scripts/doctor.py | cut -d' ' -f1)" "$(git status --short bench scripts/doctor.py | tr '\n' ' ')"
./bench doctor > ~/doctor-before.txt 2>&1
rc=$?
cat ~/doctor-before.txt
printf '## ./bench doctor (before) exit=%s\n' "$rc"
exit "$rc"
