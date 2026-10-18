#!/usr/bin/env python3
"""dashboard_post — what follows a dashboard-job sitting: check it, commit it, build the page.

  python3 scripts/dashboard_post.py <campaign dir>... [--dry-run] [--switch SWITCH]
                                    [--page-out DIR] [--no-page-commit] [--allow-subset]
  python3 scripts/dashboard_post.py results/raw/2026-10-14-dashboard-v1-s26{-anchor,-b2}-android --allow-subset

Design: docs/dashboard-autopilot-v1.md. scripts/dashboard_job.py main() runs it after its ledger
line, outside the device hold, when the sitting exits 0, over the campaign dirs the sitting wrote
SESSION.json in; a person runs it the same way over any sitting's dirs. The dirs' checkout is the
repo it commits to. In this order:

  scrub    the account name -> USER in the dirs' text files, in the forms session_check.py's
           user-name rule reads (/Users/<name>, /home/<name>, -Users-<name>-, _bazel_<name>, ls
           owner columns), as people did before each commit (d25a9985..ceeaa362); nothing else
           changes, and a JSON file must parse to the same values with only those strings changed
  check    scripts/session_check.py over the dirs. Every dir PASS, or nothing is committed: a
           REVIEW.md in each dir (rule ids, details, what a person does), one ledger line, exit 1.
           The default takes a sitting whole (the checker's pair rules hold an anchor phase whose
           payload is missing); --allow-subset commits the dirs given while the sitting's other
           dirs stay out, and names them in the message (only those links are let through)
  commit   one local commit of HEAD + the dirs + results/summary rebuilt from that tree (a temp
           index: never the disk, never another lane's staged files), the commit-msg hook run on
           a generated message; the tree committed is the one checked (commit-tree, then
           update-ref compare-and-swap: a HEAD that moved meanwhile is taken again from the top),
           so other lanes' staged and untracked files stay as they are; refused while a merge,
           rebase, cherry-pick or revert is in progress
  page     the private page (switch page_repo) built from the commit's own tree into --page-out,
           its four checks; every one PASS -> dist/ committed in the page repo the same way; the
           cells that had a number on the page before and have none now (and the reverse) go into
           the page message and the ledger note
  red      the commit's own scripts/regression_watch.py over its summary, the page's rule
           (docs/dashboard-autopilot-v1.md §8): this sitting's red points become retakes, a retake
           sitting's verdict a bisect request (logs/dashboard-job/retakes.json,
           bisect-requests.json); the page build's regression.json must hold the same red points
           ("red: mismatch" in the ledger note otherwise); it never changes the exit code
  switch   push the bench, push the page, publish — each only when ops/autopilot/switch.json says
           true, and a push only of commits this step made; while false, the ledger line says
           what it would have pushed or published

Exit codes: 0 committed (or nothing new to commit) and every later step as the switch and the
flags allow; 1 held (nothing committed) or a step after the commit failed (the ledger names it);
2 usage. Ledger: logs/dashboard-job/autopilot-ledger.tsv. One post at a time
(logs/dashboard-job/.post.lock). --dry-run writes nothing (no scrub, no REVIEW.md, no ledger, no
commit, no page) and prints the plan.
"""
import argparse
import collections
import csv
import datetime
import fcntl
import getpass
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from build_summary import cpu_cap_drop_of  # noqa: E402
from render_leaderboard import CPU_CAP_EXEMPT_ARMS, CPU_CAP_MAX_DROP_PCT  # noqa: E402
from session_check import load_records, parse_time, read_session, short  # noqa: E402

CHECKER = os.path.join(ROOT, "scripts", "session_check.py")
SWITCH_REL = "ops/autopilot/switch.json"
LOG_REL = "logs/dashboard-job"
LEDGER_NAME = "autopilot-ledger.tsv"
LOCK_NAME = ".post.lock"
PAGE_OUT_DEFAULT = "logs/dashboard-job/autopilot-page"   # cleared for every build
SUMMARY_REL = "results/summary"
SUMMARY_CSV = "results/summary/device-runs.csv"
SWITCH_KEYS = ("push_bench", "push_page", "publish")
PUSH_BRANCH = "main"
LEDGER_COLS = ("started", "ended", "dirs", "check", "bench_commit", "summary_lines", "page",
               "page_commit", "push_bench", "push_page", "publish", "note")
# the page repo's four checks (its README "Build"), in the order people ran them
PAGE_CHECKS = ("tools/check_against_bench_dashboard.py", "tools/check_regression.py",
               "tools/check_aa.py", "tools/render_check.py")
PAGE_DATA = ("index.html", "cells.csv", "cells.json", "regression.json", "regression.csv",
             "aa.json", "aa.csv")
# the red segment: the commit's tree's own copy of the page's regression rule
RED_SCRIPT = os.path.join("scripts", "regression_watch.py")
# the words the commit-msg hook every repo under ~/code carries refuses (standup
# tools/git-hooks/commit-msg); the message is checked before the hook sees it
REFUSED_WORDS = re.compile(r"claude|anthropic", re.I)
# an operation in progress: a commit now would land in the middle of it
GIT_BUSY = ("MERGE_HEAD", "rebase-merge", "rebase-apply", "CHERRY_PICK_HEAD", "REVERT_HEAD")
REVIEW = "REVIEW.md"
REVIEW_MARK = "<!-- written by scripts/dashboard_post.py for a person; removed when the dir is committed -->"
# --allow-subset lets these findings through when the dir they name is a left-out dir of the
# same sitting (the details are session_check.py check_pair's); a payload without its anchor
# phase, or an anchor phase no payload names, still holds
SUBSET_LINKS = (("pair-incomplete", re.compile(r"^payload (\S+) is neither committed nor in this set$"),
                 "a payload of the same anchor phase"),
                ("reference-uncommitted", re.compile(r"^admission reference (\S+) is neither committed nor in this set$"),
                 "the admission reference of {dir}"))
