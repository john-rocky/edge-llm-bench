# r2, before the billed session, as dev, from the clone, in step 1's venv: the clone's HEAD and status, the venv,
# the sign-in (the token is not printed), the engine files, the model in the HF cache (expected: not there yet).
. ~/elb-venv/bin/activate
cd ~/edge-llm-bench || exit 1
date -u '+## container clock %F %T UTC'
printf '## HEAD %s\n' "$(git log --oneline -1 | cut -c1-80)"
printf '## git status --short:\n'; git status --short
printf '## %s, huggingface_hub %s\n' "$(python3 --version 2>&1)" "$(pip show huggingface_hub 2>/dev/null | sed -n 's/^Version: //p')"
printf '## %s; core/project = %s\n' "$(gcloud --version 2>/dev/null | head -1)" "$(gcloud config get-value project 2>/dev/null)"
gcloud auth print-access-token > /dev/null && echo TOKEN_OK || exit 1
T=$(python3 -c 'import json; print(json.load(open("android/engine-pins.json"))["android_pins"]["litert-lm"])')
printf '## android/bin/%s: %s entries (ls -A), %s without the ._* files\n' "$T" "$(ls -A "android/bin/$T" | wc -l)" "$(ls -A "android/bin/$T" | grep -vc '^\._')"
printf '## HF cache: '; ls ~/.cache/huggingface/hub 2>/dev/null | tr '\n' ' '; echo "(end)"
printf '## disk: '; df -h ~ | tail -1
printf '## results/raw entries: %s; the campaign dir exists: ' "$(ls results/raw | wc -l)"
[ -e results/raw/2026-10-16-ddp-linux-first-run-akita-35-android ] && echo yes || echo no
