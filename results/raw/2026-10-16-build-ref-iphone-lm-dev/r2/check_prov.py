#!/usr/bin/env python3
"""K/r2/check_prov.py <label> <campaign dir>... — round 2's record check (read only; the report is
K/r2/record-check.txt). Per DDP campaign dir: the sha256 lines of each execution's provenance.txt (what
android/ddp/ddp_cell.sh read on the unit) against android/engine-pins.json litert-lm.<label> (both tools
and so_files: 9 files), the model and prompt lines; then the session report (state, job and execution
results and times), every record of app-path-android/ (engineVersion, engineArtifact, conditions.ddp ids,
decode / prompt rates, peak resident MB, protocolFlags, engineCache.gpuCache, exitCode, ddpMissing),
FAILURES.txt, and the reply text of each run (ddp-out/run<i>.engine.txt between the input_prompt line and
BenchmarkInfo: empty / on-topic / garbled, the first 80 characters)."""
import datetime
import glob
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
DEV_DIR = "/data/local/tmp/llmbench"
SHA = re.compile(r"^([0-9a-f]{64})\s+(\S+)$")
# a reply about the prompt ("Explain what on-device AI means in simple terms.") names at least one of these
TOPIC = ("on-device", "device", "ai", "artificial intelligence", "phone", "local", "privacy", "cloud", "internet")


def rel(path):
    return os.path.relpath(path, ROOT)


def seconds(start, end):
    if not start or not end:
        return None
    a = datetime.datetime.fromisoformat(start.replace("Z", "+00:00"))
    b = datetime.datetime.fromisoformat(end.replace("Z", "+00:00"))
    return round((b - a).total_seconds(), 3)


def reply(path):
    """(verdict, text) of one run's engine output: the lines after 'input_prompt:' up to 'BenchmarkInfo:'."""
    if not os.path.isfile(path):
        return "missing", ""
    lines = open(path, errors="replace").read().splitlines()
    start = next((i for i, l in enumerate(lines) if l.startswith("input_prompt:")), None)
    end = next((i for i, l in enumerate(lines) if l.startswith("BenchmarkInfo:")), len(lines))
    if start is None:
        return "no input_prompt line", ""
    text = "\n".join(l for l in lines[start + 1:end]
                     if not re.match(r"^(INFO|WARNING|ERROR|VERBOSE|DEBUG): |^[IWEF][0-9]{4} ", l)).strip()
    if not text:
        return "empty", text
    words = re.findall(r"[A-Za-z]+", text)
    letters = sum(c.isalpha() for c in text)
    low = text.lower()
    if len(words) < 5 or letters < 0.5 * len(text.replace(" ", "").replace("\n", "")):
        return "garbled", text
    return ("on-topic" if any(re.search(r"\b" + re.escape(t) + r"\b", low) for t in TOPIC) else "off-topic"), text


