#!/usr/bin/env python3
"""Full-buffer logcat capture around one gpu_runner launch on the Galaxy S26 (LiteRT #10300).

One launch = clear every logcat buffer, wait, run the 2.2.0 CompiledModel runner on one
graph, dump every buffer, pull the runner's own report, and cut the window from 5 s before
the runner started to the end of its tombstone (or to its exit when it does not crash).

    capture.py setup                          push runner + libs + graphs + inputs, verify sha256
    capture.py launch NAME GRAPH_ID MODE      one launch; MODE = single (gpu_options precision=2,
                                              1 rep / 0 warmups: the 2026-09-26 sweep's mode) or
                                              default (no gpu_options; 1 rep / 0 warmups)
    capture.py teardown                       restore stayon, remove the remote dir

Reads only from the 2026-09-26 run directory (binary, libraries, graphs, input packs); never
writes there. The device hold is a keeper process (script name litert-10300-logcat); every adb
call re-reads the hold first. Full-buffer dumps go to private/ (not committed: a personal phone's
logcat carries other apps' lines); the cut window goes to logs/ after scrub_window.py.
"""
import datetime as dt
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = Path.home() / 'code/codex-conversions/2026-09-26/gliformer-large-v1'
SERIAL = 'RFGL80R6A6H'
HOLD = Path.home() / 'code/litertlm-convert/community_accel_work/s2_npu_sweep/.device_hold'
# pid file written by the hold keeper shell (this session pointed it at the keeper's own pid file
# through the environment variable; the keeper wrote the hold with that pid)
KEEPER_PID = Path(os.environ.get('LITERT10300_KEEPER_PID', HERE / 'private' / 'keeper.pid'))
HOLD_SCRIPT = 'litert-10300-logcat'
REMOTE = '/data/local/tmp/litert10300'
GRAPHS = ['lstm_h128_t84_uni_fp32', 'lstm_h128_t88_uni_fp32']
FILES = {  # local source -> remote name
    RUN / 'android/round12/gpu_runner': 'gpu_runner',
    RUN / 'android/vendor/lib/libLiteRt.so': 'libLiteRt.so',
    RUN / 'android/vendor/lib/libLiteRtClGlAccelerator.so': 'libLiteRtClGlAccelerator.so',
}
INPUT_FILES = ['manifest.tsv', 'word_states.f32', 'text_mask.f32']
CMDLOG = HERE / 'logs/commands.log'
PRIVATE = HERE / 'private'
LOGS = HERE / 'logs'
RUNJSON = HERE / 'run.json'
WINDOW_BEFORE_S = 5.0


def now():
    return dt.datetime.now().astimezone().isoformat(timespec='milliseconds')


def sha256(path):
    with open(path, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def hold_check():
    data = json.loads(HOLD.read_text())
    pid = int(KEEPER_PID.read_text().strip())
    if data.get('script') != HOLD_SCRIPT or int(data.get('pid', -1)) != pid:
        raise SystemExit(f'BLOCKED: hold is not ours: {data}')
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        raise SystemExit('BLOCKED: keeper pid is dead')
    return data


def run(cmd, label='', timeout=120, check=True, stdout_path=None, stderr_path=None):
    """Run one command, log the exact line and rc into logs/commands.log."""
    line = cmd if isinstance(cmd, str) else shlex.join(cmd)
    with CMDLOG.open('a') as log:
        log.write(f'### CMD: {line} ({now()}){" # " + label if label else ""}\n')
    t0 = time.monotonic()
    if stdout_path or stderr_path:
        with open(stdout_path, 'w') as out, open(stderr_path, 'w') as err:
            try:
                p = subprocess.run(cmd, shell=isinstance(cmd, str), stdout=out, stderr=err, timeout=timeout)
                rc = p.returncode
            except subprocess.TimeoutExpired:
                rc = 'TIMEOUT'
        text = ''
    else:
        try:
            p = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, timeout=timeout)
            rc, text = p.returncode, p.stdout + p.stderr
        except subprocess.TimeoutExpired:
            rc, text = 'TIMEOUT', ''
    wall = time.monotonic() - t0
    with CMDLOG.open('a') as log:
        if text:
            log.write(text if text.endswith('\n') else text + '\n')
        log.write(f'### RC: {rc} ({wall:.3f} s)\n')
    if check and rc != 0:
        raise SystemExit(f'{label or line} failed rc={rc}: {text[-2000:]}')
    return rc, text