# what a person does about a finding (docs/session-check-v1.md "Rules")
ACTION = {
    "not-admitted": "refused at admission: keep the dir on disk, never commit it (a refused sitting is never partially kept, job doc §5)",
    "session-missing": "the job never closed this sitting: read the job log's tail; the records stay on disk, uncommitted",
    "stopped-sitting": "a stopped sitting's quarantine: kept on disk, never committed",
    "logcat-unscrubbed": "scrub the logcat (android/ddp/scrub.py), keep execution-level logcat.txt out, post again",
    "big-file": "move the weights / trace / engine binary out of the dir (they stay on the measuring machine), post again",
    "secret": "take the credential out of the file and rotate it, post again",
    "pair-broken": "the payload's anchor phase is gone or refused: the payload is not admissible as it is",
    "verdict": "read the job log (timeout, device lost): re-run the missing cells, or commit by hand saying what is missing",
    "partial": "re-run the cells without records (job doc §5 targeted retake), or name them in a hand commit",
    "runner-exit": "read the job log's tail for the runner's exit before calling the sitting clean",
    "failures": "read FAILURES.txt and the cell's log: re-run the cell, or commit by hand with the reason",
    "flagged": "LEVEL: a targeted retake; DEGENERATE: read the sample, never quote the rate (job doc §5)",
    "text-fail": "read the stored text of the failing runs before the numbers enter the record (fairness-rules §12)",
    "engine-stamp": "the records stamp an engine off the pin registry: a pin bump (a person decides) or a stale registry",
    "prompt-tokens": "the prompt did not reach the engine whole: read the run's log (Prefill Turn 1) and the bundle's chat template",
    "prompt-newtag": "first sitting on this build, prompt count far from other builds': read the log before the numbers count",
    "reply-empty": "read the replies (session_check.py --markdown lists one per cell)",
    "reply-loop": "read the replies: a loop is a failed run (fairness-rules §4)",
    "reply-off-task": "read the replies: an answer to another question is a failed run",
    "gen-budget": "the run decoded past its budget: read the log (thought channel?) before the rate counts",
    "invalid-decode": "'Invalid decode' lines void the rate: read the log",
    "model-sha-source": "the bytes on the phone were not hashed: re-push (push_verified), or say so in a hand commit",
    "debug-build": "a Debug build's numbers never count: install the Release build and re-run",
    "raw-log-missing": "a number without its stored report is not a measurement: find the log or set the record aside",
    "record-unreadable": "a record the summary cannot parse: repair it or set it aside (a .attempt1 copy)",
    "pair-incomplete": "post the anchor phase and its payloads together (one sitting), or name the left-out dirs with --allow-subset",
    "reference-uncommitted": "the admission reference is on this disk only: commit it first, or with this sitting",
    "user-name": "the account name is in a file the scrub does not rewrite (binary, or a form it does not know): replace it by USER",
    "big-file-size": "a file over 5 MB: keep it out of the repo, or say why in a hand commit",
    "not-job": "not a dashboard job campaign: a person reviews it",
}

_LEDGER_DIR = None


class Usage(Exception):
    """exit 2"""


def log(msg):
    print(f"[{time.strftime('%F %T')}] post: {msg}", flush=True)


def now_text():
    return time.strftime("%F %T")


# ---------------------------------------------------------------- git

