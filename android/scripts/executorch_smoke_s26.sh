#!/usr/bin/env bash
# Galaxy S26 smoke of ExecuTorch llama_main (android arm64-v8a): push, launch, collect, clean up.
#
#   ET_MODEL=<model>.pte ET_TOKENIZER=tokenizer.json \
#   ET_PROMPT_SHORT=short-chat.qwen3.txt ET_PROMPT_LONG=long-context-1024-gen256.qwen3.txt \
#   android/scripts/executorch_smoke_s26.sh <out_dir>
#
# Takes no device hold: the caller holds the phone for the whole call (shared S26). Order:
# preflight -> push (binary, model, tokenizer, the two template-applied prompts) -> short-chat
# cold x2 (ET_GAP s apart) -> 1K task cold x1 -> with the vulkan build present, one short-chat
# launch of that binary on the same model (load and run only, ET_VULKAN_TOKENS tokens) -> the
# device directory is removed (also on failure, by the EXIT trap).
#
# Each launch is one fresh process (cold), unmasked (no taskset: devices/galaxy-s26.md), with
# absolute paths and its stdout / stderr in files on the device, pulled after it exits. The
# on-device sampler reads /proc/<pid>/status (VmRSS, VmHWM, Cpus_allowed_list) every 0.5 s and
# every cpufreq policy's scaling_max_freq when it changes, the same reads as
# android/bench/run_cell.py run_once. Before every launch it waits for thermal status 0, battery
# <= BATTERY_MAX_C and no cpufreq cap; a launch that cannot start before SMOKE_DEADLINE is
# skipped and the script exits 4 after cleaning up.
#
# Output in <out_dir>: per launch <n>-<label>.{cmd,sampler,stdout,stderr}.txt, device_pre.txt,
# device_post.txt, gate.txt, push.txt, cleanup.txt, summary.json and summary.md (metrics from
# the PyTorchObserver JSON: prefill tok/s = prompt_tokens / (prompt_eval_end - inference_start),
# which includes tokenization; decode tok/s = generated_tokens / (inference_end - prompt_eval_end);
# TTFT = first_token - inference_start).
#
# Env:
#   SERIAL            adb serial (default: RFGL80R6A6H, the Galaxy S26)
#   ET_TAG            binary tag dir (default: v1.5.1)
#   BENCH_BIN_ROOT    engine binaries (default: <repo>/android/bin)
#   ET_BIN            xnnpack llama_main (default: <bin root>/executorch-<tag>/llama_main)
#   ET_VULKAN_BIN     vulkan llama_main (default: <bin root>/executorch-<tag>-vulkan/llama_main; skipped if absent)
#   ET_MODEL, ET_TOKENIZER, ET_PROMPT_SHORT, ET_PROMPT_LONG   inputs (required)
#   ET_SHORT_TOKENS / ET_LONG_TOKENS / ET_VULKAN_TOKENS        --max_new_tokens (default: 128 / 256 / 16)
#   ET_GAP            seconds between launches (default: 60)
#   BATTERY_MAX_C     battery temperature gate (default: 36.0)
#   SMOKE_DEADLINE    epoch seconds after which no launch starts (default: now + 780)
set -euo pipefail

OUT="${1:?usage: executorch_smoke_s26.sh <out_dir>}"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SERIAL="${SERIAL:-RFGL80R6A6H}"
TAG="${ET_TAG:-v1.5.1}"
BIN_ROOT="${BENCH_BIN_ROOT:-$REPO_ROOT/android/bin}"
XNN_BIN="${ET_BIN:-$BIN_ROOT/executorch-$TAG/llama_main}"
VK_BIN="${ET_VULKAN_BIN:-$BIN_ROOT/executorch-$TAG-vulkan/llama_main}"
MODEL="${ET_MODEL:?set ET_MODEL (.pte)}"
TOKENIZER="${ET_TOKENIZER:?set ET_TOKENIZER (tokenizer.json)}"
PROMPT_SHORT="${ET_PROMPT_SHORT:?set ET_PROMPT_SHORT}"
PROMPT_LONG="${ET_PROMPT_LONG:?set ET_PROMPT_LONG}"
SHORT_TOKENS="${ET_SHORT_TOKENS:-128}"
LONG_TOKENS="${ET_LONG_TOKENS:-256}"
VK_TOKENS="${ET_VULKAN_TOKENS:-16}"
GAP="${ET_GAP:-60}"
BATTERY_MAX="${BATTERY_MAX_C:-36.0}"
DEADLINE="${SMOKE_DEADLINE:-$(( $(date +%s) + 780 ))}"
DEV=/data/local/tmp/llmbench/executorch
CPUFREQ=/sys/devices/system/cpu/cpufreq

