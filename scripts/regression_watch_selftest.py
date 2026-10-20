#!/usr/bin/env python3
"""Device- and network-free selftest of scripts/regression_watch.py and the job's retake sitting (CI).

A temp bench tree (cells files, schedule.json, SESSION.json files, a synthetic
results/summary/device-runs.csv) and its own definitions file stand in for the page's constants.
Pins:

  (a) the red points: the threshold on both sides (-4.9 % is not red, -5.05 % is), decode compared
      within its regime only (a protocol cell's cold sitting is never the warm one's previous
      point), one point a day (the day's newest sitting shown, the other hidden and never red),
      engine_changed, a lower-is-better metric as a rate, a lab unit's stand-in rows, a sitting
      SESSION.json refused and a campaign that is not a weekly sitting all left out; --compare
      exit 0 on the same red set and 1 with the difference named; the prompt version cuts a series
      as the regime does (a -20 % first point on a new task text is not compared, prompt_changed,
      listed "prompt none -> <version>"; the next point compares within the version and can be red;
      a retake on another version than its previous point is not judged)
  (b) a red point that is its cell's newest sitting -> one pending retake whose row is the cells
      file's line byte for byte; the same sitting again adds none; a red point a newer sitting has
      replaced adds none; the job's close marks it done (exit 0) or counts the attempt (abandoned
      after two); a pending retake past seven days expires
  (c) the job: auto takes a device whose weekly set is done when a retake of it is pending, and
      it goes before a device whose weekly set is pending; a retake sitting is not the week's
      session; a dry-run sitting prints the retake's bench matrix line (campaign …-retake-<slug>)
      before the weekly set's, over a generated cells file (the platform's anchor rows, then the
      retake row byte for byte), the profile pair for an android native-benchmark row; no pending
      retake, no retake line (fake adb, as dashboard_job_selftest.py)
  (d) a retake still red against the red point's own previous point on another engine -> one
      bisect request (route ddp:m1q-36 for the Galaxy S26, none for the Mac; the command only when
      scripts/engine_bisect.py is in the tree); on a later UTC day than the red point too; the same
      engine, or a retake back within the line, -> no request
  (e) the draft beside a request: EN and JA, the numbers and the row, no refused word

  python3 scripts/regression_watch_selftest.py     # exit 0 = pass
"""
import argparse
import contextlib
import csv
import datetime
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import regression_watch as rw  # noqa: E402

_fails = []

COLUMNS = ["source", "campaign", "platform", "timestamp", "runtime", "schema_version", "engine_version",
           "engine_artifact", "model_id", "quantization", "task", "prompt_version", "harness_stamp", "decode_tps",
           "decode_tps_wall",
           "prefill_tps", "prompt_tokens", "gen_tokens", "ttft_ms", "mem_footprint_median_mb",
           "mem_resident_median_mb", "energy_j_per_tok", "thermal_initial", "thermal_final", "battery_state",
           "cold_run", "first_ever", "context_tokens", "device", "os_version", "mem_footprint_peak_mb",
           "mem_resident_peak_mb", "text_check", "cpu_capped", "cpu_max_freq", "backend_registered",
           "cpu_cap_drop_pct"]
GEMMA, QWEN = "litert-community/gemma-4-E2B-it-litert-lm", "litert-community/Qwen3-0.6B"
# the text file's rows; the CPU row with doubled spaces and a comment, to pin "byte for byte"
CPU_ROW = ("android litert-lm  litert-community/gemma-4-E2B-it-litert-lm short-chat backend=cpu  cooldown=300 "
           "file=gemma-4-E2B-it.litertlm   # the E2B CPU row")
TEXT_CELLS = "\n".join([
    "# selftest text rows",
    "android llama.cpp unsloth/Qwen3-0.6B-GGUF short-chat anchor=1 runs=3 file=Qwen3-0.6B-Q4_K_M.gguf",
    CPU_ROW,
    "android litert-lm litert-community/gemma-4-E2B-it-litert-lm short-chat backend=gpu cooldown=300 "
    "file=gemma-4-E2B-it.litertlm",
    "mac litert-lm litert-community/Qwen3-0.6B short-chat",
]) + "\n"
PROTO_ROW = ("android litert-lm litert-community/Qwen3-0.6B native-benchmark-1024x256 backend=gpu "
             "file=qwen3_0_6b_mixed_int4.litertlm context-tokens=2048")
PROTO_CELLS = PROTO_ROW + "\n"
ANCHORS = "\n".join([
    "# selftest anchors",
    "mac mlx-swift mlx-community/Qwen3-0.6B-4bit short-chat anchor=1 runs=3",
    "mac litert-lm litert-community/Qwen3-0.6B short-chat anchor=1 runs=3",
    "android litert-lm litert-community/Qwen3-0.6B short-chat anchor=1 runs=3 backend=gpu file=Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm",
    "android llama.cpp unsloth/Qwen3-0.6B-GGUF short-chat anchor=1 runs=3 file=Qwen3-0.6B-Q4_K_M.gguf",
]) + "\n"


def ok(cond, msg):
    print(("  ok  " if cond else "  FAIL ") + msg)
    if not cond:
        _fails.append(msg)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


def runs(camp, device, plat, arm, mid, task, day, hour, engine, decode, prefill, mem, n=3, warm=0, ctx=""):
    """n cold runs (Android) or one cold run then `warm` warm runs, two minutes apart, from
    2026-09-<day> <hour>:00 UTC."""
    out = []
    kinds = ["True"] * n if not warm else ["True"] + ["False"] * warm
    for i, cold in enumerate(kinds):
        ts = datetime.datetime(2026, 9, day, hour, 2 * i, tzinfo=datetime.timezone.utc)
        r = dict.fromkeys(COLUMNS, "")
        r.update(campaign=f"results/raw/{camp}", platform=plat, timestamp=ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                 runtime=arm, engine_version=engine, model_id=mid, task=task, decode_tps=str(decode),
                 prefill_tps=str(prefill), mem_resident_peak_mb=str(mem), mem_footprint_peak_mb="",
                 mem_resident_median_mb=str(mem - 50), cold_run=cold, first_ever="False", thermal_initial="nominal",
                 device=device, context_tokens=ctx, quantization="int4")
        out.append(r)
    return out


