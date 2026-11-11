# Verify phase (after the README fixes), as dev, in step 1's venv: the changed lines run as the fixed files print them.
# (1) README.md step 2's new bash block, from the clone. (2) android/README.md "Engine acquisition" fast path (minus
# its unchanged fetch_llama_android.sh line, a llama.cpp download the DDP route does not use) in a fresh directory
# that holds only android/engine-pins.json; its files compared with README step 2's.
. ~/elb-venv/bin/activate
cd ~/edge-llm-bench || exit 1
fail=0
blk=$(awk '/^\*\*2\. /{s=1} /^\*\*3\. /{s=0} s && /^```bash$/{n++; f=1; next} s && /^```$/{f=0; next} s && f && n==2' README.md)
printf '## (1) README.md step 2, its second bash block, as written:\n%s\n' "$blk"
[ -n "$blk" ] || { echo '## (1) block not found'; exit 1; }
eval "$blk"; r1=$?
printf '## (1) exit=%s\n' "$r1"
[ "$r1" = 0 ] || fail=1
blk2=$(awk '/^## Engine acquisition/{s=1} /^## Push runtime/{s=0} s && /^```bash$/{n++; f=1; next} s && /^```$/{f=0; next} s && f && n==1' android/README.md | grep -v 'fetch_llama_android.sh')
printf '## (2) android/README.md "Engine acquisition", its first bash block as written (the fetch_llama line left out):\n%s\n' "$blk2"
[ -n "$blk2" ] || { echo '## (2) block not found'; exit 1; }
d=$(mktemp -d ~/verify-android-readme.XXXXXX)
mkdir -p "$d/android" && cp android/engine-pins.json "$d/android/"
( cd "$d" && eval "$blk2" ); r2=$?
printf '## (2) exit=%s\n' "$r2"
T=$(python3 -c 'import json; print(json.load(open("android/engine-pins.json"))["android_pins"]["litert-lm"])')
ls -la "$d/android/bin/$T"
if diff <(cd "$d/android/bin/$T" && sha256sum * | sort) <(cd "android/bin/$T" && sha256sum * | sort); then
  printf '## (2) the %s files equal README step 2'"'"'s android/bin/%s byte for byte\n' "$(ls "$d/android/bin/$T" | wc -l)" "$T"
else
  echo '## (2) the files differ from README step 2'"'"'s'; fail=1
fi
[ "$r2" = 0 ] || fail=1
rm -rf "$d"
exit "$fail"