for f in "$XNN_BIN" "$MODEL" "$TOKENIZER" "$PROMPT_SHORT" "$PROMPT_LONG"; do
  [[ -f "$f" ]] || { echo "ERROR: missing $f" >&2; exit 1; }
done
HAVE_VK=0; [[ -f "$VK_BIN" ]] && HAVE_VK=1
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"

adbs() { adb -s "$SERIAL" "$@"; }
[[ "$(adbs get-state 2>/dev/null)" == device ]] || { echo "ERROR: $SERIAL not attached" >&2; exit 3; }
now() { date '+%Y-%m-%d %H:%M:%S'; }

device_state() {  # one block of the phone's state, read now
  echo "== $(now) $1"
  adbs shell "echo model=\$(getprop ro.product.model) android=\$(getprop ro.build.version.release) \
patch=\$(getprop ro.build.version.security_patch) soc=\$(getprop ro.soc.model); \
dumpsys thermalservice | grep -m1 'Thermal Status'; \
dumpsys battery | grep -E '^  (level|temperature|status|AC powered|USB powered):'; \
dumpsys power | grep -m1 mWakefulness=; \
for p in $CPUFREQ/policy*; do h=; m=; r=; read h <\$p/cpuinfo_max_freq; read m <\$p/scaling_max_freq; \
read r <\$p/related_cpus; echo \"CPUFREQ \${p##*/} hw=\$h max=\$m cpus=\$r\"; done; \
df -h /data | tail -1"
}

gate() {  # wait for thermal 0, battery <= BATTERY_MAX, no cpufreq cap; 1 = deadline reached first
  local label=$1 state thermal temp capped
  while :; do
    (( $(date +%s) < DEADLINE )) || return 1
    state="$(adbs shell "dumpsys thermalservice | grep -m1 'Thermal Status'; \
dumpsys battery | grep -m1 temperature; \
for p in $CPUFREQ/policy*; do h=; m=; read h <\$p/cpuinfo_max_freq; read m <\$p/scaling_max_freq; \
[ \"\$m\" -lt \"\$h\" ] && echo \"CAP \${p##*/} \$m/\$h\"; done; true" | tr -d '\r')"
    thermal="$(sed -n 's/.*Thermal Status: *\([0-9]*\).*/\1/p' <<<"$state")"
    temp="$(sed -n 's/.*temperature: *\([0-9]*\).*/\1/p' <<<"$state")"
    capped="$(grep '^CAP' <<<"$state" | tr '\n' ' ' || true)"
    echo "$(now) gate[$label] thermal=${thermal:-?} battery=${temp:-?}/10C ${capped:-no-cap}" >>"$OUT/gate.txt"
    if [[ "$thermal" == 0 && -n "$temp" && -z "$capped" ]] &&
       python3 -c "import sys; sys.exit(0 if int('$temp') / 10 <= float('$BATTERY_MAX') else 1)"; then
      return 0
    fi
    sleep 10
  done
}

cleanup() {
  local rc=$?
  {
    echo "== $(now) cleanup (exit $rc)"
    adbs shell "rm -rf $DEV; ls -d $DEV 2>&1; true" || echo "cleanup adb failed"
    adbs shell "ls /data/local/tmp/llmbench 2>&1 | head -20" || true
  } >>"$OUT/cleanup.txt" 2>&1
  device_state post >"$OUT/device_post.txt" 2>&1 || true
}

device_state pre >"$OUT/device_pre.txt" 2>&1
cat "$OUT/device_pre.txt"
trap cleanup EXIT

# on-device runner for one launch: the sampler loop of run_cell.run_once around one engine process
RUN_ONE="$OUT/run_one.sh"
cat >"$RUN_ONE" <<'SH'
# usage: sh run_one.sh <bin> <model> <tokenizer> <prompt file> <max_new_tokens> <out prefix>
bin=$1; model=$2; tok=$3; prompt=$4; n=$5; out=$6
CPUFREQ=/sys/devices/system/cpu/cpufreq
cd "${bin%/*}" || exit 90
( exec "$bin" --model_path="$model" --tokenizer_path="$tok" --prompt_file="$prompt" \
    --temperature=0 --max_new_tokens="$n" >"$out.stdout" 2>"$out.stderr" </dev/null ) &
pid=$!
read up _ </proc/uptime
echo "LAUNCH pid=$pid uptime=$up"
for p in $CPUFREQ/policy*; do h=; r=; read h <$p/cpuinfo_max_freq; read r <$p/related_cpus; echo "CPUPOLICY ${p##*/} ${h:--} $r"; done
pc=
tick() { c=CPUMAX; for f in $CPUFREQ/policy*/scaling_max_freq; do m=; read m <$f; c="$c ${m:--}"; done; [ "$c" = "$pc" ] || echo "$c"; pc=$c; }
tick
i=0
while kill -0 $pid 2>/dev/null; do
  grep -E 'VmRSS|VmHWM|Cpus_allowed_list' /proc/$pid/status 2>/dev/null
  if [ $i -eq 1 ]; then comm=; read comm </proc/$pid/comm; echo "COMM $comm EXE $(readlink /proc/$pid/exe)"; fi
  i=$((i + 1))
  tick
  sleep 0.5
