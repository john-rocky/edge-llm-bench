# r2, after the docs changes (README.md and docs/OPERATIONS.md copied in by the driver), as dev, in step 1's venv:
# the quickstart's two checks as README.md prints them, and README step 1's python3-venv phrase as written (the
# package is already installed here; 99-fresh-venv.sh runs the phrase on a stock image).
. ~/elb-venv/bin/activate
cd ~/edge-llm-bench || exit 1
fail=0
q=$(awk '/^## Quickstart/{s=1; next} /^## /{s=0} s' README.md)
printf '## the quickstart as README.md prints it:\n%s\n' "$q"
for c in './bench doctor --platform ddp' './android/ddp/selftest.py'; do
  if printf '%s\n' "$q" | grep -qF "\`$c\`"; then
    printf '\n## run: %s\n' "$c"
    eval "$c"; rc=$?
    printf '## %s exit=%s\n' "$c" "$rc"
    [ "$rc" = 0 ] || fail=1
  else
    printf '## not in the quickstart: %s\n' "$c"; fail=1
  fi
done
p=$(grep -o 'sudo apt install python3-venv' README.md | head -1)
printf '\n## README step 1 phrase: %s\n' "${p:-not found}"
[ -n "$p" ] || exit 1
eval "$p" < /dev/null; rc=$?
printf '## exit=%s\n' "$rc"
[ "$rc" = 0 ] || fail=1
o=$(grep -o 'python3 -m venv ~/elb-venv && \. ~/elb-venv/bin/activate && pip install huggingface_hub' docs/OPERATIONS.md | head -1)
printf '\n## docs/OPERATIONS.md prerequisites, the huggingface_hub line: %s\n' "${o:-not found}"
[ -n "$o" ] || fail=1
exit "$fail"
