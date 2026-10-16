#!/usr/bin/env python3
"""Counts identifier shapes in lab files without printing any value:
python3 -I labids.py <file>...  -> per file: kind, matches, distinct values, lines.
Kinds: MAC (six pairs; star-masked), IPv6 (full and :: forms), IPv4 private (10/8, 172.16/12,
192.168/16, 169.254/16, 100.64/10), IPv4 other, e-mail, UDID (40 hex; 8-16 hex), UUID (8-4-4-4-12),
and keyword lines (SSID, BSSID, serial, UDID, hostname, ECID, IMEI, MEID, ICCID, phone number,
Wi-Fi, Apple ID, DeviceName, .local)."""
import ipaddress
import re
import sys

PATTERNS = {
    "MAC (six pairs)": re.compile(r"(?<![0-9A-Fa-f:])(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}(?![0-9A-Fa-f:])"),
    "MAC (star-masked)": re.compile(r"(?:[0-9A-Fa-f*]{2}:){5}[0-9A-Fa-f*]{2}"),
    "IPv6 (full)": re.compile(r"(?<![0-9A-Fa-f:])(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}(?![0-9A-Fa-f:])"),
    "IPv6 (:: form)": re.compile(r"(?<![0-9A-Fa-f:])(?:[0-9A-Fa-f]{1,4}:){1,6}:(?:[0-9A-Fa-f]{1,4}(?::[0-9A-Fa-f]{1,4}){0,5})?(?![0-9A-Fa-f:])"),
    "e-mail": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"),
    "UDID (40 hex)": re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{40}(?![0-9A-Fa-f])"),
    "UDID (8-16 hex)": re.compile(r"(?<![0-9A-Fa-f-])[0-9A-Fa-f]{8}-[0-9A-Fa-f]{16}(?![0-9A-Fa-f-])"),
    "UUID (8-4-4-4-12)": re.compile(r"(?<![0-9A-Fa-f-])[0-9A-Fa-f]{8}-(?:[0-9A-Fa-f]{4}-){3}[0-9A-Fa-f]{12}(?![0-9A-Fa-f-])"),
}
IPV4 = re.compile(r"(?<![0-9.])(?:\d{1,3}\.){3}\d{1,3}(?![0-9.])")
KEYWORDS = ["SSID", "BSSID", "serial", "UDID", "hostname", "ECID", "IMEI", "MEID", "ICCID", "phone number",
            "Wi-Fi", "WiFi", "Apple ID", "AppleID", "DeviceName", "device name", ".local"]
PRIVATE = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
                                             "169.254.0.0/16", "100.64.0.0/10")]

for path in sys.argv[1:]:
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except OSError as exc:
        print(f"{path}: unreadable ({exc.__class__.__name__})")
        continue
    lines = text.splitlines()
    print(f"## {path.rsplit('/', 1)[-1]}: {len(lines)} lines, {len(text)} chars")
    for kind, rx in PATTERNS.items():
        hits = rx.findall(text)
        if kind == "MAC (star-masked)":
            hits = [h for h in hits if "*" in h]
        nlines = sum(1 for l in lines if rx.search(l))
        print(f"{kind}: {len(hits)} matches, {len(set(hits))} distinct, {nlines} lines")
    priv, other, loop = [], [], []
    for h in IPV4.findall(text):
        try:
            ip = ipaddress.ip_address(h)
        except ValueError:
            continue  # version strings such as 1.2.3.400
        if ip.is_loopback or str(ip) == "0.0.0.0":
            loop.append(h)
        elif any(ip in n for n in PRIVATE):
            priv.append(h)
        else:
            other.append(h)
    print(f"IPv4 private (10/8, 172.16/12, 192.168/16, 169.254/16, 100.64/10): {len(priv)} matches, {len(set(priv))} distinct")
    print(f"IPv4 other (public or a dotted version string; not split): {len(other)} matches, {len(set(other))} distinct")
    print(f"IPv4 loopback / 0.0.0.0: {len(loop)} matches")
    for kw in KEYWORDS:
        n = sum(1 for l in lines if kw.lower() in l.lower())
        if n:
            print(f"keyword '{kw}': {n} lines")
