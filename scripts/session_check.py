#!/usr/bin/env python3
"""session_check — the review a person did before committing a dashboard job's campaign dirs,
as code: PASS / HOLD / FAIL per dir.

  python3 scripts/session_check.py <campaign dir>... [--json <out>] [--markdown <out>]
  python3 scripts/session_check.py results/raw/2026-10-15-dashboard-v1-pixel8a-0180-p4{-anchor,}-android

Rules, their sources (commit hashes, doc sections) and the allow-list format:
docs/session-check-v1.md. Verdicts:

  PASS  commit as is: every rule passed, or a finding is excused by an allow-list line
        (ops/session-check/allow-list.tsv: rule, dir glob, detail substring, commit, reason)
  HOLD  a person decides: a timeout, a partial sitting, a FAILURES / LEVEL / DEGENERATE line,
        a text-check FAIL, an engine stamp off the registry, a prompt that did not reach the
        engine whole, a reply that fails the machine proxies, a dir that is not a job campaign
        (a DDP dir is a job campaign when the job's SESSION.json names it: a lab unit's sitting,
        kind "job payload (ddp)", read by the job-session rules without the anchor-pair ones)
  FAIL  do not commit: refused at admission, a stopped sitting's quarantine, no SESSION.json
        in a dir the job made, an unscrubbed or execution-level DDP logcat, model weights, a
        trace or an engine binary, a credential, a payload whose anchor phase is gone

Exit 0 = every dir PASS, 1 = a HOLD or a FAIL, 2 = usage. Reads only: the dirs, the git index
and HEAD of the repo that holds them (tracked files, the committed results/summary as the
history of prompt token counts), the pin registries as they stood when the sitting ran, and the
job's logs and ledger under logs/dashboard-job/. Needs no device and no network.

What stays a person's: reading one reply per cell. The markdown output lists one sample per
cell with text; no verdict reads it (docs/session-check-v1.md, "A person reads").
"""
import argparse
import collections
import csv
import datetime
import fnmatch
import getpass
import glob
import io
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "android", "bench"))
sys.path.insert(0, os.path.join(ROOT, "android", "ddp"))
from build_summary import cpu_cap_drop_of, platform_of  # noqa: E402
from cell_gate import degenerate  # noqa: E402
from dashboard_job import anchor_cells, session_stats  # noqa: E402
from parsers import (RE_LLAMA_BRACKET, RE_LLAMA_LOG, RE_ORTGENAI_OUTPUT, litert_reply,  # noqa: E402
                     llama_cli_reply, text_integrity)
from render_leaderboard import CPU_CAP_EXEMPT_ARMS, CPU_CAP_MAX_DROP_PCT  # noqa: E402
from scrub import scrub_text  # noqa: E402

ALLOW_LIST = os.path.join(ROOT, "ops", "session-check", "allow-list.tsv")
SESSION_SCHEMA = "dashboard-job-session.v1"
JOB = "dashboard-v1"            # the "job" value scripts/dashboard_job.py write_session stamps
# a Developer Device Platform lab unit's sitting the job ran (dashboard_job.py ddp_sitting): no anchor
# phase, its runs carry their own cap marks and text check (docs/dashboard-autopilot-v1.md §9)
JOB_DDP = "job payload (ddp)"
DASHBOARD_CAMPAIGN = "-dashboard-v1-"
ANCHOR_CAMPAIGN_RE = re.compile(r"-dashboard-v1-.*-anchor-")
STOPPED_RE = re.compile(r"-stopped(-|$)")
PLATFORM_OF_TOKEN = {"mac": "mac", "ios": "iphone", "android": "android"}   # dir suffix -> bench platform
MIN_ANCHOR_RUNS = 2             # schedule.json admission.min_anchor_runs (design §4)
# the largest file ever committed under results/raw is 4,961,673 bytes (git ls-tree, 2026-10-18)
BIG_FILE_BYTES = 5_000_000
# model weights and raw traces (.gitignore "Models and weights — never commit"; 7362040, f3db1b2),
# and engine binaries (.gitignore android/bin/: build output; no executable or library has ever
# been committed under results/raw)
WEIGHT_TRACE_EXT = (".litertlm", ".gguf", ".pte", ".onnx", ".onnx.data", ".safetensors", ".bin",
                    ".tflite", ".task", ".mlpackage", ".mlmodelc", ".mlmodel", ".aimodel",
                    ".perfetto-trace", ".trace", ".perf.data", ".xnnpack_cache",
                    ".so", ".dylib", ".a", ".apk", ".aar", ".ipa")