def adb(args, label='', **kw):
    hold_check()
    return run(['adb', '-s', SERIAL, *args], label, **kw)


def shell(cmdline, label='', **kw):
    return adb(['shell', cmdline], label, **kw)


def battery():
    _, text = shell('dumpsys battery', 'battery')
    vals = {k: int(v) for k, v in re.findall(r'^\s*(level|temperature|voltage|status):\s*(-?\d+)', text, re.M)}
    vals['temperature_c'] = vals.get('temperature', 0) / 10
    return vals


def device_time():
    _, text = shell("date '+%s.%N|%m-%d %H:%M:%S.%N'", 'device_time')
    epoch, local = text.strip().split('|')
    return {'epoch': float(epoch), 'local': local[:18]}


def screen_state():
    _, text = shell('dumpsys power | grep -E "mWakefulness=|mIsPowered"', 'screen_state')
    return ' '.join(sorted(set(text.split())))


def foreign_processes():
    _, text = shell('ps -A -o NAME', 'processes')
    return [x for x in text.splitlines()
            if re.search(r'com\.mlboydaisuke\.|PipelinedBench|ANEgate|litert_gate|litert_lm|llama|gpu_runner|bench', x, re.I)]


def load_runjson():
    return json.loads(RUNJSON.read_text()) if RUNJSON.exists() else {'launches': []}


def save_runjson(data):
    RUNJSON.write_text(json.dumps(data, indent=2) + '\n')


def setup():
    hold_check()
    LOGS.mkdir(exist_ok=True)
    PRIVATE.mkdir(exist_ok=True)
    data = load_runjson()
    data['device'] = {}
    for prop in ['ro.build.fingerprint', 'ro.build.version.security_patch', 'ro.gfx.driver.0',
                 'ro.gfx.driver.1', 'ro.soc.model', 'ro.product.model', 'ro.build.version.release']:
        _, text = shell(f'getprop {prop}', prop)
        data['device'][prop] = text.strip()
    _, text = shell('dumpsys SurfaceFlinger | grep "GLES:"', 'gles')
    data['device']['gles'] = text.strip()
    _, text = shell('sha256sum /vendor/lib64/libOpenCL_adreno.so /vendor/lib64/libCB.so '
                    '/vendor/lib64/libOpenCL.so /vendor/lib64/egl/libGLESv2_adreno.so', 'vendor_sha')
    data['device']['vendor_lib_sha256'] = dict(reversed(l.split()) for l in text.strip().splitlines())
    _, text = shell('logcat -g', 'logcat_buffers')
    data['device']['logcat_g'] = text.strip().splitlines()
    data['device']['screen_before_setup'] = screen_state()
    procs = foreign_processes()
    if procs:
        raise SystemExit(f'BLOCKED: foreign processes on the phone: {procs}')
    shell(f'mkdir -p {REMOTE}', 'mkdir')
    pushed = {}
    for local, name in FILES.items():
        adb(['push', str(local), f'{REMOTE}/{name}'], f'push {name}', timeout=180)
        _, text = shell(f'sha256sum {REMOTE}/{name}', f'hash {name}')
        assert text.split()[0] == sha256(local), name
        pushed[name] = {'sha256': sha256(local), 'bytes': local.stat().st_size, 'source': str(local.relative_to(RUN))}
    shell(f'chmod 700 {REMOTE}/gpu_runner', 'chmod')
    for gid in GRAPHS:
        local = RUN / f'results/repro_round12/{gid}.tflite'
        adb(['push', str(local), f'{REMOTE}/{gid}.tflite'], f'push {gid}', timeout=180)
        _, text = shell(f'sha256sum {REMOTE}/{gid}.tflite', f'hash {gid}')
        assert text.split()[0] == sha256(local), gid
        pushed[f'{gid}.tflite'] = {'sha256': sha256(local), 'bytes': local.stat().st_size,
                                   'source': str(local.relative_to(RUN))}
        shell(f'mkdir -p {REMOTE}/inputs_{gid}', f'mkdir inputs {gid}')
        for name in INPUT_FILES:
            src = RUN / f'results/repro_round12/inputs/{gid}/{name}'
            adb(['push', str(src), f'{REMOTE}/inputs_{gid}/{name}'], f'push {gid}/{name}', timeout=60)
            _, text = shell(f'sha256sum {REMOTE}/inputs_{gid}/{name}', f'hash {gid}/{name}')
            assert text.split()[0] == sha256(src), name
            pushed[f'inputs_{gid}/{name}'] = {'sha256': sha256(src), 'bytes': src.stat().st_size,
                                             'source': str(src.relative_to(RUN))}
    data['pushed'] = pushed
    data['runner_source_sha256'] = sha256(RUN / 'android/round12/gpu_runner.cc')
    shell('svc power stayon usb', 'stayon usb')  # the 2026-09-26 driver set this per launch; restored in teardown
    data['device']['screen_after_stayon'] = screen_state()
    data['setup_utc'] = now()
    save_runjson(data)
    print(json.dumps({'pushed': sorted(pushed)}, indent=1))


