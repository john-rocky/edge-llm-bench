# Container-only (a gLinux host has these): the base image's packages, as root.
# The launch's apt line minus python3-venv / python3-pip (13-apt-python.sh, after the venv probe), plus procps
# (pgrep / ps; the run showed the base image already has them, so it was a no-op; comment corrected after the run).
printf '## /etc/os-release\n'; cat /etc/os-release
printf '## uname -m: %s\n' "$(uname -m)"
printf '## before install:'
for t in sudo git curl gpg python3 pgrep ps; do printf ' %s=%s' "$t" "$(command -v "$t" || echo missing)"; done; printf '\n'
printf '## uid 1000 in the image: %s\n' "$(getent passwd 1000 || echo none)"
export DEBIAN_FRONTEND=noninteractive
apt-get update || exit 1
apt-get install -y sudo git curl ca-certificates gnupg python3 procps || exit 1
printf '## after install:'
for t in sudo git curl gpg python3 pgrep ps; do printf ' %s=%s' "$t" "$(command -v "$t" || echo missing)"; done; printf '\n'
