"""Device state probes over adb (Pixel-class Android).

Thermal vocabulary: Android reports an integer status (0 = THERMAL_STATUS_NONE
… 6 = SHUTDOWN). We map 0 -> "nominal" so the repo's nominal-gate tooling works
unchanged, and record the raw integer alongside — the mapping is disclosed in
methodology/android.md, not silent.
"""
import re
import subprocess
import os
import time

THERMAL_NAMES = {0: "nominal", 1: "light", 2: "moderate", 3: "severe",
                 4: "critical", 5: "emergency", 6: "shutdown"}


def adb(args, serial=None, timeout=30, retries=3):
    """adb with transient-drop tolerance: a USB renegotiation mid-campaign
    (measured: the probe between two cells) used to kill the whole run. On
    failure, wait for the device to re-enumerate and retry; only after
    `retries` consecutive failures does the error propagate."""
    cmd = ["adb"] + (["-s", serial] if serial else []) + args
    if os.environ.get("BENCH_SESSION_DEADLINE"):
        timeout = min(timeout, max(1, float(os.environ["BENCH_SESSION_DEADLINE"]) - time.time() - 1))
    if os.environ.get("BENCH_STRICT_SMOKE") == "1":
        # A failed engine shell must never be replayed after a USB loss.
        return subprocess.check_output(cmd, text=True, errors="replace", timeout=timeout)
    last = None
    for attempt in range(retries):
        try:
            return subprocess.check_output(cmd, text=True, errors="replace",
                                           timeout=timeout)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            last = e
            wait = ["adb"] + (["-s", serial] if serial else []) + ["wait-for-device"]
            try:
                subprocess.run(wait, timeout=60, check=False)
            except subprocess.TimeoutExpired:
                pass
    raise last


def getprop(name, serial=None):
    return adb(["shell", "getprop", name], serial).strip()


def device_info(serial=None):
    return {
        "modelIdentifier": getprop("ro.product.model", serial),          # "Pixel 8a"
        "systemName": "Android",
        "systemVersion": getprop("ro.build.version.release", serial),
        "securityPatch": getprop("ro.build.version.security_patch", serial),
        "soc": getprop("ro.soc.model", serial),                          # "Tensor G3"
        "product": getprop("ro.product.device", serial),                 # "akita"
    }


def battery(serial=None):
    out = adb(["shell", "dumpsys", "battery"], serial)
    level = re.search(r"level: (\d+)", out)
    status = re.search(r"status: (\d+)", out)
    plugged = re.search(r"(AC|USB|Wireless) powered: true", out)
    temperature = re.search(r"temperature:\s*(-?\d+)", out)
    return {
        "batteryLevel": int(level.group(1)) / 100 if level else None,
        # dumpsys status: 2=charging 3=discharging 4=not-charging 5=full
        "batteryState": ("charging" if plugged else "unplugged"),
        "rawStatus": int(status.group(1)) if status else None,
        "temperatureC": int(temperature.group(1)) / 10 if temperature else None,
    }


def thermal_status(serial=None):
    out = adb(["shell", "dumpsys", "thermalservice"], serial)
    m = re.search(r"Thermal Status: (\d+)", out)
    raw = int(m.group(1)) if m else None
    return raw, THERMAL_NAMES.get(raw, f"unknown({raw})")


def wakefulness(serial=None):
    """PowerManager's mWakefulness: "Awake" / "Dozing" / "Asleep" /
    "Dreaming"; None when dumpsys prints no such line."""
    out = adb(["shell", "dumpsys power 2>/dev/null | grep -E 'mWakefulness=' | head -1"], serial)
    m = re.search(r"mWakefulness=(\w+)", out)
    return m.group(1) if m else None


def stay_on_while_plugged_in(serial=None):
    """The developer option "Stay awake" as the phone holds it (settings
    global stay_on_while_plugged_in: "0" = off, otherwise a bitmask of the
    power sources that keep the screen on); None when nothing is printed."""
    lines = adb(["shell", "settings get global stay_on_while_plugged_in"], serial).strip().splitlines()
    return lines[-1].strip() if lines else None


def screen_conditions(serial=None):
    """conditions.screen / screenSource / stayOnWhilePluggedIn for one launch,
    read right before it. Same form as scripts/vl_response_android.py: "on-usb"
    only when Awake, else "off-usb (mWakefulness=<state>)". On and off are both
    admissible for speed cells (the display is not used; the session anchor
    decides the sitting), so the state is recorded, never enforced.
    BENCH_ROUND_WAKEFULNESS (run_campaign.py's sitting mode, one dumpsys power
    read per round, kept in power_roundNN.txt) wins with its raw value, and
    then no extra adb call is made."""
    env = os.environ.get("BENCH_ROUND_WAKEFULNESS")
    if env:
        return {"screen": env, "screenSource": "env"}
    state = wakefulness(serial)
    if state is None:
        screen = "unknown (no mWakefulness line in dumpsys power)"
    else:
        screen = "on-usb" if state == "Awake" else f"off-usb (mWakefulness={state})"
    return {"screen": screen, "screenSource": "measured",
            "stayOnWhilePluggedIn": stay_on_while_plugged_in(serial)}
