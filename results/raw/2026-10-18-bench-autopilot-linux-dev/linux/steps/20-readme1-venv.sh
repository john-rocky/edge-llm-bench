# README step 1, the python line (README.md line 131, the command between its backticks; verbatim between the markers), as dev.
# --- README.md:131 ---
python3 -m venv ~/elb-venv && . ~/elb-venv/bin/activate && pip install huggingface_hub
# --- end ---
rc=$?
printf '## README line rc=%s\n' "$rc"
[ "$rc" = 0 ] || exit "$rc"
printf '## python3 in the venv: %s (%s)\n' "$(command -v python3)" "$(python3 --version)"
pip --version
pip show huggingface_hub
