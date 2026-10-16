#!/usr/bin/env python3
"""Register a LiteRT-LM Android build in android/engine-pins.json: the sha256 of its two tools and of
every .so beside them, as the "litert-lm" entry <label>.

  android/scripts/pins_add.py <label> <dir> [--pins <path>] [--requested <text>] [--observed <text>]
                              [--note <text>] [--dry-run] [--replace]

<dir> holds litert_lm_main, litert_lm_advanced_main and the GPU .so files flat: the layout
android/scripts/build_litert_lm_main.sh writes to android/bin/<label>/ (it calls this script), and the
one `bench matrix --ddp <id> --engine-build <label>` reads from <BENCH_ANDROID_BIN_DIR>/<label>/. The
entry has the keys of the other litert-lm entries: requested_tag and observed (default: the label),
litert_lm_main_sha256, litert_lm_advanced_main_sha256, so_files (every *.so directly in <dir>, by name;
subdirectories are not read) and built (--note; default "android/scripts/pins_add.py <date> from <dir name>").

Refused with exit 2, the reason on stderr and nothing written: a label outside
^[A-Za-z0-9][A-Za-z0-9._-]*$; a missing tool (named); no .so file; a git-lfs pointer in place of a
binary (named: the source checkout's prebuilt/android_arm64/*.so are LFS objects); an entry of that
label already in the file without --replace; a pins file that json.dump(indent=2) would not write back
as it is. --dry-run prints {label: entry} as JSON and writes nothing (what a write would meet in --pins
goes to stderr). A write sets litert-lm[<label>] and keeps every other key byte for byte, the file's
ending included: android_pins is never changed here (a pin bump is a person's decision,
docs/OPERATIONS.md).
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PINS = os.path.join(ROOT, "android", "engine-pins.json")
LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
TOOLS = ("litert_lm_main", "litert_lm_advanced_main")
LFS_POINTER = b"version https://git-lfs"


class Refused(Exception):
    pass


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_lfs_pointer(path):
    with open(path, "rb") as fh:
        return fh.read(len(LFS_POINTER)) == LFS_POINTER


def build_entry(label, build_dir, requested=None, observed=None, note=None):
    """The litert-lm entry of build_dir; Refused naming every problem of the directory."""
    if not os.path.isdir(build_dir):
        raise Refused(f"{build_dir}: not a directory")
    missing = [t for t in TOOLS if not os.path.isfile(os.path.join(build_dir, t))]
    libs = sorted(f for f in os.listdir(build_dir)
                  if f.endswith(".so") and os.path.isfile(os.path.join(build_dir, f)))
    problems = []
    if missing:
        problems.append("no " + " and no ".join(missing))
    if not libs:
        problems.append("no .so file")
    pointers = [f for f in [t for t in TOOLS if t not in missing] + libs
                if is_lfs_pointer(os.path.join(build_dir, f))]
    if pointers:
        problems.append("git-lfs pointer file in place of the binary: " + ", ".join(pointers)
                        + " (git lfs install, then git lfs pull in the source checkout)")
    if problems:
        raise Refused(f"{build_dir}: " + "; ".join(problems)
                      + " (a build dir holds litert_lm_main, litert_lm_advanced_main and the GPU .so files flat)")
    shas = {f: sha256_file(os.path.join(build_dir, f)) for f in list(TOOLS) + libs}
    return {"requested_tag": requested or label, "observed": observed or label,
            "litert_lm_main_sha256": shas["litert_lm_main"],
            "litert_lm_advanced_main_sha256": shas["litert_lm_advanced_main"],
            "so_files": {f: shas[f] for f in libs},
            "built": note or (f"android/scripts/pins_add.py {datetime.date.today().isoformat()} "
                              f"from {os.path.basename(os.path.normpath(build_dir))}")}


def load(path):
    """(pins, text) of a registry that json.dump(indent=2) writes back as it is."""
    if not os.path.isfile(path):
        raise Refused(f"{path}: {'not a regular file' if os.path.exists(path) else 'no such pins file'}")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    try:
        pins = json.loads(text)
    except ValueError as exc:
        raise Refused(f"{path}: not JSON ({exc})")
    if not isinstance(pins, dict) or not isinstance(pins.get("litert-lm", {}), dict):
        raise Refused(f"{path}: not a pins registry (an object with a litert-lm object)")
    if json.dumps(pins, indent=2) != (text[:-1] if text.endswith("\n") else text):
        raise Refused(f"{path}: json.dump(indent=2) would not write the file back as it is, so a write "
                      "would change other entries too")
    return pins, text


def same_tools(lm, label, entry):
    """Warnings for another entry whose tool sha256 equals this one's: the witness
    (android/ddp/record.witness, run_cell.observed_engine) stamps the first entry that matches."""
    for other, e in lm.items():
        if other != label and isinstance(e, dict):
            same = [t for t in TOOLS if e.get(f"{t}_sha256") == entry[f"{t}_sha256"]]
            if same:
                print(f"pins_add: warning: {' and '.join(same)} of {label} = litert-lm {other}'s; the witness "
                      "stamps the first entry whose tool sha256 matches", file=sys.stderr)


def dry_run_note(pins_path, label, entry):
    """--dry-run: what a write would meet in --pins (read only; an unreadable path is said and skipped)."""
    try:
        pins, _ = load(pins_path)
    except (Refused, OSError, UnicodeDecodeError) as exc:
        print(f"pins_add: --dry-run: {pins_path} not read ({exc})", file=sys.stderr)
        return
    lm = pins.get("litert-lm", {})
    old = lm.get(label)
    if old is None:
        print(f"pins_add: --dry-run: {pins_path} has no litert-lm {label}; a write adds it", file=sys.stderr)
    else:
        old_libs = old.get("so_files") or {}
        diff = [k for k in ("litert_lm_main_sha256", "litert_lm_advanced_main_sha256") if old.get(k) != entry[k]]
        diff += [f"so_files {n}" for n in sorted(set(old_libs) | set(entry["so_files"]))
                 if old_libs.get(n) != entry["so_files"].get(n)]
        same = f"the same sha256 for all {len(TOOLS) + len(entry['so_files'])} files"
        print(f"pins_add: --dry-run: {pins_path} has litert-lm {label} already "
              f"({'differs: ' + ', '.join(diff) if diff else same}); a write needs --replace", file=sys.stderr)
    same_tools(lm, label, entry)


def write(pins_path, label, entry, replace):
    pins, text = load(pins_path)
    lm = pins.setdefault("litert-lm", {})
    old = lm.get(label)
    if old is not None and not replace:
        raise Refused(f"{pins_path} already has litert-lm {label} (--replace writes it again)")
    same_tools(lm, label, entry)
    lm[label] = entry
    tmp = f"{pins_path}.pins_add.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(pins, indent=2) + ("\n" if text.endswith("\n") else ""))
    shutil.copymode(pins_path, tmp)
    os.replace(tmp, pins_path)
    print(f"pins: {label} {'replaced' if old is not None else 'added'} ({len(entry['so_files'])} so files)")
    gone = [k for k in (old or {}) if k not in entry]
    if gone:
        print(f"pins_add: the old {label} entry's {', '.join(gone)} are not in the new one", file=sys.stderr)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("label", help="the entry's key: a tag, main-<sha9>, pr<N>-<sha9>, <branch>-<sha9>, ...")
    ap.add_argument("dir", help="the build directory: litert_lm_main, litert_lm_advanced_main, *.so")
    ap.add_argument("--pins", default=PINS, help="the registry to write (default: android/engine-pins.json)")
    ap.add_argument("--requested", help="requested_tag: the tag or git ref asked for (default: the label)")
    ap.add_argument("--observed", help="observed: git describe --tags --always of the source (default: the label)")
    ap.add_argument("--note", help="built: how the build was made (default: this script, the date, the dir name)")
    ap.add_argument("--dry-run", action="store_true", help="print the entry as JSON; write nothing")
    ap.add_argument("--replace", action="store_true", help="write over an entry of the same label")
    args = ap.parse_args(argv)
    try:
        if not LABEL.fullmatch(args.label):
            raise Refused(f"label {args.label!r} is not of the form ^[A-Za-z0-9][A-Za-z0-9._-]*$")
        entry = build_entry(args.label, args.dir, args.requested, args.observed, args.note)
        if args.dry_run:
            print(json.dumps({args.label: entry}, indent=2), flush=True)
            dry_run_note(args.pins, args.label, entry)
            return 0
        write(args.pins, args.label, entry, args.replace)
    except Refused as exc:
        print(f"pins_add: {exc} — nothing written", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"pins_add: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
