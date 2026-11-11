# ./bench doctor (README "Setup", line 59), as dev, from the clone, in step 1's venv. Its exit code is the step's.
. ~/elb-venv/bin/activate
cd ~/edge-llm-bench || exit 1
./bench doctor
rc=$?
printf '## ./bench doctor exit=%s\n' "$rc"
exit "$rc"
