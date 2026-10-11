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
  # the app's own language was set to en-US for the sitting (the phone is ja-JP; the driver matches English labels)
  sh(f"cmd locale set-app-locales {PKG} --user 0")
  say(f"app locales reset: {sh(f'cmd locale get-app-locales {PKG} --user 0')}")
  sh("rm -f /data/local/tmp/model_allowlist_test.json /data/local/tmp/gallery-sampler.sh /data/local/tmp/gallery-sample-*.csv /data/misc/perfetto-configs/llm_trace.pbtxt")
  say(f"removed test allowlist: {sh('ls /data/local/tmp/model_allowlist_test.json 2>&1')}")
  if not args.keep_models:
    for name, m in MODELS.items():
      sh(f"rm -rf {EXT}/{m['dir']}")
      say(f"removed {EXT}/{m['dir']}: {sh(f'ls {EXT}/{m[chr(100)+chr(105)+chr(114)]} 2>&1')}")
  say(f"ext files dir now: {sh(f'ls {EXT}')}")


# ---------------------------------------------------------------- one session
SAMPLER = "/data/local/tmp/gallery-sampler.sh"
SAMPLER_SH = r"""#!/system/bin/sh
# 1 s sampler beside a Gallery session (same columns as binary_runs.sh): epoch, uptime, policy0 cur/max kHz, policy6 cur/max kHz,
# GPU MHz, GPU busy %, thermal zones 36 5 24 63 55 (gpuss-0, cpu-0-0-0, cpu-1-0-0, battery, sys-therm-0) in m°C.
tag=$1; out=/data/local/tmp/gallery-sample-$tag.csv; rm -f $out
while :; do
  echo "$(date +%s) $(cut -d' ' -f1 /proc/uptime) $(cat /sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq /sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq /sys/devices/system/cpu/cpufreq/policy6/scaling_cur_freq /sys/devices/system/cpu/cpufreq/policy6/scaling_max_freq /sys/class/kgsl/kgsl-3d0/clock_mhz /sys/class/kgsl/kgsl-3d0/gpu_busy_percentage 2>/dev/null | tr '\n' ' ') $(for z in 36 5 24 63 55; do cat /sys/class/thermal/thermal_zone$z/temp; done | tr '\n' ' ')" >> $out
  sleep 1
done
"""


