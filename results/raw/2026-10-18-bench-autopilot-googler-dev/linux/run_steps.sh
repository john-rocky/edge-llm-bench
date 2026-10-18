#!/bin/bash
# ROUND6 driver (stage 5, the one command): the container steps of `./bench autopilot` from a clean Ubuntu 24.04, one
# after another; each step starts only after the Mac measurement window is closed (quiet_wait.py before every step)
# and appends its output to K/linux/<log>. The form of results/raw/2026-10-16-googler-first-run-dev/linux/run_steps.sh.
#   bash run_steps.sh [main|update|session|after|update2|session2|r1-tar]   (after: TAG=r1|r2)
#   START_AT=<step> resumes the phase at that step; ONLY="<step> <step>" runs just those steps.
# Writes K/linux/steps.tsv (step, start, end, seconds, rc, log), K/linux/STOPPED_AT (a fatal step that failed),
# K/linux/FAILED_STEPS (non-fatal steps that failed) and, always last, K/linux/run_steps.done.
WT=$HOME/code/edge-llm-bench-wt-autopilot-googler
K=$WT/results/raw/2026-10-18-bench-autopilot-googler-dev
L=$K/linux
C=elb-autopilot-googler
QW=$HOME/code/standup/tools/quiet/quiet_wait.py
STEPS_IN=/opt/elb-steps
# a scratch dir for the bundle, the base commit and the patches (this round's run used the session's scratchpad)
SCRATCH=${SCRATCH:?set SCRATCH to a scratch dir}
BUNDLE=$SCRATCH/repo.bundle
TSV=$L/steps.tsv
DONE=$L/run_steps.done
PHASE=${1:-main}
started=0
[ -n "${START_AT:-}" ] || started=1
rm -f "$DONE" "$L/STOPPED_AT" "$L/FAILED_STEPS"
[ -f "$TSV" ] || printf 'step\tstart\tend\tseconds\trc\tlog\n' > "$TSV"

stamp() { date '+%F %T %Z'; }
finish() { printf '%s %s\n' "$(stamp)" "$1" | tee "$DONE"; exit "$2"; }

want() {  # want <step>: does this invocation run it?
  if [ -n "${ONLY:-}" ]; then
    case " $ONLY " in *" $1 "*) return 0 ;; *) return 1 ;; esac
  fi
  if [ "$started" = 0 ]; then
    [ "$1" = "$START_AT" ] || return 1
    started=1
  fi
  return 0
}

dexec() {  # dexec root|dev <step script>: one step script inside the container (dev = a login shell, as a terminal)
  if [ "$1" = dev ]; then
    docker exec -u dev -w /home/dev -e HOME=/home/dev -e USER=dev -e LOGNAME=dev -e SHELL=/bin/bash -e LANG=C.UTF-8 \
      "$C" bash -l "$STEPS_IN/$2"
  else
    docker exec -u root -w /root -e LANG=C.UTF-8 "$C" bash "$STEPS_IN/$2"
  fi
}

step() {  # step <name> <log> <fatal 1|0> <command...>
  name=$1; log=$2; fatal=$3; shift 3
  want "$name" || return 0
  printf '%s %s: ' "$(stamp)" "$name" >> "$L/quiet_wait.log"
  python3 "$QW" --max-wait 21600 -- true >> "$L/quiet_wait.log" 2>&1
  q=$?
  if [ "$q" != 0 ]; then echo "$name (quiet_wait rc $q)" > "$L/STOPPED_AT"; finish "stopped before $name: quiet_wait rc $q" 1; fi
  s0=$(stamp); t0=$(date +%s)
  printf '\n## step %s | start %s | %s\n' "$name" "$s0" "$*" >> "$L/$log"
  echo "$s0 start $name"
  "$@" >> "$L/$log" 2>&1
  rc=$?
  s1=$(stamp); t1=$(date +%s)
  printf '## step %s | end %s | rc %s | %s s\n' "$name" "$s1" "$rc" "$((t1 - t0))" >> "$L/$log"
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$name" "$s0" "$s1" "$((t1 - t0))" "$rc" "$log" >> "$TSV"
  echo "$s1 end $name rc $rc ($((t1 - t0)) s)"
  if [ "$rc" != 0 ]; then
    if [ "$fatal" = 1 ]; then echo "$name" > "$L/STOPPED_AT"; finish "stopped at $name (rc $rc)" "$rc"; fi
    echo "$name rc $rc" >> "$L/FAILED_STEPS"
  fi
  return 0
}