def git_env(**extra):
    """The environment for git: none of a caller's GIT_DIR / GIT_WORK_TREE / GIT_INDEX_FILE (a
    hook's environment would point every command at another repo), plus `extra`."""
    env = {k: v for k, v in os.environ.items()
           if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX")}
    env.update(extra)
    return env


def git(top, *args, index=None, timeout=300):
    """(rc, output) of `git -C top <args>` (stdout; stdout + stderr when it fails); `index` = a
    temp index file in place of the checkout's own."""
    env = git_env(**({"GIT_INDEX_FILE": index} if index else {}))
    try:
        p = subprocess.run(["git", "-C", top] + list(args), capture_output=True, text=True,
                           timeout=timeout, env=env)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, str(e)
    return p.returncode, p.stdout if p.returncode == 0 else (p.stdout + p.stderr)


def rev(top, name):
    rc, out = git(top, "rev-parse", "-q", "--verify", name)
    return out.strip() if rc == 0 else None


def git_busy(top):
    """The operation in progress in this checkout (MERGE_HEAD, rebase-merge, …), or None."""
    for name in GIT_BUSY:
        rc, out = git(top, "rev-parse", "--git-path", name)
        p = out.strip()
        if rc == 0 and p and os.path.exists(p if os.path.isabs(p) else os.path.join(top, p)):
            return name
    return None


def branch_of(top):
    rc, out = git(top, "symbolic-ref", "-q", "--short", "HEAD")
    return out.strip() if rc == 0 and out.strip() else None


def run_hooks(top, index, msg_file):
    """The pre-commit and commit-msg hooks against the index being committed, as `git commit`
    runs them (git hook run: core.hooksPath and a missing hook are git's business) -> None, or
    the refusing hook's output. An old git without `git hook run` (exit 129) leaves the guard to
    REFUSED_WORDS above."""
    for hook, extra in (("pre-commit", []), ("commit-msg", ["--", msg_file])):
        rc, out = git(top, "hook", "run", "--ignore-missing", hook, *extra, index=index)
        if rc == 129:
            return None
        if rc != 0:
            return f"{hook} hook refused: {short(out, 300)}"
    return None


def commit_index(top, index, head, branch, msg_file, reset_paths):
    """Commit the tree of `index` on top of `head` and move `branch` there only if it is still at
    `head` (update-ref compare-and-swap) -> (new sha, None) or (None, why). The checkout's own
    index then takes the new HEAD's entries for `reset_paths` (git reset -- <paths>): every
    other staged entry, every untracked file and the working tree are left as they are."""
    rc, tree = git(top, "write-tree", index=index)
    if rc != 0:
        return None, f"write-tree failed: {short(tree, 200)}"
    refused = run_hooks(top, index, msg_file)
    if refused:
        return None, refused
    rc, new = git(top, "commit-tree", tree.strip(), "-p", head, "-F", msg_file)
    if rc != 0:
        return None, f"commit-tree failed: {short(new, 200)}"
    new = new.strip()
    subject = open(msg_file).read().split("\n", 1)[0]
    rc, out = git(top, "update-ref", "-m", "commit: " + subject[:200], f"refs/heads/{branch}", new, head)
    if rc != 0:
        return None, f"moved: {short(out, 200)}"
    rc, out = git(top, "reset", "-q", "--", *reset_paths)
    if rc != 0:
        log(f"WARN the index was not updated for the committed paths (git status shows them staged "
            f"as removed until `git reset -- <paths>`): {short(out, 200)}")
    return new, None


# ---------------------------------------------------------------- the dirs

def resolve(paths):
    """(checkout top, [results/raw/<campaign>, …]) of the dirs given, or Usage."""
    tops, rels = set(), []
    for p in paths:
        a = os.path.realpath(p)
        if not os.path.isdir(a):
            raise Usage(f"not a directory: {p}")
        rc, out = git(a, "rev-parse", "--show-toplevel")
        if rc != 0 or not out.strip():
            raise Usage(f"not in a git work tree: {p}")
        top = os.path.realpath(out.strip())
        rel = os.path.relpath(a, top).replace(os.sep, "/")
        if rel.count("/") != 2 or not rel.startswith("results/raw/"):
            raise Usage(f"not a campaign dir (results/raw/<campaign>): {p}")
        tops.add(top)
        if rel not in rels:
            rels.append(rel)
    if len(tops) != 1:
        raise Usage("the dirs are in more than one checkout: " + ", ".join(sorted(tops)))
    return tops.pop(), rels


def load_switch(path):
    """ops/autopilot/switch.json: push_bench / push_page / publish (only true is on; no file =
    all off) and page_repo (none = no page step)."""
    try:
        with open(path) as fh:
            raw = json.load(fh)
    except FileNotFoundError:
        raw = {}
    except (OSError, ValueError) as e:
        raise Usage(f"switch unreadable: {path}: {e}")
    if not isinstance(raw, dict):
        raise Usage(f"switch is not a JSON object: {path}")
    sw = {k: raw.get(k) is True for k in SWITCH_KEYS}
    repo = raw.get("page_repo")
    sw["page_repo"] = (os.path.realpath(os.path.expanduser(repo))
                       if isinstance(repo, str) and repo.strip() else None)
    return sw


def files_of(top, d):
    """The files a commit of dir d would carry (tracked, or untracked and not ignored)."""
    rc, out = git(top, "ls-files", "-z", "-c", "-o", "--exclude-standard", "--", d)
    return sorted({p for p in out.split("\0") if p}) if rc == 0 else []


def read_lines(d, name):
    """Lines of <d>/<name> and <d>/app-path-android/<name> (where the runners write them)."""
    out = []
    for f in (os.path.join(d, name), os.path.join(d, "app-path-android", name)):
        if os.path.exists(f):
            with open(f, errors="replace") as fh:
                out += [ln.rstrip("\n") for ln in fh if ln.strip()]
    return out


# ---------------------------------------------------------------- scrub

def name_forms(user):
    """(pattern, replacement) for the account name in each form session_check.py's user-name
    rule reads."""
    u = re.escape(user)
    return [(re.compile("/Users/" + u), "/Users/USER"), (re.compile("/home/" + u), "/home/USER"),
            (re.compile("-Users-" + u + "-"), "-Users-USER-"), (re.compile("_bazel_" + u), "_bazel_USER"),
            (re.compile(r"(?<![A-Za-z0-9])" + u + r"(\s+)(staff|wheel|admin)\b"), r"USER\1\2")]


def substitute(text, forms):
    n = 0
    for rx, repl in forms:
        text, k = rx.subn(repl, text)
        n += k
    return text, n


def json_values(text):
    """The JSON values of a file: the whole text, else one per non-empty line (.jsonl); None
    when it is not JSON."""
    try:
        return [json.loads(text)]
    except ValueError:
        pass
    try:
        return [json.loads(ln) for ln in text.splitlines() if ln.strip()] or None
    except ValueError:
        return None


def names_only(old, new, forms):
    """True when `new` is `old` with the name forms replaced inside strings and nothing else:
    every number, boolean, null and structure equal."""
    if isinstance(old, str):
        return isinstance(new, str) and substitute(old, forms)[0] == new
    if isinstance(old, dict):
        return (isinstance(new, dict) and len(old) == len(new)
                and all(substitute(k, forms)[0] in new and names_only(v, new[substitute(k, forms)[0]], forms)
                        for k, v in old.items()))
    if isinstance(old, list):
        return isinstance(new, list) and len(old) == len(new) and all(
            names_only(a, b, forms) for a, b in zip(old, new))
    return type(old) is type(new) and old == new


def scrub(top, dirs, user, dry):
    """Replace the account name by USER in the dirs' text files (a binary file — NUL in its
    first 8 KB — or one over 20 MB is left as it is; a symlink is never followed). -> (files
    changed, places, files left as they were because the change was not names-only)."""
    if not user or user == "USER":
        return 0, 0, []
    forms = name_forms(user)
    changed, places, refused = 0, 0, []
    for d in dirs:
        for rel in files_of(top, d):
            p = os.path.join(top, rel)
            if os.path.islink(p) or not os.path.isfile(p) or os.path.getsize(p) > 20_000_000:
                continue
            with open(p, "rb") as fh:
                data = fh.read()
            if b"\0" in data[:8192]:
                continue
            # surrogateescape: bytes that are not UTF-8 come back out unchanged
            text = data.decode("utf-8", "surrogateescape")
            new, n = substitute(text, forms)
            if not n:
                continue
            old_vals = json_values(text)
            if old_vals is not None:
                new_vals = json_values(new)
                if new_vals is None or not names_only(old_vals, new_vals, forms):
                    refused.append(rel)
                    continue
            changed += 1
            places += n
            if dry:
                continue
            tmp = p + ".scrub-tmp"
            with open(tmp, "wb") as fh:
                fh.write(new.encode("utf-8", "surrogateescape"))
            shutil.copymode(p, tmp)
            os.replace(tmp, p)
    return changed, places, refused


# ---------------------------------------------------------------- check

def check(top, dirs, user, tmp):
    """scripts/session_check.py over the dirs -> its JSON (dirs[], summary); Usage on its exit 2."""
    out = os.path.join(tmp, "check.json")
    # --user "" turns the checker's user-name rule off (make_context)
    cmd = [sys.executable, CHECKER] + [os.path.join(top, d) for d in dirs] + ["--json", out, "-q",
                                                                              "--user", user or ""]
    p = subprocess.run(cmd, cwd=top, capture_output=True, text=True, timeout=1800)
    for ln in (p.stdout or "").splitlines():
        log("check: " + ln)
    if p.returncode == 2 or not os.path.exists(out):
        raise Usage(f"session_check.py exit {p.returncode}: {short(p.stderr or p.stdout, 300)}")
    with open(out) as fh:
        return json.load(fh)


def sitting_prefix(top, d):
    """<date>-dashboard-v1-<device key> of a dir's sitting (SESSION.json started, device_key)."""
    s = read_session(os.path.join(top, d)) or {}
    t = parse_time(s.get("started"))
    key = s.get("device_key")
    return f"{t:%Y-%m-%d}-dashboard-v1-{key}" if t and key else None


def waive_subset(top, results, given):
    """--allow-subset: let through the findings that name a dir of the same sitting left out of
    this commit (SUBSET_LINKS); mark them and return [(dir, left-out dir, what it is)]."""
    names = {os.path.basename(d) for d in given}
    out = []
    for r in results:
        prefix = sitting_prefix(top, "results/raw/" + r["name"])
        for f in r["findings"]:
            if f.get("allowed_by"):
                continue
            for rule, rx, what in SUBSET_LINKS:
                m = rx.match(f["detail"]) if f["rule"] == rule else None
                if m and m.group(1) not in names and prefix and m.group(1).startswith(prefix + "-"):
                    f["waived"] = f"--allow-subset: {m.group(1)} left out of this commit"
                    out.append((r["name"], m.group(1), what.format(dir=r["name"])))
    return out


def verdict_of(r):
    live = [f for f in r["findings"] if not f.get("allowed_by") and not f.get("waived")]
    if any(f["severity"] == "FAIL" for f in live):
        return "FAIL"
    return "HOLD" if live else "PASS"


def write_reviews(top, dirs, results, verdicts, why):
    """REVIEW.md in every dir of a sitting that was not committed: its findings with what a
    person does, the other dirs' verdicts, how to post again."""
    by_name = {r["name"]: r for r in results}
    stamp = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    names = [os.path.basename(d) for d in dirs]
    for d, name in zip(dirs, names):
        r = by_name.get(name, {"findings": []})
        v = verdicts.get(name, "?")
        L = [REVIEW_MARK, f"# REVIEW: {name} — {v}", "",
             f"Held by scripts/dashboard_post.py at {stamp}: nothing of this sitting was committed.",
             "", "Why: " + why, "", "The dirs of this post: " + ", ".join(f"{n} {verdicts.get(n, '?')}" for n in names),
             ""]
        live = [f for f in r["findings"] if not f.get("allowed_by") and not f.get("waived")]
        if live:
            L += ["| severity | rule | detail | what a person does |", "|---|---|---|---|"]
            for f in live:
                detail = f["detail"].replace("|", "\\|")
                L.append(f"| {f['severity']} | `{f['rule']}` | {detail} | {ACTION.get(f['rule'], 'a person reviews it')} |")
            L.append("")
        excused = [f for f in r["findings"] if f.get("allowed_by") or f.get("waived")]
        if excused:
            L.append("Not holding:")
            for f in excused:
                by = (f"allowed by {f['allowed_by']['commit']} ({f['allowed_by']['reason']})"
                      if f.get("allowed_by") else f["waived"])
                L.append(f"- `{f['rule']}`: {f['detail']} — {by}")
            L.append("")
        L += ["Post again once it is fixed (the allow-list takes a line only when a commit message gives the reason):",
              "", "    python3 scripts/dashboard_post.py " + " ".join(dirs), "",
              "A dir that cannot pass is committed by hand with the reason in the message "
              "(docs/dashboard-recurring-job-v1.md §6), or stays uncommitted.", ""]
        with open(os.path.join(top, d, REVIEW), "w") as fh:
            fh.write("\n".join(L))


def remove_reviews(top, dirs):
    """A REVIEW.md this step wrote at an earlier hold goes before the commit (a person's own
    REVIEW.md, without the mark, stays)."""
    for d in dirs:
        p = os.path.join(top, d, REVIEW)
        try:
            with open(p) as fh:
                mine = fh.readline().strip() == REVIEW_MARK
        except OSError:
            continue
        if mine:
            os.remove(p)


# ---------------------------------------------------------------- the commit's tree

def build_tree(top, head, dirs, tmp):
    """HEAD + the dirs in a temp index, exported to <tmp>/tree, results/summary rebuilt there by
    the tree's own build_summary.py and put back into the temp index (CLAUDE.md: the summary
    only as rebuilt from the git index; this index holds nothing of another lane's) ->
    (index, tree dir, lines before, lines after)."""
    index, tree = os.path.join(tmp, "index"), os.path.join(tmp, "tree")
    for args in (["read-tree", head], ["add", "--"] + list(dirs),
                 ["checkout-index", "-a", f"--prefix={tree}/"]):
        rc, out = git(top, *args, index=index)
        if rc != 0:
            raise RuntimeError(f"git {args[0]} failed: {short(out, 300)}")
    builder = os.path.join(tree, "scripts", "build_summary.py")
    p = subprocess.run([sys.executable, builder], cwd=tree, capture_output=True, text=True, timeout=900,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    if p.returncode != 0:
        raise RuntimeError(f"build_summary.py exit {p.returncode}: {short(p.stderr or p.stdout, 300)}")
    rc, out = git(top, f"--work-tree={tree}", "add", "--", SUMMARY_REL, index=index)
    if rc != 0:
        raise RuntimeError(f"git add {SUMMARY_REL} failed: {short(out, 300)}")
    rc, before = git(top, "show", f"{head}:{SUMMARY_CSV}")
    lines_a = before.count("\n") if rc == 0 else 0
    after = os.path.join(tree, SUMMARY_CSV)
    with open(after, "rb") as fh:
        lines_b = fh.read().count(b"\n")
    return index, tree, lines_a, lines_b


def copy_summary(tree, top):
    """The rebuilt summary into the checkout too (the CLAUDE.md recipe's cp): the disk then reads
    what was committed, until the next `bench matrix` rebuilds it from the disk."""
    src = os.path.join(tree, SUMMARY_REL)
    for f in sorted(os.listdir(src)):
        if os.path.isfile(os.path.join(src, f)):
            shutil.copyfile(os.path.join(src, f), os.path.join(top, SUMMARY_REL, f))


# ---------------------------------------------------------------- the message

def primary_anchor(s):
    return next((a for a in ((s.get("anchor") or {}).get("anchors") or []) if a.get("primary")), None) or {}


def sitting_facts(top, dirs):
    """What the commit message says, read from the dirs: SESSION.json (device, cells, times, the
    admission) and the records (engine stamps, the text check, CPU caps)."""
    sess = {d: read_session(os.path.join(top, d)) or {} for d in dirs}
    order = sorted(dirs, key=lambda d: sess[d].get("phase") != "anchor")    # anchor phases first
    first = sess[order[0]]
    starts = [t for t in (parse_time(sess[d].get("started")) for d in dirs) if t]
    ends = [t for t in (parse_time(sess[d].get("ended")) for d in dirs) if t]
    stamps = collections.defaultdict(collections.Counter)
    runs = text_n = text_pass = capped_in = capped_past = 0
    for d in dirs:
        for _, rec in load_records(os.path.join(top, d)):
            if rec is None:
                continue
            runs += 1
            stamps[rec.get("runtime") or "?"][rec.get("engineVersion") or "unstamped"] += 1
            cond = rec.get("conditions") or {}
            tc = cond.get("textCheck")
            if isinstance(tc, dict):
                text_n += 1
                text_pass += tc.get("status") == "PASS"
            if "cpu-capped" in (cond.get("protocolFlags") or []):
                # the renderer's cpu-cap-rule (render_leaderboard.arm_row), as session_check notes it
                drop = cpu_cap_drop_of(rec)
                if rec.get("runtime") in CPU_CAP_EXEMPT_ARMS or (drop and float(drop) <= CPU_CAP_MAX_DROP_PCT):
                    capped_in += 1
                else:
                    capped_past += 1
    anchors = [sess[d] for d in order if sess[d].get("phase") == "anchor"]
    payloads = [sess[d] for d in order if sess[d].get("phase") == "payload"]
    flagged = [ln for d in dirs for ln in read_lines(os.path.join(top, d), "FLAGGED.txt")]
    return {
        "display": first.get("device_display") or first.get("device_key") or "?",
        "ident": first.get("device_identifier") or "?",
        "start": min(starts) if starts else None, "end": max(ends) if ends else None,
        "stamps": stamps, "runs": runs, "text_n": text_n, "text_pass": text_pass,
        "capped_in": capped_in, "capped_past": capped_past,
        "cells": [(s.get("cells") or "?", s.get("cells_with_records"), s.get("cells_expected")) for s in payloads],
        "anchor": anchors[0] if anchors else None,
        "anchor_phase": os.path.basename((payloads[0] if payloads else {}).get("anchor_phase") or ""),
        "payload_ratios": [primary_anchor(s).get("ratio") for s in payloads],
        "failures": [ln for d in dirs for ln in read_lines(os.path.join(top, d), "FAILURES.txt")],
        "flagged": flagged,
        "skipped": [ln for d in dirs for ln in read_lines(os.path.join(top, d), "SKIPPED.txt")],
    }


def when_text(start, end):
    if not start or not end:
        return "(times not recorded)"
    tz = start.tzname() or ""
    if start.date() == end.date():
        return f"{start:%H:%M}–{end:%H:%M} {tz}".strip()
    return f"{start:%H:%M}–{end:%Y-%m-%d %H:%M} {tz}".strip()


def anchor_text(f):
    a = f["anchor"]
    if a is None:
        return f"anchor phase {f['anchor_phase'] or '?'} committed before"
    p = primary_anchor(a)
    thermal = ", ".join(p.get("thermal") or []) or "?"
    ref = os.path.basename((p.get("reference") or {}).get("campaign") or "")
    if p.get("ratio") and ref:
        text = f"anchor admitted at ratio {p['ratio']:.3f} vs {ref}, thermal {thermal}"
    else:
        text = f"anchor admitted: {a.get('reason') or '?'}; thermal {thermal}"
    own = [f"{r:.3f}" for r in f["payload_ratios"] if r]
    if own:
        text += f"; the payload's own anchor rows at {' / '.join(own)}"
    return text


def commit_message(f, lines_a, lines_b, waived):
    """One line, as the results commits read (1798483f, e3010721): what ran, the admission, the
    text check, the CPU caps, the failures, the summary rebuild. No runtime against another."""
    arms = ", ".join(f"{arm}: {' / '.join(sorted(c))}" for arm, c in sorted(f["stamps"].items())) or "no records"
    cells = ", ".join(f"{have}/{exp} cells of {name}" for name, have, exp in f["cells"]) or "the anchor phase only"
    text = (f"text check {f['text_pass']}/{f['text_n']}" if f["text_n"]
            else "text check 0/0 (no run carries one)")
    caps = f"cpu-capped counted {f['capped_in']}/{f['runs']}, past the line {f['capped_past']}"
    fails = f["failures"]
    fail_text = ("none" if not fails else "; ".join(short(x, 90) for x in fails[:2])
                 + (f" and {len(fails) - 2} more" if len(fails) > 2 else ""))
    start = f["start"]
    msg = (f"results {start:%Y-%m-%d} " if start else "results ") + (
        f"{f['display']} ({f['ident']}), {arms}: {cells} in one dashboard-job sitting "
        f"{when_text(f['start'], f['end'])} ({anchor_text(f)}); {text}; {caps}; FAILURES: {fail_text}")
    retries = [ln for ln in f["flagged"] if not re.search(r"\b(LEVEL|DEGENERATE|GATE_ERROR)\b", ln)]
    if retries:
        msg += f"; gate retries kept: {len(retries)} (FLAGGED.txt)"
    if f["skipped"]:
        msg += f"; SKIPPED: {len(f['skipped'])} lines"
    if waived:
        left = collections.OrderedDict()
        for _, name, what in waived:
            if what not in left.setdefault(name, []):
                left[name].append(what)
        msg += "; not in this commit (--allow-subset): " + ", ".join(
            f"{n} ({', and '.join(w)})" for n, w in left.items())
    return msg + f"; results/summary rebuilt from the git index ({lines_a} -> {lines_b} lines)\n"


def page_message(bench_sha, f, rows_old, rows_new, checks, numbers=None):
    """The page repo's dist commits read "dist: the page from the bench at <sha> — …" (8100b64)."""
    added = len(rows_new - rows_old)
    removed = len(rows_old - rows_new)
    start = f["start"]
    names = ", ".join(c for c, _, _ in checks)
    return (f"dist: the page from the bench at {bench_sha[:8]} — the {start:%Y-%m-%d} " if start else
            f"dist: the page from the bench at {bench_sha[:8]} — the ") + (
        f"{f['display']} ({f['ident']}) dashboard-job sitting {when_text(f['start'], f['end'])} committed there; "
        f"cells.csv {added} rows added, {removed} removed ({len(rows_new)} rows)"
        + (f"; {numbers}" if numbers else "") + f"; checks: {names} PASS\n")


# ---------------------------------------------------------------- the page

def csv_rows(text):
    return set(text.splitlines()[1:]) if text else set()


def page_step(sw, tree, page_out, row, dry):
    """Build the page from the commit's own tree into page_out and run its four checks ->
    (every check PASS, [(check, exit, seconds)], the page repo or None)."""
    repo = sw["page_repo"]
    if not repo or not os.path.isfile(os.path.join(repo, "build.py")):
        row["page"] = "skipped: no page repo (switch page_repo)" if not repo else f"skipped: no build.py in {repo}"
        log(row["page"])
        return False, [], None
    if dry:
        row["page"] = f"would build {repo}/build.py into {page_out} and run its four checks"
        log(row["page"])
        return False, [], repo
    env = dict(os.environ, EDGE_LLM_BENCH=tree, PYTHONDONTWRITEBYTECODE="1")
    results = []
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, os.path.join(repo, "build.py"), "--out-dir", page_out],
                           cwd=page_out, env=env, capture_output=True, text=True, timeout=900)
        rc, out = p.returncode, ((p.stdout or "") + (p.stderr or "")).strip().splitlines()
    except subprocess.TimeoutExpired as e:
        rc, out = 124, [f"timeout after {e.timeout} s"]
    results.append(("build", rc, round(time.time() - t0, 1)))
    log(f"page build exit {rc} ({results[-1][2]} s): {short(out[-1] if out else '', 160)}")
    if rc != 0:
        for ln in out[-20:]:
            log(f"  build | {ln}")
    if rc == 0:
        os.makedirs(os.path.join(page_out, "checks"), exist_ok=True)
        for c in PAGE_CHECKS:
            name = os.path.splitext(os.path.basename(c))[0]
            t0 = time.time()
            try:
                p = subprocess.run([sys.executable, os.path.join(repo, c), "--dist", page_out],
                                   cwd=page_out, env=env, capture_output=True, text=True, timeout=1800)
                rc, out = p.returncode, (p.stdout or "") + (p.stderr or "")
            except subprocess.TimeoutExpired as e:
                rc, out = 124, f"timeout after {e.timeout} s"
            secs = round(time.time() - t0, 1)
            with open(os.path.join(page_out, "checks", name + ".out"), "w") as fh:
                fh.write(out)
            last = out.strip().splitlines()[-1] if out.strip() else ""
            results.append((name, rc, secs))
            log(f"page check {name} exit {rc} ({secs} s): {short(last, 120)}")
            if rc != 0:
                for ln in out.strip().splitlines()[-20:]:
                    log(f"  {name} | {ln}")
    passed = all(rc == 0 for _, rc, _ in results) and len(results) == 1 + len(PAGE_CHECKS)
    row["page"] = "; ".join(f"{n} {rc} {s}s" for n, rc, s in results) + (
        "" if passed else f" — FAIL {next(n for n, rc, _ in results if rc != 0)}")
    return passed, results, repo


