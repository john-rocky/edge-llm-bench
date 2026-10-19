#!/usr/bin/env python3
"""Device- and network-free selftest of scripts/dashboard_post.py (CI).

Builds a temp bench checkout (git; its own stub scripts/build_summary.py, one summary row per
record file; a local bare remote) holding synthetic dashboard-job sittings that
scripts/session_check.py passes, beside another lane's staged record, an untracked campaign dir,
an untracked file and an unstaged edit; and a stub page repo (build.py writing the bench summary
into every page file, the four checks as stubs that PASS unless FAKE_PAGE_FAIL names them,
tools/publish_gcs.sh writing a marker; a local bare remote). Pins:

  (i)    the commit carries the sitting's dirs and results/summary only: the other lane's staged
         file stays staged, the untracked ones untracked, the unstaged edit unstaged
  (ii)   the message is the results commits' one line, with no word the commit-msg hook refuses
         and no percentage or standing word; a sitting whose message would carry one (an anchor
         reason with '%', 'faster', 'than') is not committed: a ledger line, exit 1, no REVIEW.md;
         the checker's text_screen.json goes into the commit and the message names its text-fail
         cells (none: 'text screen: none'); --dry-run writes no text_screen.json
  (iii)  the committed summary is the tree's own (HEAD + the dirs), and the page was built from it
  (iv)   switch off: nothing pushed, nothing published, the ledger says what would have been
  (v)    one switch on: only that push reaches its remote; a push that would carry a commit this
         step did not make is refused; publish runs on its own switch only
  (vi)   a HOLD sitting: no commit, REVIEW.md in each dir, a ledger line, exit 1
  (vii)  a merge in progress: no commit; posted again once it is gone
  (viii) the name scrub rewrites text files only; a JSON record keeps every number
  and: a page check FAIL (the bench commit stands, the page repo untouched), --allow-subset,
  --dry-run (nothing written), the lock, a post over dirs already committed; the red segment (a
  stub scripts/regression_watch.py in the commit's tree: run over the sitting's dirs and the page
  build's regression.json, its mismatch and notes in the ledger note, the exit code unchanged,
  --dry-run passed on) and the page's number changes (cells.csv statuses before and after).

  python3 scripts/dashboard_post_selftest.py     # exit 0 = pass
"""
import fcntl
import getpass
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
POST = os.path.join(ROOT, "scripts", "dashboard_post.py")
USER = getpass.getuser()
ON_TASK = ("On-device AI means the model runs on your phone itself instead of a cloud server, so it "
           "works offline, answers quickly and keeps your private data local on the device.")
OFF_TASK = ("Sure! Here is a short story about a dragon who learns to bake bread in a small village "
            "near the mountains, and the baker who teaches him patience and kindness every morning.")
# the one-line results message (dashboard_post.commit_message)
MSG_RE = re.compile(r"^results \d{4}-\d\d-\d\d .+ \(.+\), .+: \d+/\d+ cells of \S+ in one dashboard-job sitting "
                    r"\d\d:\d\d–\d\d:\d\d \S+ \(anchor admitted.+\); text check .+; cpu-capped counted "
                    r"\d+/\d+, past the line \d+; FAILURES: .+; results/summary rebuilt from the git index "
                    r"\(\d+ -> \d+ lines\)$")

STUB_BUILD_SUMMARY = '''#!/usr/bin/env python3
"""Stub summary builder: one row per record file under results/raw of this tree."""
import glob, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rows = sorted(os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, "results", "raw", "*", "*.jsonl")))
os.makedirs(os.path.join(ROOT, "results", "summary"), exist_ok=True)
with open(os.path.join(ROOT, "results", "summary", "device-runs.csv"), "w") as fh:
    fh.write("campaign,file\\n" + "".join(f"{os.path.dirname(p)},{os.path.basename(p)}\\n" for p in rows))
'''
STUB_PAGE_BUILD = '''#!/usr/bin/env python3
"""Stub page build: every page file carries the bench summary it was built from."""
import argparse, os
ap = argparse.ArgumentParser()
ap.add_argument("--out-dir", required=True)
a = ap.parse_args()
summary = open(os.path.join(os.environ["EDGE_LLM_BENCH"], "results", "summary", "device-runs.csv")).read()
os.makedirs(a.out_dir, exist_ok=True)
for n in ("index.html", "cells.json", "regression.json", "regression.csv", "aa.json", "aa.csv"):
    open(os.path.join(a.out_dir, n), "w").write(n + "\\n" + summary)
open(os.path.join(a.out_dir, "cells.csv"), "w").write(summary)
print("wrote", a.out_dir)
'''
STUB_CHECK = '''#!/usr/bin/env python3
import os, sys
name = os.path.splitext(os.path.basename(__file__))[0]
dist = sys.argv[sys.argv.index("--dist") + 1]
if os.environ.get("FAKE_PAGE_FAIL") == name or not os.path.exists(os.path.join(dist, "index.html")):
    print("  FAIL stub"); print("FAIL (1)"); sys.exit(1)
if name == "render_check":
    open(os.path.join(dist, "screenshot-overview.png"), "wb").write(b"png " + open(os.path.join(dist, "index.html"), "rb").read())
print("PASS")
'''
# the red segment's script as the commit's tree carries it: the JSON a real one writes (FAKE_RED=mismatch:
# the page's red set differs), and the arguments it was given
STUB_RED = '''#!/usr/bin/env python3
import json, os, sys
a = sys.argv[1:]
names = a[a.index("--respond") + 1:a.index("--state-dir")]
cmp = None
if "--compare" in a:
    same = os.environ.get("FAKE_RED") != "mismatch"
    cmp = {"equal": same, "red": {"bench": 1, "page": 1 if same else 0}, "counts": {"series": {"bench": 1, "page": 1}}}
note = "stub red over " + " ".join(names) + (" with --dry-run" if "--dry-run" in a else "") + (
    " and --compare" if cmp else "") + " into " + os.path.basename(os.path.dirname(a[a.index("--state-dir") + 1]))
json.dump({"compare": cmp, "respond": {"notes": [note]}}, open(a[a.index("--json") + 1], "w"))
print("stub red segment")
'''
STUB_PUBLISH = '''#!/usr/bin/env bash
here="$(cd "$(dirname "$0")/.." && pwd)"
python3 -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$here/dist/index.html" >> "$here/../published.txt"
'''

