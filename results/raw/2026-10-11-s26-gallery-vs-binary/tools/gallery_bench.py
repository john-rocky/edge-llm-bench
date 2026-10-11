#!/usr/bin/env python3
"""Google AI Edge Gallery (com.google.ai.edge.gallery) on the Galaxy S26, driven through adb + uiautomator.

The Gallery's Benchmark screen (ui/benchmark/BenchmarkScreen.kt) calls the LiteRT-LM Kotlin `benchmark()` API once per
run with a fresh engine; every run of one session shares one temporary cache dir, so run 1 starts with no cache files
(cold) and runs 2..N start with the files run 1 wrote (cached), all inside one app process. Each `session` here is one
app start -> navigate -> one benchmark of N runs; the app is force-stopped between sessions so that every session's
run 1 is a first engine in a fresh process.

  python3 gallery_bench.py prepare  --out DIR --apk APK --allowlist JSON [--e2b-phone PATH] [--g3-local PATH]
  python3 gallery_bench.py session  --out DIR --model Gemma-4-E2B-it --accel GPU --prefill 1024 --decode 256 --runs 3 \
                                    --tag E2B-gpu-1 [--perfetto-cfg PBTXT]
  python3 gallery_bench.py cleanup  --out DIR [--keep-models]

Numbers are read from the results viewer (two decimals, as the app formats them) at the aggregations avg / min / max,
and from logcat (the engine's own log lines) when it prints them. Nothing here edits the app's own data.
"""
import argparse, json, os, re, subprocess, sys, time
import xml.etree.ElementTree as ET

PKG = "com.google.ai.edge.gallery"
EXT = f"/sdcard/Android/data/{PKG}/files"
MODELS = {
  "Gemma-4-E2B-it": dict(dir="Gemma_4_E2B_it", commit="6e5c4f1e395deb959c494953478fa5cec4b8008f",
                         file="gemma-4-E2B-it.litertlm", size=2588147712,
                         sha="181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c"),
  "Gemma3-1B-IT": dict(dir="Gemma3_1B_IT", commit="42d538a932e8d5b12e6b3b455f5572560bd60b2c",
                       file="gemma3-1b-it-int4.litertlm", size=584417280,
                       sha="1325ae366d31950f137c9c357b9fa89448b176d76998180c08ceaca78bba98be"),
}
SERIAL = os.environ.get("SERIAL", "RFGL80R6A6H")
OUT = None
LOG = None


def say(msg):
  line = f"[{time.strftime('%F %T')}] {msg}"
  print(line, flush=True)
  if LOG:
    with open(LOG, "a") as f:
      f.write(line + "\n")


def adb(*args, timeout=120, check=False, binary=False):
  r = subprocess.run(["adb", "-s", SERIAL, *args], capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL)
  if check and r.returncode != 0:
    raise RuntimeError(f"adb {' '.join(args)} failed: {r.stderr.decode(errors='replace')}")
  return r.stdout if binary else r.stdout.decode(errors="replace").replace("\r", "")


def sh(cmd, timeout=120):
  return adb("shell", cmd, timeout=timeout).strip()


def dsha(path):
  return sh(f"sha256sum {path}").split()[0] if sh(f"test -f {path} && echo y") == "y" else ""


# ---------------------------------------------------------------- UI helpers
class Node:
  def __init__(self, el):
    a = el.attrib
    self.text = a.get("text", ""); self.desc = a.get("content-desc", ""); self.cls = a.get("class", "")
    self.clickable = a.get("clickable") == "true"; self.enabled = a.get("enabled") != "false"
    m = re.findall(r"\d+", a.get("bounds", "[0,0][0,0]"))
    self.x0, self.y0, self.x1, self.y1 = map(int, m[:4]) if len(m) >= 4 else (0, 0, 0, 0)

  @property
  def cx(self): return (self.x0 + self.x1) // 2

  @property
  def cy(self): return (self.y0 + self.y1) // 2

  def __repr__(self): return f"<{self.cls.split('.')[-1]} text={self.text!r} desc={self.desc!r} [{self.x0},{self.y0}][{self.x1},{self.y1}]{' c' if self.clickable else ''}>"


