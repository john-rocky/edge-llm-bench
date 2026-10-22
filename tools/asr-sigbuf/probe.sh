#!/bin/bash
# One device probe over adb, printed as one JSON line (asr-npu-v1's probe, the same fields as the
# lane's sherpa arm): battery temperature and level, thermal status, the "Current temperatures from
# HAL" block of dumpsys thermalservice (the "Cached" block is stale), every cpufreq policy's
# hardware maximum / current ceiling / CPUs, MemAvailable, uptime, wakefulness.
#
#   tools/asr-sigbuf/probe.sh [label]        # SERIAL defaults to the Galaxy S26 RFGL80R6A6H
#   DRY=1 tools/asr-sigbuf/probe.sh before   # print what it would run, run nothing
#
# One remote shell per call, no background child on the phone; the parsing happens on the Mac.
set -uo pipefail
SERIAL="${SERIAL:-RFGL80R6A6H}"
LABEL="${1:-probe}"
REMOTE='
echo "uptime=$(cut -d" " -f1 /proc/uptime)"
dumpsys battery | grep -E "^ *(level|temperature|status|AC powered|USB powered):" | sed "s/^ */battery:/"
dumpsys thermalservice | grep -E "^Thermal Status:|^[A-Z].*:$|Temperature\{" | sed "s/^[[:space:]]*/thermal:/"
for p in /sys/devices/system/cpu/cpufreq/policy*; do
  echo "cpufreq:${p##*/}:cpus=$(cat $p/related_cpus)"
  echo "cpufreq:${p##*/}:hw_khz=$(cat $p/cpuinfo_max_freq)"
  echo "cpufreq:${p##*/}:max_khz=$(cat $p/scaling_max_freq)"
  echo "cpufreq:${p##*/}:cur_khz=$(cat $p/scaling_cur_freq)"
done
grep "^MemAvailable:" /proc/meminfo
dumpsys power | grep -m1 "mWakefulness="
'
if [ "${DRY:-0}" = 1 ]; then
  echo "DRY adb -s $SERIAL shell <probe: battery, thermalservice, cpufreq, meminfo, power> ($LABEL)"
  exit 0
fi
out=$(adb -s "$SERIAL" shell "$REMOTE" </dev/null 2>&1) || { echo "{\"label\": \"$LABEL\", \"error\": \"adb failed\"}"; exit 1; }
python3 - "$LABEL" "$out" <<'PY'
import datetime, json, re, sys
label, text = sys.argv[1], sys.argv[2]
rec = {"label": label, "mac_time": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}
hal, pol, block = {}, {}, None
for line in text.splitlines():
    line = line.rstrip()
    if line.startswith("uptime="):
        rec["uptime_s"] = float(line.split("=", 1)[1])
    elif line.startswith("battery:"):
        k, v = line[len("battery:"):].split(":", 1)
        k, v = k.strip().lower().replace(" ", "_"), v.strip()
        if k == "temperature":
            rec["battery_celsius"] = int(v) / 10
        elif k in ("level", "status"):
            rec["battery_" + k] = int(v)
        else:
            rec["battery_" + k] = v == "true"
    elif line.startswith("thermal:"):
        t = line[len("thermal:"):]
        m = re.match(r"Thermal Status: (\d+)", t)
        if m:
            rec["thermal_status"] = int(m.group(1))
        elif t.startswith("Temperature{"):
            if block == "Current temperatures from HAL:":
                name = re.search(r"mName=([^,}]+)", t)
                value = re.search(r"mValue=([^,}]+)", t)
                if name and value:
                    try:
                        hal[name.group(1)] = float(value.group(1))
                    except ValueError:
                        hal[name.group(1)] = value.group(1)
        else:
            block = t
    elif line.startswith("cpufreq:"):
        _, policy, kv = line.split(":", 2)
        k, v = kv.split("=", 1)
        pol.setdefault(policy, {})[k] = v.strip() if k == "cpus" else int(v)
    elif line.startswith("MemAvailable:"):
        rec["mem_available_kb"] = int(line.split()[1])
    elif "mWakefulness=" in line:
        rec["wakefulness"] = line.split("=", 1)[1].strip()
rec["hal_current"] = hal
for p in pol.values():
    if p.get("hw_khz") and p.get("max_khz") is not None:
        p["ceiling_drop_pct"] = round((1 - p["max_khz"] / p["hw_khz"]) * 100, 1)
rec["cpufreq"] = pol
print(json.dumps(rec))
PY
