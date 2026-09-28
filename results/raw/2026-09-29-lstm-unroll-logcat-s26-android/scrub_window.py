#!/usr/bin/env python3
"""Cut the public window out of a full-buffer logcat dump of a personal phone.

    scrub_window.py            rewrites logs/<launch>.window.txt for every launch in run.json

Kept, verbatim: every line of the runner's pid; the tombstone (tag DEBUG, from crash_dump64) and
the crash pipeline (crash_dump64, tombstoned); system lines whose tag names the GPU driver,
memory pressure, thermal state, DVFS / performance HAL or the graphics allocator; and any line
whose message names the runner (gpu_runner, its /data/local/tmp/litert10300 directory, or its
pid). Everything else in the window (SystemUI, wallpaper, telephony, sensors, audio, codecs,
Wi-Fi, Bluetooth, ...) is dropped and only counted, because the phone is a personal device.
The dropped lines were read one by one before this rule was fixed (NOTES.md); the full dumps
stay on disk in private/ and are not committed.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
LINE = re.compile(r'^(\d\d-\d\d \d\d:\d\d:\d\d\.\d{3}) +(\S+) +(\d+) +(\d+) ([VDIWEFS]) ([^:]+?) *: ?(.*)$')
KEEP_TAG = re.compile(r'kgsl|adreno|gpu|opencl|lmkd|lowmemorykiller|GraphicsEnvironment|thermal|PERFHAL|'
                      r'Dvfs|CustomFrequency|HYPER-HAL|^crash_dump64$|^tombstoned$|^DEBUG$|^SnapAlloc$', re.I)
PRIVATE_MARKERS = re.compile(r'majimadaisuke|/Users/|RFGL80R6A6H|@gmail|daisuke', re.I)


def scrub(name, pid, raw_path, out_path, meta):
    kept, dropped, dropped_tags = [], 0, {}
    pid_word = re.compile(rf'\b{pid}\b')
    for line in raw_path.read_text(errors='replace').splitlines():
        m = LINE.match(line)
        if not m:
            dropped += 1
            continue
        tag, msg = m.group(6).strip(), m.group(7)
        keep = (m.group(3) == str(pid) or KEEP_TAG.search(tag) or 'gpu_runner' in msg
                or 'litert10300' in msg or pid_word.search(msg))
        if keep:
            kept.append(line)
        else:
            dropped += 1
            dropped_tags[tag] = dropped_tags.get(tag, 0) + 1
    assert not any(PRIVATE_MARKERS.search(l) for l in kept), 'private marker in a kept line'
    header = [
        f'# LiteRT #10300 logcat window, launch {name} (Galaxy S26 SM-S942Q, Android 16, LiteRT 2.2.0)',
        f'# graph {meta["graph"]}, runner mode {meta["mode"]}, runner pid {pid}, exit code {meta["exit_code"]}',
        f'# window: device local time {meta["window_from"]} to {meta["window_to"]} '
        f'(5 s before the runner started to {"the end of its tombstone" if meta["crashed"] else "1 s after it exited"})',
        f'# all buffers were cleared (logcat -c -b all) 6 s before the runner started; dump = logcat -b all -d -v threadtime -v uid',
        f'# {len(kept)} lines kept verbatim; redacted: {dropped} lines from unrelated apps/services (SystemUI, wallpaper, telephony, sensors, audio, codecs, Wi-Fi, Bluetooth)',
        f'# kept: every line of pid {pid}; the tombstone and crash pipeline; system lines tagged GPU driver / memory pressure / thermal / DVFS / performance HAL / graphics allocator; lines naming the runner',
    ]
    out_path.write_text('\n'.join(header + kept) + '\n')
    return len(kept), dropped, dropped_tags


def main():
    run = json.loads((HERE / 'run.json').read_text())
    for launch in run['launches']:
        name, pid = launch['name'], launch['runner_pid']
        w = launch['window']
        import datetime as dt
        fmt = lambda e: dt.datetime.fromtimestamp(e).strftime('%m-%d %H:%M:%S.%f')[:-3]
        meta = {'graph': launch['graph'], 'mode': launch['mode'], 'exit_code': launch['exit_code'],
                'window_from': fmt(w['from_epoch']), 'window_to': fmt(w['to_epoch']),
                'crashed': w['crash_end_epoch'] is not None}
        kept, dropped, tags = scrub(name, pid, HERE / 'private' / f'{name}.window.raw.txt',
                                    HERE / 'logs' / f'{name}.window.txt', meta)
        launch['window']['public_lines_kept'] = kept
        launch['window']['public_lines_redacted'] = dropped
        print(f'{name}: kept {kept}, redacted {dropped}; top dropped tags: '
              + ', '.join(f'{t}x{n}' for t, n in sorted(tags.items(), key=lambda x: -x[1])[:6]))
    (HERE / 'run.json').write_text(json.dumps(run, indent=2) + '\n')


if __name__ == '__main__':
    main()
