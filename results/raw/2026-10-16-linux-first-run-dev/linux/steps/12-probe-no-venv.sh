# Probe (not a README step), as dev: python3 -m venv and pip before the python3-venv / python3-pip packages.
python3 --version
python3 -m venv ~/probe-venv; printf '## python3 -m venv ~/probe-venv rc=%s\n' "$?"
rm -rf ~/probe-venv
python3 -m pip --version; printf '## python3 -m pip --version rc=%s\n' "$?"
exit 0