# ---------------------------------------------------------------- host-side steps
h_image() {  # the image already in colima's store (the digest D3 ran); not pulled again
  docker image inspect ubuntu:24.04 --format 'RepoDigests={{json .RepoDigests}} Id={{.Id}} {{.Os}}/{{.Architecture}} Created={{.Created}}'
  docker info --format 'server {{.ServerVersion}} cpus {{.NCPU}} mem {{.MemTotal}} os {{.OperatingSystem}} kernel {{.KernelVersion}}'
  printf 'client %s; %s\n' "$(docker version --format '{{.Client.Version}}')" "$(colima version | head -1)"
}
h_run() {
  docker run -d --name "$C" --memory 6g ubuntu:24.04 sleep infinity || return 1
  docker inspect "$C" --format 'Name={{.Name}} Image={{.Config.Image}} Running={{.State.Running}} Memory={{.HostConfig.Memory}}'
}
ensure_up() {  # the container running, the step scripts in it (every phase, every resume)
  if [ "$(docker inspect -f '{{.State.Running}}' "$C" 2>/dev/null)" != true ]; then
    docker start "$C" > /dev/null || return 1
  fi
  docker cp "$L/steps/." "$C:$STEPS_IN"
}
h_gcloud_copy() {  # the Mac's gcloud sign-in into dev's ~/.config/gcloud, without its logs/ and the ADC file
  docker exec -u dev "$C" mkdir -p /home/dev/.config || return 1
  COPYFILE_DISABLE=1 tar -C "$HOME/.config" --exclude 'gcloud/logs' --exclude 'gcloud/application_default_credentials.json' \
    --no-xattrs --no-mac-metadata -cf - gcloud | docker cp - "$C:/home/dev/.config" || return 1
  docker exec -u root "$C" chown -R dev:dev /home/dev/.config/gcloud || return 1
  printf '## gcloud config entries in the container: %s (names not listed)\n' \
    "$(docker exec -u dev "$C" find /home/dev/.config/gcloud -mindepth 1 | wc -l | tr -d ' ')"
}
h_bundle() {  # the host checkout's branch as a bundle into /opt/elb (the clone's origin); its tip = the base
  local tip
  tip=$(git -C "$WT" rev-parse bench-autopilot-googler) || return 1
  rm -f "$BUNDLE"
  git -C "$WT" bundle create "$BUNDLE" bench-autopilot-googler || return 1
  git -C "$WT" bundle verify "$BUNDLE" > /dev/null || return 1
  printf '## bundle: branch bench-autopilot-googler at %s, %s bytes, sha256 %s\n' "$tip" "$(stat -f %z "$BUNDLE")" \
    "$(shasum -a 256 < "$BUNDLE" | cut -d' ' -f1)"
  docker exec -u root "$C" mkdir -p /opt/elb || return 1
  docker cp "$BUNDLE" "$C:/opt/elb/repo.bundle" || return 1
  printf '%s\n' "$tip" > "$SCRATCH/base-commit"
  docker cp "$SCRATCH/base-commit" "$C:/opt/elb/base-commit" || return 1
  docker exec -u root "$C" chmod -R a+rX /opt/elb || return 1
  printf '## in the container: %s\n' "$(docker exec -u dev "$C" sha256sum /opt/elb/repo.bundle | cut -d' ' -f1)"
}
h_patch() {  # r5's 63ec5615 (bench-autopilot) as a patch for the clone only: no ref of the host repo is made or moved
  git -C "$WT" format-patch -1 63ec5615 --stdout > "$SCRATCH/63ec5615.patch" || return 1
  printf '## %s: %s bytes, sha256 %s\n' "63ec5615.patch" "$(stat -f %z "$SCRATCH/63ec5615.patch")" \
    "$(shasum -a 256 < "$SCRATCH/63ec5615.patch" | cut -d' ' -f1)"
  docker cp "$SCRATCH/63ec5615.patch" "$C:/opt/elb/63ec5615.patch" || return 1
  docker exec -u root "$C" chmod a+r /opt/elb/63ec5615.patch
}
h_r1_tar() {  # r1's dir without ddp-raw/ (the logcats before the scrub) -> K/container-campaign-r1.tar (untracked)
  local d=results/raw/2026-10-18-dashboard-v1-pixel8a-ddp-akita-35-android
  docker exec -u dev "$C" tar -C /home/dev/edge-llm-bench --exclude=ddp-raw -cf /tmp/campaign-r1.tar "$d" || return 1
  printf '## campaign-r1.tar: %s members, ddp-raw members %s\n' "$(docker exec -u dev "$C" tar -tf /tmp/campaign-r1.tar | wc -l | tr -d ' ')" \
    "$(docker exec -u dev "$C" tar -tf /tmp/campaign-r1.tar | grep -c 'ddp-raw')"
  docker cp "$C:/tmp/campaign-r1.tar" "$K/container-campaign-r1.tar" || return 1
  printf '## %s: %s bytes\n' "container-campaign-r1.tar" "$(stat -f %z "$K/container-campaign-r1.tar")"
}
h_patch2() {  # r5's 6e3d5908 (bench-autopilot) as a patch for the clone only
  git -C "$WT" format-patch -1 6e3d5908 --stdout > "$SCRATCH/6e3d5908.patch" || return 1
  printf '## %s: %s bytes, sha256 %s\n' "6e3d5908.patch" "$(stat -f %z "$SCRATCH/6e3d5908.patch")" \
    "$(shasum -a 256 < "$SCRATCH/6e3d5908.patch" | cut -d' ' -f1)"
  docker cp "$SCRATCH/6e3d5908.patch" "$C:/opt/elb/6e3d5908.patch" || return 1
  docker exec -u root "$C" chmod a+r /opt/elb/6e3d5908.patch
}
h_hf_copy() {  # the model's HF cache entry (refs/main, the snapshot link, the blob) from the host's cache; no download
  local H=$HOME/.cache/huggingface/hub M=models--litert-community--Qwen3-1.7B F=Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm rev blob
  rev=$(cat "$H/$M/refs/main") || return 1
  blob=$(readlink "$H/$M/snapshots/$rev/$F") || return 1
  printf '## host: refs/main %s, snapshots/%s/%s -> %s (%s bytes)\n' "$rev" "$rev" "$F" "$blob" "$(stat -f %z "$H/$M/blobs/${blob##*/}")"
  docker exec -u dev "$C" mkdir -p /home/dev/.cache/huggingface/hub || return 1
  # -n: the members named only (the repo folder holds other snapshots, blobs and engine caches), their dirs first
  COPYFILE_DISABLE=1 tar -C "$H" -n --no-xattrs --no-mac-metadata -cf - "$M" "$M/refs" "$M/refs/main" "$M/snapshots" \
    "$M/snapshots/$rev" "$M/snapshots/$rev/$F" "$M/blobs" "$M/blobs/${blob##*/}" \
    | docker cp - "$C:/home/dev/.cache/huggingface/hub" || return 1
  docker exec -u root "$C" chown -R dev:dev /home/dev/.cache || return 1
  docker exec -u dev "$C" find "/home/dev/.cache/huggingface/hub/$M" -mindepth 1 -printf '  %y %p %s\n'
}
h_copy_after() {  # after a billed run (TAG r1 / r2): the post's commits as a bundle, the job's log and ledgers, into K
  local camp TAG=${TAG:-r1}
  local day
  camp=$(docker exec -u dev "$C" bash -c 'cd /home/dev/edge-llm-bench && ls -d results/raw/*-dashboard-v1-pixel8a-ddp-akita-35*-android | tail -1')
  day=$(docker exec "$C" date +%F)   # the job names its log by the container's day (UTC)
  printf '## campaign %s\n' "$camp"
  if docker exec -u dev "$C" test -f /tmp/autopilot-commit.bundle; then
    docker cp "$C:/tmp/autopilot-commit.bundle" "$K/autopilot-commit-$TAG.bundle" || return 1
    printf '## %s: %s bytes, sha256 %s\n' "autopilot-commit-$TAG.bundle" "$(stat -f %z "$K/autopilot-commit-$TAG.bundle")" \
      "$(shasum -a 256 < "$K/autopilot-commit-$TAG.bundle" | cut -d' ' -f1)"
    git -C "$WT" bundle verify "$K/autopilot-commit-$TAG.bundle" || return 1
    git -C "$WT" fetch -q "$K/autopilot-commit-$TAG.bundle" bench-autopilot-googler || return 1
    printf '## host: git fetch <bundle> bench-autopilot-googler -> FETCH_HEAD %s (no branch moved)\n' "$(git -C "$WT" rev-parse FETCH_HEAD)"
    git -C "$WT" log -1 --stat --format='commit %H%nAuthor: %an <%ae>%nDate:   %cI%n%n    %s' FETCH_HEAD | cut -c1-400
  else
    echo '## no commit bundle (the post committed nothing): the campaign dir as a tar instead, ddp-raw/ left out'
    # ddp-raw/ holds the pulled logcats before the scrub (the lab network's identifiers): never copied out
    docker exec -u dev "$C" tar -C /home/dev/edge-llm-bench --exclude=ddp-raw -cf /tmp/campaign.tar "$camp" || return 1
    printf '## campaign.tar: %s members, ddp-raw members %s\n' "$(docker exec -u dev "$C" tar -tf /tmp/campaign.tar | wc -l | tr -d ' ')" \
      "$(docker exec -u dev "$C" tar -tf /tmp/campaign.tar | grep -c 'ddp-raw')"
    docker cp "$C:/tmp/campaign.tar" "$K/container-campaign-$TAG.tar" || return 1
  fi
  for f in "logs/dashboard-job/$day-pixel8a-ddp.log" logs/dashboard-job/ledger.tsv logs/dashboard-job/autopilot-ledger.tsv; do
    docker cp "$C:/home/dev/edge-llm-bench/$f" "$L/container-$TAG-$(basename "$f")" && printf '## copied %s\n' "$f"
  done
  docker cp "$C:/home/dev/edge-llm-bench/logs/autopilot/$(basename "$camp")/." "$L/container-$TAG-autopilot-out" \
    && printf '## copied logs/autopilot/%s/\n' "$(basename "$camp")"
}

# ---------------------------------------------------------------- phases
case "$PHASE" in
  main)
    step image 01-admin.log 1 h_image
    step run 01-admin.log 1 h_run
    ensure_up || finish "container $C not up" 1
    step apt-base 01-admin.log 1 dexec root 10-apt-base.sh
    step user 01-admin.log 1 dexec root 11-user.sh
    step apt-python 01-admin.log 1 dexec root 13-apt-python.sh
    step gcloud-install 01-admin.log 1 dexec dev 15-gcloud-install.sh
    step venv 02-venv-gcloud.log 1 dexec dev 20-readme1-venv.sh
    step gcloud-copy 02-venv-gcloud.log 1 h_gcloud_copy
    step gcloud 02-venv-gcloud.log 1 dexec dev 22-gcloud.sh
    step bundle 03-clone-asset.log 1 h_bundle
    step clone 03-clone-asset.log 1 dexec dev 30-clone.sh
    step asset 03-clone-asset.log 1 dexec dev 31-asset.sh
    step git-identity 03-clone-asset.log 1 dexec dev 32-git-identity.sh
    step hf-copy 04-hf-cache.log 1 h_hf_copy
    step hf-probe 04-hf-cache.log 0 dexec dev 33-hf-probe.sh
    step doctor 05-doctor.log 0 dexec dev 40-doctor.sh
    step selftests 06-selftests.log 0 dexec dev 50-selftests.sh
    step dryrun 07-dryrun.log 0 dexec dev 60-dryrun.sh
    step versions 08-versions.log 0 dexec dev 16-versions.sh
    ;;
  update)  # after the go: the host branch's new tip, then 63ec5615 in the clone only (the supervisor's decision (2))
    ensure_up || finish "container $C not up" 1
    step bundle-2 09-update.log 1 h_bundle
    step patch 09-update.log 1 h_patch
    step update 09-update.log 1 dexec dev 34-update.sh
    ;;
  session)
    ensure_up || finish "container $C not up" 1
    step session 10-session.log 0 dexec dev 70-session.sh
    ;;
  update2)  # the retake's go (23:5x): r5's 6e3d5908 (.gitignore: an execution's own logcat.txt) in the clone only
    ensure_up || finish "container $C not up" 1
    step patch-2 12-update2.log 1 h_patch2
    step update2 12-update2.log 1 dexec dev 35-update2.sh
    ;;
  session2)
    ensure_up || finish "container $C not up" 1
    step session-r2 13-session-r2.log 0 dexec dev 71-session-r2.sh
    ;;
  r1-tar)  # the r1 sitting's dir (FAILED, kept as evidence) as a tar without ddp-raw/; r1's after phase made none
    ensure_up || finish "container $C not up" 1
    step r1-tar 11-after.log 0 h_r1_tar
    ;;
  after)
    ensure_up || finish "container $C not up" 1
    step after 11-after.log 0 dexec dev 80-after.sh
    step copy-after 11-after.log 0 h_copy_after
    ;;
  *) finish "unknown phase $PHASE" 2 ;;
esac
[ -n "${ONLY:-}" ] || [ "$started" = 1 ] || finish "START_AT=$START_AT names no step of phase $PHASE" 2
if [ -f "$L/FAILED_STEPS" ]; then finish "phase $PHASE done; non-fatal failures: $(tr '\n' ';' < "$L/FAILED_STEPS")" 0; fi
finish "phase $PHASE done" 0
