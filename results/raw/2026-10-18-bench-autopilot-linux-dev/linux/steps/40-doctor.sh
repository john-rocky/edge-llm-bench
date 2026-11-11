# ./bench doctor --platform ddp (README quickstart "Check"), as dev, from the clone, in step 1's venv. The container
# has no adb and no xcrun: the doctor's Android and iPhone checks warn, nothing reaches a phone.
. ~/elb-venv/bin/activate
cd ~/edge-llm-bench || exit 1
printf '## adb: %s; xcrun: %s; gtimeout: %s; timeout: %s\n' "$(command -v adb || echo none)" "$(command -v xcrun || echo none)" \
  "$(command -v gtimeout || echo none)" "$(command -v timeout || echo none)"
./bench doctor --platform ddp
rc=$?
printf '## ./bench doctor --platform ddp exit=%s\n' "$rc"
exit "$rc"
