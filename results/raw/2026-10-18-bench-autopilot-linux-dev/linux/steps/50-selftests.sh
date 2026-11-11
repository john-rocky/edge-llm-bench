# The selftests as the CI job runs them: the system python3 (no venv, no huggingface_hub), the engine files README
# step 2 put in place as BENCH_ANDROID_BIN_DIR; as dev, from the clone. The autopilot's first.
cd ~/edge-llm-bench || exit 1
export BENCH_ANDROID_BIN_DIR="$HOME/edge-llm-bench/android/bin"
printf '## %s (%s); huggingface_hub: %s\n' "$(python3 --version)" "$(command -v python3)" \
  "$(python3 -c 'import huggingface_hub; print(huggingface_hub.__version__)' 2>&1 | tail -1)"
fail=0
for t in scripts/autopilot_selftest.py scripts/dashboard_job_selftest.py scripts/session_check_selftest.py \
         scripts/dashboard_post_selftest.py scripts/regression_watch_selftest.py android/ddp/selftest.py; do
  s0=$(date +%s)
  python3 "$t" > /tmp/selftest.out 2>&1
  rc=$?
  printf '## %s exit=%s %s s | %s\n' "$t" "$rc" "$(( $(date +%s) - s0 ))" "$(tail -1 /tmp/selftest.out)"
  [ "$rc" = 0 ] || { fail=1; tail -40 /tmp/selftest.out; }
done
exit "$fail"