def page_commit(repo, page_out, msg_for, tmp):
    """dist/ of the page repo := the checked build, committed there the same way as the bench ->
    (sha or None, why not)."""
    busy = git_busy(repo)
    if busy:
        return None, f"a {busy} is in progress in the page repo"
    branch, head = branch_of(repo), rev(repo, "HEAD")
    if not branch or not head:
        return None, "the page repo's HEAD is detached or has no commit"
    rc, dirty = git(repo, "status", "--porcelain", "--untracked-files=no")
    if rc != 0 or dirty.strip():
        return None, ("the page repo has uncommitted changes to tracked files (the page was built "
                      f"by its working tree, not its HEAD): {short(dirty, 160)}")
    rc, tracked = git(repo, "ls-files", "-z", "--", "dist")
    tracked = {os.path.basename(p) for p in tracked.split("\0") if p}
    rc_old, old_cells = git(repo, "show", f"{head}:dist/cells.csv")
    dist = os.path.join(repo, "dist")
    os.makedirs(dist, exist_ok=True)
    written = []
    for n in sorted(tracked | set(PAGE_DATA)):
        src = os.path.join(page_out, n)
        if os.path.isfile(src):
            if n not in tracked and os.path.exists(os.path.join(dist, n)):
                continue    # an untracked file of someone else's in dist/ stays as it is
            shutil.copyfile(src, os.path.join(dist, n))
            written.append(n)

    def undo(why):
        """dist/ back to the page repo's HEAD (its HEAD now: a commit that moved it meanwhile
        is someone's): the build stays in page_out, the repo is as it was."""
        git(repo, "checkout", "-q", "HEAD", "--", "dist")
        for n in written:
            if n not in tracked:
                os.remove(os.path.join(dist, n))
        return None, why

    index = os.path.join(tmp, "page-index")
    for args in (["read-tree", head], ["add", "--", "dist"]):
        rc, out = git(repo, *args, index=index)
        if rc != 0:
            return undo(f"git {args[0]} failed in the page repo: {short(out, 200)}")
    rc, _ = git(repo, "diff", "--cached", "--quiet", head, "--", "dist", index=index)
    if rc == 0:
        return None, "unchanged: dist/ is the page repo's HEAD already"
    with open(os.path.join(page_out, "cells.csv")) as fh:
        new_cells = fh.read()
    msg = msg_for(csv_rows(old_cells if rc_old == 0 else ""), csv_rows(new_cells))
    bad = REFUSED_WORDS.findall(msg)
    if bad:
        return undo(f"the generated page message carries a word the commit-msg hook refuses ({bad[0]})")
    msg_file = os.path.join(tmp, "page-message.txt")
    with open(msg_file, "w") as fh:
        fh.write(msg)
    sha, why = commit_index(repo, index, head, branch, msg_file, ["dist"])
    return (sha, None) if sha else undo(why)


