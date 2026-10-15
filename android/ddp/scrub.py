#!/usr/bin/env python3
"""The lab network's identifiers out of the logcats a DDP job pulls (D12; design:
results/raw/2026-10-15-ddp-backend-dev/LANE.md §1). android/ddp/run_ddp.py runs it on every
pulled logcat (the per-run run<i>_logcat.txt files and the execution's logcat.txt) right after
the pull, keeps the original bytes in <campaign>/ddp-raw/ (gitignored) and the counts in
<campaign>/ddp/scrub.json. No number is read from a logcat (android/ddp/record.py reads
run<i>.log, run<i>.state and provenance.txt), so a replacement never touches a measurement.

  ./android/ddp/scrub.py --raw-dir <dir> <file>...   # each original copied to <dir>/<file name> first

Rules, in this order (each a count key; the line count and every byte outside a replaced span kept):
  ssid      a Wi-Fi SSID: the value of SSID: "…", ssid():"…", ssid="…" or ssid=… (unquoted), and every
            other occurrence of such a value of 3+ characters (the value as seen in the text or passed in
            from the session's other logcats) -> <lab-ssid>
  hash      on a line naming an ssid / bssid: a 64-hex run, and a 20+-hex run right after the word
            (Samsung MobileWips: "[ssid: <sha-256>, bssid: <sha-256>") -> <hash>
  ip6       a global (2xxx: / 3xxx:), unique-local (fcxx: / fdxx:) or link-local (fe80:) IPv6 address
            (::1 and :: kept) -> <ip6>
  mac       a six-pair MAC, Samsung's star-masked aa:bb:cc:**:**:ff included (Android's
            02:00:00:00:00:00 and 00:00:00:00:00:00 kept) -> <mac>
  mac-part  Samsung's three-octet BSSID part after pBssid: / bssid: -> <mac-part>
  ip        a private IPv4 address (10/8, 172.16/12, 192.168/16) -> <ip>
  id        on a line naming an iccid / imei / imsi: a run of 10+ digits -> <id>
A file's original is copied once and never overwritten: a second scrub of the same file reads the
copy, so the result and the counts stay those of the original bytes.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys

KINDS = ("ssid", "hash", "ip6", "mac", "mac-part", "ip", "id")
SSID_MIN_LITERAL = 3
KEEP_MAC = {"02:00:00:00:00:00", "00:00:00:00:00:00"}

# SSID values: quoted after ssid / ssid() and : or =; unquoted after ssid=. (?<!b): not a BSSID.
SSID_QUOTED = re.compile(r'(?i)(?<!b)(ssid(?:\(\))?[ \t]*[:=][ \t]*")([^"\n]*)(")')
SSID_BARE = re.compile(r'(?i)(?<!b)(ssid=)(?!")([^\s,;)\]}"]+)')
SSID_LINE = re.compile(r"(?im)^[^\n]*ssid[^\n]*$")
HEX64 = re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{64}(?![0-9A-Fa-f])")
HASH_AFTER = re.compile(r"(?i)(ssid[ \t]*[:=][ \t]*)[0-9a-f]{20,}")
IP6 = re.compile(r"(?<![0-9A-Fa-f:])(?:[23][0-9A-Fa-f]{3}|[Ff][CcDd][0-9A-Fa-f]{2}|[Ff][Ee]80):[0-9A-Fa-f:]{3,}")
MAC = re.compile(r"(?<![0-9A-Fa-f*])([0-9A-Fa-f*]{2}(?::[0-9A-Fa-f*]{2}){5})(?![0-9A-Fa-f*])")
MAC_PART = re.compile(r"(?i)(bssid:[ \t]?)[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}(?![0-9a-f:])")
IP4 = re.compile(r"(?<![0-9.])(?:10\.[0-9]{1,3}|172\.(?:1[6-9]|2[0-9]|3[01])|192\.168)\.[0-9]{1,3}\.[0-9]{1,3}(?![0-9.])")
ID_LINE = re.compile(r"(?im)^[^\n]*(?:iccid|imei|imsi)[^\n]*$")
DIGITS10 = re.compile(r"(?<![0-9])[0-9]{10,}(?![0-9])")


def _is_value(value):
    """An SSID value worth replacing: not empty, not a placeholder (<unknown ssid>, our own <lab-ssid>,
    null) and holding a letter or digit."""
    v = value.strip()
    return bool(v) and not v.startswith("<") and v.lower() not in ("null", "none") \
        and re.search(r"[A-Za-z0-9]", v) is not None


def ssid_values(text):
    """The SSID values a text names (quoted or after ssid=), placeholders left out."""
    found = {m.group(2) for m in SSID_QUOTED.finditer(text)} | {m.group(2) for m in SSID_BARE.finditer(text)}
    return {v for v in found if _is_value(v)}


def scrub_text(text, ssids=()):
    """-> (text with the lab network's identifiers replaced, {kind: replacements}); ssids = SSID values
    seen in the session's other logcats, replaced here too."""
    counts = dict.fromkeys(KINDS, 0)
    lines_before = text.count("\n")
    values = ssid_values(text) | {v for v in ssids if _is_value(v)}
    for v in sorted((v for v in values if len(v) >= SSID_MIN_LITERAL), key=lambda s: (-len(s), s)):
        n = text.count(v)
        if n:
            text = text.replace(v, "<lab-ssid>")
            counts["ssid"] += n

    def short_value(m):
        if not _is_value(m.group(2)):
            return m.group(0)
        counts["ssid"] += 1
        return m.group(1) + "<lab-ssid>" + (m.group(3) if m.lastindex >= 3 else "")
    text = SSID_QUOTED.sub(short_value, text)
    text = SSID_BARE.sub(short_value, text)

    def hash_line(m):
        line, n = HEX64.subn("<hash>", m.group(0))
        line, k = HASH_AFTER.subn(lambda h: h.group(1) + "<hash>", line)
        counts["hash"] += n + k
        return line
    text = SSID_LINE.sub(hash_line, text)
    text, counts["ip6"] = IP6.subn("<ip6>", text)

    def mac(m):
        value = m.group(1)
        if value.lower() in KEEP_MAC or not re.search(r"[0-9A-Fa-f]", value):
            return value
        counts["mac"] += 1
        return "<mac>"
    text = MAC.sub(mac, text)
    text, counts["mac-part"] = MAC_PART.subn(lambda m: m.group(1) + "<mac-part>", text)
    text, counts["ip"] = IP4.subn("<ip>", text)

    def id_line(m):
        line, n = DIGITS10.subn("<id>", m.group(0))
        counts["id"] += n
        return line
    text = ID_LINE.sub(id_line, text)
    if text.count("\n") != lines_before:
        raise RuntimeError("scrub changed the line count")
    return text, counts


def _decode(data):
    return data.decode("utf-8", "surrogateescape")


def original_of(path, raw_dir):
    """The original bytes of a file: its copy in raw_dir when one exists, else the file."""
    raw = os.path.join(raw_dir, os.path.basename(path))
    with open(raw if os.path.isfile(raw) else path, "rb") as fh:
        return fh.read()


def original_text(path, raw_dir):
    return _decode(original_of(path, raw_dir))


def scrub_file(path, raw_dir, ssids=()):
    """Copy the file's original bytes to raw_dir/<file name> (once: an existing copy is never
    overwritten), write the scrub of the original over the file. -> {kind: replacements}."""
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    raw = os.path.join(raw_dir, os.path.basename(path))
    if os.path.realpath(raw) == os.path.realpath(path):
        raise ValueError(f"{path}: the raw dir is the file's own directory")
    if not os.path.isfile(raw):
        os.makedirs(raw_dir, exist_ok=True)
        shutil.copy2(path, raw)
    with open(raw, "rb") as fh:
        text, counts = scrub_text(_decode(fh.read()), ssids)
    data = text.encode("utf-8", "surrogateescape")
    with open(path, "rb") as fh:
        same = fh.read() == data
    if not same:
        tmp = path + ".scrub-tmp"
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    return counts


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw-dir", required=True, help="where each file's original goes (<dir>/<file name>)")
    ap.add_argument("files", nargs="+")
    args = ap.parse_args(argv)
    names = [os.path.basename(f) for f in args.files]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        ap.error(f"two files named {', '.join(dupes)} would share one copy in --raw-dir: one call per directory")
    missing = [f for f in args.files if not os.path.isfile(f)]
    if missing:
        ap.error(f"not a file: {', '.join(missing)}")
    ssids = set()
    for f in args.files:
        ssids |= ssid_values(original_text(f, args.raw_dir))
    for f in args.files:
        counts = scrub_file(f, args.raw_dir, ssids)
        raw = os.path.join(args.raw_dir, os.path.basename(f))
        print(json.dumps({"file": f, "raw": raw, "rawSha256": sha256_of(raw), "counts": counts,
                          "replaced": sum(counts.values())}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