BINARY_MAGIC = (b"\x7fELF", b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe")
SCAN_MAX_BYTES = 20_000_000     # content scans skip larger files (they fail big-file anyway)
# credentials (memory: xctrace bundles, ps eww and crash dumps carry ANTHROPIC_API_KEY; c32f470)
SECRET_RES = [
    ("anthropic key", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    ("anthropic key variable", re.compile(r"ANTHROPIC_API_KEY\s*[=:]\s*[\"']?[A-Za-z0-9_-]{8,}")),
    ("hugging face token", re.compile(r"\bhf_[A-Za-z0-9]{30,}")),
    ("github token", re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})")),
    ("aws key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("google oauth token", re.compile(r"\bya29\.[0-9A-Za-z_-]{20,}")),
    ("google api key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("slack token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}")),
]
# the reply proxies' text screen is the Android runner's own (fairness-rules §12): the task
# prompts' subject is on-device AI, so a reply without its terms is off the prompt
TEXT_TASKS = ("short-chat", "long-context-")
PROTOCOL_TASK_PREFIX = "native-benchmark-"
# the rules whose finding means "do not commit"; every other rule's finding is a HOLD
FAIL_RULES = {"session-missing", "not-admitted", "stopped-sitting", "logcat-unscrubbed",
              "big-file", "secret", "pair-broken"}
# platform blocks of environment.lock.json registered after the fact: the newest registry's block,
# with the date it became true (`since`), covers a sitting on or after that date that the registry
# of its day did not know (arms.litert-lm.mac: the Mac yardstick stamps v0.18.0 from the
# 2026-10-12 sitting on, registered 2026-10-18)
REGISTERED_LATER = (("litert-lm", "mac"),)


# ---------------------------------------------------------------- small helpers

def run(cmd, cwd=None):
    """(rc, stdout) of a read-only command; never raises."""
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)
        return p.returncode, p.stdout
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""


def read_text(path, limit=SCAN_MAX_BYTES):
    """A text file's content, or None when it is binary (NUL in the first 8 KB), too big or
    unreadable."""
    try:
        if os.path.getsize(path) > limit:
            return None
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return None
    if b"\0" in data[:8192]:
        return None
    return data.decode("utf-8", "replace")


def parse_time(text):
    """A record or SESSION.json time -> aware datetime (naive = the host's local time), or None."""
    if not text:
        return None
    try:
        t = datetime.datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.astimezone()


def cell_of(r):
    """A cell as findings name it: arm, model, task and the engine build its records stamp."""
    return (f"{r.get('runtime')} {(r.get('model') or {}).get('id')} {r.get('task')} "
            f"({r.get('engineVersion') or 'unstamped'})")


def short(text, n=100):
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[:n - 1] + "…"


# ---------------------------------------------------------------- repo state (cached)

class Repo:
    """The git work tree that holds a set of campaign dirs: which files are tracked, which
    would be committed, the committed summary, the pin registries over time, the job logs."""

    def __init__(self, top):
        self.top = top
        self._status = None
        self._history = None
        self._registry = {}
        self._registry_commits = None
        self._job_campaigns = None
        self._ledger = None

    def status(self):
        """relpath -> 'tracked' | 'untracked' | 'ignored' under results/raw."""
        if self._status is None:
            st = {}
            if self.top:
                for mode, flags in (("tracked", ["-c"]), ("untracked", ["-o", "--exclude-standard"]),
                                    ("ignored", ["-o", "-i", "--exclude-standard"])):
                    rc, out = run(["git", "-C", self.top, "ls-files", "-z"] + flags + ["--", "results/raw"])
                    for p in out.split("\0"):
                        if p:
                            st.setdefault(p, mode)
            self._status = st
        return self._status

    def tracked_dirs(self):
        return {p.split("/")[2] for p, m in self.status().items()
                if m == "tracked" and p.count("/") >= 3}

    def history(self, override=None):
        """Rows of the committed results/summary/device-runs.csv (git HEAD), or of --history."""
        if self._history is None:
            text = ""
            if override:
                text = open(override).read()
            elif self.top:
                rc, text = run(["git", "-C", self.top, "show", "HEAD:results/summary/device-runs.csv"])
            self._history = list(csv.DictReader(io.StringIO(text))) if text else []
        return self._history

    def registry_at(self, when, day=None):
        """(android pins, environment.lock.json, where) as committed at the newest change at or
        before `when` (the sitting's first record), read from git history; the files on disk
        when the history is not there (a shallow CI clone, a dir outside git). A platform block
        registered after the fact (REGISTERED_LATER: it names the date it became true, `since`)
        is taken from the newest registry into one of a day that did not have it, for a sitting
        on or after that date (`day`, sitting_day); `where` says so."""
        base = self.top or ROOT
        if self._registry_commits is None:
            self._registry_commits = []
            rc, out = run(["git", "-C", base, "log", "--format=%H %cI", "--",
                           "android/engine-pins.json", "environment.lock.json"])
            for ln in out.splitlines():
                sha, _, when_c = ln.partition(" ")
                t = parse_time(when_c)
                if t:
                    self._registry_commits.append((t, sha))
            self._registry_commits.sort(reverse=True)
        commit = next((sha for t, sha in self._registry_commits if when and t <= when), None)
        pins, lock, where = self.registry_of(commit)
        newest = self._registry_commits[0][1] if self._registry_commits else None
        if newest == commit:
            return pins, lock, where
        _, last, last_where = self.registry_of(newest)
        for arm, plat in REGISTERED_LATER:
            block = (((last.get("arms") or {}).get(arm) or {}).get(plat)) or {}
            have = (((lock.get("arms") or {}).get(arm) or {}).get(plat))
            if have or not block_applies(block, day):
                continue
            lock = dict(lock, arms=dict(lock.get("arms") or {}))
            lock["arms"][arm] = dict(lock["arms"].get(arm) or {}, **{plat: block})
            where += f"; arms.{arm}.{plat} as registered at {last_where} (since {block.get('since')})"
        return pins, lock, where

    def registry_of(self, commit):
        """(android pins, environment.lock.json, where) at a commit, or on disk (commit None)."""
        base = self.top or ROOT
        key = commit or "disk"
        if key not in self._registry:
            def load(rel):
                if commit:
                    rc, out = run(["git", "-C", base, "show", f"{commit}:{rel}"])
                    try:
                        return json.loads(out) if rc == 0 else {}
                    except ValueError:
                        return {}
                try:
                    return json.load(open(os.path.join(base, rel)))
                except (OSError, ValueError):
                    return {}
            self._registry[key] = (load("android/engine-pins.json"), load("environment.lock.json"),
                                   commit[:8] if commit else "disk")
        return self._registry[key]

    def job_campaigns(self, log_dir=None):
        """Campaign names the job's sitting logs name (`--campaign <name>` in a bench matrix
        line), or None when there are no job logs to read."""
        if self._job_campaigns is None:
            d = log_dir or (os.path.join(self.top, "logs", "dashboard-job") if self.top else None)
            names = set()
            files = sorted(glob.glob(os.path.join(d, "*.log"))) if d and os.path.isdir(d) else []
            for f in files:
                text = read_text(f) or ""
                names.update(re.findall(r"--campaign (\S+)", text))
            self._job_campaigns = names if files else None
        return self._job_campaigns

    def ledger(self, path=None):
        if self._ledger is None:
            p = path or (os.path.join(self.top, "logs", "dashboard-job", "ledger.tsv") if self.top else None)
            rows = []
            if p and os.path.exists(p):
                with open(p) as fh:
                    rows = list(csv.DictReader(fh, delimiter="\t"))
            self._ledger = rows
        return self._ledger


def repo_of(path, cache):
    rc, out = run(["git", "-C", path, "rev-parse", "--show-toplevel"])
    top = out.strip() if rc == 0 and out.strip() else None
    if top not in cache:
        cache[top] = Repo(top)
    return cache[top]


# ---------------------------------------------------------------- one campaign dir

def load_records(d):
    """(path, record) of every run record build_summary.py reads from this dir: app-path*/*.json
    and device-jsonl/*.json at any depth, the dir's own *.jsonl; deduplicated by id. Files that
    do not parse come back as (path, None), except a Mac native-benchmark cell's .jsonl, which is
    one YARDSTICK_NATIVE_OK text line by design (c32f470) and is read through app-path-native."""
    out, seen = [], set()

    def add(path, rec):
        rid = rec.get("id")
        if rid and rid in seen:
            return
        if rid:
            seen.add(rid)
        if rec.get("metrics"):
            out.append((path, rec))

    for f in sorted(glob.glob(os.path.join(d, "**", "app-path*", "*.json"), recursive=True)
                    + glob.glob(os.path.join(d, "**", "device-jsonl", "*.json"), recursive=True)):
        try:
            rec = json.load(open(f))
        except (OSError, ValueError):
            out.append((f, None))
            continue
        if isinstance(rec, dict):
            add(f, rec)
    for f in sorted(glob.glob(os.path.join(d, "*.jsonl"))):
        text = (read_text(f) or "").strip()
        if not text or text.startswith("YARDSTICK_NATIVE_OK"):
            continue
        try:
            recs = [json.loads(text)]
        except ValueError:
            try:
                recs = [json.loads(ln) for ln in text.splitlines() if ln.strip()]
            except ValueError:
                out.append((f, None))
                continue
        for rec in recs:
            if isinstance(rec, dict):
                add(f, rec)
    return out


def read_session(d):
    """The dir's SESSION.json when it is a dashboard-job-session.v1 record, else None."""
    p = os.path.join(d, "SESSION.json")
    try:
        s = json.load(open(p))
    except (OSError, ValueError):
        return None
    return s if isinstance(s, dict) and s.get("schema") == SESSION_SCHEMA else None


def kind_of(name, d, session, records, job_campaigns):
    """job payload / job anchor / job payload (ddp) / job (stopped) / hand run / DDP / dev."""
    if name.endswith("-dev"):
        return "dev"
    if (os.path.isdir(os.path.join(d, "ddp")) or os.path.isdir(os.path.join(d, "ddp-session"))
            or "-ddp-" in name
            or any(isinstance((r.get("device") or {}).get("ddp"), dict) for _, r in records if r)):
        # the job's lab-unit sitting closes with its SESSION.json; a DDP dir without one ran by hand
        return JOB_DDP if session is not None and session.get("job") == JOB else "DDP"
    if STOPPED_RE.search(name):
        return "job (stopped)"
    if session is not None and session.get("job") == JOB:
        return "job anchor" if session.get("phase") == "anchor" else "job payload"
    if session is None and DASHBOARD_CAMPAIGN in name:
        base = re.sub(r"-(mac|ios|android)$", "", name)
        if job_campaigns is None or base in job_campaigns:
            return "job anchor" if ANCHOR_CAMPAIGN_RE.search(name) else "job payload"
    return "hand run"


def reply_text(path, rec, cache):
    """(source, text) of the reply a record's run printed, or (None, None): the record's
    outputSample (Apple), its stored decoded text (Android context-prompt), else read out of its
    engine log by the runner's own parsers (Android short-chat records carry no text)."""
    if rec.get("outputSample") is not None:
        return "outputSample", rec.get("outputSample") or ""
    prov = rec.get("provenance") or {}
    base = os.path.dirname(path)
    if prov.get("decodedText"):
        p = os.path.join(base, prov["decodedText"])
        text = cache_text(p, cache)
        if text is not None:
            return os.path.basename(p), text
    log = prov.get("rawLog")
    if not log:
        return None, None
    p = os.path.join(base, os.path.basename(log))
    text = cache_text(p, cache)
    if text is None:
        return None, None
    rt = rec.get("runtime") or ""
    if rt.startswith("llama.cpp"):
        return os.path.basename(p), llama_reply(text)
    if rt.startswith("onnxruntime-genai"):
        m = RE_ORTGENAI_OUTPUT.findall(text)
        return (os.path.basename(p), m[-1].strip()) if m else (None, None)
    if rt.startswith("litert-lm"):
        out = text.split("===ENGINE_OUTPUT===", 1)[-1]
        if re.search(r"^.* Running single-turn conversation\s*$", out, re.M):
            return os.path.basename(p), litert_reply(text)
        return os.path.basename(p), litert_main_reply(out)
    return None, None


# llama-cli b8999 between its prompt echo and the reply: a spinner drawn with backspaces
RE_SPINNER = re.compile(r"(?:[|/\\ -]\x08)+")
RE_LLAMA_PRINT = re.compile(r"^\w+_print: ")


def llama_reply(text):
    """The reply llama-cli printed: after its prompt echo ("> …", the first 500 bytes and
    " ... (truncated)" for a long prompt) and the backspace spinner that follows it, up to the
    "[ Prompt: … ]" line, its *_print: lines (common_memory_breakdown_print) and -lv 4 log lines
    taken out. Without that layout, android/bench/parsers.llama_cli_reply."""
    out = text.split("===ENGINE_OUTPUT===", 1)[-1]
    stop = RE_LLAMA_BRACKET.search(out)
    out = out[:stop.start()] if stop else out
    echo = re.search(r"(?m)^> ", out)
    spin = RE_SPINNER.search(out, echo.start()) if echo else None
    if not spin:
        return llama_cli_reply(text)
    kept = [RE_LLAMA_LOG.sub("", ln) for ln in out[spin.end():].splitlines()
            if not RE_LLAMA_PRINT.match(ln)]
    return "\n".join(kept).strip()


# the on-device sampler's lines run_cell.py interleaves with the engine's console
RE_SAMPLER_LINE = re.compile(r"^(?:[A-Za-z_]+:\t.*|CPU[A-Z]+ .*|[A-Z_]+ policy\d.*)$")
RE_ENGINE_LOG_LINE = re.compile(r"^(?:INFO|WARNING|ERROR|VERBOSE|DEBUG): .*$|^[IWEF]\d{4} \d\d:\d\d:")


def litert_main_reply(out):
    """The reply litert_lm_main's short-chat launch streamed: between its input_prompt line and
    the column-zero BenchmarkInfo marker (android/bench/parsers.py module doc), the engine's and
    the sampler's log lines taken out."""
    start = re.search(r"^input_prompt: .*$", out, re.M)
    body = out[start.end():] if start else out
    stop = re.search(r"(?m)^BenchmarkInfo:\s*$", body)
    body = body[:stop.start()] if stop else body
    kept = [ln for ln in body.splitlines()
            if not RE_SAMPLER_LINE.match(ln) and not RE_ENGINE_LOG_LINE.match(ln)]
    return "\n".join(kept).strip()


def cache_text(path, cache):
    if path not in cache:
        cache[path] = read_text(path) if os.path.isfile(path) else None
    return cache[path]


def resolve_raw_log(path, rec, d, top):
    """Where a record's provenance.rawLog is: beside the record, in the campaign dir, or at the
    repo path the log names (an import names the console by its results/raw/ path)."""
    log = (rec.get("provenance") or {}).get("rawLog")
    if not log:
        return None, None
    cands = [os.path.join(os.path.dirname(path), log), os.path.join(d, os.path.basename(log))]
    if "results/raw/" in log:
        tail = log[log.index("results/raw/"):]
        cands.append(os.path.join(top or os.path.dirname(os.path.dirname(os.path.dirname(d))), tail))
        cands.append(os.path.join(os.path.dirname(d), tail[len("results/raw/"):]))
    return log, next((c for c in cands if os.path.isfile(c)), None)


def sitting_day(name, when):
    """The local date a sitting ran: the YYYY-MM-DD its campaign name starts with (the job names a
    sitting by its local day), else its first record's date on this host; None without either."""
    m = re.match(r"(\d{4}-\d{2}-\d{2})-", name or "")
    if m:
        try:
            return datetime.date.fromisoformat(m.group(1))
        except ValueError:
            pass
    return when.astimezone().date() if when else None


def block_applies(block, day):
    """A registry block with a tag applies to a sitting on or after its `since` day (YYYY-MM-DD);
    without a since, or a sitting day, always."""
    if not block or not block.get("tag"):
        return False
    try:
        since = datetime.date.fromisoformat(str(block.get("since")))
    except ValueError:
        return True
    return day is None or day >= since


def registry_pin(platform, runtime, pins, lock, day=None):
    """(pin, registry key) the registry names for a record's arm, or (None, why). The Mac's LiteRT-LM
    is arms.litert-lm.mac when the lock has that block and the sitting's day (sitting_day) is on or
    after its since day; the iPhone's, and the Mac's without it, default_tag."""
    arms = (lock or {}).get("arms") or {}
    if platform == "android":
        ap = (pins or {}).get("android_pins") or {}
        if runtime in ("llama.cpp-npu", "llama.cpp-gpu", "litert-lm-npu"):
            return None, "side build (engine-build=, its own tag)"
        for prefix, key in (("litert-lm", "litert-lm"), ("llama.cpp", "llama.cpp"),
                            ("onnxruntime-genai", "onnxruntime-genai"), ("executorch", "executorch")):
            if runtime == prefix or runtime.startswith(prefix + "-"):
                if ap.get(key):
                    return ap[key], f"android/engine-pins.json android_pins.{key}"
                # before android_pins (2026-10-15, d33ffa53) the lock carried the Android pins
                arm = arms.get(key) or {}
                droid = arm.get("android") or {}
                aar = re.search(r"/download/v?([0-9][^/]*)/", (droid.get("release_aar") or {}).get("url", ""))
                pin = (droid.get("tag") or droid.get("tag_built") if key == "litert-lm" else
                       arm.get("tag") if key in ("llama.cpp", "executorch") else
                       aar.group(1) if aar else None)
                return pin, f"environment.lock.json arms.{key} (android)"
        return None, "no registry entry"
    if runtime in ("litert-lm", "litert-lm-cpu"):
        litert = arms.get("litert-lm") or {}
        mac = litert.get("mac") or {}
        if platform == "mac" and block_applies(mac, day):
            return mac["tag"], f"environment.lock.json arms.litert-lm.mac.tag (since {mac.get('since')})"
        return litert.get("default_tag"), "environment.lock.json arms.litert-lm.default_tag"
    if runtime == "llama.cpp":
        return (arms.get("llama.cpp") or {}).get("tag"), "environment.lock.json arms.llama.cpp.tag"
    if runtime == "mlx-swift":
        return (arms.get("mlx-swift-lm") or {}).get("revision"), "environment.lock.json arms.mlx-swift-lm.revision"
    if runtime == "core-ai":
        return (arms.get("coreai-models") or {}).get("tag"), "environment.lock.json arms.coreai-models.tag"
    if runtime == "core-ai-ane":
        return ((arms.get("coreai-models") or {}).get("stock-v1") or {}).get("describe"), \
            "environment.lock.json arms.coreai-models.stock-v1.describe"
    if runtime.startswith("onnxruntime-genai") and platform == "mac":
        return (((arms.get("onnxruntime-genai") or {}).get("mac") or {}).get("packages") or {}).get(
            "onnxruntime-genai"), "environment.lock.json arms.onnxruntime-genai.mac.packages"
    if runtime.startswith("onnxruntime-genai"):
        url = (((arms.get("onnxruntime-genai") or {}).get(platform) or {}).get("release_zip") or {}).get("url", "")
        m = re.search(r"/download/v?([0-9][^/]*)/", url)
        return (m.group(1) if m else None), f"environment.lock.json arms.onnxruntime-genai.{platform}.release_zip"
    if runtime.startswith("executorch") and platform == "mac":
        return (arms.get("executorch") or {}).get("tag"), "environment.lock.json arms.executorch.tag"
    for arm, key in (("cactus", "commit"), ("uzu", "tag")):
        if runtime == arm:
            return (arms.get(arm) or {}).get(key), f"environment.lock.json arms.{arm}.{key}"
    return None, "no registry entry"


def stamp_matches(stamp, pin):
    """The pin appears in the stamp as a whole version token (v-prefix optional)."""
    p = re.escape(pin.lstrip("v"))
    return re.search(r"(?<![0-9A-Za-z.])v?" + p + r"(?![0-9A-Za-z])", stamp or "") is not None


# ---------------------------------------------------------------- allow-list

def load_allow_list(path):
    """[{rule, dir, match, commit, reason, line}] from the TSV; raises ValueError on a malformed
    line (exit 2): every line names its rule, its dir glob, its detail substring (or *), the
    commit whose message gives the reason, and the reason."""
    entries = []
    if not path or not os.path.exists(path):
        return entries
    with open(path) as fh:
        for n, raw in enumerate(fh, 1):
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) != 5 or not all(p.strip() for p in parts):
                raise ValueError(f"{path}:{n}: want 5 tab-separated fields (rule, dir, match, commit, reason)")
            rule, dirglob, match, commit, reason = (p.strip() for p in parts)
            if not re.fullmatch(r"[0-9a-f]{7,40}", commit):
                raise ValueError(f"{path}:{n}: commit {commit!r} is not a hash")
            if match.startswith("re:"):
                try:
                    re.compile(match[3:])
                except re.error as e:
                    raise ValueError(f"{path}:{n}: match {match!r}: {e}")
            entries.append({"rule": rule, "dir": dirglob, "match": match, "commit": commit,
                            "reason": reason, "line": n})
    return entries