def cell_numbers(text):
    """The page's cells.csv -> {cell: 'number' where the page shows a decode value (status measured),
    else the status's first word (cpu-capped, text-fail, excluded, no-decode, not measured)}; None
    for a file without the status column. A cell is (device, arm, model id, task, file), and its
    context only where the page has that cell at several allocations (a ladder): elsewhere the
    context column is what the cell's pooled runs recorded, which moves with the sitting (the
    Galaxy S26 llama.cpp Gemma 4 E4B short-chat cell: 4096 from its 09-14 sitting, none from its
    10-14 one, whose runs all left the pool under the cpu-cap rule)."""
    rows = list(csv.DictReader(io.StringIO(text or "")))
    if not rows or "status" not in rows[0]:
        return None
    base = [tuple(r.get(k) or "" for k in ("device", "arm", "model_id", "task", "artifact_file")) for r in rows]
    many = {k for k, n in collections.Counter(base).items() if n > 1}
    out = {}
    for k, r in zip(base, rows):
        kind = (r.get("status") or "").split(":", 1)[0]
        out[k + ((r.get("context_tokens") or "",) if k in many else ())] = "number" if kind == "measured" else kind
    return out


def number_changes(old_text, new_text):
    """One phrase: the cells (in both pages) that had a number on the page committed before and have
    none in this build, by their new status, and the reverse — a night that empties cells reads so
    in the morning, whatever the checker said. None when either page has no status column."""
    old, new = cell_numbers(old_text), cell_numbers(new_text)
    if old is None or new is None:
        return None
    both = [k for k in new if k in old]
    lost = collections.Counter(new[k] for k in both if old[k] == "number" and new[k] != "number")
    gained = sum(1 for k in both if new[k] == "number" and old[k] != "number")
    return (f"cells with a number before and none now: {sum(lost.values())}"
            + (f" ({', '.join(f'{k} {v}' for k, v in sorted(lost.items()))})" if lost else "")
            + f", the reverse: {gained}")


