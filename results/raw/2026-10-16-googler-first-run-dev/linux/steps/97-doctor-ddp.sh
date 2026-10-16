# r2: the changed bench + scripts/doctor.py (copied in by the driver), as dev, in step 1's venv:
# (1) `./bench doctor` again: the diff with 96-doctor-before.sh's output must be added lines only;
# (2) `./bench doctor --platform ddp` as the quickstart prints it (expected exit 0);
# (3) the failure paths with --platform ddp (expected exit 1 and the FAIL line with its fix): gcloud signed out
#     (an empty CLOUDSDK_CONFIG), no gcloud on PATH, no huggingface_hub (the system python3, no venv), no engine
#     files, one engine file with other bytes; (4) the signed-out case without --platform (expected: warn, exit 0).
. ~/elb-venv/bin/activate
cd ~/edge-llm-bench || exit 1
fail=0
T=$(python3 -c 'import json; print(json.load(open("android/engine-pins.json"))["android_pins"]["litert-lm"])')
expect() {  # expect <case> <wanted exit> <command...>: run, print, compare the exit code
  name=$1; want=$2; shift 2
  printf '\n## case %s: %s\n' "$name" "$*"
  "$@" 2>&1; got=$?
  printf '## case %s: exit=%s (expected %s)\n' "$name" "$got" "$want"
  [ "$got" = "$want" ] || fail=1
}

./bench doctor > ~/doctor-after.txt 2>&1
printf '## (1) ./bench doctor (after) exit=%s; diff before -> after:\n' "$?"
diff ~/doctor-before.txt ~/doctor-after.txt
printf '## (1) lines removed or changed: %s; lines added: %s\n' \
    "$(diff ~/doctor-before.txt ~/doctor-after.txt | grep -c '^<')" "$(diff ~/doctor-before.txt ~/doctor-after.txt | grep -c '^>')"
[ "$(diff ~/doctor-before.txt ~/doctor-after.txt | grep -c '^<')" = 0 ] || fail=1

expect ddp 0 ./bench doctor --platform ddp

empty=$(mktemp -d ~/doctor-gcloud-config.XXXXXX)
expect signed-out 1 env CLOUDSDK_CONFIG="$empty" ./bench doctor --platform ddp
expect signed-out-not-required 0 env CLOUDSDK_CONFIG="$empty" ./bench doctor
rm -rf "$empty"

onlypy=$(mktemp -d ~/doctor-path.XXXXXX)
printf '#!/bin/sh\nexec /home/dev/elb-venv/bin/python3 "$@"\n' > "$onlypy/python3" && chmod +x "$onlypy/python3"
expect no-gcloud 1 env PATH="$onlypy" ./bench doctor --platform ddp
rm -rf "$onlypy"

expect no-huggingface_hub 1 env PATH=/usr/local/bin:/usr/bin:/bin ./bench doctor --platform ddp

nobin=$(mktemp -d ~/doctor-bin.XXXXXX)
expect no-engine-files 1 env BENCH_ANDROID_BIN_DIR="$nobin" ./bench doctor --platform ddp
mkdir -p "$nobin/$T"
for f in android/bin/"$T"/*; do ln -s "$PWD/$f" "$nobin/$T/$(basename "$f")"; done
rm "$nobin/$T/libwebgpu_dawn.so" && printf 'x' > "$nobin/$T/libwebgpu_dawn.so"
expect engine-file-other-bytes 1 env BENCH_ANDROID_BIN_DIR="$nobin" ./bench doctor --platform ddp
rm -rf "$nobin"

printf '\n## doctor-ddp verdict: %s\n' "$([ "$fail" = 0 ] && echo 'every case as expected' || echo 'a case differs')"
exit "$fail"