def allowed(finding, name, entries):
    """The first allow-list line that excuses a finding: same rule, the dir name matches its glob,
    and its match is * , a substring of the detail, or re:<regex> found in the detail."""
    for e in entries:
        m = e["match"]
        hit = (m == "*" or (re.search(m[3:], finding["detail"]) is not None if m.startswith("re:")
                            else m in finding["detail"]))
        if e["rule"] == finding["rule"] and fnmatch.fnmatch(name, e["dir"]) and hit:
            return e
    return None


# ---------------------------------------------------------------- the check

class Check:
    def __init__(self, path, ctx):
        self.path = os.path.abspath(path.rstrip("/"))
        self.name = os.path.basename(self.path)
        self.raw = os.path.dirname(self.path)
        self.ctx = ctx
        self.repo = repo_of(self.path, ctx["repos"])
        self.findings = []
        self.notes = []
        self.samples = []
        self.texts = {}

    def add(self, rule, detail):
        self.findings.append({"rule": rule, "severity": "FAIL" if rule in FAIL_RULES else "HOLD",
                              "detail": detail})

    def note(self, text):
        self.notes.append(text)

    # -- files the commit would carry
    def files(self):
        """(path in the dir, path, tracked | untracked | ignored) of every file; outside a git work
        tree every file counts as untracked (the commit would carry it)."""
        out = []
        st = self.repo.status()
        rel_base = os.path.relpath(self.path, self.repo.top) if self.repo.top else None
        for a, dirs, fs in os.walk(self.path):
            for f in fs:
                p = os.path.join(a, f)
                rel = os.path.relpath(p, self.path)
                mode = "untracked" if rel_base is None else st.get(os.path.join(rel_base, rel), "ignored")
                out.append((rel, p, mode))
        return out

    def run(self):
        self.session = read_session(self.path)
        self.records = load_records(self.path)
        recs = [(p, r) for p, r in self.records if r is not None]
        self.kind = kind_of(self.name, self.path, self.session, recs,
                            self.repo.job_campaigns(self.ctx["job_logs"]))
        files = self.files()
        self.counts = collections.Counter(m for _, _, m in files)
        if self.counts["tracked"] and self.counts["untracked"]:
            left = sorted(rel for rel, _, m in files if m == "untracked")
            self.note(f"committed dir ({self.counts['tracked']} tracked files); untracked beside them: "
                      + ", ".join(left[:3]) + (f" and {len(left) - 3} more" if len(left) > 3 else ""))
        self.check_files(files)
        self.check_stopped()
        for p, r in self.records:
            if r is None:
                self.add("record-unreadable", f"{os.path.relpath(p, self.path)} does not parse")
        if self.kind in ("job anchor", "job payload", JOB_DDP):
            self.check_job(recs)
        elif self.kind != "job (stopped)":
            self.add("not-job", f"{self.kind}: not a dashboard job campaign; a person reviews it "
                                f"(the job-session rules do not cover it)")
            if self.session is not None and self.session.get("admitted") is False:
                self.add("not-admitted", f"admitted false ({self.session.get('verdict')}): "
                                         f"{short(self.session.get('reason'), 120)}")
        self.ledger_row = self.find_ledger()
        self.apply_allow_list()
        return self

    # ------------------------------------------------------------ rules: every kind
    def check_files(self, files):
        user = self.ctx["user"]
        user_res = [re.compile(re.escape(form)) for form in
                    (f"/Users/{user}", f"/home/{user}", f"-Users-{user}-", f"_bazel_{user}")] if user else []
        if user:
            user_res.append(re.compile(r"(?<![A-Za-z0-9])" + re.escape(user) + r"\s+(staff|wheel|admin)\b"))
        ddp = self.kind in ("DDP", JOB_DDP)
        named = []
        for rel, p, mode in files:
            if mode == "ignored":
                continue
            try:
                size = os.path.getsize(p)
            except OSError:
                continue
            low = rel.lower()
            try:
                with open(p, "rb") as fh:
                    magic = fh.read(4)
            except OSError:
                magic = b""
            if any(part.endswith(ext) for part in low.split("/") for ext in WEIGHT_TRACE_EXT) \
                    or os.path.basename(low) == "perf.data" or magic in BINARY_MAGIC:
                self.add("big-file", f"{rel} ({size / 1e6:.1f} MB, {mode}): model weights, a raw trace "
                                     f"or an engine binary")
                continue
            elif size > BIG_FILE_BYTES:
                self.add("big-file-size", f"{rel} ({size / 1e6:.1f} MB, {mode}): larger than any file "
                                          f"committed under results/raw so far (4.96 MB)")
            is_logcat = "logcat" in os.path.basename(low) and low.endswith(".txt")
            in_ddp_tree = ddp or "/ddp/" in "/" + low or low.startswith("ddp-session/")
            if is_logcat and in_ddp_tree and re.search(r"(^|/)execution-[^/]+/logcat\.txt$", rel):
                self.add("logcat-unscrubbed", f"{rel} ({mode}): the execution-level logcat.txt stays out "
                                              f"of every commit")
                continue
            text = read_text(p)
            if text is None:
                continue
            if is_logcat and in_ddp_tree:
                _, counts = scrub_text(text)
                left = {k: v for k, v in counts.items() if v}
                if left:
                    self.add("logcat-unscrubbed", f"{rel} ({mode}): network identifiers scrub.py replaces "
                                                  f"remain ({', '.join(f'{k} {v}' for k, v in sorted(left.items()))})")
            for label, rx in SECRET_RES:
                if rx.search(text):
                    self.add("secret", f"{rel} ({mode}): {label}")
            if any(rx.search(text) for rx in user_res):
                named.append(f"{rel} ({mode})")
        if named:
            self.add("user-name", f"the account name in a path in {len(named)} files (replace it by "
                                  f"USER): " + ", ".join(named[:3]) + (" …" if len(named) > 3 else ""))

    def check_stopped(self):
        if STOPPED_RE.search(self.name):
            self.add("stopped-sitting", "the quarantine of a stopped sitting (-stopped- in the name): "
                                        "kept on disk, never committed")

    # ------------------------------------------------------------ rules: job campaigns
    def check_job(self, recs):
        s = self.session
        if s is None:
            self.add("session-missing", "no SESSION.json: the job never closed this sitting "
                                        "(killed, or still running)")
        else:
            self.check_session(s, recs)
        self.check_records(recs)

    def check_session(self, s, recs):
        phase = s.get("phase")
        verdict = s.get("verdict")
        reason = s.get("reason") or ""
        unjudged = (phase == "payload" and verdict == "TIMEOUT" and s.get("admitted") is False
                    and reason == "anchor-short" and self.own_anchor_runs(recs) >= MIN_ANCHOR_RUNS)
        if s.get("admitted") is False and not unjudged:
            self.add("not-admitted", f"admitted false ({verdict}): {short(reason, 120)}")
        if verdict in ("TIMEOUT", "DEVICE"):
            extra = ""
            if unjudged:
                extra = (f"; SESSION.json says admitted false (anchor-short), but the job re-judged "
                         f"the payload's own anchor on a summary bench matrix never rebuilt (killed at "
                         f"the timeout) while the dir holds {self.own_anchor_runs(recs)} usable "
                         f"primary-anchor runs: the admission is unjudged, a person re-judges it")
            self.add("verdict", f"verdict {verdict}{extra}")
        rc = s.get("runner_exit")
        if rc not in (0, None, 124):
            self.add("runner-exit", f"runner_exit {rc}")
        if phase == "payload":
            exp, have = s.get("cells_expected"), s.get("cells_with_records")
            if isinstance(exp, int) and isinstance(have, int) and have < exp:
                self.add("partial", f"{have} of {exp} cells with records (SESSION.json)")
        for line in self.lines("FAILURES.txt"):
            self.add("failures", f"{line} (cell records in the dir: {self.cell_records(line, recs)})")
        for line in self.lines("FLAGGED.txt"):
            verdicts = set(re.findall(r"\b(SHORT|DEAD|DEGENERATE|HOT|SPREAD|COLLAPSE|LEVEL|GATE_ERROR)\b", line))
            if not line.startswith("GATE_FAIL") or not verdicts:
                self.add("flagged", f"unrecognized FLAGGED line: {short(line, 160)}")
            elif verdicts & {"LEVEL", "DEGENERATE", "GATE_ERROR"}:
                self.add("flagged", short(line, 200))
            else:
                self.note(f"FLAGGED (retry kept, renders ⚠): {short(line, 160)}")
        for line in self.lines("SKIPPED.txt"):
            self.note(f"SKIPPED: {short(line, 160)}")
        if "non-nominal start" in reason:
            self.note(f"admission: {short(reason, 160)}")
        if self.kind == JOB_DDP:
            # a lab unit's sitting has no anchor phase and no admission reference: the pair rules are n/a
            self.note("pair rules n/a: a DDP lab unit's sitting has no anchor phase (SESSION.json anchor "
                      "null); its runs carry their own cap marks and text check")
        else:
            self.check_pair(s)

    @staticmethod
    def cell_records(line, recs):
        """Records of the cell a FAILURES.txt line names ("[FAIL ]<runtime> <model> <task> …"; an
        Android line names the bare runtime, its records the backend arm)."""
        parts = line.split()
        if parts[:1] == ["FAIL"]:
            parts = parts[1:]
        if len(parts) < 3:
            return 0
        rt, model, task = parts[:3]
        return sum(1 for _, r in recs
                   if (r.get("runtime") == rt or (r.get("runtime") or "").startswith(rt + "-"))
                   and (r.get("model") or {}).get("id") == model and r.get("task") == task)

    def lines(self, name):
        out = []
        for f in (os.path.join(self.path, name), os.path.join(self.path, "app-path-android", name)):
            out += [ln.rstrip("\n") for ln in open(f) if ln.strip()] if os.path.exists(f) else []
        return out

    def own_anchor_runs(self, recs):
        """Usable runs of the platform's primary anchor in this dir (dashboard_job.session_stats,
        the basis admit() judges: warm on Apple, cold on Android, cache-build runs out)."""
        token = self.name.rsplit("-", 1)[-1]
        plat = PLATFORM_OF_TOKEN.get(token)
        if not plat:
            return 0
        try:
            cells = anchor_cells({"anchors": "matrices/anchors.cells"}, plat)
        except (OSError, KeyError, ValueError):
            return 0
        if not cells:
            return 0
        c = cells[0]
        rows = [{"first_ever": str(bool((r.get("metrics") or {}).get("firstEver"))),
                 "cold_run": str(bool((r.get("metrics") or {}).get("coldRun"))),
                 "decode_tps": str((r.get("metrics") or {}).get("decodeTokensPerSecond") or 0),
                 "thermal_initial": (r.get("metrics") or {}).get("initialThermalState") or ""}
                for _, r in recs
                if r.get("runtime") == c["arm"] and (r.get("model") or {}).get("id") == c["model_id"]
                and r.get("task") == c["task"]]
        regime = "cold" if plat == "android" else "warm"
        return session_stats(rows, regime)[1]

    def check_pair(self, s):
        """A payload and its anchor phase are one sitting: both go into the record together, and
        the admission reference must be in the record too (0684f01)."""
        sessions = self.ctx["sessions"](self.raw)
        tracked = self.repo.tracked_dirs()
        in_set = self.ctx["names"]
        if s.get("phase") == "payload":
            a = os.path.basename(s.get("anchor_phase") or "")
            asess = sessions.get(a)
            if not a or not os.path.isdir(os.path.join(self.raw, a)):
                self.add("pair-broken", f"anchor phase {a or '(none named)'} is not on disk")
            elif asess is None or asess.get("admitted") is False:
                self.add("pair-broken", f"anchor phase {a} has no admitted SESSION.json")
            elif a not in tracked and a not in in_set:
                self.add("pair-incomplete", f"anchor phase {a} is neither committed nor in this set")
        elif s.get("phase") == "anchor":
            payloads = sorted(n for n, ss in sessions.items()
                              if os.path.basename(ss.get("anchor_phase") or "") == self.name)
            if not payloads and s.get("admitted") is not False:
                self.add("pair-incomplete", "no payload dir names this anchor phase (the sitting "
                                            "stopped after admission?)")
            for p in payloads:
                if p not in tracked and p not in in_set:
                    self.add("pair-incomplete", f"payload {p} is neither committed nor in this set")
        prim = next((a for a in ((s.get("anchor") or {}).get("anchors") or []) if a.get("primary")), None)
        ref = os.path.basename(((prim or {}).get("reference") or {}).get("campaign") or "")
        own = os.path.basename(s.get("anchor_phase") or "")
        if ref and ref not in (self.name, own) and ref not in tracked and ref not in in_set:
            self.add("reference-uncommitted", f"admission reference {ref} is neither committed nor in "
                                              f"this set")

    # ------------------------------------------------------------ rules: records
    def check_records(self, recs):
        if not recs:
            return
        when = min((t for t in (parse_time(r.get("timestamp")) for _, r in recs) if t), default=None)
        day = sitting_day(self.name, when)
        pins, lock, where = self.repo.registry_at(when, day)
        hist = self.history_index()
        by_cell = collections.defaultdict(list)
        for p, r in recs:
            by_cell[cell_of(r)].append((p, r))
        stamps = collections.defaultdict(collections.Counter)
        sha_fix = self.ctx["sha_fix"]
        raw_missing, debug = [], []
        for cell, items in by_cell.items():
            p0, r0 = items[0]
            rt, task = r0.get("runtime") or "", r0.get("task") or ""
            plat = platform_of(r0)
            for p, r in items:
                stamps[(plat, rt)][r.get("engineVersion") or "(none)"] += 1
                dev = r.get("device") or {}
                if "debug" in str(dev.get("buildConfiguration") or "").lower():
                    debug.append(os.path.basename(p))
                log, found = resolve_raw_log(p, r, self.path, self.repo.top)
                if log and not found:
                    raw_missing.append(os.path.relpath(p, self.path))
            self.check_cell_text(cell, items, task)
            self.check_cell_counts(cell, items, plat, rt, task, hist)
            if plat == "android" and sha_fix:
                late = [r for _, r in items if (parse_time(r.get("timestamp")) or sha_fix) >= sha_fix
                        and (r.get("provenance") or {}).get("modelShaSource") != "device"]
                if late:
                    self.add("model-sha-source", f"{cell}: {len(late)} of {len(items)} records without "
                                                 f"provenance.modelShaSource device (the bytes on the "
                                                 f"phone were not hashed)")
        if debug:
            self.add("debug-build", f"{len(debug)} records from a Debug build (first: {debug[0]})")
        if raw_missing:
            self.add("raw-log-missing", f"{len(raw_missing)} records name a rawLog that is not on disk "
                                        f"(first: {raw_missing[0]})")
        for (plat, rt), c in sorted(stamps.items()):
            pin, src = registry_pin(plat, rt, pins, lock, day)
            have = ", ".join(f"{v} x{n}" for v, n in c.most_common())
            if len(c) > 1:
                self.add("engine-stamp", f"{plat} {rt}: one session, {len(c)} engine stamps ({have})")
            elif pin is None:
                self.note(f"engine {plat} {rt}: {have}; registry: {src}")
            elif not all(stamp_matches(v, pin) for v in c):
                self.add("engine-stamp", f"{plat} {rt}: stamps {have}; registry {pin} ({src} at {where})")
        self.note_caps(recs)
        if self.kind == JOB_DDP:
            self.note("cpu-cap: a lab unit holds its CPU clock ceilings below the line from the start "
                      "(android/ddp/devices.json): its CPU runs pool into no number, its GPU runs count "
                      "marked; the renderer's cpu-cap-rule decides, never a verdict here")

    def check_cell_text(self, cell, items, task):
        """text-fail, the reply proxies, gen-budget, invalid-decode: one finding per cell."""
        checked = [r for _, r in items if isinstance((r.get("conditions") or {}).get("textCheck"), dict)]
        fails = [r for r in checked if r["conditions"]["textCheck"].get("status") == "FAIL"]
        if fails:
            flags = sorted({f for r in fails for f in (r["conditions"]["textCheck"].get("flags") or [])})
            self.add("text-fail", f"{cell}: {len(fails)} of {len(checked)} runs FAIL ({', '.join(flags)})")
        over = []
        invalid = 0
        logs_read = set()      # a two-iteration launch writes two records over one log
        replies = []
        for p, r in items:
            m, c = r.get("metrics") or {}, r.get("conditions") or {}
            budget = (r.get("parameters") or {}).get("maxTokens") or c.get("outputTokenBudget")
            gen = m.get("generatedTokenCount")
            if isinstance(gen, (int, float)) and isinstance(budget, (int, float)) and budget and gen > budget:
                over.append(f"{gen}>{budget}")
            invalid += int(c.get("invalidDecodeCount") or 0) + int(m.get("vlInvalidDecodeLines") or 0)
            log, found = resolve_raw_log(p, r, self.path, self.repo.top)
            if found and "invalidDecodeCount" not in c and found not in logs_read:
                logs_read.add(found)
                invalid += len(re.findall(r"Invalid decode", cache_text(found, self.texts) or "", re.I))
            if task.startswith(PROTOCOL_TASK_PREFIX) or not task.startswith(TEXT_TASKS):
                continue
            src, text = reply_text(p, r, self.texts)
            if src is not None:
                replies.append((src, text, r))
        if over:
            self.add("gen-budget", f"{cell}: {len(over)} of {len(items)} runs generated past the budget "
                                   f"({', '.join(sorted(set(over)))})")
        if invalid:
            self.add("invalid-decode", f"{cell}: {invalid} 'Invalid decode' lines")
        if not replies:
            if not task.startswith(PROTOCOL_TASK_PREFIX):
                self.samples.append({"cell": cell, "source": "-", "text": "(no reply text stored)"})
            return
        src, text, _ = next(((s, t, r) for s, t, r in replies if t and t.strip()), replies[0])
        self.samples.append({"cell": cell, "source": src, "text": short(text, 160)})
        if checked:
            return      # the runner's own text check judged these runs (text-fail above)
        screens = [(t or "", text_integrity(t or "")["flags"]) for _, t, _ in replies]
        empty = sum(1 for _, fl in screens if "text-empty-or-degenerate" in fl)
        loop = sum(1 for t, fl in screens if degenerate(t, 0.5) or "text-repetition-loop" in fl)
        off = sum(1 for t, fl in screens if t.strip() and "text-off-task-screen" in fl)
        n = len(replies)
        if empty:
            self.add("reply-empty", f"{cell}: {empty} of {n} replies empty or near-empty")
        if loop:
            self.add("reply-loop", f"{cell}: {loop} of {n} replies a repetition loop")
        if off:
            self.add("reply-off-task", f"{cell}: {off} of {n} replies name none of the prompt's subject "
                                       f"terms (sample: {short(text, 60)!r})")

    def check_cell_counts(self, cell, items, plat, rt, task, hist):
        """The prompt reached the engine whole: its token count is the committed history's for the
        same platform, build, arm, model and task (the mode of the admitted sessions' rows, this
        sitting left out); with no history on this build, it is within 10 % of every other build's."""
        counts = collections.Counter(int((r.get("metrics") or {}).get("promptTokenCount"))
                                     for _, r in items
                                     if isinstance((r.get("metrics") or {}).get("promptTokenCount"), (int, float)))
        if not counts:
            return
        engine = items[0][1].get("engineVersion") or ""
        model = (items[0][1].get("model") or {}).get("id")
        sitting = self.ctx["sitting_of"](self.raw, self.name)
        same = collections.Counter()
        other = collections.defaultdict(collections.Counter)
        for (hplat, heng, hrt, hmodel, htask), rows in hist.items():
            if (hplat, hrt, hmodel, htask) != (plat, rt, model, task):
                continue
            for pt, camp in rows:
                if self.ctx["sitting_of"](self.raw, camp) == sitting:
                    continue
                (same if heng == engine else other[heng])[pt] += 1
        mine = ", ".join(f"{v} x{n}" if n > 1 else str(v) for v, n in sorted(counts.items()))
        if same:
            mode, n = same.most_common(1)[0]
            off = sorted(v for v in counts if v != mode)
            if off:
                self.add("prompt-tokens", f"{cell}: prompt {mine} tokens; committed history on this "
                                          f"build reads {mode} ({n} rows)")
            return
        if not other:
            self.note(f"prompt history: none for {cell}; prompt {mine} tokens")
            return
        modes = {eng: c.most_common(1)[0][0] for eng, c in other.items()}
        far = [v for v in counts if all(abs(v - m) > 0.10 * m for m in modes.values())]
        if far:
            self.add("prompt-newtag", f"{cell}: prompt {mine} tokens, no history on this build; "
                                      f"other builds read "
                                      + ", ".join(f"{e} {m}" for e, m in sorted(modes.items())))
        else:
            self.note(f"prompt history: none on this build for {cell}; prompt {mine} tokens matches "
                      + ", ".join(f"{e} {m}" for e, m in sorted(modes.items())))

    def history_index(self):
        """(platform, engine, runtime, model, task) -> [(prompt tokens, campaign dir name)] over the
        committed summary's admitted rows whose text check did not fail."""
        key = id(self.repo)
        if key not in self.ctx["hist_cache"]:
            admitted = self.ctx["admission"](self.raw)
            idx = collections.defaultdict(list)
            for r in self.repo.history(self.ctx["history"]):
                camp = os.path.basename(r.get("campaign") or "")
                if not r.get("prompt_tokens") or not admitted.get(camp, True):
                    continue
                if (r.get("text_check") or "").startswith("FAIL"):
                    continue
                try:
                    pt = int(float(r["prompt_tokens"]))
                except ValueError:
                    continue
                idx[(r.get("platform"), r.get("engine_version") or "", r.get("runtime"),
                     r.get("model_id"), r.get("task"))].append((pt, camp))
            self.ctx["hist_cache"][key] = idx
        return self.ctx["hist_cache"][key]

    def note_caps(self, recs):
        """cpu-cap-rule is the renderer's (arm_row pools or drops each run); listed, never a verdict."""
        past, within = 0, 0
        for _, r in recs:
            flags = (r.get("conditions") or {}).get("protocolFlags") or []
            if "cpu-capped" not in flags:
                continue
            drop = cpu_cap_drop_of(r)
            if r.get("runtime") in CPU_CAP_EXEMPT_ARMS or (drop and float(drop) <= CPU_CAP_MAX_DROP_PCT):
                within += 1
            else:
                past += 1
        if past or within:
            self.note(f"cpu-capped runs: {past} past the {CPU_CAP_MAX_DROP_PCT} % line (pool into no "
                      f"number), {within} counted (◇)")
        first = sum(1 for _, r in recs if (r.get("metrics") or {}).get("firstEver"))
        if first:
            self.note(f"firstEver (cache-build) runs: {first}, kept out of every number by arm_row")

    # ------------------------------------------------------------ ledger, allow-list, verdict
    def find_ledger(self):
        rows = self.repo.ledger(self.ctx["ledger"])
        camp = f"results/raw/{self.name}"
        for r in rows:
            if r.get("campaign") == camp:
                return r
        s = self.session or {}
        start = parse_time(s.get("started"))
        for r in rows:
            a, b = parse_time(r.get("started")), parse_time(r.get("ended"))
            if start and a and b and r.get("device") == s.get("device_key") \
                    and a - datetime.timedelta(minutes=1) <= start <= b:
                return r
        return None

    def apply_allow_list(self):
        for f in self.findings:
            e = allowed(f, self.name, self.ctx["allow"])
            f["allowed_by"] = {"commit": e["commit"], "reason": e["reason"], "line": e["line"]} if e else None

    def verdict(self):
        live = [f for f in self.findings if not f["allowed_by"]]
        if any(f["severity"] == "FAIL" for f in live):
            return "FAIL"
        return "HOLD" if live else "PASS"

    def result(self):
        led = self.ledger_row
        return {
            "dir": self.path, "name": self.name, "kind": self.kind, "verdict": self.verdict(),
            "findings": self.findings, "notes": self.notes, "samples": self.samples,
            "files": {"tracked": self.counts.get("tracked", 0), "untracked": self.counts.get("untracked", 0),
                      "ignored": self.counts.get("ignored", 0)},
            "records": len([1 for _, r in self.records if r is not None]),
            "ledger": ({k: led.get(k) for k in ("started", "device", "campaign", "verdict", "reason",
                                                 "exit", "minutes", "attempt")} if led else None),
        }


