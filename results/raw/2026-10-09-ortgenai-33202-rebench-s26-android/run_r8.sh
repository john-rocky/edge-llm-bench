#!/system/bin/sh
# One engine launch with a 0.5 s on-device sampler, for ORT GenAI round
# r8-33202 on the Galaxy S26 (2026-10-09, by hand): r2b's run_diag.sh
# (../2026-10-07-ortgenai-diag-s26-android/run_diag.sh) with the runtime
# directory and the ONNX Runtime library given per launch, so one copy serves
# the release library and the one built with microsoft/onnxruntime PR #33202,
# and every output lands under this round's directory, never in the release
# runtime dir. No CPU mask. Two extra line kinds, each written once:
#   ENV <name>=<value>   ORT_* and LD_LIBRARY_PATH from the engine's environ
#                        (first tick)
#   ORTLIB <path>        every mapped libonnxruntime*.so, at the first tick
#                        whose /proc/<pid>/maps shows libonnxruntime.so (which
#                        ONNX Runtime library ran)
#
# usage: sh run_r8.sh <tag> <rt_dir> <ort_dir> <limit_s> <binary path> [engine args...]
#   rt_dir   LD_LIBRARY_PATH (libonnxruntime-genai.so, libmat.so)
#   ort_dir  ORT_LIB_PATH=<ort_dir>/libonnxruntime.so (GenAI dlopens that path)
#   limit_s  the engine is killed (KILLED line, no result) after this many seconds
# The caller's environment passes through (ORT_GQA_DISABLE_FLASH_ATTENTION=1
# for the flash-off launches). Writes out/<tag>.engine.txt (engine stdout +
# stderr), out/<tag>.sampler.txt and out/<tag>.d/ (the engine's cwd: profile
# JSON, logits dumps) under /data/local/tmp/llmbench/ortgenai-33202.
# Sampler lines (run_diag.sh's, without mask=):
#   CPUPOLICY <policy> hw= cap= cpus=        every cpufreq policy, once
#   START uptime= battery_temp= thermal=     before the launch
#   LAUNCH uptime= pid= engine_pid= exe= rt= ort= cmd=
#   TICK <uptime> VmRSS: VmHWM: Threads: Cpus_allowed_list: sockets= run=<cpu,...>
#        cur=<kHz per policy> bat=<deci-C>   run = last CPU of each thread in state R
#   CPUMAX <cap per policy> uptime=          whenever a cap changes
#   ORTLIB / ENV                             once (above)
#   SOCKET fd=<n> inode=<i> / SOCKET_IN <table> <line> / SOCKET_IN none   once
#   EXIT_CODE= uptime= / KILLED uptime= limit_s=
#   END battery_temp= thermal= / LOGCAT_LINES= / LOGCAT <line> (first 15)
#   OUTDIR <file> <bytes>
D8=/data/local/tmp/llmbench/ortgenai-33202
cd $D8 || exit 1
tag=$1
rt=$2
ortd=$3
limit=$4
bin=$5
shift 5
[ -x "$bin" ] || { echo "no executable $bin"; exit 1; }
[ -f "$ortd/libonnxruntime.so" ] || { echo "no $ortd/libonnxruntime.so"; exit 1; }
mkdir -p out
eng=$D8/out/$tag.engine.txt
smp=$D8/out/$tag.sampler.txt
wd=$D8/out/$tag.d
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
LD_LIBRARY_PATH=$rt ORT_LIB_PATH=$ortd/libonnxruntime.so ORT_DISABLE_TELEMETRY=1 $bin "$@" >$eng 2>&1 </dev/null &
pid=$!
sleep 0.2
exe=$(readlink /proc/$pid/exe)
case $exe in
  $bin) epid=$pid ;;
  *) epid=$(pgrep -n -f "$bin") ;;
esac
read up rest </proc/uptime
t0=${up%%.*}
echo "LAUNCH uptime=$up pid=$pid engine_pid=$epid exe=$exe rt=$rt ort=$ortd cmd=${bin##*/} $*" >>$smp
pc=
sockdone=
envdone=
libdone=
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
  if [ -z "$envdone" ]; then
    envdone=1
    tr '\000' '\n' </proc/$epid/environ 2>/dev/null | grep -E '^(ORT_|LD_LIBRARY_PATH=)' | while read -r e; do echo "ENV $e" >>$smp; done
  fi
  if [ -z "$libdone" ]; then
    # libonnxruntime-genai.so is mapped from the start (DT_NEEDED); wait for
    # the ONNX Runtime library GenAI dlopens at its first call
    libs=$(grep -o '/[^ ]*/libonnxruntime[^ /]*\.so' /proc/$epid/maps 2>/dev/null | sort -u)
    case "$libs" in
      */libonnxruntime.so*) libdone=1; for x in $libs; do echo "ORTLIB $x" >>$smp; done ;;
    esac
  fi
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
