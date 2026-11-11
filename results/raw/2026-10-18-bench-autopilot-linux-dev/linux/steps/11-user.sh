# Container-only: the login user dev (uid 1000, passwordless sudo, HOME /home/dev), as root.
if ! useradd -m -u 1000 -s /bin/bash dev; then
  old=$(getent passwd 1000 | cut -d: -f1)
  printf '## useradd -u 1000 refused: the image already has user %s at uid 1000 -> userdel -r %s, useradd again\n' "$old" "$old"
  userdel -r "$old"
  if id "$old" > /dev/null 2>&1; then echo "## $old still exists"; exit 1; fi
  useradd -m -u 1000 -s /bin/bash dev || exit 1
fi
echo 'dev ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/dev && chmod 0440 /etc/sudoers.d/dev || exit 1
id dev
getent passwd dev
sudo -u dev sudo -n true && echo '## sudo for dev: passwordless OK' || exit 1