def red_step(top, tree, page_out, dirs, dry, tmp):
    """The red segment (docs/dashboard-autopilot-v1.md §8): the commit's own tree's
    scripts/regression_watch.py over its summary with this sitting's dirs -> the ledger note's phrase.
    The state it writes (retakes, bisect requests, drafts) goes under this checkout's
    logs/dashboard-job/; with a page build, its regression.json is compared. Nothing here changes
    the post's exit code: a mismatch or an error is the phrase."""
    script = os.path.join(tree, RED_SCRIPT)
    if not os.path.isfile(script):
        return f"red: skipped (no {RED_SCRIPT} in the commit's tree)"
    out = os.path.join(tmp, "red.json")
    cmd = ([sys.executable, script, "--root", tree, "--respond"] + [os.path.basename(d) for d in dirs]
           + ["--state-dir", os.path.join(top, LOG_REL), "--json", out])
    page_json = os.path.join(page_out, "regression.json") if page_out else None
    if page_json and os.path.isfile(page_json):
        cmd += ["--compare", page_json]
    if dry:
        cmd.append("--dry-run")
    try:
        p = subprocess.run(cmd, cwd=tree, capture_output=True, text=True, timeout=600,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        rc, text = p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        return "red: error (regression_watch.py ran past 600 s)"
    except OSError as e:
        return f"red: error (regression_watch.py did not start: {e})"
    for ln in text.splitlines():
        log(f"  red | {ln}")
    if rc == 2 or not os.path.isfile(out):
        return f"red: error (regression_watch.py exit {rc}: {short(text.splitlines()[-1] if text else '', 160)})"
    try:
        with open(out) as fh:
            doc = json.load(fh)
        cmp, resp = doc.get("compare"), doc.get("respond") or {}
    except (OSError, ValueError, AttributeError) as e:
        return f"red: error (its output unreadable: {e})"
    parts = []
    if cmp is not None:
        parts.append(f"page and bench agree ({cmp['red']['page']} red points)" if cmp["equal"] else
                     f"mismatch with the page's regression.json (red: bench {cmp['red']['bench']}, page "
                     f"{cmp['red']['page']}; " + ", ".join(f"{k} {v['bench']} / {v['page']}"
                                                          for k, v in cmp["counts"].items()) + ")")
    parts += resp.get("notes") or []
    return "red: " + "; ".join(parts) + (" (dry-run: nothing written)" if dry else "")


# ---------------------------------------------------------------- the switch

def ledger_commits(top, col):
    """The commits this step made before (a column of the ledger), so a push carries no other."""
    path = os.path.join(top, LOG_REL, LEDGER_NAME)
    if not os.path.exists(path):
        return set()
    with open(path) as fh:
        return {r.get(col) for r in csv.DictReader(fh, delimiter="\t") if r.get(col)}


def push(repo, sha, mine, on, what):
    """Push sha to origin main when the switch is on and every commit it adds to origin/main is
    one this step made (`mine`); off: what it would push. -> the ledger text."""
    if not sha:
        return "no commit to push"
    if on:
        rc, out = git(repo, "fetch", "-q", "origin", PUSH_BRANCH, timeout=300)
        if rc != 0:
            return f"push refused: fetch failed ({short(out, 120)})"
    old = rev(repo, f"refs/remotes/origin/{PUSH_BRANCH}")
    if not old:
        return f"{'push refused' if on else 'would push'}: no origin/{PUSH_BRANCH} to push onto"
    rc, out = git(repo, "rev-list", f"{old}..{sha}")
    adds = out.split() if rc == 0 else []
    others = [c for c in adds if c not in mine]
    rc_ff, _ = git(repo, "merge-base", "--is-ancestor", old, sha)
    span = (f"{old[:8]}..{sha[:8]} ({len(adds)} commit{'' if len(adds) == 1 else 's'}"
            + (f", {len(others)} not made by this step" if others else "") + ")")
    if not on:
        return f"would push {what} {span}" + ("" if rc_ff == 0 else " — not a fast-forward of origin/main")
    if rc_ff != 0:
        return f"push refused: origin/{PUSH_BRANCH} {old[:8]} is not an ancestor of {sha[:8]} (rebase first — a person)"
    if others:
        return f"push refused: {span} — a push would publish commits this step did not make (first {others[-1][:8]})"
    rc, out = git(repo, "push", "-q", "origin", f"{sha}:refs/heads/{PUSH_BRANCH}", timeout=600)
    return f"pushed {what} {span}" if rc == 0 else f"push failed: {short(out, 160)}"


def publish(repo, committed, on):
    """The page's publish script (tools/publish_gcs.sh) when the switch is on and this step
    committed the page; off: what it would publish."""
    index = os.path.join(repo, "dist", "index.html") if repo else None
    if not committed or not index or not os.path.isfile(index):
        return "nothing to publish (no page committed by this step)"
    with open(index, "rb") as fh:
        sha = hashlib.sha256(fh.read()).hexdigest()
    if not on:
        return f"would publish dist/index.html sha256 {sha}"
    script = os.path.join(repo, "tools", "publish_gcs.sh")
    try:
        p = subprocess.run(["bash", script], cwd=repo, capture_output=True, text=True, timeout=900)
        rc, out = p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        rc, out = 124, "timeout"
    for ln in out.strip().splitlines()[-5:]:
        log(f"publish | {ln}")
    return f"published dist/index.html sha256 {sha}" if rc == 0 else f"publish failed (exit {rc}): {short(out, 160)}"


# ---------------------------------------------------------------- ledger, lock

def write_ledger(top, row):
    d = os.path.join(top, LOG_REL)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, LEDGER_NAME)
    new = not os.path.exists(path)
    with open(path, "a") as fh:
        if new:
            fh.write("\t".join(LEDGER_COLS) + "\n")
        fh.write("\t".join(re.sub(r"[\t\r\n]+", " ", str(row.get(k) or "")) for k in LEDGER_COLS) + "\n")


