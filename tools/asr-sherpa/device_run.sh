#!/system/bin/sh
# One sherpa-onnx process on the phone (asr-sherpa-v1), started under nohup by
# run_sherpa_s26.sh. Android's /system/bin/sh (mksh): $EPOCHREALTIME, builtin read.
#
#   sh device_run.sh <tag> <list> <binary> <flag>...
#
# <list> holds "id path" lines. sherpa-onnx-offline-parallel gets it as --wav-scp=<list>;
# any other binary gets the paths as positional arguments (one batch). Writes $P/runs/<tag>*:
#   .stdout.log   the binary's stdout: one JSON result per decoded file, in list order
#   .stderr.log   the binary's stderr, each line prefixed by the phone's $EPOCHREALTIME and a
#                 tab when it arrives (stderr is unbuffered: the file name line follows the
#                 file's decode, the "----" line closes it)
#   .vmhwm.log    1 s samples: epoch VmHWM_kB VmRSS_kB Threads, each cpufreq policy's
#                 scaling_max_freq (kHz), battery temp (0.1 C)
#   .scp          the list as run; .cpus: the process's Cpus_allowed_list; .exit: rc, epoch
#                 before / after the exec, pid
#   .stall        written when the stderr log stopped growing for STALL_S s (process killed)
#   .hangs        one line per stalled file; the next attempt (<tag>.a2.*, ...) runs the first
#                 list line (the warm-up file), the finished files whose result was still in
#                 the binary's stdout buffer when it was killed, and the files after the stalled one
#   .done         written last
P=${P:-/data/local/tmp/edge-llm-bench/asr-sherpa}
R=$P/runs
STALL_S=${STALL_S:-600}
MAX_ATTEMPTS=${MAX_ATTEMPTS:-4}
tag=$1; list0=$2; bin=$3; shift 3
FLAGS="$*"
mkdir -p $R
cd $P
# The termux builds need libc++_shared.so, which a stock Android shell does not have (LOCK.json cxx_runtime).
[ -f $P/lib/libc++_shared.so ] && export LD_LIBRARY_PATH=$P/lib

if [ -n "$EPOCHREALTIME" ]; then
  stamp() { while IFS= read -r l; do print -r -- "$EPOCHREALTIME	$l"; done; }  # print -r: no escapes
  now() { echo "$EPOCHREALTIME"; }
else
  stamp() { while IFS= read -r l; do printf '%s\t%s\n' "$(date +%s.%N)" "$l"; done; }
  now() { date +%s.%N; }
fi

policies=
for d in /sys/devices/system/cpu/cpufreq/policy*; do
  [ -d "$d" ] && policies="$policies ${d##*/}"
done

sample() {  # <pid> <base>: VmHWM / VmRSS / clock ceilings every second, stall watchdog
  spid=$1; sbase=$2; i=0; last=-1; still=0
  hdr="# epoch VmHWM_kB VmRSS_kB Threads"
  for p in $policies; do hdr="$hdr ${p}_scaling_max_kHz"; done
  echo "$hdr battery_temp_0.1C" > $sbase.vmhwm.log
  hw="# cpuinfo_max_freq_kHz"
  for p in $policies; do v=; read -r v 2>/dev/null < /sys/devices/system/cpu/cpufreq/$p/cpuinfo_max_freq; hw="$hw $p=$v"; done
  echo "$hw" >> $sbase.vmhwm.log
  while kill -0 $spid 2>/dev/null; do
    hwm=; rss=; thr=; cal=
    while IFS= read -r l; do
      case $l in
        VmHWM:*) set -- ${l#VmHWM:}; hwm=$1 ;;
        VmRSS:*) set -- ${l#VmRSS:}; rss=$1 ;;
        Threads:*) set -- ${l#Threads:}; thr=$1 ;;
        Cpus_allowed_list:*) set -- ${l#Cpus_allowed_list:}; cal=$1 ;;
      esac
    done 2>/dev/null < /proc/$spid/status
    f=
    for p in $policies; do
      v=; read -r v 2>/dev/null < /sys/devices/system/cpu/cpufreq/$p/scaling_max_freq; f="$f $v"
    done
    bt=; read -r bt 2>/dev/null < /sys/class/power_supply/battery/temp
    [ -n "$hwm" ] && echo "$(now) $hwm $rss $thr$f $bt" >> $sbase.vmhwm.log
    [ -n "$cal" ] && [ ! -f $sbase.cpus ] && echo "$cal" > $sbase.cpus
    i=$((i + 1))
    if [ $((i % 10)) -eq 0 ]; then
      sz=$(wc -c < $sbase.stderr.log)
      if [ "$sz" = "$last" ]; then still=$((still + 10)); else still=0; last=$sz; fi
      if [ $still -ge $STALL_S ]; then
        echo "$(now) stderr unchanged ${still}s, killing $spid" > $sbase.stall
        kill $spid; sleep 5; kill -9 $spid 2>/dev/null
        break
      fi
    fi
    sleep 1
  done
}