def dump(save_as=None):
  xml = adb("exec-out", "uiautomator", "dump", "/dev/tty", timeout=60)
  i = xml.find("<?xml")
  xml = xml[i:] if i >= 0 else xml
  xml = xml.split("UI hierchary dumped")[0]
  if save_as:
    with open(os.path.join(OUT, save_as), "w") as f:
      f.write(xml)
  try:
    root = ET.fromstring(xml)
  except ET.ParseError as e:
    say(f"dump parse error: {e}; head={xml[:200]!r}")
    return []
  return [Node(el) for el in root.iter("node")]


def find(nodes, text=None, desc=None, contains=None, cls=None, clickable=None):
  out = []
  for n in nodes:
    if text is not None and n.text != text: continue
    if desc is not None and n.desc != desc: continue
    if contains is not None and contains not in n.text and contains not in n.desc: continue
    if cls is not None and not n.cls.endswith(cls): continue
    if clickable is not None and n.clickable != clickable: continue
    out.append(n)
  return out


def tap(n, note=""):
  say(f"tap {note or n!r} at ({n.cx},{n.cy})")
  sh(f"input tap {n.cx} {n.cy}")
  time.sleep(1.0)


def tap_xy(x, y, note=""):
  say(f"tap {note} at ({x},{y})")
  sh(f"input tap {x} {y}")
  time.sleep(1.0)


def screenshot(name):
  png = adb("exec-out", "screencap", "-p", binary=True, timeout=60)
  with open(os.path.join(OUT, name), "wb") as f:
    f.write(png)
  say(f"screenshot {name} ({len(png)} bytes)")


def wait_for(pred, timeout=30, poll=2, what=""):
  t0 = time.time()
  while time.time() - t0 < timeout:
    nodes = dump()
    r = pred(nodes)
    if r:
      return r
    time.sleep(poll)
  raise TimeoutError(f"wait_for {what} timed out after {timeout}s")


def dismiss_dialogs(nodes):
  """Dialogs the app may show after an update; only buttons whose text is in this list are tapped."""
  for label in ("Got it", "OK", "Ok", "Dismiss", "Close", "Not now", "Later"):
    for n in find(nodes, text=label, clickable=True):
      tap(n, f"dialog button {label!r}")
      return True
  return False


# ---------------------------------------------------------------- prepare / cleanup
def prepare(args):
  say(f"prepare: {sh('getprop ro.product.model')} {sh('getprop ro.build.display.id')} sdk {sh('getprop ro.build.version.sdk')}")
  before = sh(f"dumpsys package {PKG} | grep -E 'versionName|versionCode' | head -2").replace("\n", " ")
  say(f"installed before: {before}")
  if args.apk:
    r = subprocess.run(["adb", "-s", SERIAL, "install", "-r", "-g", args.apk], capture_output=True, text=True, timeout=600)
    say(f"adb install -r -g: rc={r.returncode} {r.stdout.strip()} {r.stderr.strip()}")
    if r.returncode != 0:
      raise SystemExit(5)
  after = sh(f"dumpsys package {PKG} | grep -E 'versionName|versionCode|lastUpdateTime' | head -3").replace("\n", " ")
  say(f"installed after: {after}")
  sh(f"am force-stop {PKG}")
  # model files, placed where the app's DownloadWorker would have written them (<ext files>/<normalized name>/<commit>/<file>)
  for name, m in MODELS.items():
    d = f"{EXT}/{m['dir']}/{m['commit']}"; dst = f"{d}/{m['file']}"
    sh(f"mkdir -p {d}")
    have = dsha(dst)
    if have == m["sha"]:
      say(f"{name}: already in place ({have[:12]})"); continue
    t0 = time.time()
    if name == "Gemma-4-E2B-it" and args.e2b_phone and dsha(args.e2b_phone) == m["sha"]:
      sh(f"cp {args.e2b_phone} {dst}", timeout=600); how = f"copied on the phone from {args.e2b_phone}"
    else:
      src = args.e2b_local if name == "Gemma-4-E2B-it" else args.g3_local
      if not src or not os.path.isfile(src):
        raise SystemExit(f"no source for {name}")
      adb("push", src, dst, timeout=1800, check=True); how = "pushed from the Mac"
    got = dsha(dst); size = sh(f"stat -c %s {dst}")
    say(f"{name}: {how} in {time.time()-t0:.0f} s; sha256 {got[:12]} {'ok' if got == m['sha'] else 'MISMATCH'}; bytes {size} {'ok' if int(size) == m['size'] else 'MISMATCH'}")
    if got != m["sha"]:
      raise SystemExit(5)
  if args.allowlist:
    adb("push", args.allowlist, "/data/local/tmp/model_allowlist_test.json", check=True)
    say(f"pushed test allowlist: {sh('sha256sum /data/local/tmp/model_allowlist_test.json')}")
  say("prepare done")


