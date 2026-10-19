#!/usr/bin/env bash
# The phone's state as one JSON line, read in one short adb shell call:
#
#   tools/asr-sherpa/probe.sh <label> [serial]  > probe-<label>.json
#
# Battery (dumpsys battery), Thermal Status and the "Current temperatures from HAL" block of
# dumpsys thermalservice (the "Cached temperatures" block is stale and is not read), every
# cpufreq policy's cpus / cpuinfo_max_freq / scaling_max_freq / scaling_cur_freq, MemTotal /
# MemAvailable, uptime, the screen state (mWakefulness, stay_on_while_plugged_in), /data free,
# and any running sherpa-onnx process.
set -euo pipefail
LABEL=${1:?usage: probe.sh <label> [serial]}
SERIAL=${2:-${SERIAL:-RFGL80R6A6H}}
tmp=$(mktemp -t asr-sherpa-probe)
trap 'rm -f "$tmp"' EXIT
adb -s "$SERIAL" shell '
echo "@@epoch $EPOCHREALTIME"
echo "@@uptime $(cat /proc/uptime)"
echo "@@model $(getprop ro.product.model)"
echo "@@release $(getprop ro.build.version.release)"
echo "@@soc $(getprop ro.soc.model)"
echo "@@patch $(getprop ro.build.version.security_patch)"
echo "@@build $(getprop ro.build.display.id)"
for d in /sys/devices/system/cpu/cpufreq/policy*; do
  echo "@@policy ${d##*/} $(cat $d/related_cpus | tr " " ,) $(cat $d/cpuinfo_max_freq) $(cat $d/scaling_max_freq) $(cat $d/scaling_cur_freq)"
done
grep -E "^(MemTotal|MemAvailable):" /proc/meminfo | sed "s/^/@@mem /"
echo "@@df $(df -k /data | tail -n 1)"
echo "@@wake $(dumpsys power | grep -m 1 mWakefulness=)"
echo "@@stayon $(settings get global stay_on_while_plugged_in)"
ps -A -o PID,NAME | grep -i sherpa | sed "s/^/@@proc /"
echo "@@battery"
dumpsys battery
echo "@@thermal"
dumpsys thermalservice
' > "$tmp"
python3 -I - "$tmp" "$LABEL" "$SERIAL" <<'EOF'
import json, re, sys
raw, label, serial = sys.argv[1:4]
lines = open(raw, errors="replace").read().splitlines()
out = {"label": label, "serial": serial, "policies": {}, "mem_kB": {}, "procs": []}
section = None
battery, thermal = [], []
for line in lines:
    if line.startswith("@@battery"):
        section = "battery"; continue
    if line.startswith("@@thermal"):
        section = "thermal"; continue
    if section == "battery":
        battery.append(line); continue
    if section == "thermal":
        thermal.append(line); continue
    key, _, val = line.partition(" ")
    val = val.strip()
    if key == "@@epoch": out["device_epoch"] = float(val) if val else None
    elif key == "@@uptime": out["uptime_s"] = float(val.split()[0])
    elif key == "@@model": out["model"] = val
    elif key == "@@release": out["android"] = val
    elif key == "@@soc": out["soc"] = val
    elif key == "@@patch": out["security_patch"] = val
    elif key == "@@build": out["build"] = val
    elif key == "@@policy":
        name, cpus, hw, smax, cur = val.split()
        out["policies"][name] = {"cpus": cpus, "cpuinfo_max_freq_kHz": int(hw),
                                 "scaling_max_freq_kHz": int(smax), "scaling_cur_freq_kHz": int(cur)}
    elif key == "@@mem":
        k, v = val.split(":"); out["mem_kB"][k] = int(v.split()[0])
    elif key == "@@df":
        f = val.split(); out["data_free_kB"] = int(f[3]) if len(f) > 3 else None
    elif key == "@@wake":
        m = re.search(r"mWakefulness=(\w+)", val); out["wakefulness"] = m.group(1) if m else None
    elif key == "@@stayon": out["stay_on_while_plugged_in"] = val
    elif key == "@@proc": out["procs"].append(val)
b = "\n".join(battery)
def num(pat):
    m = re.search(pat, b)
    return int(m.group(1)) if m else None
temp = num(r"temperature: (-?\d+)")
out["battery"] = {
    "level": num(r"level: (\d+)"), "status": num(r"status: (\d+)"),
    "temperature_C": temp / 10 if temp is not None else None,
    "ac": "AC powered: true" in b, "usb": "USB powered: true" in b, "wireless": "Wireless powered: true" in b,
}
t = "\n".join(thermal)
m = re.search(r"Thermal Status: (\d+)", t)
out["thermal_status"] = int(m.group(1)) if m else None
hal, inside = [], False
for line in thermal:
    if line.startswith("Current temperatures from HAL"):
        inside = True; continue
    if inside:
        mm = re.search(r"Temperature\{mValue=([-0-9.eE]+), mType=(-?\d+), mName=([^,]+), mStatus=(\d+)", line)
        if mm:
            hal.append({"name": mm.group(3), "type": int(mm.group(2)), "value_C": float(mm.group(1)), "status": int(mm.group(4))})
        elif line.strip() and not line.startswith((" ", "\t")):
            break
out["hal_temperatures"] = hal
print(json.dumps(out, ensure_ascii=False))
EOF
