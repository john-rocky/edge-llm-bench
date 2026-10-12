# Screen state for the GPU holds (catalog X2, Galaxy S26 RFGL80R6A6H, 2026-10-12)

The GPU reading this lane lines up with (the 2026-09-24 re-take) ran with the screen off: `mWakefulness=Dozing`,
`stay_on_while_plugged_in=0`. A GPU client that draws the screen halves a LiteRT-LM GPU decode (S26, 2026-10-07),
so every GPU hold turns the screen off first and checks it. Each record carries `conditions.screen` (read before
every launch) and each round's `power_roundNN.txt` / `round_state.jsonl`.

At the head of hold 1 (after `state.sh <hold> start`, which records the values found):

```bash
adb -s RFGL80R6A6H shell settings put global stay_on_while_plugged_in 0
adb -s RFGL80R6A6H shell input keyevent 223          # KEYCODE_SLEEP
adb -s RFGL80R6A6H shell dumpsys power | grep mWakefulness   # expect Dozing or Asleep
```

(The lane's helper ran these three and stopped unless the phone read Dozing / Asleep.) Each later GPU hold checks `mWakefulness` again and repeats the two commands when the phone
is awake.

At the end of the last hold (the values found at the head of hold 1, from `device-state/hold1-start.txt`):

```bash
adb -s RFGL80R6A6H shell settings put global stay_on_while_plugged_in <found value, 15 on 2026-10-11>
adb -s RFGL80R6A6H shell input keyevent 224          # KEYCODE_WAKEUP, only when the phone was found awake
```

Nothing else on the phone is changed: no reboot, no power setting beyond `stay_on_while_plugged_in`.
