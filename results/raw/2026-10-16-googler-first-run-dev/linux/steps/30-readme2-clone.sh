# README step 2 (README.md lines 126-130, verbatim between the markers), as dev, in the shell state of step 1
# (a terminal keeps step 1's venv active; a fresh docker exec does not, hence the activate line).
. ~/elb-venv/bin/activate
# --- README.md:126-130 ---
git clone https://github.com/john-rocky/edge-llm-bench && cd edge-llm-bench
TAG=$(python3 -c 'import json; print(json.load(open("android/engine-pins.json"))["android_pins"]["litert-lm"])')
mkdir -p android/bin
curl -fL https://github.com/john-rocky/edge-llm-bench/releases/download/android-litert-lm-$TAG/litert-lm-$TAG-android-arm64.tar.gz \
  | tar xz -C android/bin && mv android/bin/litert-lm-$TAG-android-arm64 android/bin/$TAG
# --- end ---
rc=$?
printf '## README block rc (its last list)=%s\n' "$rc"
printf '## pwd=%s TAG=%s\n' "$(pwd)" "$TAG"
git log -1 --format='## HEAD %H %cI'
printf '## git status --short: %s line(s)\n' "$(git status --short | wc -l)"
ls -la "android/bin/$TAG"
printf '## files in android/bin/%s: %s\n' "$TAG" "$(ls "android/bin/$TAG" | wc -l)"
if [ -f "android/bin/$TAG/SHA256SUMS" ]; then ( cd "android/bin/$TAG" && sha256sum -c SHA256SUMS ) || exit 1; else echo '## no SHA256SUMS in the asset'; fi
du -sh "android/bin/$TAG" .git
[ "$rc" = 0 ] && [ -d "android/bin/$TAG" ]