def cleanup(args):
  sh(f"am force-stop {PKG}")
  sh("rm -f /data/local/tmp/model_allowlist_test.json")
  say(f"removed test allowlist: {sh('ls /data/local/tmp/model_allowlist_test.json 2>&1')}")
  if not args.keep_models:
    for name, m in MODELS.items():
      sh(f"rm -rf {EXT}/{m['dir']}")
      say(f"removed {EXT}/{m['dir']}: {sh(f'ls {EXT}/{m[chr(100)+chr(105)+chr(114)]} 2>&1')}")
  say(f"ext files dir now: {sh(f'ls {EXT}')}")


# ---------------------------------------------------------------- one session
def start_app():
  sh(f"am force-stop {PKG}"); time.sleep(1)
  sh(f"am start -W -n {PKG}/.MainActivity", timeout=60); time.sleep(4)


def open_models_list():
  nodes = dump("ui-home.xml")
  dismiss_dialogs(nodes)
  nodes = dump()
  # The home screen's navigation drawer holds "Models"; open it with the top-left button, else via the drawer label.
  drawer = find(nodes, desc="Menu") or find(nodes, desc="Open navigation drawer")
  if drawer:
    tap(drawer[0], "drawer")
  else:
    cands = [n for n in find(nodes, clickable=True) if n.y1 < 400 and n.x0 < 300]
    if not cands:
      screenshot("ui-home-no-drawer.png"); raise RuntimeError("no drawer button found on the home screen")
    tap(min(cands, key=lambda n: (n.y0, n.x0)), "top-left button")
  models = wait_for(lambda ns: find(ns, text="Models"), timeout=15, what="Models in drawer")
  tap(models[0], "Models")
  wait_for(lambda ns: find(ns, contains="Model Manager") or find(ns, contains="Recommended") or find(ns, contains="Gemma"), timeout=20, what="model list")


def open_benchmark(model_name):
  """Model list -> the model item's 'More options' menu -> Benchmark."""
  for attempt in range(6):
    nodes = dump(f"ui-models-{attempt}.xml")
    items = find(nodes, text=model_name)
    if items:
      item = items[0]
      more = find(nodes, desc="More options")
      if not more:
        screenshot("ui-no-more-options.png"); raise RuntimeError(f"{model_name} is listed but has no 'More options' button (not downloaded?)")
      btn = min(more, key=lambda n: abs(n.cy - item.cy))
      say(f"model item {item!r}; menu button {btn!r}")
      tap(btn, "More options")
      bench = wait_for(lambda ns: find(ns, text="Benchmark"), timeout=10, what="Benchmark menu item")
      tap(bench[0], "Benchmark menu item")
      wait_for(lambda ns: find(ns, text="Benchmark model"), timeout=15, what="Benchmark screen")
      return
    sh("input swipe 540 1800 540 900 400"); time.sleep(1.5)
  screenshot("ui-model-not-found.png"); raise RuntimeError(f"{model_name} not found in the model list")