_fails = []


def ok(cond, msg):
    print(("  ok  " if cond else "  FAIL ") + msg)
    if not cond:
        _fails.append(msg)


def sh(cwd, *cmd, check=True):
    p = subprocess.run(list(cmd), cwd=cwd, capture_output=True, text=True,
                       env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")})
    if check and p.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} in {cwd}: {p.stdout}{p.stderr}")
    return p.stdout.strip()


def write(path, text, mode="w"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode) as fh:
        fh.write(text)


def new_repo(path, remote):
    os.makedirs(path)
    sh(path, "git", "init", "-q", "-b", "main")
    for k, v in (("user.email", "selftest@example.com"), ("user.name", "selftest"), ("commit.gpgsign", "false")):
        sh(path, "git", "config", k, v)
    sh(os.path.dirname(remote), "git", "init", "-q", "--bare", remote)
    sh(path, "git", "remote", "add", "origin", remote)


def commit_paths(path, msg, *paths):
    sh(path, "git", "add", "--", *paths)
    sh(path, "git", "commit", "-q", "-m", msg)
    sh(path, "git", "push", "-q", "origin", "main")


def remote_main(remote):
    return sh(os.path.dirname(remote), "git", "--git-dir", remote, "rev-parse", "refs/heads/main")


# ---------------------------------------------------------------- synthetic sittings

def mac_record(runtime, model, engine, i, **extra):
    rec = {"schemaVersion": 1, "id": str(uuid.uuid4()), "runtime": runtime, "engineVersion": engine,
           "model": {"id": model, "quantization": "4bit"}, "task": "short-chat",
           "timestamp": f"2026-10-01T17:0{i}:00Z",
           "device": {"modelIdentifier": "Mac16,9", "systemName": "macOS", "buildConfiguration": "Release"},
           "parameters": {"maxTokens": 128},
           "metrics": {"decodeTokensPerSecond": 500.0 + i, "promptTokenCount": 19, "generatedTokenCount": 128,
                       "coldRun": i == 0, "initialThermalState": "nominal"},
           "outputSample": ON_TASK}
    rec.update(extra)
    return rec


def cell_file(d, runtime, model, engine, n=4, **extra):
    write(os.path.join(d, f"{runtime}_{model.replace('/', '_')}_short-chat.jsonl"),
          "".join(json.dumps(mac_record(runtime, model, engine, i, **extra)) + "\n" for i in range(n)))


def session(d, phase, date, anchor_phase=None, reference=None, **over):
    s = {"schema": "dashboard-job-session.v1", "job": "dashboard-v1", "phase": phase,
         "campaign": f"results/raw/{os.path.basename(d)}", "device_key": "m4max",
         "device_display": "Mac Studio (M4 Max)", "device_identifier": "Mac16,9", "platform": "mac",
         "attempt": 1, "started": f"{date} 02:00:04", "ended": f"{date} 03:1{'0' if phase == 'anchor' else '9'}:30",
         "admitted": True, "verdict": "ADMITTED" if phase == "anchor" else "COMPLETED",
         "reason": "anchor nominal, first session on this device" if not reference
         else "anchor nominal, ratio 0.980 vs reference (v0.0.1)", "runner_exit": 0,
         "anchor": {"regime": "warm", "anchors": [
             {"cell": "mlx-swift mlx-community/Qwen3-0.6B-4bit short-chat", "primary": True, "median": 500.0,
              "n": 3, "thermal": ["nominal"], "engine_version": "abc1234",
              "reference": {"campaign": f"results/raw/{reference}", "median": 510.0} if reference else None,
              "ratio": 0.98 if reference else None}]}}
    if phase == "payload":
        s.update(anchor_phase=f"results/raw/{anchor_phase}", cells="matrices/dashboard-text-v1.cells",
                 cells_expected=2, cells_with_records=2)
    s.update(over)
    write(os.path.join(d, "SESSION.json"), json.dumps(s, indent=1))


