# git's identity, as dev. First what the post's commit (git commit-tree) meets on a fresh host with none set: a
# probe in a scratch repo. Then the identity a workstation account has, set for dev (the container's stand-in);
# the post commits with it.
d=$(mktemp -d)
( cd "$d" && git init -q . && t=$(git write-tree) && git commit-tree "$t" -m probe ) 2>&1 | sed 's/^/  | /'
printf '## commit-tree with no identity set: rc=%s\n' "${PIPESTATUS[0]}"
rm -rf "$d"
git config --global user.name "dev (container)"
git config --global user.email "dev@container.invalid"
printf '## set: user.name=%s user.email=%s\n' "$(git config --global user.name)" "$(git config --global user.email)"