attempt() {  # <base> <list>
  base=$1; list=$2
  rm -f $base.stall $base.cpus $base.pid $base.rc
  case ${bin##*/} in
    *-parallel) args="--wav-scp=$list" ;;
    *) args=; while read -r id path; do args="$args $path"; done < $list ;;
  esac
  # stderr goes through a pipe into the stamper (mkfifo is denied in /data/local/tmp on Android 16);
  # the sh -c wrapper writes its pid and execs the binary, so the pid is the binary's; pipefail keeps its rc
  t0=$(now)
  ( set -o pipefail
    sh -c 'echo $$ > "$0"; exec "$@"' $base.pid $bin $FLAGS $args 2>&1 1>$base.stdout.log | stamp > $base.stderr.log
    echo $? > $base.rc ) &
  job=$!
  i=0; while [ ! -s $base.pid ] && [ $i -lt 200 ]; do sleep 0.05; i=$((i + 1)); done
  pid=; read -r pid < $base.pid
  sample $pid $base &
  smp=$!
  wait $job
  t1=$(now)
  rc=; read -r rc < $base.rc
  kill $smp 2>/dev/null; wait $smp 2>/dev/null
  echo "rc=$rc t0=$t0 t1=$t1 pid=$pid list=$list" > $base.exit
  echo "$(now) attempt $base rc=$rc"
}

echo "$(now) start $tag list=$list0 bin=$bin flags=$FLAGS policies=$policies LD_LIBRARY_PATH=${LD_LIBRARY_PATH:-}"
rm -f $R/$tag.done $R/$tag.hangs
cp $list0 $R/$tag.scp; list0=$R/$tag.scp  # the run keeps its own copy of its list
k=1; list=$list0; base=$R/$tag
while :; do
  attempt $base $list
  [ -f $base.stall ] || break
  case ${bin##*/} in *-parallel) ;; *) break ;; esac
  n=$(grep -c "	----\$" $base.stderr.log)  # files finished (stderr is unbuffered)
  j=$(wc -l < $base.stdout.log)                # their results that left the stdout buffer
  hung=$(sed -n "$((n + 1))p" $list)
  echo "$(now) attempt=$k finished=$n with_result=$j hung=$hung" >> $R/$tag.hangs
  [ "$n" -eq 0 ] && break  # the warm-up file itself stalled
  k=$((k + 1))
  [ $k -gt $MAX_ATTEMPTS ] && break
  next=$R/$tag.a$k.scp
  lost=$((j + 1)); [ $lost -lt 2 ] && lost=2
  { head -n 1 $list0; [ $lost -le $n ] && sed -n "${lost},${n}p" $list; tail -n +$((n + 2)) $list; } > $next
  [ $(($(wc -l < $next))) -le 1 ] && break
  list=$next; base=$R/$tag.a$k
done
echo "$(now) attempts=$k" > $R/$tag.done
echo "$(now) done $tag attempts=$k"