def sitting(raw, n, payloads=("",), reference=None, names=False, failures=False, off_task=False):
    """One sitting of day n: its anchor phase and payloads -> [results/raw/<name>, …] (anchor first);
    off_task: the payloads' LiteRT-LM replies answer another question (the text screen fails them)."""
    date = f"2026-10-{n:02d}"
    base = f"{date}-dashboard-v1-m4max"
    anchor = f"{base}-anchor-mac"
    d = os.path.join(raw, anchor)
    session(d, "anchor", date, reference=reference if isinstance(reference, str) else None)
    cell_file(d, "mlx-swift", "mlx-community/Qwen3-0.6B-4bit", "abc1234")
    out = [anchor]
    for tag in payloads:
        name = f"{base}{'-' + tag if tag else ''}-mac"
        d = os.path.join(raw, name)
        ref = reference
        if isinstance(reference, dict):
            ref = reference.get(tag)
        session(d, "payload", date, anchor_phase=anchor, reference=ref)
        cell_file(d, "mlx-swift", "mlx-community/Qwen3-0.6B-4bit", "abc1234")
        cell_file(d, "litert-lm", "litert-community/Qwen3-1.7B", "v0.0.1",
                  **({"outputSample": OFF_TASK} if off_task else {}))
        if names:
            rec = mac_record("litert-lm", "litert-community/Qwen3-1.7B", "v0.0.1", 9,
                             provenance={"command": f"/Users/{USER}/code/edge-llm-bench/.build/yardstick run",
                                         "trace": f"/private/var/tmp/_bazel_{USER}/x"})
            write(os.path.join(d, "app-path-mac", "litert-lm_extra_run9.json"), json.dumps(rec, indent=1))
            write(os.path.join(d, "console.txt"),
                  f"yardstick: /Users/{USER}/code/edge-llm-bench/.build/dd-mac/yardstick\n"
                  f"appended to /private/tmp/x/-Users-{USER}-code-edge-llm-bench/s.jsonl\n"
                  f"-rw-r--r--  1 {USER}  staff  4096 Oct  1 02:00 model.bin\n")
            write(os.path.join(d, "sampler.dat"), b"\x00\x01" + f"/Users/{USER}/bin".encode() + b"\x00", "wb")
        if failures:
            write(os.path.join(d, "FAILURES.txt"), "FAIL litert-lm litert-community/Qwen3-1.7B short-chat rc=1\n")
        out.append(name)
    return ["results/raw/" + x for x in out]


# ---------------------------------------------------------------- main