def parse_ts(local):
    """'MM-DD HH:MM:SS.mmm' (device local time, current year) -> epoch seconds."""
    year = dt.datetime.now().year
    t = dt.datetime.strptime(f'{year}-{local}', '%Y-%m-%d %H:%M:%S.%f')
    return t.astimezone().timestamp() if t.tzinfo else t.replace(tzinfo=dt.datetime.now().astimezone().tzinfo).timestamp()


LINE_RE = re.compile(r'^(\d\d-\d\d \d\d:\d\d:\d\d\.\d{3}) +(\S+) +(\d+) +(\d+) ([VDIWEFS]) (.*)$')


def cut_window(all_lines, t_start, t_end, pid):
    """Lines whose timestamp lies in [t_start - 5 s, end], end = last DEBUG tombstone line for pid
    (when it crashed) else t_end + 1 s. Buffer-header lines are dropped."""
    lo = t_start - WINDOW_BEFORE_S
    parsed = []
    for line in all_lines:
        m = LINE_RE.match(line)
        if not m:
            continue
        parsed.append((parse_ts(m.group(1)), m, line))
    crash_end = None
    in_block = False
    for ts, m, line in parsed:
        if ts < lo:
            continue
        if m.group(5) == 'F' and m.group(6).startswith('DEBUG'):
            if '*** *** ***' in line:
                in_block = True
            if in_block:
                crash_end = ts
    hi = crash_end + 0.001 if crash_end else t_end + 1.0
    return [line for ts, m, line in parsed if lo <= ts <= hi], lo, hi, crash_end