def set_number(label_prefix, value):
  """Type `value` into the number field of the slider row whose label starts with label_prefix."""
  nodes = dump()
  rows = [n for n in nodes if n.text.startswith(label_prefix) or n.desc.startswith(label_prefix)]
  if not rows:
    screenshot(f"ui-no-row-{label_prefix.split()[0]}.png"); raise RuntimeError(f"row {label_prefix!r} not found")
  row = rows[0]
  fields = [n for n in find(nodes, cls="EditText") if n.y0 >= row.y0 - 5 and n.y1 <= row.y1 + 200]
  if fields:
    f = min(fields, key=lambda n: abs(n.cy - row.cy)); x, y = f.cx, f.cy
  else:
    # the 80 dp field sits at the right end of the controls row, under the label
    x, y = row.x1 - 60, row.y1 - 60
  tap_xy(x, y, f"{label_prefix} field")
  sh("input keycombination 113 29"); time.sleep(0.3)   # ctrl+A
  sh(f"input text {value}"); time.sleep(0.5)
  sh("input keyevent 66"); time.sleep(0.8)             # done -> clears focus
  nodes = dump()
  shown = [n for n in nodes if n.text == str(value) or n.text.startswith(label_prefix)]
  say(f"set {label_prefix!r} -> {value}: {shown[:3]}")


def read_results(tag, runs):
  """Dump the results viewer at avg / min / max and parse the stat rows."""
  out = {}
  for agg in ("avg", "min", "max"):
    nodes = dump(f"ui-results-{tag}-{agg}.xml")
    chips = find(nodes, text=agg, clickable=True)
    if chips:
      tap(chips[0], f"aggregation {agg}")
      nodes = dump(f"ui-results-{tag}-{agg}.xml")
    texts = [n.text for n in nodes if n.text] + [n.desc for n in nodes if n.desc]
    out[agg] = texts
  screenshot(f"ui-results-{tag}.png")
  return out