def take_lock(top, timeout):
    """-> (open lock file, None) once this process holds logs/dashboard-job/.post.lock, or
    (None, the holder's pid) after `timeout` seconds."""
    d = os.path.join(top, LOG_REL)
    os.makedirs(d, exist_ok=True)
    fh = open(os.path.join(d, LOCK_NAME), "a+")
    t0 = time.time()
    while True:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except OSError:
            if time.time() - t0 >= timeout:
                fh.seek(0)
                holder = fh.read().strip() or "?"
                fh.close()
                return None, holder
            time.sleep(2)
    fh.seek(0)
    fh.truncate()
    fh.write(str(os.getpid()))
    fh.flush()
    return fh, None


# ---------------------------------------------------------------- one post

def post(top, dirs, sw, args, row, tmp):
    names = [os.path.basename(d) for d in dirs]
    notes = []
    changed, places, refused = scrub(top, dirs, args.user, args.dry_run)
    log(f"scrub: the account name -> USER in {changed} files ({places} places)"
        + (" [dry-run: not written]" if args.dry_run else "")
        + (f"; left as they were (not names-only): {', '.join(refused)}" if refused else ""))
    if changed:
        notes.append(f"scrub {changed} files" + (" (dry-run)" if args.dry_run else ""))
    check_user = args.user
    if args.dry_run and changed and not refused:
        # the scrub would rewrite every file the user-name rule reads (the same forms, the same
        # text files): read the dirs as it would leave them
        check_user = ""
        log("dry-run: the user-name rule is read as the scrub would leave the dirs")

    result = check(top, dirs, check_user, tmp)
    results = result["dirs"]
    waived = waive_subset(top, results, dirs) if args.allow_subset else []
    verdicts = {r["name"]: verdict_of(r) for r in results}
    row["check"] = " ".join(f"{n}={verdicts.get(n, '?')}" for n in names)
    for n, left, what in waived:
        log(f"--allow-subset: {n}: {left} ({what}) left out of this commit")
    held = [n for n in names if verdicts.get(n) != "PASS"]
    if held:
        rules = sorted({f["rule"] for r in results if r["name"] in held for f in r["findings"]
                        if not f.get("allowed_by") and not f.get("waived")})
        why = (f"{', '.join(f'{n} {verdicts.get(n)}' for n in held)} (rules: {', '.join(rules)}); "
               "a sitting is committed whole or not at all")
        notes.append("held: " + why)
        row["note"] = "; ".join(notes)
        if args.dry_run:
            log("would hold: " + why + " [dry-run: no REVIEW.md]")
        else:
            write_reviews(top, dirs, results, verdicts, why)
            log("held: " + why + f"; REVIEW.md in {len(dirs)} dirs")
        return 1

    def hold_git(why):
        notes.append("held: " + why)
        row["note"] = "; ".join(notes)
        if not args.dry_run:
            write_reviews(top, dirs, results, verdicts, why + " (every dir passed the checker)")
        log("held: " + why)
        return 1

    busy = git_busy(top)
    if busy:
        return hold_git(f"a {busy} is in progress in the checkout: post again when it is done")
    branch = branch_of(top)
    if not branch:
        return hold_git("HEAD is detached: the post commits onto a branch")
    if not args.dry_run:
        remove_reviews(top, dirs)

    for attempt in (1, 2, 3):
        head = rev(top, "HEAD")
        work = os.path.join(tmp, f"commit-{attempt}")
        os.makedirs(work)
        index, tree, lines_a, lines_b = build_tree(top, head, dirs, work)
        rc, _ = git(top, "diff", "--cached", "--quiet", head, index=index)
        if rc == 0:
            notes.append("nothing to commit: the dirs and the summary are in HEAD already")
            row["note"] = "; ".join(notes)
            log(notes[-1])
            return 0
        facts = sitting_facts(top, dirs)
        msg = commit_message(facts, lines_a, lines_b, waived)
        bad = REFUSED_WORDS.findall(msg)
        if bad:
            return hold_git(f"the generated message carries a word the commit-msg hook refuses ({bad[0]})")
        log("message: " + msg.strip())
        if args.dry_run:
            row["summary_lines"] = f"{lines_a} -> {lines_b}"
            page_step(sw, tree, args.page_out or os.path.join(top, PAGE_OUT_DEFAULT), row, True)
            notes.append(red_step(top, tree, None, dirs, True, work))
            log(notes[-1])
            for key in SWITCH_KEYS:
                row[key] = f"{'on' if sw[key] else 'off'} (dry-run)"
            row["note"] = "; ".join(notes + ["dry-run: nothing written"])
            return 0
        msg_file = os.path.join(work, "message.txt")
        with open(msg_file, "w") as fh:
            fh.write(msg)
        sha, why = commit_index(top, index, head, branch, msg_file, list(dirs) + [SUMMARY_REL])
        if sha:
            break
        if not why.startswith("moved:") or attempt == 3:
            return hold_git(f"not committed: {why}")
        log(f"HEAD moved while the summary was built ({why}); building again on the new HEAD")
    row["bench_commit"] = sha
    row["summary_lines"] = f"{lines_a} -> {lines_b}"
    copy_summary(tree, top)
    log(f"committed {sha[:8]} on {branch}: {len(dirs)} dirs + {SUMMARY_REL} ({lines_a} -> {lines_b} lines)")
    code = 0

    page_out = args.page_out or os.path.join(top, PAGE_OUT_DEFAULT)
    if not args.page_out and os.path.isdir(page_out):
        shutil.rmtree(page_out)
    os.makedirs(page_out, exist_ok=True)
    passed, checks, repo = page_step(sw, tree, page_out, row, False)
    page_sha = None
    numbers = None
    if repo and os.path.isfile(os.path.join(page_out, "cells.csv")):
        rc_old, old_cells = git(repo, "show", "HEAD:dist/cells.csv")
        with open(os.path.join(page_out, "cells.csv")) as fh:
            numbers = number_changes(old_cells, fh.read()) if rc_old == 0 else None
        if numbers:
            notes.append(f"page cells: {numbers}")
            log(notes[-1])
    if repo and not passed:
        code = 1
        notes.append("page: not committed (a check failed; the bench commit stands)")
    elif passed and args.no_page_commit:
        row["page_commit"] = ""
        notes.append(f"page: built and checked in {page_out}, not committed (--no-page-commit)")
    elif passed:
        page_sha, why = page_commit(repo, page_out,
                                    lambda old, new: page_message(sha, facts, old, new, checks[1:], numbers), tmp)
        row["page_commit"] = page_sha or ""
        if page_sha:
            log(f"page committed {page_sha[:8]} in {repo}")
        else:
            notes.append(f"page: not committed ({why})")
            log(f"page not committed: {why}")
            if not why.startswith("unchanged"):
                code = 1
    notes.append(red_step(top, tree, page_out if repo else None, dirs, False, tmp))
    log(notes[-1])
    row["push_bench"] = push(top, sha, ledger_commits(top, "bench_commit") | {sha}, sw["push_bench"], "bench")
    row["push_page"] = (push(repo, page_sha, ledger_commits(top, "page_commit") | {page_sha}, sw["push_page"], "page")
                        if page_sha else "no page commit to push")
    row["publish"] = publish(repo, bool(page_sha), sw["publish"])
    for key in SWITCH_KEYS:
        log(f"{key}: {row[key]}")
        if sw[key] and re.match(r"(push refused|push failed|publish failed)", row[key]):
            code = 1
    row["note"] = "; ".join(notes)
    return code


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dirs", nargs="+", help="the sitting's campaign dirs (results/raw/<campaign>)")
    ap.add_argument("--dry-run", action="store_true", help="write nothing; print the plan")
    ap.add_argument("--switch", help=f"the switch file (default: <checkout>/{SWITCH_REL})")
    ap.add_argument("--page-out", help=f"build the page here (an empty or new dir; default: "
                                       f"<checkout>/{PAGE_OUT_DEFAULT}, cleared for every build)")
    ap.add_argument("--no-page-commit", action="store_true",
                    help="build and check the page, commit nothing in the page repo")
    ap.add_argument("--allow-subset", action="store_true",
                    help="the dirs are part of a sitting: its other dirs stay out of this commit and "
                         "the message names them")
    ap.add_argument("--user", default=getpass.getuser(),
                    help="the account name the scrub replaces and the checker looks for (default: this account)")
    ap.add_argument("--lock-timeout", type=float, default=1800,
                    help="seconds to wait for another post to finish (default 1800)")
    args = ap.parse_args(argv)
    started = now_text()
    try:
        top, dirs = resolve(args.dirs)
        sw = load_switch(args.switch or os.path.join(top, SWITCH_REL))
        if args.page_out:
            args.page_out = os.path.realpath(args.page_out)
            if os.path.exists(args.page_out) and (not os.path.isdir(args.page_out) or os.listdir(args.page_out)):
                raise Usage(f"--page-out must be an empty or new directory: {args.page_out}")
    except Usage as e:
        print(f"dashboard_post: {e}", file=sys.stderr)
        return 2
    row = {"started": started, "dirs": " ".join(os.path.basename(d) for d in dirs)}
    log(f"{len(dirs)} dirs in {top}: {row['dirs']}"
        + "; switch " + ", ".join(f"{k} {'on' if sw[k] else 'off'}" for k in SWITCH_KEYS)
        + f", page repo {sw['page_repo'] or 'none'}" + (" [dry-run]" if args.dry_run else ""))
    lock = None
    if not args.dry_run:
        lock, holder = take_lock(top, args.lock_timeout)
        if lock is None:
            row.update(ended=now_text(), note=f"busy: another post holds {LOG_REL}/{LOCK_NAME} (pid {holder})")
            write_ledger(top, row)
            log(row["note"])
            return 1
    tmp = tempfile.mkdtemp(prefix="dashboard-post-")
    try:
        code = post(top, dirs, sw, args, row, tmp)
    except Usage as e:
        row["note"] = (row.get("note", "") + f"; usage: {e}").strip("; ")
        log(str(e))
        code = 2
    except Exception as e:  # noqa: BLE001 — the ledger line must say what stopped the post
        row["note"] = (row.get("note", "") + f"; error: {type(e).__name__}: {short(str(e), 200)}").strip("; ")
        log("error:\n" + traceback.format_exc())
        code = 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    row["ended"] = now_text()
    if not args.dry_run:
        write_ledger(top, row)
        lock.close()
    log(f"exit {code}" + (f": committed {row['bench_commit'][:8]}" if row.get("bench_commit") else "")
        + (f"; {row['note']}" if row.get("note") else ""))
    return code


if __name__ == "__main__":
    sys.exit(main())
