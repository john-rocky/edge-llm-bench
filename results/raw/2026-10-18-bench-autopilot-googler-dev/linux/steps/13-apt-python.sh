# Container-only: the venv and pip packages, as root.
export DEBIAN_FRONTEND=noninteractive
apt-get install -y python3-venv python3-pip || exit 1
dpkg-query -W python3 python3-venv python3-pip python3.12 python3.12-venv