def session(args):
  tag = args.tag
  mark = sh("date '+%m-%d %H:%M:%S.000'")
  say(f"SESSION {tag}: model={args.model} accel={args.accel} prefill={args.prefill} decode={args.decode} runs={args.runs} uptime={sh('cut -d\" \" -f1 /proc/uptime')} gpu_mhz={sh('cat /sys/class/kgsl/kgsl-3d0/clock_mhz')} cpu7_max={sh('cat /sys/devices/system/cpu/cpufreq/policy6/scaling_max_freq')} thermal={sh('dumpsys thermalservice | grep -m1 \"Thermal Status\"')}")
  start_app()
  open_models_list()
  open_benchmark(args.model)
  screenshot(f"ui-bench-{tag}-0.png")
  nodes = dump(f"ui-bench-{tag}-0.xml")
  seg = find(nodes, text=args.accel)
  if not seg:
    raise RuntimeError(f"accelerator button {args.accel!r} not found: {[n.text for n in nodes if n.text]}")
  tap(seg[0], f"accelerator {args.accel}")
  set_number("Prefill tokens", args.prefill)
  set_number("Decode tokens", args.decode)
  set_number("Number of runs", args.runs)
  screenshot(f"ui-bench-{tag}-1.png")
  nodes = dump(f"ui-bench-{tag}-1.xml")
  limit = [n.text for n in nodes if "Ensure that the sum" in n.text]
  say(f"limit line: {limit}")
  run_btn = [n for n in find(nodes, text="Benchmark", clickable=True) if n.y0 > 1200]
  if not run_btn:
    run_btn = [n for n in find(nodes, contains="Benchmark") if n.clickable and n.y0 > 1200]
  if not run_btn:
    raise RuntimeError("Benchmark button not found")
  if not run_btn[0].enabled:
    raise RuntimeError("Benchmark button disabled (token limit)")
  tap(run_btn[0], "Benchmark (run)")
  cont = wait_for(lambda ns: find(ns, text="Continue"), timeout=10, what="confirmation dialog")
  traced = False
  if args.perfetto_cfg:
    adb("push", args.perfetto_cfg, "/data/local/tmp/llm_trace.pbtxt", check=True)
    r = sh(f"perfetto --detach={tag} -c /data/local/tmp/llm_trace.pbtxt --txt -o /data/misc/perfetto-traces/{tag}.perfetto-trace")
    say(f"perfetto started: {r[-120:]}"); traced = True; time.sleep(2)
  t_start = time.time()
  mark = sh("date '+%m-%d %H:%M:%S.000'")
  tap(cont[0], "Continue")
  # wait for the runs: the view model logs "Done #i" per run (Log.d AGBenchmarkVM), and the results viewer appears
  done = 0; t0 = time.time()
  while time.time() - t0 < args.timeout:
    lc = adb("logcat", "-d", "-T", mark, timeout=60)
    done = len(re.findall(r"AGBenchmarkVM: Done #\d+", lc))
    err = [l for l in lc.splitlines() if "AGBenchmarkVM" in l and ("rror" in l or "xception" in l)]
    if err:
      say(f"benchmark error lines: {err[:3]}")
    if done >= args.runs:
      break
    time.sleep(5)
  elapsed = time.time() - t_start
  say(f"runs done: {done}/{args.runs} in {elapsed:.0f} s")
  time.sleep(3)
  if traced:
    sh(f"perfetto --attach={tag} --stop"); time.sleep(2)
    local = os.path.join(args.trace_dir or OUT, f"{tag}.perfetto-trace")
    os.makedirs(os.path.dirname(local), exist_ok=True)
    adb("pull", f"/data/misc/perfetto-traces/{tag}.perfetto-trace", local, timeout=600)
    say(f"perfetto trace: {local} {os.path.getsize(local) if os.path.exists(local) else 'MISSING'} bytes")
    sh(f"rm -f /data/misc/perfetto-traces/{tag}.perfetto-trace")
  lc = adb("logcat", "-d", "-T", mark, timeout=120)
  with open(os.path.join(OUT, f"{tag}.logcat.txt"), "w") as f:
    f.write(lc)
  interesting = [l for l in lc.splitlines() if re.search(r"AGBenchmarkVM|max_tokens|max_num_tokens|Prefill|Decode Speed|Init Total|Time To First|RegisterAccelerator|Benchmark", l)]
  with open(os.path.join(OUT, f"{tag}.logcat-benchmark-lines.txt"), "w") as f:
    f.write("\n".join(interesting))
  say(f"logcat: {len(lc.splitlines())} lines, {len(interesting)} benchmark-related")
  results = read_results(tag, args.runs)
  with open(os.path.join(OUT, f"{tag}.results-ui.json"), "w") as f:
    json.dump(dict(tag=tag, model=args.model, accel=args.accel, prefill=args.prefill, decode=args.decode, runs=args.runs,
                   done=done, elapsed_s=elapsed, ui=results), f, indent=1, ensure_ascii=False)
  say(f"SESSION {tag} END; results in {tag}.results-ui.json")
  sh(f"am force-stop {PKG}")


def main():
  global OUT, LOG
  ap = argparse.ArgumentParser()
  ap.add_argument("cmd", choices=["prepare", "session", "cleanup"])
  ap.add_argument("--out", required=True)
  ap.add_argument("--apk"); ap.add_argument("--allowlist")
  ap.add_argument("--e2b-phone", default="/data/local/tmp/gemma-4-E2B-it.litertlm"); ap.add_argument("--e2b-local"); ap.add_argument("--g3-local")
  ap.add_argument("--model"); ap.add_argument("--accel", default="GPU"); ap.add_argument("--prefill", type=int, default=1024)
  ap.add_argument("--decode", type=int, default=256); ap.add_argument("--runs", type=int, default=3); ap.add_argument("--tag")
  ap.add_argument("--perfetto-cfg"); ap.add_argument("--trace-dir"); ap.add_argument("--timeout", type=int, default=1500)
  ap.add_argument("--keep-models", action="store_true")
  args = ap.parse_args()
  OUT = args.out; os.makedirs(OUT, exist_ok=True); LOG = os.path.join(OUT, "steps.log")
  {"prepare": prepare, "session": session, "cleanup": cleanup}[args.cmd](args)


if __name__ == "__main__":
  main()