# ---------------------------------------------------------------- context shared by the dirs

def make_context(args, names):
    sessions_cache, admission_cache, sitting_cache = {}, {}, {}

    def sessions(raw):
        """name -> SESSION.json (dashboard-job-session.v1) of every campaign dir beside these."""
        if raw not in sessions_cache:
            out = {}
            for f in glob.glob(os.path.join(raw, "*", "SESSION.json")):
                s = read_session(os.path.dirname(f))
                if s is not None:
                    out[os.path.basename(os.path.dirname(f))] = s
            sessions_cache[raw] = out
        return sessions_cache[raw]

    def admission(raw):
        if raw not in admission_cache:
            admission_cache[raw] = {n: bool(s.get("admitted", True)) for n, s in sessions(raw).items()}
        return admission_cache[raw]

    def sitting_of(raw, name):
        """A sitting = an anchor phase and the payloads that name it (one id for both)."""
        if raw not in sitting_cache:
            m = {}
            for n, s in sessions(raw).items():
                a = os.path.basename(s.get("anchor_phase") or "")
                if a:
                    m[n] = a
            sitting_cache[raw] = m
        return sitting_cache[raw].get(name, name)

    # the commit that made run_cell.py hash the phone's copy (f41b3661, 2026-10-15 03:08 JST); a
    # shallow clone without it skips the model-sha-source rule
    rc, out = run(["git", "-C", ROOT, "log", "--format=%cI", "-S", "modelShaSource", "--",
                   "android/bench/run_cell.py"])
    sha_fix = parse_time(out.split()[-1]) if out.split() else None
    user = args.user if args.user is not None else getpass.getuser()
    return {"repos": {}, "allow": load_allow_list(args.allow_list), "history": args.history,
            "ledger": args.ledger, "job_logs": args.job_logs, "names": names,
            "sessions": sessions, "admission": admission, "sitting_of": sitting_of,
            "hist_cache": {}, "sha_fix": sha_fix, "user": user if user not in ("", "USER") else None}


