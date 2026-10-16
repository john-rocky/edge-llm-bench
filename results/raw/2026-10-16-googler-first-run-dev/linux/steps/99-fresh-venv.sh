# r2: README step 1's python line on a stock ubuntu:24.04 (a throwaway container, removed on exit; root, so sudo asks
# no password): python3 alone, the venv line fails; `sudo apt install python3-venv` as written (apt's Y/n answered on
# stdin by `yes`); then the venv line of README.md:114 (the same as docs/OPERATIONS.md's) with python3-venv and
# without python3-pip.
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq > /dev/null && apt-get install -y -qq sudo python3 > /dev/null || exit 1
. /etc/os-release
installed() { dpkg -s "$1" > /dev/null 2>&1 && echo yes || echo no; }
printf '## %s, %s; python3-venv installed: %s; python3-pip installed: %s\n' "$PRETTY_NAME" "$(python3 --version 2>&1)" \
    "$(installed python3-venv)" "$(installed python3-pip)"
python3 -m venv ~/probe-venv > /dev/null 2>&1
printf '## python3 -m venv before python3-venv: rc=%s\n' "$?"
yes | sudo apt install python3-venv
printf '## sudo apt install python3-venv: rc=%s\n' "$?"
python3 -m venv ~/elb-venv && . ~/elb-venv/bin/activate && pip install huggingface_hub
rc=$?
printf '## README.md:114 rc=%s; huggingface_hub %s; python3-venv installed: %s; python3-pip installed: %s\n' "$rc" \
    "$(pip show huggingface_hub 2>/dev/null | sed -n 's/^Version: //p')" "$(installed python3-venv)" "$(installed python3-pip)"
exit "$rc"