def start_sampler(tag):
  """The sampler loop runs in a remote shell held open by a Mac-side adb client (a loop backgrounded inside its own
  `adb shell` call keeps that call from returning); stop_sampler kills the loop on the phone, then the client exits."""
  local = os.path.join(OUT, "gallery-sampler.sh")
  with open(local, "w") as f:
    f.write(SAMPLER_SH)
  adb("push", local, SAMPLER, check=True)
  p = subprocess.Popen(["adb", "-s", SERIAL, "shell", f"sh {SAMPLER} {tag}"], stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
  say(f"sampler started for {tag} (client pid {p.pid})")
  return p


def stop_sampler(p, tag):
  sh(f"pkill -f 'gallery-sampler.sh {tag}'")
  try:
    p.wait(timeout=10)
  except subprocess.TimeoutExpired:
    p.kill()
  adb("pull", f"/data/local/tmp/gallery-sample-{tag}.csv", os.path.join(OUT, f"{tag}.sample.csv"), timeout=60)
  sh(f"rm -f /data/local/tmp/gallery-sample-{tag}.csv")
  n = sum(1 for _ in open(os.path.join(OUT, f"{tag}.sample.csv"))) if os.path.exists(os.path.join(OUT, f"{tag}.sample.csv")) else 0
  say(f"sampler stopped for {tag}: {n} samples")


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
  """Models page -> the model item's expanded panel -> its 'Benchmark' action button (DownloadModelPanel.kt: shown for a
  downloaded LLM when the page passes showBenchmarkActionButton; the 'More options' menu holds only Delete)."""
  for attempt in range(8):
    nodes = dump(f"ui-models-{attempt}.xml")
    items = find(nodes, text=model_name)
    if items:
      item = items[0]
      if item.cy > 1900:                     # near the navigation bar: a tap there hits the nav buttons (Recents opened at 15:44); scroll first
        sh("input swipe 540 1500 540 700 400"); time.sleep(1.5)
        nodes = dump(f"ui-models-{attempt}-scrolled.xml")
        items = find(nodes, text=model_name)
        if not items:
          continue
        item = items[0]
      def button(ns, it):
        return [n for n in find(ns, text="Benchmark") if it.cy < n.cy < it.cy + 900]
      bench = button(nodes, item)
      if not bench:
        tap(item, "model item (expand)"); time.sleep(1.5)
        nodes = dump(f"ui-models-{attempt}-expanded.xml")
        items = find(nodes, text=model_name)
        item = items[0] if items else item
        bench = button(nodes, item)
      if not bench:
        screenshot("ui-no-benchmark-button.png"); raise RuntimeError(f"{model_name} is listed but shows no Benchmark button")
      say(f"model item {item!r}; benchmark button {bench[0]!r}")
      tap(bench[0], "Benchmark button")
      wait_for(lambda ns: find(ns, text="Benchmark model") or [n for n in ns if n.text.startswith("Prefill tokens")], timeout=15, what="Benchmark screen")
      return
    sh("input swipe 540 1800 540 900 400"); time.sleep(1.5)
  screenshot("ui-model-not-found.png"); raise RuntimeError(f"{model_name} not found in the model list")


def keyboard_shown():
  return "mInputShown=true" in sh("dumpsys input_method | grep -m1 mInputShown")


def hide_keyboard():
  """BACK closes an open soft keyboard (never sent when no keyboard is up: it would leave the screen)."""
  for _ in range(3):
    if not keyboard_shown():
      return
    sh("input keyevent 4"); time.sleep(0.8)
  say("keyboard still shown after 3 BACKs")


def number_fields(nodes):
  """The three EditTexts of the screen, top to bottom (prefill, decode, runs), with the keyboard closed."""
  return sorted(find(nodes, cls="EditText"), key=lambda n: n.cy)


def set_number(label_prefix, value):
  """Type `value` into the number field of the slider row whose label starts with label_prefix.
  The keyboard is closed first: with it open the lower rows scroll out of view and a blind tap types into the wrong field
  (attempt 3 of E2B-gpu-1 put the run count into the decode field; the run button check caught it)."""
  hide_keyboard()
  nodes = dump()
  rows = [n for n in nodes if n.text.startswith(label_prefix) or n.desc.startswith(label_prefix)]
  if not rows:
    screenshot(f"ui-no-row-{label_prefix.split()[0]}.png"); raise RuntimeError(f"row {label_prefix!r} not found")
  row = rows[0]
  fields = [n for n in find(nodes, cls="EditText") if n.y0 >= row.y0 - 5 and n.y1 <= row.y1 + 200]
  if not fields:
    screenshot(f"ui-no-field-{label_prefix.split()[0]}.png"); raise RuntimeError(f"no number field under {label_prefix!r}: {number_fields(nodes)}")
  f = min(fields, key=lambda n: abs(n.cy - row.cy))
  tap_xy(f.cx, f.cy, f"{label_prefix} field")
  sh("input keycombination 113 29"); time.sleep(0.3)   # ctrl+A
  sh(f"input text {value}"); time.sleep(0.5)
  sh("input keyevent 66"); time.sleep(0.8)             # done
  hide_keyboard()
  nodes = dump()
  rows = [n for n in nodes if n.text.startswith(label_prefix)]
  fields = [n for n in find(nodes, cls="EditText") if rows and n.y0 >= rows[0].y0 - 5 and n.y1 <= rows[0].y1 + 200]
  got = fields[0].text if fields else None
  say(f"set {label_prefix!r} -> {value}: field reads {got!r}; all fields {[n.text for n in number_fields(nodes)]}")
  if got != str(value):
    screenshot(f"ui-set-failed-{label_prefix.split()[0]}.png"); raise RuntimeError(f"{label_prefix!r} reads {got!r}, wanted {value}")


METRICS = [("Prefill speed", "prefill_tok_s"), ("Decode speed", "decode_tok_s"), ("Time to first token", "ttft_s"),
           ("First init time", "first_init_ms"), ("Steady init time", "steady_init_ms")]


def graph_point_order(png_path, n_points):
  """Rank the n points of the series graph by height. The sheet plots the runs left to right (x at the graph's left edge,
  evenly spaced, right edge) and the value on y; a tap only reads the y axis, so the per-run value comes from matching the
  points' order of height to the sorted {min, median, max} the sheet prints. Returns the list of ranks per run
  (0 = lowest value) or None when the picture does not resolve."""
  from PIL import Image
  im = Image.open(png_path).convert("L"); w, h = im.size
  # graph box: the light band under "Tap on graph to see value" (y ~1775..2015 at 1080x2340); find it from the picture:
  # rows whose middle is light-blue background and whose dark pixels are few. Use a fixed region, scaled by height.
  y0, y1 = int(h * 0.758), int(h * 0.862)
  xs = [int(w * 0.078)] if n_points == 1 else [int(w * 0.078 + (w * 0.922 - w * 0.078) * i / (n_points - 1)) for i in range(n_points)]
  px = im.load(); ys = []
  for x in xs:
    dark = [(yy, xx) for yy in range(y0, y1) for xx in range(max(0, x - 22), min(w, x + 22)) if px[xx, yy] < 150]
    if len(dark) < 20:
      return None
    ys.append(sum(d[0] for d in dark) / len(dark))
  order = sorted(range(n_points), key=lambda i: -ys[i])      # largest y (lowest on screen) = smallest value
  ranks = [0] * n_points
  for rank, i in enumerate(order):
    ranks[i] = rank
  return ranks, ys


def read_results(tag, runs):
  """The new result card (expanded): the five rows at the 'avg' aggregation, then each row's series sheet."""
  out = {}
  nodes = dump(f"ui-results-{tag}.xml")
  screenshot(f"ui-results-{tag}.png")
  for label, key in METRICS:
    rows = [n for n in nodes if n.desc.startswith(label + ":")]
    if rows:
      out[key] = {"avg_text": rows[0].desc}
    else:
      lab = find(nodes, text=label)
      if lab:
        vals = [n for n in nodes if n.cls.endswith("TextView") and n.x0 >= lab.x1 - 5 and abs(n.cy - lab[0].cy) < 40] if False else \
               [n for n in nodes if n.cls.endswith("TextView") and n.x0 >= lab[0].x1 - 5 and abs(n.cy - lab[0].cy) < 40 and re.fullmatch(r"[0-9.]+", n.text)]
        out[key] = {"avg_text": f"{label}: {vals[0].text if vals else '?'}"}
  for label, key in METRICS:
    if key == "first_init_ms":
      continue                                     # one value (run 1); the card shows it directly
    lab = find(nodes, text=label)
    if not lab:
      continue
    vals = [n for n in nodes if n.cls.endswith("TextView") and n.clickable and n.x0 >= lab[0].x1 - 5 and abs(n.cy - lab[0].cy) < 80 and re.fullmatch(r"[0-9.]+", n.text)]
    if not vals:
      say(f"{label}: no clickable value"); continue
    tap(vals[0], f"{label} value (series sheet)"); time.sleep(0.8)
    sheet = dump(f"ui-series-{tag}-{key}.xml")
    stats = {}
    for agg in ("avg", "median", "min", "max"):
      lab2 = find(sheet, text=agg)
      if lab2:
        above = [n for n in sheet if n.cls.endswith("TextView") and re.fullmatch(r"[0-9.]+", n.text) and abs(n.x0 - lab2[0].x0) < 60 and -5 <= lab2[0].y0 - n.y1 < 40]
        if above:
          stats[agg] = above[0].text
    title = [n.text for n in sheet if n.text.endswith(")") and "(" in n.text and n.y0 > 1400]
    png = f"ui-series-{tag}-{key}.png"
    screenshot(png)
    n_points = runs - 1 if key == "steady_init_ms" else runs
    per_run = None
    try:
      r = graph_point_order(os.path.join(OUT, png), n_points)
      if r:
        ranks, ys = r
        ordered = sorted(float(v) for k, v in stats.items() if k in ("min", "median", "max"))
        if n_points == 3 and len(set(ordered)) == 3:
          per_run = [ordered[rk] for rk in ranks]
        elif n_points == 2 and "min" in stats and "max" in stats:
          per_run = [float(stats["max"]) if rk == 1 else float(stats["min"]) for rk in ranks]
        elif n_points == 1 and "avg" in stats:
          per_run = [float(stats["avg"])]
        out[key]["point_y"] = ys
    except Exception as e:
      say(f"graph ranking failed for {key}: {e}")
    out[key].update({"title": title, "stats": stats, "per_run_by_graph": per_run})
    say(f"{label}: {stats} per-run (graph order) {per_run}")
    sh("input keyevent 4"); time.sleep(0.8)        # close the sheet
  return out


def session(args):
  tag = args.tag
  if args.read_only:
    results = read_results(tag, args.runs)
    with open(os.path.join(OUT, f"{tag}.results-ui.json"), "w") as f:
      json.dump(dict(tag=tag, model=args.model, accel=args.accel, prefill=args.prefill, decode=args.decode, runs=args.runs, ui=results), f, indent=1, ensure_ascii=False)
    say(f"read-only: results in {tag}.results-ui.json")
    return
  mark = sh("date '+%m-%d %H:%M:%S.000'")
  say(f"app locales: {sh(f'cmd locale get-app-locales {PKG} --user 0')}; system: {sh('getprop persist.sys.locale')}")
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
  hide_keyboard()
  nodes = dump(f"ui-bench-{tag}-1.xml")
  limit = [n.text for n in nodes if "Ensure that the sum" in n.text]
  say(f"limit line: {limit}")
  vals = [n.text for n in number_fields(nodes)]
  if vals != [str(args.prefill), str(args.decode), str(args.runs)]:
    screenshot(f"ui-values-{tag}.png"); raise RuntimeError(f"fields read {vals}, wanted {[args.prefill, args.decode, args.runs]}")
  say(f"fields verified: prefill/decode/runs = {vals}")
  labels = find(nodes, text="Benchmark")            # the bottom-right run button's label (the title is 'Benchmark model')
  if not labels:
    screenshot(f"ui-no-run-button-{tag}.png"); raise RuntimeError("Benchmark button not found")
  lab = max(labels, key=lambda n: n.cy)
  holders = [n for n in nodes if n.clickable and n.x0 <= lab.cx <= n.x1 and n.y0 <= lab.cy <= n.y1]
  if holders and not all(h.enabled for h in holders):
    screenshot(f"ui-run-disabled-{tag}.png"); raise RuntimeError("Benchmark button disabled (token limit)")
  tap(lab, "Benchmark (run)")
  cont = wait_for(lambda ns: find(ns, text="Continue"), timeout=10, what="confirmation dialog")
  traced = False
  if args.perfetto_cfg:
    # the perfetto command cannot read a config under /data/local/tmp (errno 13); /data/misc/perfetto-configs is for that
    adb("push", args.perfetto_cfg, "/data/misc/perfetto-configs/llm_trace.pbtxt", check=True)
    r = sh(f"perfetto --detach={tag} -c /data/misc/perfetto-configs/llm_trace.pbtxt --txt -o /data/misc/perfetto-traces/{tag}.perfetto-trace")
    say(f"perfetto started: {r[-120:]}"); traced = True; time.sleep(2)
  sampler = start_sampler(tag)
  time.sleep(2)
  t_start = time.time()
  mark = sh("date '+%m-%d %H:%M:%S.000'")
  mark_iso = sh("date '+%Y-%m-%d %H:%M:%S'")
  tap(cont[0], "Continue")
  # wait for the runs. The release build prints no AGBenchmarkVM lines, so completion = the new result card: the
  # view model adds it after the loop (addBenchmarkResult), with the session's start time as its title line. UI dumps
  # cost the phone a little CPU, so nothing is polled before --min-wait seconds, then every --poll seconds.
  done = 0; t0 = time.time(); card_ts = None
  time.sleep(args.min_wait)
  while time.time() - t0 < args.timeout:
    nodes = dump()
    if dismiss_dialogs(nodes):             # e.g. the one-time sheet "How to compare benchmark runs" (Dismiss) over the viewer
      time.sleep(1.0); nodes = dump()
    stamps = [n.text for n in nodes if re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", n.text)]
    new = [t for t in stamps if t >= mark_iso]
    results = [n.text for n in nodes if re.fullmatch(r"Results \((\d+) runs?\)", n.text)]
    first_init = find(nodes, text="First init time")
    if new and results and first_init:
      m = re.fullmatch(r"Results \((\d+) runs?\)", results[0]); done = int(m.group(1)); card_ts = max(new)
      break
    say(f"waiting: stamps={stamps[:3]} results={results} {time.time()-t0:.0f} s")
    time.sleep(args.poll)
  elapsed = time.time() - t_start
  say(f"runs done: {done}/{args.runs} in {elapsed:.0f} s (card {card_ts})")
  time.sleep(3)
  stop_sampler(sampler, tag)
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
  interesting = [l for l in lc.splitlines() if re.search(r"AGBenchmarkVM|max_tokens|max_num_tokens|Prefill|Decode Speed|Init Total|Time To First|RegisterAccelerator|Benchmark|litert|LiteRt|tflite|OpenCL|xnnpack|XNNPACK", l)]
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
  ap.add_argument("--perfetto-cfg"); ap.add_argument("--trace-dir"); ap.add_argument("--timeout", type=int, default=900)
  ap.add_argument("--min-wait", type=int, default=20, help="seconds after Continue before the first UI poll")
  ap.add_argument("--poll", type=int, default=8, help="seconds between UI polls while the runs go")
  ap.add_argument("--read-only", action="store_true", help="session: only read the newest result card on the current screen")
  ap.add_argument("--keep-models", action="store_true")
  args = ap.parse_args()
  OUT = args.out; os.makedirs(OUT, exist_ok=True); LOG = os.path.join(OUT, "steps.log")
  {"prepare": prepare, "session": session, "cleanup": cleanup}[args.cmd](args)


if __name__ == "__main__":
  main()