def main():
    tmp = tempfile.mkdtemp(prefix="dashboard-post-selftest-")
    bench, page = os.path.join(tmp, "bench"), os.path.join(tmp, "page")
    bench_remote, page_remote = os.path.join(tmp, "bench.git"), os.path.join(tmp, "page.git")
    raw = os.path.join(bench, "results", "raw")
    ledger_path = os.path.join(bench, "logs", "dashboard-job", "autopilot-ledger.tsv")
    marker = os.path.join(tmp, "published.txt")

    new_repo(bench, bench_remote)
    write(os.path.join(bench, ".gitignore"), "/logs/\n")
    write(os.path.join(bench, "README.md"), "bench\n")
    write(os.path.join(bench, "scripts", "build_summary.py"), STUB_BUILD_SUMMARY)
    sh(bench, sys.executable, "scripts/build_summary.py")
    commit_paths(bench, "initial", ".gitignore", "README.md", "scripts", "results/summary")
    new_repo(page, page_remote)
    write(os.path.join(page, "build.py"), STUB_PAGE_BUILD)
    for c in ("check_against_bench_dashboard", "check_regression", "check_aa", "render_check"):
        write(os.path.join(page, "tools", c + ".py"), STUB_CHECK)
    write(os.path.join(page, "tools", "publish_gcs.sh"), STUB_PUBLISH)
    for n in ("index.html", "cells.csv", "cells.json", "regression.json", "regression.csv", "aa.json", "aa.csv",
              "screenshot-overview.png"):
        write(os.path.join(page, "dist", n), "old\n")
    commit_paths(page, "dist: the first page", "build.py", "tools", "dist")
    bench0, page0 = remote_main(bench_remote), remote_main(page_remote)

    switches = {}
    for name, on in (("off", ()), ("bench", ("push_bench",)), ("page", ("push_page",)),
                     ("publish", ("publish",))):
        sw = {k: k in on for k in ("push_bench", "push_page", "publish")}
        sw["page_repo"] = page
        switches[name] = os.path.join(tmp, f"switch-{name}.json")
        write(switches[name], json.dumps(sw))

    # another lane's work in the same checkout: a staged record, an untracked campaign dir, an
    # untracked file, an unstaged edit — none of it belongs in the post's commit or summary
    write(os.path.join(raw, "2026-09-30-other-lane-staged-mac", "rec.jsonl"), "{}\n")
    sh(bench, "git", "add", "--", "results/raw/2026-09-30-other-lane-staged-mac")
    write(os.path.join(raw, "2026-09-30-other-lane-untracked-mac", "rec.jsonl"), "{}\n")
    write(os.path.join(bench, "notes-other-lane.txt"), "mine\n")
    write(os.path.join(bench, "README.md"), "bench, edited by another lane\n")

    def post(dirs, switch="off", *extra, env=None):
        cmd = [sys.executable, POST] + [os.path.join(bench, d) for d in dirs] + ["--switch", switches[switch]] + list(extra)
        p = subprocess.run(cmd, cwd=bench, capture_output=True, text=True,
                           env=dict({k: v for k, v in os.environ.items() if not k.startswith("GIT_")}, **(env or {})))
        return p.returncode, p.stdout + p.stderr

    def head():
        return sh(bench, "git", "rev-parse", "HEAD")

    def ledger():
        if not os.path.exists(ledger_path):
            return []
        with open(ledger_path) as fh:
            lines = fh.read().splitlines()
        cols = lines[0].split("\t")
        return [dict(zip(cols, ln.split("\t"))) for ln in lines[1:]]

    def committed_files(rev="HEAD"):
        return set(sh(bench, "git", "show", "--name-only", "--format=", rev).splitlines())

    def staged():
        return set(sh(bench, "git", "diff", "--cached", "--name-only").splitlines())

    def status():
        p = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=bench,
                           capture_output=True, text=True)
        return p.stdout.splitlines()     # not stripped: " M" keeps its leading space

    other_state = {"?? notes-other-lane.txt", "?? results/raw/2026-09-30-other-lane-untracked-mac/rec.jsonl",
                   " M README.md", "A  results/raw/2026-09-30-other-lane-staged-mac/rec.jsonl"}

    def others_intact(when):
        st = set(status())
        ok(other_state <= st, f"{when}: the other lane's staged record still staged, its untracked files "
                              f"untracked, its edit unstaged ({sorted(other_state - st) or 'all there'})")

    print("--- --dry-run: the plan and the message, nothing written")
    s1 = sitting(raw, 1, names=True)
    console = os.path.join(bench, s1[1], "console.txt")
    before_console = open(console).read()
    h0 = head()
    rc, out = post(s1, "off", "--dry-run")
    ok(rc == 0 and "message: results 2026-10-01 Mac Studio (M4 Max) (Mac16,9)" in out,
       f"dry run exit {rc}, the message printed")
    ok(head() == h0 and not os.path.exists(ledger_path) and open(console).read() == before_console
       and not any(os.path.exists(os.path.join(bench, d, n)) for d in s1 for n in ("REVIEW.md", "text_screen.json"))
       and "would write text_screen.json" in out,
       "dry run: HEAD, the files (no scrub), the ledger, REVIEW.md and text_screen.json untouched (the checker's "
       "--no-text-screen: 'would write')")

    print("--- (i)-(iv), (viii): a PASS sitting with the switch off")
    rec_path = os.path.join(bench, s1[1], "app-path-mac", "litert-lm_extra_run9.json")
    rec_before = json.load(open(rec_path))
    dat_path = os.path.join(bench, s1[1], "sampler.dat")
    dat_before = open(dat_path, "rb").read()
    rc, out = post(s1, "off")
    ok(rc == 0, f"exit {rc}")
    ok(sh(bench, "git", "rev-parse", "HEAD~1") == h0, "one commit on top of the HEAD it started from")
    files = committed_files()
    want = {p for d in s1 for p in sh(bench, "git", "ls-files", "--", d).splitlines()} | {"results/summary/device-runs.csv"}
    ok(files == want and all(f.startswith(tuple(s1)) or f == "results/summary/device-runs.csv" for f in files)
       and {f"{d}/text_screen.json" for d in s1} <= files,
       f"(i) the commit carries the sitting's {len(want) - 1} files (each dir's text_screen.json among them) and "
       f"the summary, nothing else")
    others_intact("(i)")
    msg = sh(bench, "git", "log", "-1", "--format=%B").strip()
    ok("\n" not in msg and MSG_RE.match(msg) is not None, f"(ii) one line in the results commits' form: {msg[:150]}…")
    ok(not re.search(r"claude|anthropic|co-authored-by", msg, re.I), "(ii) no word the commit-msg hook refuses")
    ok("Mac Studio (M4 Max) (Mac16,9), litert-lm: v0.0.1, mlx-swift: abc1234: 2/2 cells of "
       "matrices/dashboard-text-v1.cells in one dashboard-job sitting 02:00–03:19" in msg
       and "(anchor admitted: anchor nominal, first session on this device; thermal nominal)" in msg
       and "text check 0/0 (no run carries one); text screen: none; cpu-capped counted 0/13, past the line 0; "
           "FAILURES: none" in msg
       and msg.endswith("results/summary rebuilt from the git index (1 -> 4 lines)"),
       "(ii) device, arms and stamps, cells, times, admission, text check, caps, failures, summary lines")
    summary = sh(bench, "git", "show", "HEAD:results/summary/device-runs.csv")
    ok(all(d in summary for d in s1) and "other-lane" not in summary,
       "(iii) the committed summary holds the sitting's records and none of the other lane's (staged or untracked)")
    ok(open(os.path.join(bench, "results/summary/device-runs.csv")).read().strip() == summary,
       "(iii) the checkout's results/summary is the committed one")
    page_head = sh(page, "git", "log", "-1", "--format=%s")
    page_cells = sh(page, "git", "show", "HEAD:dist/cells.csv")
    ok(page_head.startswith(f"dist: the page from the bench at {head()[:8]} — the 2026-10-01 Mac Studio (M4 Max)")
       and page_head.endswith("checks: check_against_bench_dashboard, check_regression, check_aa, render_check PASS"),
       f"(iii) the page repo's commit names the bench commit: {page_head[:110]}…")
    ok(page_cells.strip() == summary and sh(page, "git", "status", "--porcelain") == "",
       "(iii) the page was built from the commit's tree (its cells = that summary); the page repo is clean")
    ok(remote_main(bench_remote) == bench0 and remote_main(page_remote) == page0 and not os.path.exists(marker),
       "(iv) switch off: neither remote moved, nothing published")
    row = ledger()[-1]
    idx = hashlib.sha256(open(os.path.join(page, "dist", "index.html"), "rb").read()).hexdigest()
    ok(row["push_bench"].startswith(f"would push bench {bench0[:8]}..{head()[:8]} (1 commit)")
       and row["push_page"].startswith("would push page ") and row["publish"] == f"would publish dist/index.html sha256 {idx}",
       f"(iv) the ledger says what would have been pushed and published: {row['push_bench']} | {row['push_page']} | {row['publish'][:40]}…")
    ok(row["bench_commit"] == head() and row["summary_lines"] == "1 -> 4" and row["page_commit"] == sh(page, "git", "rev-parse", "HEAD")
       and "=PASS" in row["check"] and all(row[k] for k in ("started", "ended", "dirs", "page")),
       "the ledger line: dirs, verdicts, bench commit, summary lines, page build + checks, page commit")
    rec_after = json.load(open(rec_path))
    ok(rec_after["metrics"] == rec_before["metrics"] and rec_after["id"] == rec_before["id"]
       and rec_after["provenance"]["command"] == "/Users/USER/code/edge-llm-bench/.build/yardstick run"
       and rec_after["provenance"]["trace"] == "/private/var/tmp/_bazel_USER/x",
       "(viii) the JSON record: every number as it was, the paths read USER")
    text = open(console).read()
    ok(all(form in text for form in ("/Users/USER/code", "-Users-USER-code", "USER  staff"))
       and f"/Users/{USER}/" not in text and f"-Users-{USER}-" not in text
       and not re.search(r"(?<![A-Za-z0-9])" + re.escape(USER) + r"\s+staff", text),
       "(viii) the text file: the path, the scratchpad form and the ls owner column read USER")
    ok(open(dat_path, "rb").read() == dat_before, "(viii) the binary file left byte for byte")

    print("--- (v) one switch on: only that push or publish")
    s2 = sitting(raw, 2, reference=os.path.basename(s1[0]))
    rc, out = post(s2, "bench")
    ok(rc == 0 and remote_main(bench_remote) == head() and remote_main(page_remote) == page0 and not os.path.exists(marker),
       f"push_bench on: the bench remote is at HEAD (both post commits), the page remote and publish untouched (exit {rc})")
    msg = sh(bench, "git", "log", "-1", "--format=%B").strip()
    ok(f"anchor admitted at ratio 0.980 to reference {os.path.basename(s1[0])}, thermal nominal; the payload's own anchor rows at 0.980" in msg,
       "the admission ratio and its reference campaign in the message")
    import dashboard_post as dp
    ok(not dp.STANDING_WORDS.search(msg) and re.search(r"message guard: no '%' and no standing word .*: OK", out),

       "no percentage and no standing word in the message, and the guard's OK line in the output")
    ok(not dp.STANDING_WORDS.search("anchor admitted at ratio 0.813 to reference 2026-09-14-catalog-int4-vs-int8-pixel8a-dtypeonly-norope-android")
       and dp.STANDING_WORDS.search("LiteRT-LM vs llama.cpp") and dp.STANDING_WORDS.search("12 % faster"),
       "the standings guard ignores a word inside a hyphenated name (a campaign name with -vs-) and refuses it as prose")
    write(os.path.join(bench, "other-lane-commit.txt"), "x\n")
    sh(bench, "git", "add", "--", "other-lane-commit.txt")
    sh(bench, "git", "commit", "-q", "-m", "another lane's local commit", "--", "other-lane-commit.txt")
    s3 = sitting(raw, 3)
    pushed = remote_main(bench_remote)
    rc, out = post(s3, "bench")
    row = ledger()[-1]
    ok(rc == 1 and remote_main(bench_remote) == pushed and row["push_bench"].startswith("push refused")
       and "not made by this step" in row["push_bench"],
       f"push_bench on with another lane's local commit in between: refused, the remote unchanged ({row['push_bench'][:90]})")
    s4 = sitting(raw, 4)
    rc, out = post(s4, "page")
    ok(rc == 0 and remote_main(page_remote) == sh(page, "git", "rev-parse", "HEAD") and remote_main(bench_remote) == pushed
       and not os.path.exists(marker), f"push_page on: the page remote is at the page HEAD, the bench remote unchanged (exit {rc})")
    s5 = sitting(raw, 5)
    page_remote_now = remote_main(page_remote)
    rc, out = post(s5, "publish")
    idx = hashlib.sha256(open(os.path.join(page, "dist", "index.html"), "rb").read()).hexdigest()
    ok(rc == 0 and os.path.exists(marker) and open(marker).read().split() == [idx]
       and remote_main(page_remote) == page_remote_now and remote_main(bench_remote) == pushed,
       f"publish on: the publish script ran once on the committed dist/index.html, no push (exit {rc})")

    print("--- (vi) a HOLD sitting: nothing committed")
    h = head()
    h1 = sitting(raw, 6, failures=True)
    rc, out = post(h1, "off")
    row = ledger()[-1]
    reviews = [os.path.join(bench, d, "REVIEW.md") for d in h1]
    ok(rc == 1 and head() == h and not row["bench_commit"] and "=HOLD" in row["check"] and row["note"].startswith("held:"),
       f"exit {rc}, HEAD unchanged, the ledger line says held ({row['check']})")
    ok(all(os.path.exists(p) for p in reviews) and "`failures`" in open(reviews[1]).read()
       and "read FAILURES.txt" in open(reviews[1]).read() and "HOLD" in open(reviews[0]).read(),
       "REVIEW.md in each dir: the rule id, its detail, what a person does")
    others_intact("(vi)")

    print("--- (vii) a merge in progress: nothing committed, then posted once it is gone")
    m1 = sitting(raw, 7)
    merge_head = sh(bench, "git", "rev-parse", "--git-path", "MERGE_HEAD")
    merge_head = merge_head if os.path.isabs(merge_head) else os.path.join(bench, merge_head)
    write(merge_head, head() + "\n")
    rc, out = post(m1, "off")
    row = ledger()[-1]
    ok(rc == 1 and head() == h and "MERGE_HEAD" in row["note"] and os.path.exists(os.path.join(bench, m1[0], "REVIEW.md")),
       f"MERGE_HEAD present: exit {rc}, no commit, the ledger names it, REVIEW.md written")
    os.remove(merge_head)
    rc, out = post(m1, "off")
    ok(rc == 0 and sh(bench, "git", "rev-parse", "HEAD~1") == h
       and not any(os.path.exists(os.path.join(bench, d, "REVIEW.md")) for d in m1)
       and not any(f.endswith("REVIEW.md") for f in committed_files()),
       "posted again without it: committed, the REVIEW.md it had written gone and not in the commit")

    print("--- the message guard: a percentage or a standing word in the generated message is never committed")
    g1 = sitting(raw, 13)
    anchor_session = os.path.join(bench, g1[0], "SESSION.json")
    s = json.load(open(anchor_session))
    s["reason"] = "anchor nominal, 3% faster than the newest session"
    write(anchor_session, json.dumps(s, indent=1))
    h = head()
    rc, out = post(g1, "off")
    row = ledger()[-1]
    ok(rc == 1 and head() == h and not row["bench_commit"] and "=PASS" in row["check"]
       and "a percentage or a standing word (%, faster, than)" in row["note"]
       and not any(os.path.exists(os.path.join(bench, d, "REVIEW.md")) for d in g1),
       f"every dir PASS, the message carries the anchor's reason with '%', 'faster' and 'than': exit {rc}, "
       f"HEAD unchanged, the ledger line says why, no REVIEW.md ({row['note'][:120]})")
    rc, out = post(g1, "off", "--dry-run")
    ok(rc == 1 and head() == h and "held: the generated message carries a percentage" in out,
       f"--dry-run: the same hold (exit {rc})")

    print("--- the text screen: a sitting's off-task cell is committed with its text_screen.json, named in the message")
    t1 = sitting(raw, 14, off_task=True)
    h = head()
    phrase = "text screen: 1 cell text-fail (litert-lm litert-community/Qwen3-1.7B short-chat 4/4 runs)"
    rc, out = post(t1, "off", "--dry-run")
    ok(rc == 0 and head() == h and not any(os.path.exists(os.path.join(bench, d, "text_screen.json")) for d in t1)
       and phrase in out and "would write text_screen.json (2 cells, 1 text-fail" in out,
       f"--dry-run: PASS, no file written, the message and the checker's line say what it would carry (exit {rc})")
    rc, out = post(t1, "off")
    msg = sh(bench, "git", "log", "-1", "--format=%B").strip()
    files = committed_files()
    screen = json.loads(sh(bench, "git", "show", f"HEAD:{t1[1]}/text_screen.json"))
    ok(rc == 0 and sh(bench, "git", "rev-parse", "HEAD~1") == h and {f"{d}/text_screen.json" for d in t1} <= files
       and screen["cells"]["litert-lm litert-community/Qwen3-1.7B short-chat (v0.0.1)"]["verdict"] == "FAIL",
       f"committed: both dirs' text_screen.json in the commit, the cell FAIL in it (exit {rc})")
    ok(f"text check 0/0 (no run carries one); {phrase}; cpu-capped counted" in msg and MSG_RE.match(msg) is not None
       and not dp.STANDING_WORDS.search(msg) and re.search(r"message guard: no '%' and no standing word .*: OK", out),
       f"the message names the cell, its runs off and no percentage or standing word: {msg[:60]}…")

    print("--- a page check FAIL: the bench commit stands, the page repo is left as it was")
    f1 = sitting(raw, 8)
    page_before = sh(page, "git", "rev-parse", "HEAD")
    h = head()
    rc, out = post(f1, "off", env={"FAKE_PAGE_FAIL": "check_aa"})
    row = ledger()[-1]
    ok(rc == 1 and sh(bench, "git", "rev-parse", "HEAD~1") == h and sh(page, "git", "rev-parse", "HEAD") == page_before
       and "FAIL check_aa" in row["page"] and not row["page_commit"] and sh(page, "git", "status", "--porcelain") == "",
       f"exit {rc}: bench committed, page not, the ledger says FAIL check_aa ({row['page'][:80]})")

    print("--- --allow-subset: a sitting's dirs left out are named; a payload without its anchor still holds")
    a1 = sitting(raw, 9, payloads=("x", "y"), reference={"y": "2026-10-09-dashboard-v1-m4max-x-mac"})
    anchor, x, y = a1
    h = head()
    rc, out = post([x], "off", "--allow-subset")
    ok(rc == 1 and head() == h, "a payload alone (its anchor phase neither committed nor given): held")
    rc, out = post([anchor, y], "off")
    ok(rc == 1 and head() == h, "anchor + one payload without --allow-subset: held (pair-incomplete, reference-uncommitted)")
    rc, out = post([anchor, y], "off", "--allow-subset")
    msg = sh(bench, "git", "log", "-1", "--format=%B").strip()
    files = committed_files()
    ok(rc == 0 and any(f.startswith(anchor + "/") for f in files) and any(f.startswith(y + "/") for f in files)
       and not any(f.startswith(x + "/") for f in files),
       f"with --allow-subset: the anchor and that payload committed, the other payload not (exit {rc})")
    ok("not in this commit (--allow-subset): 2026-10-09-dashboard-v1-m4max-x-mac (a payload of the same anchor "
       "phase, and the admission reference of 2026-10-09-dashboard-v1-m4max-y-mac); results/summary" in msg
       and MSG_RE.match(msg) is not None, "the message names the left-out dir and what it is to the committed ones")

    print("--- the lock: one post at a time")
    s6 = sitting(raw, 10)
    lock = open(os.path.join(bench, "logs", "dashboard-job", ".post.lock"), "a+")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    lock.seek(0); lock.truncate(); lock.write("4242"); lock.flush()
    h = head()
    rc, out = post(s6, "off", "--lock-timeout", "1")
    row = ledger()[-1]
    ok(rc == 1 and head() == h and "busy" in row["note"] and "4242" in row["note"], f"lock held: exit {rc}, {row['note']}")
    fcntl.flock(lock, fcntl.LOCK_UN); lock.close()

    print("--- dirs already committed: nothing to commit, exit 0")
    rc, out = post(s1, "off")
    ok(rc == 0 and head() == h and "nothing to commit" in ledger()[-1]["note"], f"exit {rc}: {ledger()[-1]['note']}")

    print("--- the red segment: the commit's own scripts/regression_watch.py, after the page; its note, never the exit code")
    write(os.path.join(bench, "scripts", "regression_watch.py"), STUB_RED)
    sh(bench, "git", "add", "--", "scripts/regression_watch.py")
    sh(bench, "git", "commit", "-q", "-m", "the red stub", "--", "scripts/regression_watch.py")
    r1 = sitting(raw, 11)
    rc, out = post(r1, "off", "--dry-run")
    ok(rc == 0 and "red: stub red over " + " ".join(os.path.basename(d) for d in r1) + " with --dry-run into logs" in out,
       "--dry-run: the red segment runs over the sitting's dirs with --dry-run, the state dir is the checkout's logs/")
    rc, out = post(r1, "off", env={"FAKE_RED": "mismatch"})
    row = ledger()[-1]
    ok(rc == 0 and row["bench_commit"] == head() and "red: mismatch with the page's regression.json (red: bench 1, page 0;" in row["note"]
       and "and --compare into logs" in row["note"],
       f"a red set that differs from the page build's: 'red: mismatch' in the note, exit {rc}, committed")
    import dashboard_post as dp
    cols = "device,arm,model_id,task,context_tokens,artifact_file,decode_tps,status\n"
    before = cols + "S,a,m1,t,,f,1,measured\nS,a,m2,t,,f,1,measured\nS,a,m3,t,,f,,excluded:x\nS,a,m4,t,,f,,cpu-capped:y\n"
    after = cols + "S,a,m1,t,,f,,cpu-capped:z\nS,a,m2,t,,f,1,measured\nS,a,m3,t,,f,1,measured\nS,a,m4,t,,f,,cpu-capped:y\n"
    ok(dp.number_changes(before, after) == "cells with a number before and none now: 1 (cpu-capped 1), the reverse: 1"
       and dp.number_changes("campaign,file\nx,y\n", after) is None,
       "the page's number changes: a cell that lost its number by its new status, one that gained it; none without a status column")
    ladder = cols + "S,a,m5,t,2048,f,1,measured\nS,a,m5,t,4096,f,1,measured\nS,a,m6,t,4096,f,1,measured\n"
    later = cols + "S,a,m5,t,2048,f,1,measured\nS,a,m5,t,4096,f,,cpu-capped:y\nS,a,m6,t,,f,,text-fail:z\n"
    ok(dp.number_changes(ladder, later) == "cells with a number before and none now: 2 (cpu-capped 1, text-fail 1), the reverse: 0",
       "a cell is its context only on a ladder: a recorded context that moved (4096 -> none) is still the same cell")
    ok("cells with a number before and none now: 1 (cpu-capped 1)" in dp.page_message(
        "0" * 40, {"start": None, "display": "D", "ident": "I", "end": None}, set(), {"r"}, [],
        dp.number_changes(before, after)), "the phrase in the page commit's message")

    print("--- a DDP lab unit's sitting: the message names the platform, the pool, the units, the sessions and the caps")
    import collections as _c
    import datetime
    facts = {"display": "Galaxy S26 (DDP m1q-36)", "ident": "SM-S942U1 (DDP m1q-36)",
             "start": datetime.datetime(2026, 10, 18, 22, 30).astimezone(),
             "end": datetime.datetime(2026, 10, 18, 23, 50).astimezone(),
             "stamps": {"litert-lm-cpu": _c.Counter({"v0.18.0": 3}), "litert-lm-gpu": _c.Counter({"v0.18.0": 3})},
             "runs": 6, "text_n": 2, "text_pass": 2, "capped_in": 3, "capped_past": 3,
             "arms_in": _c.Counter({"litert-lm-gpu": 3}), "arms_past": _c.Counter({"litert-lm-cpu": 3}),
             "cells": [("matrices/dashboard-ddp-v1-android-s26.cells", 2, 2)], "anchor": None, "anchor_phase": "",
             "payload_ratios": [], "failures": [], "flagged": [], "skipped": ["CELL_SKIP x reason=y"],
             "ddp": {"id": "m1q-36", "sessions": ["session-aaaa0001", "session-bbbb0002"], "jobs": 2,
                     "device_minutes": 21.4}, "units": 2}
    msg = dp.commit_message(facts, 4537, 4591, [])
    ok(msg.startswith("results 2026-10-18 Galaxy S26 lab units on the Developer Device Platform (DDP m1q-36, "
                      "SM-S942U1, 2 units), litert-lm-cpu: v0.18.0, litert-lm-gpu: v0.18.0: 2/2 cells of "
                      "matrices/dashboard-ddp-v1-android-s26.cells in one dashboard-job sitting ")
       and "(2 Device Run sessions session-aaaa0001, session-bbbb0002, 2 jobs, 21.4 device-min; no session anchor: "
           "a lab unit's runs carry their own cap marks and text check)" in msg
       and "cpu-capped counted 3/6 (litert-lm-gpu 3), past the line 3 (litert-lm-cpu 3; a lab unit starts capped: "
           "no number)" in msg and "SKIPPED: 1 lines" in msg and not dp.REFUSED_WORDS.search(msg)
       and not dp.STANDING_WORDS.search(msg), msg)
    ok("the 2026-10-18 Galaxy S26 lab units on the Developer Device Platform (DDP m1q-36, SM-S942U1, 2 units) "
       "dashboard-job sitting" in dp.page_message("0" * 40, facts, set(), {"r"}, []),
       "the page commit's message names the lab units the same way")

    print("--- a DDP lab unit's job sitting: its executions' own logcat.txt stays on disk and out of the commit "
          "(the repo's .gitignore line), its runs' logcats go in")
    unit = "2026-10-12-dashboard-v1-s26-ddp-m1q-36-android"
    ud = os.path.join(raw, unit)
    exe = os.path.join(ud, "ddp", "session-fake0001", "j01-gpu-x-short-chat", "execution-fake")
    run_logcat = os.path.join(exe, "artifacts", "data", "local", "tmp", "llmbench", "ddp-out", "run1_logcat.txt")
    write(run_logcat, "10-12 13:47:01.000  1000  1100 I litert: engine loaded\n")
    write(os.path.join(exe, "logcat.txt"), "10-12 13:47:00.000  1000  1100 I ActivityManager: unit log\n")
    log_name = "litert-lm-gpu_litert-community_Qwen3-1.7B_short-chat_2026-10-12T13-47-00_run1.log"
    write(os.path.join(ud, "app-path-android", log_name),
          "===ENGINE_OUTPUT===\ninput_prompt: What does on-device AI mean?\n" + ON_TASK + "\nBenchmarkInfo:\n")
    for i in range(3):
        write(os.path.join(ud, "app-path-android", f"run{i + 1}.json"), json.dumps({
            "schemaVersion": 1, "id": str(uuid.uuid4()), "runtime": "litert-lm-gpu", "engineVersion": "v0.0.1",
            "model": {"id": "litert-community/Qwen3-1.7B"}, "task": "short-chat",
            "timestamp": f"2026-10-12T13:4{i}:00Z",
            "device": {"modelIdentifier": "SM-S942U1", "systemName": "Android",
                       "ddp": {"deviceId": "m1q-36", "serial": "FAKEUNIT1"}},
            "metrics": {"decodeTokensPerSecond": 20.0 + i, "promptTokenCount": 19, "generatedTokenCount": 120,
                        "coldRun": True, "firstEver": i == 0},
            "conditions": {"protocolFlags": ["cpu-capped", "cpu-capped-at-start"]},
            "provenance": {"rawLog": log_name, "modelShaSource": "device"}}))
    write(os.path.join(ud, "SESSION.json"), json.dumps({
        "schema": "dashboard-job-session.v1", "job": "dashboard-v1", "phase": "payload",
        "campaign": f"results/raw/{unit}", "device_key": "s26-ddp", "device_display": "Galaxy S26 (DDP m1q-36)",
        "device_identifier": "SM-S942U1 (DDP m1q-36)", "platform": "ddp", "attempt": 1,
        "started": "2026-10-12 22:46:21", "ended": "2026-10-12 23:29:13", "admitted": True, "verdict": "COMPLETED",
        "reason": "ddp lab unit: no session anchor; each run carries its cap marks and the text check",
        "anchor": None, "runner_exit": 0, "cells": "matrices/dashboard-ddp-v1-android-s26.cells",
        "cells_expected": 1, "cells_with_records": 1,
        "ddp": {"id": "m1q-36", "sessions": ["session-fake0001"], "jobs": 1, "device_minutes": 5.8}}, indent=1))
    before = head()
    rc, out = post(["results/raw/" + unit])
    held = ledger()[-1]
    ok(rc == 1 and head() == before and held["check"] == f"{unit}=FAIL" and "logcat-unscrubbed" in held["note"],
       f"without the line: the execution's logcat.txt holds the sitting (FAIL logcat-unscrubbed), nothing committed (exit {rc})")
    rules = [ln for ln in open(os.path.join(ROOT, ".gitignore")).read().splitlines()
             if ln.startswith("results/raw/") and "/ddp/" in ln and ln.endswith("logcat.txt")]
    with open(os.path.join(bench, ".gitignore")) as fh:
        kept = fh.read()
    write(os.path.join(bench, ".gitignore"), kept + "".join(r + "\n" for r in rules))
    rc, out = post(["results/raw/" + unit])
    done = ledger()[-1]
    files = committed_files()
    rel = lambda p: os.path.relpath(p, bench)
    ok(len(rules) == 1 and rc == 0 and done["check"] == f"{unit}=PASS" and head() != before
       and rel(run_logcat) in files and rel(os.path.join(ud, "SESSION.json")) in files
       and rel(os.path.join(exe, "logcat.txt")) not in files and os.path.exists(os.path.join(exe, "logcat.txt"))
       and not os.path.exists(os.path.join(ud, "REVIEW.md")),
       f"with the repo's line ({rules}): PASS and committed; the run's logcat in the commit, the execution's "
       f"logcat.txt on disk only, the held post's REVIEW.md gone (exit {rc}, {done['check']})")
    msg = sh(bench, "git", "log", "-1", "--format=%s")
    ok(msg.startswith("results 2026-10-12 Galaxy S26 lab units on the Developer Device Platform (DDP m1q-36, SM-S942U1, "
                      "1 unit), litert-lm-gpu: v0.0.1: 1/1 cells of matrices/dashboard-ddp-v1-android-s26.cells")
       and "1 Device Run session session-fake0001, 1 jobs, 5.8 device-min" in msg, msg[:160])
    write(os.path.join(bench, ".gitignore"), kept)

    print("--- usage")
    rc, out = post([os.path.join("results", "raw", "no-such-dir")], "off")
    ok(rc == 2, f"a path that is not a directory: exit 2 (got {rc})")
    others_intact("at the end")

    if _fails:
        print(f"\n{len(_fails)} failure(s); temp dir kept: {tmp}")
        return 1
    shutil.rmtree(tmp)
    print("\nselftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
