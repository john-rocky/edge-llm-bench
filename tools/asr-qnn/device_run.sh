#!/system/bin/sh
# One measured process on the phone (asr-qnn-v1), started under nohup by run_qnn_s26.sh. Android's
# /system/bin/sh (mksh): $EPOCHREALTIME, builtin read. asr-sherpa-v1's device_run.sh with the QNN
# environment and a second mode for the driver.
#
#   sh device_run.sh <tag> cli <list> <flag>...     bin/sherpa-onnx-offline-parallel <flags> --wav-scp=<list>
#   sh device_run.sh <tag> driver <flag>...         bin/asr-qnn-burst-driver <flags> --out=runs/<tag>.jsonl
#                                                     --ceil-log=runs/<tag>.ceil.log --tag=<tag>
#
# Environment of both (sherpa's QNN docs): LD_LIBRARY_PATH=$P/lib (libonnxruntime.so and the QNN client
# libraries), ADSP_LIBRARY_PATH="$P/lib;<previous>" (the FastRPC client looks for libQnnHtpV81Skel.so there;
# the separator is ';'). Writes $P/runs/<tag>*:
#   .stdout.log   the binary's stdout: the QNN log callback's lines (both modes) and, for cli, one JSON
#                 result per decoded file in list order
#   .stderr.log   the binary's stderr, each line prefixed by the phone's $EPOCHREALTIME and a tab when it
#                 arrives (stderr is unbuffered; cli: the file name line follows the file's decode, "----"
#                 closes it; driver: "[asr-qnn] begin / end" around every attempt)
#   .vmhwm.log    1 s samples: epoch VmHWM_kB VmRSS_kB Threads, each cpufreq policy's scaling_max_freq (kHz)
#   .cpus         the process's Cpus_allowed_list; .cgroup: its /proc/<pid>/cgroup (the cpuset line)
#   .exit         rc, epoch before / after the exec, pid
#   .stall        written when the stderr log stopped growing for STALL_S s (process killed)
#   .hangs        cli only: one line per stalled file; the next attempt (<tag>.a2.*, ...) runs the first list
#                 line (the warm-up file), the finished files whose result was still in the binary's stdout
#                 buffer when it was killed, and the files after the stalled one
#   .done         written last
P=${P:-/data/local/tmp/edge-llm-bench/asr-qnn}
R=$P/runs
STALL_S=${STALL_S:-600}
MAX_ATTEMPTS=${MAX_ATTEMPTS:-4}
tag=$1; mode=$2; shift 2
case $mode in
  cli) list0=$1; shift; bin=$P/bin/sherpa-onnx-offline-parallel ;;
  driver) list0=; bin=$P/bin/asr-qnn-burst-driver ;;
  *) echo "mode must be cli or driver" >&2; exit 2 ;;
esac
FLAGS="$*"            # for the log line
set -A FLAGV -- "$@"  # for the exec: a flag value with spaces stays one argument
mkdir -p $R
cd $P
export LD_LIBRARY_PATH=$P/lib
export ADSP_LIBRARY_PATH="$P/lib;$ADSP_LIBRARY_PATH"

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
  echo "$hdr" > $sbase.vmhwm.log
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
    [ -n "$hwm" ] && echo "$(now) $hwm $rss $thr$f" >> $sbase.vmhwm.log
    [ -n "$cal" ] && [ ! -f $sbase.cpus ] && echo "$cal" > $sbase.cpus
    [ -r /proc/$spid/cgroup ] && [ ! -f $sbase.cgroup ] && cat /proc/$spid/cgroup > $sbase.cgroup 2>/dev/null
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
  rm -f $base.stall $base.cpus $base.cgroup $base.pid $base.rc
  case $mode in
    cli) args="--wav-scp=$list" ;;
    driver) args="--out=$base.jsonl --ceil-log=$base.ceil.log --tag=${base##*/}" ;;
  esac
  # stderr goes through a pipe into the stamper (mkfifo is denied in /data/local/tmp on Android 16);
  # the sh -c wrapper writes its pid and execs the binary, so the pid is the binary's; pipefail keeps its rc
  t0=$(now)
  ( set -o pipefail
    sh -c 'echo $$ > "$0"; exec "$@"' $base.pid $bin "${FLAGV[@]}" $args 2>&1 1>$base.stdout.log | stamp > $base.stderr.log
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

echo "$(now) start $tag mode=$mode list=$list0 bin=$bin flags=$FLAGS policies=$policies LD_LIBRARY_PATH=$LD_LIBRARY_PATH ADSP_LIBRARY_PATH=$ADSP_LIBRARY_PATH"
rm -f $R/$tag.done $R/$tag.hangs
if [ $mode = driver ]; then
  attempt $R/$tag ""
  echo "$(now) attempts=1" > $R/$tag.done
  echo "$(now) done $tag attempts=1"
  exit 0
fi
cp $list0 $R/$tag.scp; list0=$R/$tag.scp  # the run keeps its own copy of its list
k=1; list=$list0; base=$R/$tag
while :; do
  attempt $base $list
  [ -f $base.stall ] || break
  n=$(grep -c "	----\$" $base.stderr.log)  # files finished (stderr is unbuffered)
  j=$(grep -c "^{" $base.stdout.log)         # their results that left the stdout buffer
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