done
wait $pid; ec=$?
read up _ </proc/uptime
echo "END uptime=$up"
echo "EXIT_CODE=$ec"
SH

push_one() {  # <local> <device path>: push, then compare size and sha256
  local src=$1 dst=$2 want have
  adbs push "$src" "$dst" >/dev/null
  want="$(shasum -a 256 "$src" | cut -d' ' -f1)"
  have="$(adbs shell "sha256sum $dst" | cut -d' ' -f1)"
  echo "$(now) $dst $(wc -c <"$src" | tr -d ' ') bytes sha256 $want $([[ "$want" == "$have" ]] && echo match || echo "MISMATCH device=$have")" | tee -a "$OUT/push.txt"
  [[ "$want" == "$have" ]]
}

adbs shell "mkdir -p $DEV/out"
push_one "$XNN_BIN" "$DEV/llama_main"
adbs shell "chmod 755 $DEV/llama_main"
push_one "$MODEL" "$DEV/model.pte"
push_one "$TOKENIZER" "$DEV/tokenizer.json"
push_one "$PROMPT_SHORT" "$DEV/short-chat.txt"
push_one "$PROMPT_LONG" "$DEV/long-context-1024-gen256.txt"
push_one "$RUN_ONE" "$DEV/run_one.sh"
if (( HAVE_VK )); then
  adbs shell "mkdir -p $DEV/vulkan"
  push_one "$VK_BIN" "$DEV/vulkan/llama_main"
  adbs shell "chmod 755 $DEV/vulkan/llama_main"
fi

SKIPPED=0
launch() {  # <n> <label> <device binary> <device prompt> <max_new_tokens>
  local n=$1 label=$2 bin=$3 prompt=$4 tokens=$5 stem
  stem="$n-$label"
  if ! gate "$stem"; then
    echo "$(now) $stem skipped: gate not met before the deadline" | tee -a "$OUT/gate.txt"
    SKIPPED=$((SKIPPED + 1)); return 0
  fi
  echo "$(now) sh $DEV/run_one.sh $bin $DEV/model.pte $DEV/tokenizer.json $prompt $tokens $DEV/out/$stem" >"$OUT/$stem.cmd.txt"
  echo "$(now) launch $stem"
  adbs shell "sh $DEV/run_one.sh $bin $DEV/model.pte $DEV/tokenizer.json $prompt $tokens $DEV/out/$stem" \
    >"$OUT/$stem.sampler.txt" 2>&1 || echo "WARN: adb shell exit $? for $stem"
  adbs exec-out cat "$DEV/out/$stem.stdout" >"$OUT/$stem.stdout.txt" || true
  adbs exec-out cat "$DEV/out/$stem.stderr" >"$OUT/$stem.stderr.txt" || true
  grep -h -E '^(EXIT_CODE|END)' "$OUT/$stem.sampler.txt" || true
}

pause() { (( $(date +%s) + GAP < DEADLINE )) && sleep "$GAP" || true; }
launch 1 short-chat "$DEV/llama_main" "$DEV/short-chat.txt" "$SHORT_TOKENS"
pause
launch 2 short-chat "$DEV/llama_main" "$DEV/short-chat.txt" "$SHORT_TOKENS"
pause
launch 3 long-context-1024-gen256 "$DEV/llama_main" "$DEV/long-context-1024-gen256.txt" "$LONG_TOKENS"
if (( HAVE_VK )); then
  pause
  launch 4 short-chat-vulkan "$DEV/vulkan/llama_main" "$DEV/short-chat.txt" "$VK_TOKENS"
fi

python3 - "$OUT" "$PROMPT_SHORT" "$PROMPT_LONG" <<'PY'
import glob, json, os, re, statistics, sys
out, prompt_short, prompt_long = sys.argv[1:4]
prompts = {"short-chat": open(prompt_short, encoding="utf-8").read(),
           "long-context-1024-gen256": open(prompt_long, encoding="utf-8").read()}
