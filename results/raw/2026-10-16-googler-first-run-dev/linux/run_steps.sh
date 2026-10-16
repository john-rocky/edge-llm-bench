#!/bin/bash
# D3S4 r1 / r2 driver: the container steps of the Linux first run, one after another; each step starts only after the
# Mac measurement window is closed (quiet_wait.py before every step) and appends its output to K/linux/<log>.
#   bash run_steps.sh [main|verify|r2-dry|r2-session|r2-after]
#   START_AT=<step> resumes the phase at that step; ONLY="<step> <step>" runs just those steps.
# Writes K/linux/steps.tsv (step, start, end, seconds, rc, log), K/linux/STOPPED_AT (a fatal step that failed),
# K/linux/FAILED_STEPS (non-fatal steps that failed) and, always last, K/linux/run_steps.done.
K=$HOME/code/edge-llm-bench-wt-googler/results/raw/2026-10-16-googler-first-run-dev
WT=$HOME/code/edge-llm-bench-wt-googler
L=$K/linux
C=elb-googler-first-run
QW=$HOME/code/standup/tools/quiet/quiet_wait.py
STEPS_IN=/opt/elb-steps
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
h_pull() {
  docker pull ubuntu:24.04 || return 1
  docker image inspect ubuntu:24.04 --format 'RepoDigests={{json .RepoDigests}} Id={{.Id}} {{.Os}}/{{.Architecture}} Created={{.Created}}'
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
h_copy_cells() {  # the worktree's new cells file into the clone (not on GitHub main yet)
  docker cp "$WT/matrices/ddp-first-run.cells" "$C:/home/dev/edge-llm-bench/matrices/ddp-first-run.cells" || return 1
  docker exec -u root "$C" chown dev:dev /home/dev/edge-llm-bench/matrices/ddp-first-run.cells || return 1
  printf '## sha256 worktree %s\n' "$(shasum -a 256 < "$WT/matrices/ddp-first-run.cells" | cut -d' ' -f1)"
  printf '## sha256 clone    %s\n' "$(docker exec -u dev "$C" sha256sum /home/dev/edge-llm-bench/matrices/ddp-first-run.cells | cut -d' ' -f1)"
}
h_offline() {  # 80-offline.sh with the container off its network; reconnected whatever the probe says
  docker network disconnect bridge "$C" || return 1
  dexec dev 80-offline.sh; prc=$?
  docker network connect bridge "$C"; crc=$?
  printf '## network reconnected rc=%s; probe rc=%s\n' "$crc" "$prc"
  [ "$crc" = 0 ] || return 2
  return "$prc"
}
h_copy_readmes() {  # the worktree's fixed READMEs into the clone, to run their changed lines as written
  for f in README.md android/README.md; do
    docker cp "$WT/$f" "$C:/home/dev/edge-llm-bench/$f" || return 1
    docker exec -u root "$C" chown dev:dev "/home/dev/edge-llm-bench/$f" || return 1
    printf '## %s sha256 worktree %s clone %s\n' "$f" "$(shasum -a 256 < "$WT/$f" | cut -d' ' -f1)" \
      "$(docker exec -u dev "$C" sha256sum "/home/dev/edge-llm-bench/$f" | cut -d' ' -f1)"
  done
}
h_copy_into_clone() {  # r2: h_copy_into_clone <path>...: the worktree's files into the clone, owned by dev
  for f in "$@"; do
    docker cp "$WT/$f" "$C:/home/dev/edge-llm-bench/$f" || return 1
    docker exec -u root "$C" chown dev:dev "/home/dev/edge-llm-bench/$f" || return 1
    printf '## %s sha256 worktree %s clone %s\n' "$f" "$(shasum -a 256 < "$WT/$f" | cut -d' ' -f1)" \
      "$(docker exec -u dev "$C" sha256sum "/home/dev/edge-llm-bench/$f" | cut -d' ' -f1)"
  done
}
h_doctor_mac() {  # r2: the worktree's `bench doctor --platform ddp` on the Mac -> K/doctor-ddp-mac.log (user name ->
  # USER); adb left off PATH, so the doctor reaches no attached phone (no phone in this round); the pinned engine
  # files are the main checkout's (the worktree has no android/bin)
  local p rc out=$K/doctor-ddp-mac.log
  p=$(printf '%s' "$PATH" | tr ':' '\n' | grep -v '/platform-tools$' | paste -sd: -)
  {
    printf '## %s; python3 = %s (%s); adb on PATH: %s\n' "$(stamp)" "$(PATH=$p command -v python3)" \
      "$(PATH=$p python3 --version 2>&1)" "$(PATH=$p command -v adb || echo none)"
    printf '## BENCH_ANDROID_BIN_DIR=%s\n' "$HOME/code/edge-llm-bench/android/bin"
    PATH=$p BENCH_ANDROID_BIN_DIR=$HOME/code/edge-llm-bench/android/bin "$WT/bench" doctor --platform ddp 2>&1
    rc=$?
    printf '## %s bench doctor --platform ddp exit=%s\n' "$(stamp)" "$rc"
  } > "$out.tmp"
  sed "s/$(id -un)/USER/g" "$out.tmp" > "$out" && rm -f "$out.tmp"
  printf '## written %s (exit %s)\n' "${out#"$WT"/}" "$rc"
  return "$rc"
}
h_fresh_venv() {  # r2: 99-fresh-venv.sh in a throwaway ubuntu:24.04 container (removed when it exits)
  docker image inspect ubuntu:24.04 --format 'image {{index .RepoDigests 0}} {{.Os}}/{{.Architecture}}'
  docker run --rm -i --memory 2g ubuntu:24.04 bash -s < "$L/steps/99-fresh-venv.sh"
}
h_clone_state() {  # r2: the clone's copies of r1's changed files = the worktree's committed ones
  for f in README.md android/README.md matrices/ddp-first-run.cells; do
    printf '## %s sha256 worktree HEAD %s clone %s\n' "$f" "$(git -C "$WT" show "HEAD:$f" | shasum -a 256 | cut -d' ' -f1)" \
      "$(docker exec -u dev "$C" sha256sum "/home/dev/edge-llm-bench/$f" | cut -d' ' -f1)"
  done
}

# ---------------------------------------------------------------- phases
case "$PHASE" in
  main)
    step pull 01-admin.log 1 h_pull
    step run 01-admin.log 1 h_run
    ensure_up || finish "container $C not up" 1
    step apt-base 01-admin.log 1 dexec root 10-apt-base.sh
    step user 01-admin.log 1 dexec root 11-user.sh
    step probe-no-venv 01-admin.log 0 dexec dev 12-probe-no-venv.sh
    step apt-python 01-admin.log 1 dexec root 13-apt-python.sh
    step probe-pip 01-admin.log 0 dexec dev 14-probe-pip-outside-venv.sh
    step gcloud-install 01-admin.log 1 dexec dev 15-gcloud-install.sh
    step readme1-venv 02-venv.log 1 dexec dev 20-readme1-venv.sh
    step gcloud-copy 02-gcloud.log 1 h_gcloud_copy
    step readme1-gcloud 02-gcloud.log 1 dexec dev 22-readme1-gcloud.sh
    step readme2-clone 03-clone-asset.log 1 dexec dev 30-readme2-clone.sh
    step doctor 04-doctor.log 0 dexec dev 40-doctor.sh
    step selftest 05-selftest.log 0 dexec dev 50-selftest.sh
    step copy-cells 07-dryrun-first-run.log 1 h_copy_cells
    step dryrun-dashboard 06-dryrun-dashboard.log 0 dexec dev 60-dryrun-dashboard.sh
    step dryrun-first-run 07-dryrun-first-run.log 0 dexec dev 70-dryrun-first-run.sh
    step offline 08-offline.log 0 h_offline
    step versions 09-versions.log 0 dexec dev 16-versions.sh
    ;;
  verify)
    ensure_up || finish "container $C not up" 1
    step copy-readmes 10-verify-readme.log 1 h_copy_readmes
    step verify-readme 10-verify-readme.log 0 dexec dev 90-verify-readme.sh
    ;;
  r2-dry)
    ensure_up || finish "container $C not up" 1
    step clone-state 09-dryrun-before-session.log 1 h_clone_state
    step before-session 09-dryrun-before-session.log 1 dexec dev 91-before-session.sh
    step dryrun-before-session 09-dryrun-before-session.log 1 dexec dev 92-dryrun-before-session.sh
    ;;
  r2-session)
    ensure_up || finish "container $C not up" 1
    step session 10-session.log 0 dexec dev 95-session.sh
    ;;
  r2-after)
    ensure_up || finish "container $C not up" 1
    step model-blob 10-session.log 0 dexec dev 93-model-blob.sh
    step doctor-before 08-doctor-ddp.log 1 dexec dev 96-doctor-before.sh
    step copy-doctor 08-doctor-ddp.log 1 h_copy_into_clone bench scripts/doctor.py
    step doctor-ddp 08-doctor-ddp.log 0 dexec dev 97-doctor-ddp.sh
    step doctor-mac 08-doctor-ddp.log 0 h_doctor_mac
    step copy-docs 11-verify-docs.log 1 h_copy_into_clone README.md docs/OPERATIONS.md
    step verify-docs 11-verify-docs.log 0 dexec dev 98-verify-docs.sh
    step fresh-venv 11-verify-docs.log 0 h_fresh_venv
    ;;
  *) finish "unknown phase $PHASE" 2 ;;
esac
[ -n "${ONLY:-}" ] || [ "$started" = 1 ] || finish "START_AT=$START_AT names no step of phase $PHASE" 2
if [ -f "$L/FAILED_STEPS" ]; then finish "phase $PHASE done; non-fatal failures: $(tr '\n' ';' < "$L/FAILED_STEPS")" 0; fi
finish "phase $PHASE done" 0
