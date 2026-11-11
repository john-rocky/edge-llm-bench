# The DDP selftest (android/README.md "DDP lab phones"; CI's android-driver-selftest job), as dev, from the clone,
# in step 1's venv, with the engine files where README step 2 put them (no BENCH_ANDROID_BIN_DIR).
. ~/elb-venv/bin/activate
cd ~/edge-llm-bench || exit 1
printf '## BENCH_ANDROID_BIN_DIR=%s\n' "${BENCH_ANDROID_BIN_DIR:-unset}"
./android/ddp/selftest.py
rc=$?
printf '## ./android/ddp/selftest.py exit=%s\n' "$rc"
exit "$rc"
