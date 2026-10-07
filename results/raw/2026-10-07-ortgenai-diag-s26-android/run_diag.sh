#!/system/bin/sh
# One engine launch with a 0.5 s on-device sampler, for the ORT GenAI Galaxy S26
# 1K prefill diagnosis (round r2b, 2026-10-07, by hand). The shape of round r2's
# results/raw/2026-10-07-ortgenai-smoke-s26-android/run_sampled.sh, plus: an
# optional CPU mask (taskset), the engine's thread count and the CPUs its
# running threads sit on, the current clock next to the cap, the battery
# temperature per tick, one look at what the engine's socket fds are, the
# engine's own logcat lines, a time limit, and a per-launch working directory
# (model_benchmark --profile_prefill writes its profile JSON into the cwd).
#
# usage: sh run_diag.sh <tag> <mask|-> <limit_s> <binary> [engine args...]
#   mask     taskset hex mask (c0 = cpus 6-7), or - for none
#   limit_s  the engine is killed (KILLED line, no result) after this many seconds
# Writes out/<tag>.engine.txt (engine stdout + stderr, read after exit),
# out/<tag>.sampler.txt, and out/<tag>.d/ (the engine's cwd: profile JSON).
# Sampler lines:
#   CPUPOLICY <policy> hw= cap= cpus=        every cpufreq policy, once
#   START uptime= battery_temp= thermal=     before the launch
#   LAUNCH uptime= pid= engine_pid= exe= mask= cmd=
#   TICK <uptime> VmRSS: VmHWM: Threads: Cpus_allowed_list: sockets= run=<cpu,...>
#        cur=<kHz per policy> bat=<deci-C>   run = last CPU of each thread in state R
#   CPUMAX <cap per policy> uptime=          whenever a cap changes
#   SOCKET fd=<n> inode=<i> / SOCKET_IN <table> <line> / SOCKET_IN none   once
#   EXIT_CODE= uptime= / KILLED uptime= limit_s=
#   END battery_temp= thermal= / LOGCAT_LINES= / LOGCAT <line> (first 15)
#   OUTDIR <file> <bytes>
D=/data/local/tmp/llmbench/ortgenai
cd $D || exit 1
tag=$1
mask=$2
limit=$3
bin=$4
shift 4
mkdir -p out
eng=$D/out/$tag.engine.txt
smp=$D/out/$tag.sampler.txt
wd=$D/out/$tag.d
if [ -e $smp ] || [ -e $eng ] || [ -e $wd ]; then echo "refusing to overwrite out/$tag.*"; exit 1; fi
mkdir -p $wd
for p in /sys/devices/system/cpu/cpufreq/policy*; do
  read hw <$p/cpuinfo_max_freq; read cap <$p/scaling_max_freq; read cpus <$p/related_cpus
  echo "CPUPOLICY ${p##*/} hw=$hw cap=$cap cpus=$cpus" >>$smp
done
bt=$(dumpsys battery | sed -n 's/^ *temperature: *//p')
th=$(dumpsys thermalservice | sed -n 's/^Thermal Status: *//p')
read up rest </proc/uptime
echo "START uptime=$up battery_temp=$bt thermal=$th online=$(cat /sys/devices/system/cpu/online)" >>$smp
cd $wd || exit 1
if [ "$mask" = "-" ]; then
  LD_LIBRARY_PATH=$D ORT_LIB_PATH=$D/libonnxruntime.so ORT_DISABLE_TELEMETRY=1 $D/$bin "$@" >$eng 2>&1 </dev/null &
else
  LD_LIBRARY_PATH=$D ORT_LIB_PATH=$D/libonnxruntime.so ORT_DISABLE_TELEMETRY=1 taskset $mask $D/$bin "$@" >$eng 2>&1 </dev/null &
fi
pid=$!
sleep 0.2
exe=$(readlink /proc/$pid/exe)
case $exe in
  */$bin) epid=$pid ;;
  *) epid=$(pgrep -n -f "$D/$bin") ;;
esac
read up rest </proc/uptime
t0=${up%%.*}
echo "LAUNCH uptime=$up pid=$pid engine_pid=$epid exe=$exe mask=$mask cmd=$bin $*" >>$smp
pc=
sockdone=
killed=
while kill -0 $epid 2>/dev/null; do
  read up rest </proc/uptime
  t="TICK $up"
  while read k v u; do
    case $k in VmRSS:|VmHWM:|Threads:|Cpus_allowed_list:) t="$t $k$v" ;; esac
  done 2>/dev/null </proc/$epid/status
  n=0
  for l in $(ls -l /proc/$epid/fd 2>/dev/null); do
    case $l in socket:*) n=$((n + 1)) ;; esac
  done
  run=
  for s in /proc/$epid/task/*/stat; do
    set -- $(cat $s 2>/dev/null)
    [ "$3" = "R" ] && run="$run${run:+,}${39}"
  done
  cur=
  for f in /sys/devices/system/cpu/cpufreq/policy*/scaling_cur_freq; do read c <$f; cur="$cur${cur:+/}$c"; done
  bat=$(cat /sys/class/power_supply/battery/temp 2>/dev/null)
  echo "$t sockets=$n run=${run:--} cur=$cur bat=${bat:--}" >>$smp
  c=CPUMAX
  for f in /sys/devices/system/cpu/cpufreq/policy*/scaling_max_freq; do read m <$f; c="$c $m"; done
  [ "$c" = "$pc" ] || echo "$c uptime=$up" >>$smp
  pc=$c
  if [ -z "$sockdone" ] && [ $n -gt 0 ]; then
    sockdone=1
    for fd in /proc/$epid/fd/*; do
      l=$(readlink $fd 2>/dev/null)
      case $l in
        socket:*)
          i=${l#socket:[}; i=${i%]}
          echo "SOCKET fd=${fd##*/} inode=$i" >>$smp
          hit=
          for tb in unix tcp tcp6 udp udp6 raw raw6 netlink packet; do
            m=$(grep -w "$i" /proc/net/$tb 2>&1 | head -2)
            case $m in
              *"Permission denied"*|*"No such file"*) echo "SOCKET_IN $tb unreadable: $m" >>$smp ;;
              ?*) echo "SOCKET_IN $tb $m" >>$smp; hit=1 ;;
            esac
          done
          [ -n "$hit" ] || echo "SOCKET_IN none" >>$smp
          ;;
      esac
    done
  fi
  if [ $(( ${up%%.*} - t0 )) -ge $limit ]; then
    kill $epid 2>/dev/null
    killed=1
    echo "KILLED uptime=$up limit_s=$limit" >>$smp
    break
  fi
  sleep 0.5
done
wait $pid
ec=$?
read up rest </proc/uptime
echo "EXIT_CODE=$ec uptime=$up" >>$smp
bt=$(dumpsys battery | sed -n 's/^ *temperature: *//p')
th=$(dumpsys thermalservice | sed -n 's/^Thermal Status: *//p')
echo "END battery_temp=$bt thermal=$th" >>$smp
lc=$(logcat -d --pid=$epid 2>/dev/null | grep -vc '^-----')
echo "LOGCAT_LINES=$lc" >>$smp
logcat -d --pid=$epid -v time 2>/dev/null | grep -v '^-----' | head -15 | while read -r l; do echo "LOGCAT $l" >>$smp; done
for f in $wd/*; do [ -e "$f" ] && echo "OUTDIR ${f##*/} $(stat -c %s "$f")" >>$smp; done
[ -n "$killed" ] && echo "KILLED" || echo "EXIT_CODE=$ec"