rows = []
for cmd in sorted(glob.glob(os.path.join(out, "*.cmd.txt"))):
    stem = os.path.basename(cmd)[:-len(".cmd.txt")]
    read = lambda ext: open(os.path.join(out, f"{stem}.{ext}.txt"), encoding="utf-8", errors="replace").read() \
        if os.path.exists(os.path.join(out, f"{stem}.{ext}.txt")) else ""
    sampler, stdout, stderr = read("sampler"), read("stdout"), read("stderr")
    row = {"launch": stem}
    m = re.search(r"^EXIT_CODE=(\d+)", sampler, re.M)
    row["exitCode"] = int(m.group(1)) if m else None
    up = [float(x) for x in re.findall(r"uptime=([\d.]+)", sampler)]
    row["wallS"] = round(up[1] - up[0], 2) if len(up) == 2 else None
    hwm = [int(x) for x in re.findall(r"^VmHWM:\s+(\d+)", sampler, re.M)]
    rss = [int(x) for x in re.findall(r"^VmRSS:\s+(\d+)", sampler, re.M)]
    row["vmHWMMB"] = round(max(hwm) / 1024, 1) if hwm else None
    row["vmRSSMedianMB"] = round(statistics.median(rss) / 1024, 1) if rss else None
    row["rssReads"] = len(rss)
    allowed = re.findall(r"^Cpus_allowed_list:\s+(\S+)", sampler, re.M)
    row["cpusAllowedList"] = sorted(set(allowed))
    order = re.findall(r"^CPUPOLICY (\S+) (\S+) (.*)$", sampler, re.M)
    maxes = [line.split()[1:] for line in re.findall(r"^CPUMAX .*$", sampler, re.M)]
    freq = {}
    for i, (name, hw, cpus) in enumerate(order):
        vals = [int(v[i]) for v in maxes if len(v) == len(order) and v[i].isdigit()]
        if vals and hw.isdigit():
            freq[name] = {"minMHz": min(vals) // 1000, "hwMHz": int(hw) // 1000, "cpus": cpus.strip()}
    row["cpuMaxFreqMHz"] = freq
    row["cpuCapped"] = [k for k, v in freq.items() if v["minMHz"] < v["hwMHz"]]
    m = re.search(r"^PyTorchObserver (\{.*\})\s*$", stdout, re.M)
    obs = json.loads(m.group(1)) if m else None
    row["observer"] = obs
    if obs:
        t = obs
        prefill_ms = t["prompt_eval_end_ms"] - t["inference_start_ms"]
        decode_ms = t["inference_end_ms"] - t["prompt_eval_end_ms"]
        row.update({
            "promptTokens": t["prompt_tokens"], "generatedTokens": t["generated_tokens"],
            "prefillTokPerS": round(t["prompt_tokens"] / prefill_ms * 1000, 1) if prefill_ms > 0 else None,
            "decodeTokPerS": round(t["generated_tokens"] / decode_ms * 1000, 1) if decode_ms > 0 else None,
            "ttftMs": t["first_token_ms"] - t["inference_start_ms"],
            "loadMs": t["model_load_end_ms"] - t["model_load_start_ms"],
            "prefillMs": prefill_ms, "decodeMs": decode_ms,
        })
    task = "long-context-1024-gen256" if "long-context" in stem else "short-chat"
    body = stdout[:m.start()] if m else stdout
    prompt = prompts[task]
    row["echoedPrompt"] = body.startswith(prompt)
    text = body[len(prompt):] if body.startswith(prompt) else body
    row["text"] = text.rstrip("\n")
    row["textHead60"] = row["text"][:60]
    m = re.search(r"Resetting threadpool with num threads = (\d+)", stderr)
    row["threads"] = int(m.group(1)) if m else None
    row["backendLines"] = [l for l in stderr.splitlines()
                           if re.search(r"backend|xnnpack|vulkan|delegate", l, re.I)]
    row["errorLines"] = [l for l in stderr.splitlines() if l.startswith(("E ", "F "))]
    rows.append(row)
    with open(os.path.join(out, f"{stem}.text.txt"), "w", encoding="utf-8") as fh:
        fh.write(row["text"] + "\n")
json.dump(rows, open(os.path.join(out, "summary.json"), "w"), indent=2, ensure_ascii=False)
hdr = ("| launch | exit | prompt tok | gen tok | prefill tok/s | decode tok/s | TTFT ms | load ms "
       "| VmHWM MB | threads | cpus | capped | text (first 60) |")
lines = [hdr, "|" + "---|" * (hdr.count("|") - 1)]
for r in rows:
    lines.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
        r["launch"], r["exitCode"], r.get("promptTokens"), r.get("generatedTokens"),
        r.get("prefillTokPerS"), r.get("decodeTokPerS"), r.get("ttftMs"), r.get("loadMs"),
        r["vmHWMMB"], r["threads"], ",".join(r["cpusAllowedList"]), ",".join(r["cpuCapped"]) or "none",
        r["textHead60"].replace("\n", "\\n").replace("|", "\\|")))
open(os.path.join(out, "summary.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("\n".join(lines))
PY

if (( SKIPPED )); then
  echo "== $SKIPPED launch(es) skipped (gate not met before the deadline)"; exit 4
fi
echo "== done: $OUT"