def session(root, camp, key, phase="payload", cells="matrices/st-text.cells", admitted=True, **extra):
    s = {"schema": "dashboard-job-session.v1", "job": "dashboard-v1", "campaign": f"results/raw/{camp}",
         "device_key": key, "device_display": {"s26": "Galaxy S26", "m4max": "Mac Studio (M4 Max)"}[key], "phase": phase, "cells": cells if phase == "payload" else "matrices/anchors.cells",
         "admitted": admitted, "verdict": "COMPLETED" if admitted else "ABORTED"}
    s.update(extra)
    write(os.path.join(root, "results", "raw", camp, "SESSION.json"), json.dumps(s, indent=1))


def write_summary(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)


def series_of(doc, device, arm, task):
    return next((s for s in doc["series"] if (s["device"], s["arm"], s["task"]) == (device, arm, task)), None)


def point(s, camp):
    return next((p for p in s["points"] if p["campaign"] == camp), None) if s else None


def main():
    tmp = tempfile.mkdtemp(prefix="regression-watch-selftest-")
    root = os.path.join(tmp, "bench")
    state = os.path.join(tmp, "state")
    write(os.path.join(root, "matrices", "st-text.cells"), TEXT_CELLS)
    write(os.path.join(root, "matrices", "st-protocol.cells"), PROTO_CELLS)
    write(os.path.join(root, "matrices", "anchors.cells"), ANCHORS)
    write(os.path.join(root, "ops", "dashboard-v1", "schedule.json"), json.dumps({"devices": {
        "s26": {"platform": "android", "identifier": "SM-S942Q"},
        "m4max": {"platform": "mac", "identifier": "Mac16,9"}}}))
    with open(rw.DEFINITIONS) as fh:
        cfg_doc = json.load(fh)
    cfg_doc.update(devices=[["SM-S942Q", "android"], ["Mac16,9", "mac"]],
                   cell_files=[["st-text.cells", "short-chat", None],
                               ["st-protocol.cells", "native-benchmark-1024x256", None],
                               ["st-optional.cells", "short-chat", None]],
                   optional_cell_files=["st-optional.cells"])
    defs_path = os.path.join(tmp, "defs.json")
    write(defs_path, json.dumps(cfg_doc))
    cfg = rw.load_definitions(defs_path)
    S = "SM-S942Q"
    W = [f"2026-09-0{d}-dashboard-v1-s26-android" if d < 10 else f"2026-09-{d}-dashboard-v1-s26-android"
         for d in (1, 8, 15)]
    W1, W2, W3 = W
    G2a, G2b = "2026-09-08-dashboard-v1-s26-gpu-a-android", "2026-09-08-dashboard-v1-s26-gpu-b-android"
    P1, P2 = "2026-09-01-dashboard-v1-s26-p1-android", "2026-09-08-dashboard-v1-s26-p2-android"
    M1, M2 = "2026-09-01-dashboard-v1-m4max-mac", "2026-09-08-dashboard-v1-m4max-mac"
    REFUSED, DDP = "2026-09-12-dashboard-v1-s26-refused-android", "2026-09-12-dashboard-v1-s26-ddp-android"
    CATALOG = "2026-09-12-catalog-x9-s26-android"
    rows = []
    cpu, gpu = "litert-lm-cpu", "litert-lm-gpu"
    # the CPU series: 10.0 -> 9.51 (-4.9 %, not red) -> 9.03 on another engine (-5.05 %, red)
    rows += runs(W1, S, "android", cpu, GEMMA, "short-chat", 1, 17, "v0.16.0", 10.0, 50.0, 2000)
    rows += runs(W2, S, "android", cpu, GEMMA, "short-chat", 8, 17, "v0.16.0", 9.51, 50.0, 2000)
    rows += runs(W3, S, "android", cpu, GEMMA, "short-chat", 15, 17, "v0.18.0", 9.03, 50.0, 2000)
    # left out: a refused sitting, a lab unit standing in, a campaign that is not a weekly sitting
    rows += runs(REFUSED, S, "android", cpu, GEMMA, "short-chat", 12, 17, "v0.16.0", 3.0, 20.0, 2000)
    rows += runs(CATALOG, S, "android", cpu, GEMMA, "short-chat", 12, 18, "v0.16.0", 3.0, 20.0, 2000)
    rows += runs(DDP, "SM-S942U1 (DDP m1q-36)", "android", gpu, GEMMA, "short-chat", 12, 19, "v0.18.0", 5.0, 20.0, 2000)
    # the GPU series: one point a day — the morning sitting's -15 % hidden behind the evening's
    rows += runs(W1, S, "android", gpu, GEMMA, "short-chat", 1, 18, "v0.16.0", 20.0, 200.0, 2100)
    rows += runs(G2a, S, "android", gpu, GEMMA, "short-chat", 8, 9, "v0.16.0", 17.0, 200.0, 2100)
    rows += runs(G2b, S, "android", gpu, GEMMA, "short-chat", 8, 21, "v0.16.0", 19.9, 200.0, 2100)
    # the protocol cell: a cold-only sitting, then one with warm calls (another regime)
    rows += runs(P1, S, "android", gpu, QWEN, "native-benchmark-1024x256", 1, 19, "v0.16.0", 30.0, 900.0, 900,
                 ctx="2048")
    rows += runs(P2, S, "android", gpu, QWEN, "native-benchmark-1024x256", 8, 19, "v0.16.0", 20.0, 900.0, 900,
                 warm=3, ctx="2048")
    # the Mac: peak memory 1000 -> 1060 MB, a lower-is-better metric as a rate (-5.66 %)
    rows += runs(M1, "Mac16,9", "mac", "litert-lm", QWEN, "short-chat", 1, 20, "v0.16.0", 100.0, 1000.0, 1000, warm=3)
    rows += runs(M2, "Mac16,9", "mac", "litert-lm", QWEN, "short-chat", 8, 20, "v0.16.0", 100.0, 1000.0, 1060, warm=3)
    summary = os.path.join(root, "results", "summary", "device-runs.csv")
    write_summary(summary, rows)
    for camp in (W1, W2, W3, G2a, G2b, P1, P2, DDP):
        session(root, camp, "s26")
    for camp in (M1, M2):
        session(root, camp, "m4max")
    session(root, REFUSED, "s26", admitted=False)
    session(root, W3.replace("-android", "-anchor-android"), "s26", phase="anchor")

    print("--- (a) the red points, the page's rule")
    doc = rw.compute(root, summary, cfg)
    cpu_s, gpu_s = series_of(doc, S, cpu, "short-chat"), series_of(doc, S, gpu, "short-chat")
    proto, mac = series_of(doc, S, gpu, "native-benchmark-1024x256"), series_of(doc, "Mac16,9", "litert-lm", "short-chat")
    ok(len(doc["series"]) == 4 and doc["meta"]["cells_files_skipped"] == ["st-optional.cells"],
       f"four series (CPU, GPU, protocol, Mac); a missing optional cells file is skipped ({len(doc['series'])} series)")
    p2, p3 = point(cpu_s, W2), point(cpu_s, W3)
    ok(p2["vs_prev"]["decode_tps"]["regression"] is False and round(p2["vs_prev"]["decode_tps"]["pct"], 2) == -4.9,
       f"threshold: -4.90 % is not red ({p2['vs_prev']['decode_tps']['pct']:.2f})")
    ok(p3["vs_prev"]["decode_tps"]["regression"] is True and round(p3["vs_prev"]["decode_tps"]["pct"], 2) == -5.05
       and p3["vs_prev"]["decode_tps"]["prev_campaign"] == W2,
       f"threshold: -5.05 % vs the nearest earlier shown point is red ({p3['vs_prev']['decode_tps']['pct']:.2f})")
    ok(p3["vs_prev"]["decode_tps"]["engine_changed"] is True and p2["vs_prev"]["decode_tps"]["engine_changed"] is False,
       "engine_changed: v0.16.0 -> v0.18.0 true, v0.16.0 -> v0.16.0 false")
    camps = {p["campaign"] for s in doc["series"] for p in s["points"]}
    ok(not camps & {REFUSED, CATALOG, DDP} and doc["meta"]["stand_in_rows"] == 3,
       f"left out: the refused sitting, the catalog campaign, the lab unit's 3 stand-in rows ({doc['meta']['stand_in_rows']})")
    a, b = point(gpu_s, G2a), point(gpu_s, G2b)
    ok(a["shown"] is False and b["shown"] is True and a["sittings_that_day"] == 2
       and all(v is None for v in a["vs_prev"].values()) and not b["vs_prev"]["decode_tps"]["regression"],
       "one point a day: the morning sitting (-15 %) hidden and never red, the evening one shown (-0.5 %)")
    q = point(proto, P2)
    ok(point(proto, P1)["regime"] == "cold" and q["regime"] == "warm" and q["vs_prev"]["decode_tps"]["pct"] is None
       and q["vs_prev"]["decode_tps"]["regime_changed"] is True and not q["vs_prev"]["decode_tps"]["regression"],
       "regime: the protocol cell's warm sitting is never compared with its cold one (20 vs 30 tok/s, no pct)")
    m = point(mac, M2)["vs_prev"]["mem_peak_mb"]
    ok(m["regression"] is True and round(m["pct"], 2) == -5.66, f"peak memory 1000 -> 1060 MB: {m['pct']:.2f} %, red")
    ok(sorted((x["campaign"], x["metric"]) for x in doc["red"]) == [(M2, "mem_peak_mb"), (W3, "decode_tps")],
       f"the red set: {[(x['campaign'], x['metric']) for x in doc['red']]}")
    page = {"series": [{"device": s["device"], "model": s["model"], "task": s["task"], "backend": s["backend"],
                        "arm": s["arm"], "model_id": s["model_id"], "ctx": s["ctx"], "artifact_file": s["artifact_file"],
                        "points": [{"campaign": p["campaign"], "shown": p["shown"],
                                    "vs_prev": {k: ({"pct": v["pct"], "regression": v["regression"]} if v else None)
                                                for k, v in p["vs_prev"].items()}} for p in s["points"]]}
                       for s in doc["series"]]}
    page_path = os.path.join(tmp, "regression.json")
    write(page_path, json.dumps(page))
    cli = [sys.executable, os.path.join(ROOT, "scripts", "regression_watch.py"), "--root", root, "--definitions",
           defs_path, "--compare", page_path]
    p = subprocess.run(cli, capture_output=True, text=True)
    ok(p.returncode == 0 and "equal (red bench 2, page 2;" in p.stdout, f"--compare, the same red set: exit {p.returncode}")
    page["series"][0]["points"][2]["vs_prev"]["decode_tps"]["regression"] = False
    write(page_path, json.dumps(page))
    p = subprocess.run(cli, capture_output=True, text=True)
    ok(p.returncode == 1 and "only in the bench: SM-S942Q Gemma 4 E2B short-chat CPU " + W3 in p.stdout,
       f"--compare, one red point fewer on the page: exit {p.returncode}, the difference named")

    print("--- (a') the prompt version cuts a series as the regime does (2026-10-19: the 1K task's tail)")
    root_p = os.path.join(tmp, "bench-prompt")
    for rel in ("matrices/st-text.cells", "matrices/st-protocol.cells", "matrices/anchors.cells",
                "ops/dashboard-v1/schedule.json"):
        with open(os.path.join(root, rel)) as fh:
            write(os.path.join(root_p, rel), fh.read())
    M3, M4 = "2026-09-15-dashboard-v1-m4max-mac", "2026-09-22-dashboard-v1-m4max-mac"

    def mac_runs(camp, day, decode, version):
        out = runs(camp, "Mac16,9", "mac", "litert-lm", QWEN, "short-chat", day, 20, "v0.16.0", decode, 1000.0, 1000,
                   warm=3)
        for r in out:
            r["prompt_version"] = version
        return out
    # M1 100 / M2 100 on the first text, M3 80 (-20 %) on a new text, M4 75.6 (-5.5 % within the new text)
    rows_p = [r for r in rows if r["campaign"] in (f"results/raw/{M1}", f"results/raw/{M2}")]
    rows_p += mac_runs(M3, 15, 80.0, "noref-2026-10-19") + mac_runs(M4, 22, 75.6, "noref-2026-10-19")
    summary_p = os.path.join(root_p, "results", "summary", "device-runs.csv")
    write_summary(summary_p, rows_p)
    for camp in (M1, M2, M3, M4):
        session(root_p, camp, "m4max")
    doc_p = rw.compute(root_p, summary_p, cfg)
    mac_p = series_of(doc_p, "Mac16,9", "litert-lm", "short-chat")
    v3, v4 = point(mac_p, M3)["vs_prev"], point(mac_p, M4)["vs_prev"]
    ok(point(mac_p, M2)["prompt"] == "" and point(mac_p, M3)["prompt"] == "noref-2026-10-19"
       and all(v3[k]["pct"] is None and v3[k]["prompt_changed"] is True and v3[k]["prev_prompt"] == ""
               and v3[k]["regression"] is False and v3[k]["regime_changed"] is False for k in v3),
       "the first point on a new prompt version is compared with none on every metric: prompt_changed, the old "
       "version kept, never red (80 vs 100 tok/s, no pct)")
    ok(v4["decode_tps"]["prev_campaign"] == M3 and v4["decode_tps"]["prompt_changed"] is False
       and v4["decode_tps"]["regression"] is True and round(v4["decode_tps"]["pct"], 2) == -5.5,
       f"the next point compares within the version: -5.50 % vs {M3}, red ({v4['decode_tps']['pct']:.2f})")
    ok(doc_p["meta"]["prompt_changes"] == 1 and [(b["campaign"], b["prev_prompt"], b["prompt"]) for b in doc_p["prompt_breaks"]]
       == [(M3, "", "noref-2026-10-19")] and "prompt changes 1" in rw.summary_line(doc_p)
       and f"- Mac16,9 Qwen 3 0.6B short-chat GPU {M3}: prompt none -> noref-2026-10-19" in rw.markdown(doc_p),
       f"the break counted and listed ({doc_p['prompt_breaks']})")
    result, judged = rw.judge({"metrics": [{"metric": "decode_tps", "prev_campaign": M2}]}, mac_p, M3, cfg)
    ok(result == "unjudged" and "prompt version is noref-2026-10-19, the previous point's none" in judged[0].get("why", ""),
       f"a retake on another prompt version than its previous point is not judged ({result}: {judged[0].get('why')})")
    p = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "regression_watch.py"), "--root", root_p,
                        "--definitions", defs_path], capture_output=True, text=True)
    ok(p.returncode == 0 and f"| {M3} | prompt none -> noref-2026-10-19 (not compared)" in p.stdout,
       f"the console lists the break: exit {p.returncode}")

    print("--- (b) a red point that is its cell's newest sitting -> one pending retake, the row byte for byte")
    now = datetime.datetime(2026, 9, 16, 3, 0)
    sitting = [f"results/raw/{W3.replace('-android', '-anchor-android')}", f"results/raw/{W3}"]
    resp = rw.respond(doc, sitting, root, state, cfg, now=now)
    ret = rw.load_state(state, rw.RETAKES)
    e = ret[0] if ret else {}
    ok(len(ret) == 1 and e.get("status") == "pending" and e.get("device") == "s26"
       and e.get("id") == "2026-09-16-s26-gemma4e2b-cpu-short-chat", f"one pending retake: {e.get('id')}")
    ok(e.get("row") == CPU_ROW and e.get("cells_file") == "matrices/st-text.cells" and e.get("line") == 3,
       "its row is line 3 of the cells file the red sitting ran, byte for byte (spaces and comment kept)")
    mm = (e.get("metrics") or [{}])[0]
    ok(mm.get("metric") == "decode_tps" and mm.get("prev_campaign") == W2 and mm.get("engine_changed") is True
       and mm.get("prev_engine") == "v0.16.0" and round(mm.get("pct"), 2) == -5.05,
       "the red metric, its percentage, previous campaign and engines in the retake")
    rw.respond(doc, sitting, root, state, cfg, now=now)
    ok(len(rw.load_state(state, rw.RETAKES)) == 1, "the same sitting again: no second retake (the first covers it)")
    later = rows + runs("2026-09-22-dashboard-v1-s26-android", S, "android", cpu, GEMMA, "short-chat", 22, 17,
                        "v0.18.0", 9.0, 50.0, 2000)
    write_summary(os.path.join(tmp, "later.csv"), later)
    resp2 = rw.respond(rw.compute(root, os.path.join(tmp, "later.csv"), cfg), sitting, root,
                       os.path.join(tmp, "state-later"), cfg, now=now)
    ok(not resp2["queued"] and any("not its cell's newest sitting" in n for n in resp2["notes"]),
       "a red point a newer sitting has replaced: no retake")
    rw.respond(doc, [f"results/raw/{M2}"], root, state, cfg, now=now)
    mac_e = next((x for x in rw.load_state(state, rw.RETAKES) if x["device"] == "m4max"), {})
    ok(mac_e.get("row") == "mac litert-lm litert-community/Qwen3-0.6B short-chat"
       and mac_e["metrics"][0]["metric"] == "mem_peak_mb", "the Mac's memory red point -> its own retake")
    st2 = os.path.join(tmp, "state-attempts")
    rw.save_state(st2, rw.RETAKES, [dict(e, id="x1"), dict(e, id="x2")])
    rw.finish_retakes(st2, ["x1"], 0, "ok", "results/raw/2026-09-16-dashboard-v1-s26-retake-x-android")
    rw.finish_retakes(st2, ["x2"], 4, "anchor-collapse", "")
    mid = {x["id"]: x["status"] for x in rw.load_state(st2, rw.RETAKES)}
    rw.finish_retakes(st2, ["x2"], 4, "anchor-collapse", "")
    end = {x["id"]: x for x in rw.load_state(st2, rw.RETAKES)}
    ok(end["x1"]["status"] == "done" and end["x1"]["retake_campaign"].endswith("-retake-x-android")
       and mid["x2"] == "pending" and end["x2"]["status"] == "abandoned" and len(end["x2"]["attempts"]) == 2,
       "exit 0 -> done with its campaign; a sitting that does not admit -> pending, abandoned after two")
    st3 = os.path.join(tmp, "state-busy")
    rw.save_state(st3, rw.RETAKES, [dict(e, id="b1")])
    for _ in range(3):
        rw.finish_retakes(st3, ["b1"], rw.RETAKE_BUSY_EXIT, "the Mac measurement window is held by another lane", "")
    busy_mid = rw.load_state(st3, rw.RETAKES)[0]
    rw.finish_retakes(st3, ["b1"], 4, "anchor-collapse", "")
    after_one = rw.load_state(st3, rw.RETAKES)[0]["status"]
    rw.finish_retakes(st3, ["b1"], 4, "anchor-collapse", "")
    busy_end = rw.load_state(st3, rw.RETAKES)[0]
    ok(busy_mid["status"] == "pending" and len(busy_mid["attempts"]) == 3 and after_one == "pending"
       and busy_end["status"] == "abandoned" and len(busy_end["attempts"]) == 5,
       "busy exits (nothing ran) are logged and not counted: pending after three, abandoned after two sittings that ran")
    sup_root = os.path.join(tmp, "root-supersede")
    sup_cells = os.path.join(sup_root, e["cells_file"])
    write(sup_cells, f"# the cells file the red sitting ran\n{e['row']}\n")
    st4 = os.path.join(tmp, "state-supersede")
    rw.save_state(st4, rw.RETAKES, [dict(e, id="s1", status="pending", created=rw.now_text(now))])
    kept = rw.pending_retakes(st4, e["device"], now=now, root=sup_root)
    counted = rw.pending_counts(st4, root=sup_root).get(e["device"])
    write(sup_cells, f"# the cells file the red sitting ran\n{e['row'].split('#', 1)[0].rstrip()} context-tokens=4096\n")
    moved = rw.pending_counts(st4, root=sup_root).get(e["device"])
    gone = []
    left = rw.pending_retakes(st4, e["device"], now=now, root=sup_root, gone=gone)
    s1 = rw.load_state(st4, rw.RETAKES)[0]
    ok([x["id"] for x in kept] == ["s1"] and counted == 1 and moved is None and left == []
       and s1["status"] == "superseded" and gone == [("s1", f"its row is no longer in {e['cells_file']}")],
       "a retake whose row left its cells file is not counted for the choice and is marked superseded, not run")
    st5 = os.path.join(tmp, "state-no-cells-file")
    rw.save_state(st5, rw.RETAKES, [dict(e, id="s2", status="pending", created=rw.now_text(now))])
    ok([x["id"] for x in rw.pending_retakes(st5, e["device"], now=now, root=os.path.join(tmp, "no-such-root"))] == ["s2"],
       "a cells file that is not there supersedes nothing (no row to compare): the retake stays pending")
    result, judged = rw.judge(e, None, "x", cfg)
    ok(result == "unjudged" and all("define this cell no more" in j["why"] for j in judged),
       f"no series of the retake's cell any more: unjudged, the row changed ({judged[0].get('why')})")
    old = rw.pending_retakes(state, "s26", now=now + datetime.timedelta(days=8), write=False)
    ok(old == [] and rw.pending_retakes(state, "s26", now=now)[0]["id"] == e["id"],
       "a pending retake past seven days is expired; within them it is the device's pending one")

    print("--- (c) the job: a pending retake before the weekly set; a retake sitting is not the week's")
    import dashboard_job as dj
    import dashboard_job_selftest as djs
    dj.LOG_DIR = os.path.join(tmp, "joblogs")
    bin_dir, fstate = os.path.join(tmp, "bin"), os.path.join(tmp, "adbstate")
    os.makedirs(bin_dir)
    os.makedirs(fstate)
    write(os.path.join(bin_dir, "adb"), djs.FAKE_ADB.replace("__STATE__", repr(fstate)))
    os.chmod(os.path.join(bin_dir, "adb"), 0o755)
    os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
    write(os.path.join(fstate, "devices.txt"), "FAKE-A\nFAKE-B\nFAKE-S\n")
    real_pgrep = dj.pgrep
    dj.pgrep = lambda pattern: []     # host drivers of other lanes are not this test's business
    jnow = datetime.datetime.now().astimezone().replace(hour=2, minute=0, second=0, microsecond=0)

    def jrow(camp, dev, **delta):
        t = (jnow - datetime.timedelta(**delta)).astimezone(datetime.timezone.utc)
        return {"campaign": f"results/raw/{camp}", "platform": "android", "timestamp": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "device": dev}
    sched = {"devices": {"alpha": {"platform": "android", "display": "Fake A", "identifier": "FakeA", "serial": "FAKE-A",
                                   "hold": os.path.join(tmp, "hold_a")},
                         "beta": {"platform": "android", "display": "Fake B", "identifier": "FakeB", "serial": "FAKE-B",
                                  "hold": os.path.join(tmp, "hold_b")}}}
    week = [jrow("now-dashboard-v1-alpha-android", "FakeA", minutes=30), jrow("d14-dashboard-v1-beta-android", "FakeB", days=14)]

    def choose(rows_, retakes, skip=frozenset()):
        k, _, rep = dj.resolve_device(sched, "auto", now=jnow, rows=rows_, admitted={}, retakes=retakes, skip=skip)
        return k, {x["key"]: x for x in rep}
    k, rep = choose(week, {})
    ok(k == "beta" and rep["alpha"]["state"] == "done", f"no retake: alpha done this week, beta pending -> {k}")
    k, rep = choose(week, {"alpha": 1})
    ok(k == "alpha" and rep["alpha"].get("weekly_done") is True and "1 retake pending" in rep["alpha"]["detail"],
       f"alpha done this week with a pending retake: chosen before beta's weekly set -> {k} ({rep['alpha']['detail']})")
    rt = "now-dashboard-v1-beta-retake-gemma4e2b-cpu-short-chat-android"
    k, rep = choose(week + [jrow(rt, "FakeB", minutes=10)], {}, skip={f"results/raw/{rt}"})
    ok(k == "beta" and rep["beta"]["state"] == "candidate",
       f"beta's retake sitting this week (SESSION.json names retakes) is not its weekly session -> {k}")
    k, rep = choose(week + [jrow(rt, "FakeB", minutes=10)], {})
    ok(k is None, "the same campaign without that SESSION.json mark (a by-hand -retake) counts as before -> no device")

    half = os.path.join(tmp, "set-android-h1.cells")
    write(half, "android llama.cpp unsloth/Qwen3-0.6B-GGUF short-chat anchor=1 runs=3 file=Qwen3-0.6B-Q4_K_M.gguf\n")
    s26 = {"platform": "android", "display": "Fake S", "identifier": "FakeS", "serial": "FAKE-S", "cpu_mask": "",
           "hold": os.path.join(tmp, "hold_s"), "storage_gb_full": 100, "timeout_hours": 3,
           "split": [{"cells": half, "min_free_gb": 1}]}
    sched_path = os.path.join(tmp, "schedule-job.json")
    write(sched_path, json.dumps({"anchors": "matrices/anchors.cells", "cells": half, "devices": {"s26": s26}}))
    today = datetime.date.today().isoformat()
    base = f"{today}-dashboard-v1-s26"
    cpu_entry = dict(e, created=rw.now_text(), status="pending", device="s26",
                     row="android litert-lm litert-community/gemma-4-E2B-it-litert-lm short-chat backend=cpu "
                         "cooldown=300 file=gemma-4-E2B-it.litertlm")

    def job(*argv):
        buf, saved = io.StringIO(), sys.argv
        sys.argv = ["dashboard_job.py", *argv, "--schedule", sched_path]
        try:
            with contextlib.redirect_stdout(buf):
                code = dj.main()
        finally:
            sys.argv = saved
        return code, buf.getvalue().splitlines()

    def index(lines, needle):
        return next((i for i, ln in enumerate(lines) if needle in ln), None)
    rw.save_state(dj.LOG_DIR, rw.RETAKES, [cpu_entry])
    code, lines = job("s26", "--dry-run", "--once")
    gen = os.path.relpath(os.path.join(dj.LOG_DIR, f"retake-{today}-s26.cells"), ROOT)
    r_m = index(lines, f"bench matrix {gen} --platform android --campaign {base}-retake-gemma4e2b-cpu-short-chat ")
    r_a = index(lines, f"--campaign {base}-retake-gemma4e2b-cpu-short-chat-anchor ")
    w_a = index(lines, f"--campaign {base}-anchor ")
    ok(code == 0 and None not in (r_m, r_a, w_a) and r_a < r_m < w_a,
       f"dry run: the retake sitting's anchor and its bench matrix line (…-retake-<slug>) before the weekly set's (exit {code})")
    posts = [i for i, ln in enumerate(lines) if "post: $ " in ln]
    ok(len(posts) == 2 and posts[0] < w_a and f"results/raw/{base}-retake-gemma4e2b-cpu-short-chat-android" in lines[posts[0]],
       "the retake sitting closes with its own post line, before the weekly set starts")
    with open(os.path.join(ROOT, "matrices", "anchors.cells")) as fh:
        real_anchors = [ln.rstrip("\n") for ln in fh if ln.split("#", 1)[0].strip().startswith("android ")]
    with open(os.path.join(dj.LOG_DIR, f"retake-{today}-s26.cells")) as fh:
        body = [ln.rstrip("\n") for ln in fh if ln.split("#", 1)[0].strip()]
    ok(body == real_anchors + [cpu_entry["row"]], "the generated cells file: the android anchor rows byte for byte, then the retake row")
    ok(any("retake profile: none" in ln for ln in lines) and index(lines, "bench profile ") is None,
       "a text-task retake: no profile pair, the reason logged")
    ok(rw.load_state(dj.LOG_DIR, rw.RETAKES)[0]["status"] == "pending", "a dry run leaves the retake pending")
    proto_entry = dict(cpu_entry, id="p1", slug="qwen306b-gpu-protocol-1024", row=PROTO_ROW,
                       task="native-benchmark-1024x256", arm="litert-lm-gpu")
    rw.save_state(dj.LOG_DIR, rw.RETAKES, [proto_entry])
    code, lines = job("s26", "--dry-run", "--once")
    pm = index(lines, f"bench matrix {gen} --platform android --campaign {base}-retake-qwen306b-gpu-protocol-1024 ")
    pp = index(lines, f"bench profile {gen} --campaign {base}-retake-qwen306b-gpu-protocol-1024")
    ok(code == 0 and None not in (pm, pp) and pm < pp < index(lines, f"--campaign {base}-anchor "),
       "an android native-benchmark retake: ./bench profile over the same file into the payload campaign, after its matrix line")
    rw.save_state(dj.LOG_DIR, rw.RETAKES, [])
    code, lines = job("s26", "--dry-run", "--once")
    ok(code == 0 and index(lines, "-retake-") is None and index(lines, f"--campaign {base}-anchor ") is not None,
       "no pending retake: no retake line, the weekly set as before")
    rw.save_state(dj.LOG_DIR, rw.RETAKES, [cpu_entry])
    code, lines = job("s26", "--dry-run", "--once", "--no-retake")
    ok(index(lines, "-retake-") is None, "--no-retake: the weekly set only")
    rw.save_state(dj.LOG_DIR, rw.RETAKES, [dict(cpu_entry, row=ANCHORS.splitlines()[3])])
    text, rows_written = rw.retake_cells_text(ROOT, "matrices/anchors.cells", "android", rw.load_state(dj.LOG_DIR, rw.RETAKES))
    ok(rows_written == real_anchors, "a retake row identical to an anchor row is written once")
    twice = [cpu_entry, dict(cpu_entry, id="again", row=cpu_entry["row"].replace("cooldown=300", "cooldown=60"))]
    text, rows_written = rw.retake_cells_text(ROOT, "matrices/anchors.cells", "android", twice)
    ok(rows_written == real_anchors + [cpu_entry["row"]] and "# again: the same cell as another retake row" in text,
       "two retakes of one cell: one row (validate_cells refuses a cell twice in a file)")
    real_rows, real_adm = dj.load_rows, dj.load_admission
    # the job's auto path reads the real clock: a row 40 min old is "done this week" except in the first 40 min
    # after Monday 00:00 local, so the row is stamped no earlier than one minute into this week (found 2026-10-19 00:02)
    real_now = datetime.datetime.now().astimezone()
    t = max(real_now - datetime.timedelta(minutes=40),
            dj.week_start(real_now) + datetime.timedelta(minutes=1)).astimezone(datetime.timezone.utc)
    done_rows = [{"campaign": f"results/raw/{base}-android", "platform": "android", "device": "FakeS",
                  "timestamp": t.strftime("%Y-%m-%dT%H:%M:%SZ")}]
    dj.load_rows, dj.load_admission = (lambda path=None: done_rows), (lambda: {})
    rw.save_state(dj.LOG_DIR, rw.RETAKES, [cpu_entry])
    code, lines = job("auto", "--dry-run")
    ok(code == 0 and index(lines, "auto chose s26") is not None
       and index(lines, f"--campaign {base}-retake-gemma4e2b-cpu-short-chat ") is not None
       and index(lines, f"--campaign {base}-anchor ") is None
       and index(lines, "=== done: OK (the retake sitting only: the weekly set is done this week)") is not None,
       "auto, the weekly set done this week and a retake pending: the firing runs the retake sitting only")
    rw.save_state(dj.LOG_DIR, rw.RETAKES, [])
    code, lines = job("auto", "--dry-run")
    ok(code == 0 and index(lines, "nothing pending this week") is not None and index(lines, "bench matrix") is None,
       "auto, the weekly set done and no retake: nothing pending, nothing planned")
    rw.save_state(dj.LOG_DIR, rw.RETAKES, [cpu_entry])
    code, lines = job("auto", "--dry-run", "--no-retake")
    ok(code == 0 and index(lines, "nothing pending this week") is not None,
       "auto --no-retake: a pending retake does not make a done device a candidate")
    dj.load_rows, dj.load_admission = real_rows, real_adm
    write(os.path.join(dj.LOG_DIR, rw.RETAKES), "{not json")
    code, lines = job("s26", "--dry-run", "--once")
    ok(code == 0 and index(lines, "WARN retake state unusable") is not None and index(lines, "-retake-") is None
       and index(lines, f"--campaign {base}-anchor ") is not None,
       "an unreadable retakes.json: one WARN line, no retake, the weekly set as before")
    dj.pgrep = real_pgrep
    lock = "/tmp/edge-llm-bench-android-FAKE-S.lock"   # the preflight's campaign-lock probe
    if os.path.exists(lock):
        os.remove(lock)

    print("--- (d) a retake still red on another engine -> one bisect request; the same engine or back within the line -> none")
    RT = "2026-09-16-dashboard-v1-s26-retake-gemma4e2b-cpu-short-chat-android"
    RTA = RT.replace("-android", "-anchor-android")
    gen_rel = "logs/dashboard-job/retake-2026-09-16-s26.cells"
    rw.finish_retakes(state, [e["id"]], 0, "ok", f"results/raw/{RT}", cells_file=gen_rel,
                      suffix="retake-gemma4e2b-cpu-short-chat")

    def retake_world(decode, day, engine="v0.18.0", name=RT):
        rows_ = rows + runs(name, S, "android", cpu, GEMMA, "short-chat", day, 18, engine, decode, 50.0, 2000)
        path = os.path.join(tmp, f"retake-{decode}-{day}-{engine}.csv")
        write_summary(path, rows_)
        session(root, name, "s26", cells=gen_rel, retake={"ids": [e["id"]], "cells_file": gen_rel, "rows": [CPU_ROW]})
        session(root, name.replace("-android", "-anchor-android"), "s26", phase="anchor")
        return rw.compute(root, path, cfg)
    later_day = retake_world(9.0, 16)    # 2026-09-16 UTC: a later day than the red point's (09-15)
    rp = point(series_of(later_day, S, cpu, "short-chat"), RT)
    ok(rp["shown"] and rp["vs_prev"]["decode_tps"]["prev_campaign"] == W3 and not rp["vs_prev"]["decode_tps"]["regression"],
       "on a later UTC day the page compares the retake with the red point itself (-0.3 %, not red)")
    resp = rw.respond(later_day, [f"results/raw/{RTA}", f"results/raw/{RT}"], root, state, cfg, now=now)
    j = (resp["judged"] or [{}])[0]
    reqs = rw.load_state(state, rw.REQUESTS)
    req = reqs[0] if reqs else {}
    ok(j.get("result") == "red-stays" and round(j["metrics"][0]["pct"], 2) == -5.36,
       f"the retake judged against the red point's previous point {W2}: red stays ({j.get('result')})")
    ok(len(reqs) == 1 and req.get("good") == "v0.16.0" and req.get("bad") == "v0.18.0" and req.get("route") == "ddp:m1q-36"
       and req.get("verdict") == "speed:decode<=-5%" and req.get("row") == CPU_ROW and req.get("status") == "pending",
       f"one bisect request: good v0.16.0, bad v0.18.0, verdict speed:decode<=-5%, route ddp:m1q-36 ({req.get('id')})")
    ok(req.get("tooling") == "not on this branch" and req.get("command") is None
       and "tooling not on this branch" in (req.get("why_no_command") or "")
       and any("tooling not on this branch" in n for n in resp["notes"]),
       "scripts/engine_bisect.py not in the tree: 'tooling not on this branch' logged, the request kept, no command")
    ok(not rw.load_state(state, rw.RETAKES)[0].get("result") is None
       and rw.load_state(state, rw.RETAKES)[0]["result"] == "red-stays",
       "the retake carries its verdict")
    ok(not any(x["id"] != e["id"] and x["device"] == "s26" for x in rw.load_state(state, rw.RETAKES)),
       "a retake sitting's red point queues no retake")
    write(os.path.join(root, "scripts", "engine_bisect.py"), "# stub\n")
    cmd, why, notes = rw.bisect_command(root, dict(e, row=CPU_ROW), "decode_tps", "v0.16.0", "main@1dadd00c", "ddp:m1q-36")
    ok(cmd == ("python3 scripts/engine_bisect.py --good v0.16.0 --bad 1dadd00c --cells matrices/st-text.cells --row 3 "
               "--verdict 'speed:decode<=-5%' --route ddp:m1q-36") and why is None and notes,
       f"with scripts/engine_bisect.py in the tree: the command (--good/--bad/--cells/--row/--verdict/--route): {cmd}")
    cmd, why, _ = rw.bisect_command(root, dict(mac_e), "mem_peak_mb", "v0.16.0", "v0.18.0", "none")
    ok(cmd is None and why.startswith("no route"), f"the Mac: route none, no command ({why})")
    cmd, why, _ = rw.bisect_command(root, dict(e, row=CPU_ROW), "mem_peak_mb", "v0.16.0", "v0.18.0", "ddp:m1q-36")
    ok(cmd is None and "no mem verdict" in why, f"a memory verdict: no command ({why})")
    os.remove(os.path.join(root, "scripts", "engine_bisect.py"))
    for decode, engine, what in ((9.0, "v0.16.0", "red stays on the same engine"), (9.5, "v0.18.0", "back within the line")):
        st = os.path.join(tmp, f"state-{decode}")
        rw.save_state(st, rw.RETAKES, [dict(rw.load_state(state, rw.RETAKES)[0], result=None, status="done")])
        resp = rw.respond(retake_world(decode, 15, engine), [f"results/raw/{RTA}", f"results/raw/{RT}"], root, st, cfg, now=now)
        ok(not rw.load_state(st, rw.REQUESTS) and resp["judged"][0]["result"] == ("red-stays" if decode == 9.0 else "cleared"),
           f"{what}: no request ({resp['judged'][0]['result']}; {resp['notes'][-1][:90]})")

    print("--- (e) the draft beside the request")
    draft = os.path.join(state, "regression-2026-09-16-gemma4e2b-cpu-short-chat.md")
    text = open(draft).read() if os.path.exists(draft) else ""
    ok(text and "## EN" in text and "## JA" in text and CPU_ROW in text and "9.03 tok/s" in text and "9.51 tok/s" in text
       and "9.00 tok/s" in text and "On Galaxy S26 (SM-S942Q), LiteRT-LM v0.18.0 runs Gemma 4 E2B" in text
       and f"./bench dashboard-job s26 --cells {gen_rel} --suffix retake-gemma4e2b-cpu-short-chat" in text,
       "EN and JA, the two points and the retake's number, the row, the command that re-measures it")
    bad = rw.DRAFT_REFUSED.findall(text)
    ok(not bad, f"no refused word in the draft ({bad or 'none'})")

    if _fails:
        print(f"\n{len(_fails)} failure(s); temp dir kept: {tmp}")
        return 1
    shutil.rmtree(tmp)
    print("\nselftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
