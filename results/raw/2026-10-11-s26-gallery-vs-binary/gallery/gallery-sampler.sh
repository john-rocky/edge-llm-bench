#!/system/bin/sh
# 1 s sampler beside a Gallery session (same columns as binary_runs.sh): epoch, uptime, policy0 cur/max kHz, policy6 cur/max kHz,
# GPU MHz, GPU busy %, thermal zones 36 5 24 63 55 (gpuss-0, cpu-0-0-0, cpu-1-0-0, battery, sys-therm-0) in m°C.
tag=$1; out=/data/local/tmp/gallery-sample-$tag.csv; rm -f $out
while :; do
  echo "$(date +%s) $(cut -d' ' -f1 /proc/uptime) $(cat /sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq /sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq /sys/devices/system/cpu/cpufreq/policy6/scaling_cur_freq /sys/devices/system/cpu/cpufreq/policy6/scaling_max_freq /sys/class/kgsl/kgsl-3d0/clock_mhz /sys/class/kgsl/kgsl-3d0/gpu_busy_percentage 2>/dev/null | tr '\n' ' ') $(for z in 36 5 24 63 55; do cat /sys/class/thermal/thermal_zone$z/temp; done | tr '\n' ' ')" >> $out
  sleep 1
done
