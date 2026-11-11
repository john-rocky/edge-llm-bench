# r2b: the selftest as CI's android-driver-selftest job runs it, without huggingface_hub: the container's system
# python3 (no venv), from the clone, with the engine files where README step 2 put them.
cd ~/edge-llm-bench || exit 1
printf '## %s (%s); huggingface_hub importable: ' "$(/usr/bin/python3 --version 2>&1)" "$(command -v /usr/bin/python3)"
/usr/bin/python3 -c 'import huggingface_hub' 2> /dev/null && echo yes || echo no
/usr/bin/python3 android/ddp/selftest.py
rc=$?
printf '## /usr/bin/python3 android/ddp/selftest.py exit=%s\n' "$rc"
exit "$rc"