# ---------------------------------------------------------------- output

def ledger_text(led):
    if not led:
        return "—"
    return f"{led['started']} {led['device']} {led['verdict']} ({short(led['reason'], 40)}) exit {led['exit']}"


def render_markdown(results):
    L = ["| dir | kind | verdict | reasons (rule ids) | tracked / untracked | ledger | to read |",
         "|---|---|---|---|---|---|---|"]
    for r in results:
        live = sorted({f["rule"] for f in r["findings"] if not f["allowed_by"]})
        allowed_rules = sorted({f["rule"] for f in r["findings"] if f["allowed_by"]})
        reasons = ", ".join(live) or "—"
        if allowed_rules:
            reasons += f" (allowed: {', '.join(allowed_rules)})"
        n_read = sum(1 for s in r["samples"] if s["source"] != "-")
        L.append(f"| `{r['name']}` | {r['kind']} | **{r['verdict']}** | {reasons} | "
                 f"{r['files']['tracked']} / {r['files']['untracked']} | {ledger_text(r['ledger'])} | "
                 f"{n_read} |")
    total = collections.Counter(r["verdict"] for r in results)
    L += ["", f"PASS {total['PASS']}, HOLD {total['HOLD']}, FAIL {total['FAIL']} of {len(results)} dirs.", ""]
    L += ["## Findings", ""]
    for r in results:
        if not r["findings"]:
            continue
        L.append(f"- `{r['name']}` — {r['verdict']}")
        for f in r["findings"]:
            tail = f" — allowed by {f['allowed_by']['commit']} ({f['allowed_by']['reason']})" if f["allowed_by"] else ""
            L.append(f"  - {f['severity']} `{f['rule']}`: {f['detail']}{tail}")
    L += ["", "## A person reads one reply per cell", "",
          "No verdict reads these: the proxies above screen them, a person reads them.", ""]
    for r in results:
        rows = [s for s in r["samples"] if s["source"] != "-"]
        if not rows:
            continue
        L.append(f"- `{r['name']}`")
        for s in rows:
            L.append(f"  - {s['cell']} ({s['source']}): {s['text']}")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dirs", nargs="+", help="campaign dirs (results/raw/<campaign>)")
    ap.add_argument("--json", help="write every finding, note and sample here")
    ap.add_argument("--markdown", help="write the table, the findings and the samples here")
    ap.add_argument("--allow-list", default=ALLOW_LIST)
    ap.add_argument("--history", help="a device-runs.csv to read prompt-token history from "
                                      "(default: the committed results/summary of the dirs' repo)")
    ap.add_argument("--ledger", help="the job ledger (default: <repo>/logs/dashboard-job/ledger.tsv)")
    ap.add_argument("--job-logs", help="the job's log dir (default: <repo>/logs/dashboard-job)")
    ap.add_argument("--user", help="the account name to look for in paths (default: this account)")
    ap.add_argument("-q", "--quiet", action="store_true", help="one line per dir, no findings")
    args = ap.parse_args(argv)
    missing = [d for d in args.dirs if not os.path.isdir(d)]
    if missing:
        ap.error("not a directory: " + ", ".join(missing))
    try:
        ctx = make_context(args, {os.path.basename(os.path.abspath(d.rstrip("/"))) for d in args.dirs})
    except ValueError as e:
        ap.error(str(e))
    results = [Check(d, ctx).run().result() for d in args.dirs]
    for r in results:
        live = [f for f in r["findings"] if not f["allowed_by"]]
        print(f"{r['verdict']:4}  {r['name']}  ({r['kind']})"
              + (f"  {', '.join(sorted({f['rule'] for f in live}))}" if live else ""))
        if not args.quiet:
            for f in r["findings"]:
                tail = f"  [allowed: {f['allowed_by']['commit']}]" if f["allowed_by"] else ""
                print(f"        {f['severity']} {f['rule']}: {f['detail']}{tail}")
    total = collections.Counter(r["verdict"] for r in results)
    print(f"PASS {total['PASS']}  HOLD {total['HOLD']}  FAIL {total['FAIL']}  of {len(results)}")
    if args.json:
        with open(args.json, "w") as fh:
            json.dump({"checked_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
                       "allow_list": args.allow_list, "dirs": results,
                       "summary": dict(total)}, fh, indent=1, default=str)
    if args.markdown:
        with open(args.markdown, "w") as fh:
            fh.write(render_markdown(results))
    return 0 if total["PASS"] == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