def main(label, dirs):
    pins = json.load(open(os.path.join(ROOT, "android", "engine-pins.json")))
    entry = pins["litert-lm"][label]
    want = {"litert_lm_main": entry["litert_lm_main_sha256"],
            "litert_lm_advanced_main": entry["litert_lm_advanced_main_sha256"], **entry["so_files"]}
    print(f"label {label}: pins entry {len(want)} files; litert_lm_main_sha256 {entry['litert_lm_main_sha256']}")
    bad = 0
    for d in dirs:
        d = os.path.abspath(d)
        print(f"\n=== {rel(d)}")
        for n in sorted(glob.glob(os.path.join(d, "ddp", "session-[0-9]*.json"))):
            s = json.load(open(n))
            rep = s.get("sessionReport", {})
            print(f"session {s.get('name', '').rsplit('/', 1)[-1]}: status {rep.get('status')} result "
                  f"{(rep.get('result') or {}).get('resultType')} "
                  f"session {seconds(rep.get('startTime'), rep.get('endTime'))} s")
            for jr in rep.get("jobReports", []):
                print(f"  job {jr.get('displayName')} {jr.get('id')}: {(jr.get('result') or {}).get('resultType')} "
                      f"{seconds(jr.get('startTime'), jr.get('endTime'))} s")
                for ex in jr.get("executionReports", []):
                    print(f"    execution {ex.get('id')}: {(ex.get('result') or {}).get('resultType')} "
                          f"{seconds(ex.get('startTime'), ex.get('endTime'))} s")
        provs = sorted(glob.glob(os.path.join(d, "ddp", "session-*", "*", "*", "artifacts", DEV_DIR.lstrip("/"),
                                              "ddp-out", "provenance.txt")))
        if not provs:
            print("no provenance.txt"); bad += 1
        for p in provs:
            shas = {}
            for line in open(p, errors="replace"):
                m = SHA.match(line.strip())
                if m:
                    shas[m.group(2)] = m.group(1)
            props = dict(l.split(": ", 1) for l in open(p, errors="replace").read().splitlines()
                         if l.startswith("ro.") and ": " in l)
            print(f"provenance {rel(p)}")
            print(f"  unit: {props.get('ro.product.model')} serial {props.get('ro.serialno')} "
                  f"fingerprint {props.get('ro.build.fingerprint')}")
            same = 0
            for name in ["litert_lm_main", "litert_lm_advanced_main"] + sorted(entry["so_files"]):
                got = shas.get(f"{DEV_DIR}/{name}")
                ok = got == want[name]
                same += ok
                bad += not ok
                print(f"  {'OK      ' if ok else 'MISMATCH'} {name} unit {got} pins {want[name]}")
            others = sorted(k for k in shas if os.path.dirname(k) == DEV_DIR and os.path.basename(k) not in want)
            print(f"  {same}/{len(want)} engine files = pins entry {label}; other engine-dir files on the unit: "
                  f"{others or 'none'}")
            for k in sorted(shas):
                if os.path.dirname(k) != DEV_DIR:
                    print(f"  {shas[k]}  {k}")
        out = os.path.join(d, "app-path-android")
        recs = sorted(glob.glob(os.path.join(out, "*_run[0-9]*.json")))
        print(f"records: {len(recs)}; FAILURES.txt: {'present' if os.path.exists(os.path.join(out, 'FAILURES.txt')) else 'absent'}")
        for r_path in recs:
            r = json.load(open(r_path))
            c, m = r["conditions"], r["metrics"]
            ddp = c.get("ddp") or {}
            ids = {k: ddp.get(k) for k in ("sessionId", "jobId", "executionId", "serial", "buildFingerprint")}
            # the launched tool (short-chat: litert_lm_main) = the first word of the engine command
            tool = os.path.basename((c.get("engineCommand") or "./litert_lm_main").split()[0])
            checks = {"engineVersion": r.get("engineVersion") == label,
                      "engineArtifact": r.get("engineArtifact") == entry.get(f"{tool}_sha256"),
                      "ddp ids": all(ids.values()),
                      "decode": isinstance(m.get("decodeTokensPerSecond"), (int, float))}
            bad += not all(checks.values())
            print(f"{os.path.basename(r_path)}")
            print(f"  checks {' '.join(k + '=' + ('OK' if v else 'FAIL') for k, v in checks.items())}")
            print(f"  engineVersion {r.get('engineVersion')} engineArtifact {r.get('engineArtifact')}")
            print(f"  ddp {json.dumps(ids)} runIndex {ddp.get('runIndex')} resultType {ddp.get('resultType')}")
            print(f"  decode {m.get('decodeTokensPerSecond')} prompt(prefill) {m.get('promptTokensPerSecond')} "
                  f"ttft_ms {m.get('firstTokenLatencyMS')} prompt_tokens {m.get('promptTokenCount')} "
                  f"generated {m.get('generatedTokenCount')} peakMB {m.get('memoryPeakResidentMB')} "
                  f"firstEver {m.get('firstEver')}")
            print(f"  exitCode {c.get('exitCode')} protocolFlags {c.get('protocolFlags')} "
                  f"invalidDecodeCount {c.get('invalidDecodeCount')} engineCache {c.get('engineCache')} "
                  f"thermal {c.get('thermalRawStatus')}->{c.get('thermalRawStatusFinal')} "
                  f"elapsed {c.get('elapsedSeconds')} s")
            print(f"  cpuMaxFreqMHz {json.dumps(c.get('cpuMaxFreqMHz'))} ddpMissing "
                  f"{r.get('provenance', {}).get('ddpMissing')}")
            run = ddp.get("runIndex")
            eng = os.path.join(d, r["provenance"]["ddpSessionDir"], "artifacts", DEV_DIR.lstrip("/"), "ddp-out",
                               f"run{run}.engine.txt")
            verdict, text = reply(eng)
            bad += verdict != "on-topic"
            flat = " ".join(text.split())
            print(f"  reply run{run}: {verdict}, {len(text)} chars: {flat[:80]!r}")
    print(f"\n{'ALL OK' if not bad else f'{bad} check(s) not OK'}")
    return 1 if bad else 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2:]))