def launch(name, gid, mode):
    assert mode in ('single', 'default'), mode
    assert gid in GRAPHS, gid
    assert re.fullmatch(r'[a-z0-9-]+', name), name
    data = load_runjson()
    if any(l['name'] == name for l in data['launches']):
        raise SystemExit(f'launch {name} already recorded')
    hold = hold_check()
    procs = foreign_processes()
    if procs:
        raise SystemExit(f'BLOCKED: foreign processes on the phone: {procs}')
    rec = {'name': name, 'graph': gid, 'mode': mode, 'hold': hold, 'started_utc': now()}
    rec['battery_before'] = battery()
    rec['screen_before'] = screen_state()
    for name_, name_remote in [(l, r) for l, r in FILES.items()]:
        _, text = shell(f'sha256sum {REMOTE}/{name_remote}', f'recheck {name_remote}')
        assert text.split()[0] == sha256(name_), name_remote
    _, text = shell(f'sha256sum {REMOTE}/{gid}.tflite', f'recheck {gid}')
    assert text.split()[0] == sha256(RUN / f'results/repro_round12/{gid}.tflite')
    out = f'{REMOTE}/out_{name}'
    shell(f'test ! -e {out}', 'output dir absent')
    rc, text = shell('logcat -c -b all', 'clear all buffers', check=False)
    rec['logcat_clear'] = {'rc': rc, 'text': text.strip()}
    _, text = shell('logcat -g', 'buffers after clear')
    rec['logcat_g_after_clear'] = text.strip().splitlines()
    rec['t_clear'] = device_time()
    time.sleep(WINDOW_BEFORE_S + 1)
    rec['t_start'] = device_time()
    argv = [f'{REMOTE}/gpu_runner', f'{REMOTE}/{gid}.tflite', f'{REMOTE}/inputs_{gid}', out, mode, '1', '0',
            REMOTE, f'{REMOTE}/inputs_{gid}/manifest.tsv', '900']
    rec['runner_argv'] = argv
    cmdline = f'env LD_LIBRARY_PATH={REMOTE} ' + ' '.join(argv) + '; echo "##EXIT=$?"'
    rec['runner_cmdline'] = cmdline
    so, se = LOGS / f'{name}.runner.stdout.log', LOGS / f'{name}.runner.stderr.log'
    t0 = time.monotonic()
    rc, _ = shell(cmdline, 'execute', timeout=960, check=False, stdout_path=so, stderr_path=se)
    rec['runner_wall_s'] = round(time.monotonic() - t0, 3)
    rec['t_end'] = device_time()
    stdout = so.read_text(errors='replace')
    m = re.search(r'##EXIT=(\d+)', stdout)
    rec['exit_code'] = int(m.group(1)) if m else None
    rec['adb_rc'] = rc
    time.sleep(3)  # let crash_dump finish writing the tombstone into the crash buffer
    allf = PRIVATE / f'{name}.logcat-all.txt'
    rc, _ = shell('logcat -b all -d -v threadtime -v uid', 'dump all buffers', check=False,
                  stdout_path=allf, stderr_path=PRIVATE / f'{name}.logcat-all.stderr.txt')
    rec['logcat_dump_rc'] = rc
    outdir = PRIVATE / f'{name}.out'
    adb(['pull', out, str(outdir)], 'pull output', timeout=120, check=False)
    native = {}
    if (outdir / 'run.json').exists():
        native = json.loads((outdir / 'run.json').read_text())
        (LOGS / f'{name}.runner.run.json').write_text((outdir / 'run.json').read_text())
    if (outdir / 'memory.json').exists():
        (LOGS / f'{name}.runner.memory.json').write_text((outdir / 'memory.json').read_text())
    rec['runner_pid'] = native.get('pid')
    rec['runner_status'] = native.get('status')
    rec['runner_stage'] = native.get('stage')
    rec['compile_status'] = native.get('compile_status')
    rec['compile_ms'] = native.get('compile_ms')
    rec['gpu_options_toml'] = native.get('gpu_options_toml')
    rec['peak_rss_bytes'] = native.get('peak_rss_bytes')
    rec['is_fully_accelerated'] = native.get('is_fully_accelerated')
    rec['battery_after'] = battery()
    rec['screen_after'] = screen_state()
    all_lines = allf.read_text(errors='replace').splitlines()
    rec['all_buffer_lines'] = len(all_lines)
    stderr = se.read_text(errors='replace')
    sel = re.findall(r'Replacing (\d+) out of (\d+) node\(s\) with delegate \(LITERT_CL\) node, yielding (\d+) partitions', stderr)
    rec['delegate_selection'] = list(map(int, sel[-1])) if sel else None
    rec['stderr_last_lines'] = stderr.strip().splitlines()[-3:]
    window, lo, hi, crash_end = cut_window(all_lines, rec['t_start']['epoch'], rec['t_end']['epoch'], rec['runner_pid'])
    raw = PRIVATE / f'{name}.window.raw.txt'
    raw.write_text('\n'.join(window) + '\n')
    rec['window'] = {'from_epoch': lo, 'to_epoch': hi, 'crash_end_epoch': crash_end, 'lines': len(window),
                     'fatal_signal_lines': [l for l in window if 'Fatal signal' in l],
                     'runner_pid_lines': sum(1 for l in window if LINE_RE.match(l) and
                                             LINE_RE.match(l).group(3) == str(rec['runner_pid']))}
    rec['finished_utc'] = now()
    data['launches'].append(rec)
    save_runjson(data)
    print(json.dumps({k: rec.get(k) for k in ['name', 'graph', 'mode', 'runner_pid', 'exit_code', 'runner_status',
                                              'runner_stage', 'compile_status', 'delegate_selection',
                                              'all_buffer_lines', 'window', 'battery_before', 'battery_after',
                                              'stderr_last_lines']}, indent=1))


def teardown():
    hold_check()
    data = load_runjson()
    shell('svc power stayon false', 'stayon false')
    data['device']['screen_after_teardown'] = screen_state()
    shell(f'rm -rf {REMOTE}', 'remove remote dir')
    shell(f'test ! -e {REMOTE}', 'verify removed')
    data['teardown_utc'] = now()
    data['remote_removed'] = True
    save_runjson(data)
    print('teardown done')


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[:1] == ['setup']:
        setup()
    elif a[:1] == ['launch'] and len(a) == 4:
        launch(a[1], a[2], a[3])
    elif a[:1] == ['teardown']:
        teardown()
    else:
        raise SystemExit(__doc__)
