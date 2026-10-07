#!/system/bin/sh
# One engine launch with a 0.5 s on-device sampler (ORT GenAI Galaxy S26 smoke,
# round r2, 2026-10-07, by hand; android/bench/run_cell.py run_once samples the
# same way for the wired arms).
# usage: sh run_sampled.sh <tag> <binary> [engine args...]
# Writes out/<tag>.engine.txt (engine stdout + stderr, read after exit: a
# backgrounded engine's stdout races the adb pty teardown) and
# out/<tag>.sampler.txt: every cpufreq policy once (hardware max, current cap,
# CPUs), the launch line, then per tick the uptime, the engine's VmRSS / VmHWM /
# Cpus_allowed_list, its socket fd count, and every policy's scaling_max_freq
# whenever it changes.
D=/data/local/tmp/llmbench/ortgenai
cd $D || exit 1
tag=$1
bin=$2
shift 2
mkdir -p out
eng=$D/out/$tag.engine.txt
smp=$D/out/$tag.sampler.txt
if [ -e $smp ] || [ -e $eng ]; then echo "refusing to overwrite out/$tag.*"; exit 1; fi
for p in /sys/devices/system/cpu/cpufreq/policy*; do
  read hw <$p/cpuinfo_max_freq; read cap <$p/scaling_max_freq; read cpus <$p/related_cpus
  echo "CPUPOLICY ${p##*/} hw=$hw cap=$cap cpus=$cpus" >>$smp
done
LD_LIBRARY_PATH=$D ORT_LIB_PATH=$D/libonnxruntime.so ORT_DISABLE_TELEMETRY=1 ./$bin "$@" >$eng 2>&1 </dev/null &
pid=$!
sleep 0.2
exe=$(readlink /proc/$pid/exe)
case $exe in
  */$bin) epid=$pid ;;
  *) epid=$(pgrep -n -f "^\./$bin") ;;
esac
read up rest </proc/uptime
echo "LAUNCH uptime=$up pid=$pid engine_pid=$epid exe=$exe cmd=./$bin $*" >>$smp
pc=
while kill -0 $epid 2>/dev/null; do
  read up rest </proc/uptime
  t="TICK $up"
  while read k v u; do
    case $k in VmRSS:|VmHWM:|Cpus_allowed_list:) t="$t $k$v" ;; esac
  done 2>/dev/null </proc/$epid/status
  n=0
  for l in $(ls -l /proc/$epid/fd 2>/dev/null); do
    case $l in socket:*) n=$((n + 1)) ;; esac
  done
  echo "$t sockets=$n" >>$smp
  c=CPUMAX
  for f in /sys/devices/system/cpu/cpufreq/policy*/scaling_max_freq; do read m <$f; c="$c $m"; done
  [ "$c" = "$pc" ] || echo "$c uptime=$up" >>$smp
  pc=$c
  sleep 0.5
done
wait $pid
ec=$?
read up rest </proc/uptime
echo "EXIT_CODE=$ec uptime=$up" >>$smp
echo "EXIT_CODE=$ec"
