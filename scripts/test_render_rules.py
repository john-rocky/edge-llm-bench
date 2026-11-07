#!/usr/bin/env python3
"""Device-free checks of the text-check-rule and the cpu-cap-rule on the summary -> arm_row ->
dashboard path (CI: leaderboard-check).

A run whose decoded text failed the Android runner's text check (record
conditions.textCheck status FAIL) stays a row of results/summary/device-runs.csv — column
text_check — and pools into no number: render_leaderboard.arm_row drops it the way it drops
a firstEver run, and render_dashboard renders a cell left without a headline for that
reason as "text-fail" with the reason, never the rate (methodology/fairness-rules.md). A run
during which the phone capped a CPU the engine ran on (record protocolFlags cpu-capped; column
cpu_capped) is kept out the same way when the ceiling fell by more than the line (column
cpu_cap_drop_pct above render_leaderboard.CPU_CAP_MAX_DROP_PCT), and a cell left without a
headline for that reason renders as "cpu-capped": no valid run, with the count; a run whose
ceiling fell less pools, and the number carries the count. On an Android NPU or GPU arm
(render_leaderboard.CPU_CAP_EXEMPT_ARMS) a capped run pools whatever the fall, and the number
carries the count and the largest fall. So is a llama.cpp side build's run whose own
device lines did not show the cell's NPU / GPU device (protocolFlags backend-not-registered;
column backend_registered), and its cell reads only its own arm's rows.
The executorch arm's rows (docs/executorch-arm-v1.md) carry their delegate in the arm on every
platform (executorch-xnnpack, …): the cells file's backend= and the runners' records name the
same arm, and validate_cells keeps such a row to an own export with its recipe alias.

Fixtures live in temp dirs; results/ is neither read nor written.

  python3 scripts/test_render_rules.py
"""
import argparse
import base64
from contextlib import redirect_stdout
import csv
import datetime
import hashlib
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bench_common  # noqa: E402
import build_summary  # noqa: E402
import render_dashboard  # noqa: E402
import render_dashboard_html  # noqa: E402
import render_leaderboard  # noqa: E402
import run_windows_matrix  # noqa: E402
import validate_cells  # noqa: E402
from render_leaderboard import arm_row  # noqa: E402

OFF = "FAIL:text-off-task-screen"
TODAY = datetime.date(2026, 10, 6)
FIELDS = ["source", "campaign", "platform", "timestamp", "runtime", "schema_version",
          "engine_version", "engine_stamped", "engine_artifact", "model_id", "model_file", "quantization", "task",
          "prompt_version", "harness_stamp", "decode_tps", "decode_tps_wall", "prefill_tps", "prompt_tokens",
          "gen_tokens", "ttft_ms", "mem_footprint_median_mb", "mem_resident_median_mb",
          "energy_j_per_tok", "thermal_initial", "thermal_final", "battery_state", "cold_run",
          "first_ever", "context_tokens", "device", "os_version", "mem_footprint_peak_mb",
          "mem_resident_peak_mb", "text_check"]
# appended after text_check on 2026-10-07 (cpu-cap-rule)
CPU_FIELDS = ["cpu_capped", "cpu_max_freq"]
# appended after them the same day (a llama.cpp side build's device lines)
BACKEND_FIELDS = ["backend_registered"]
# appended last on 2026-10-08 (the cpu-cap-rule line)
DROP_FIELDS = ["cpu_cap_drop_pct"]


def setUpModule():
    # the scripts under test read with json.load(open(...)) and leave the file to the
    # collector; unittest's default filter would print a ResourceWarning per fixture
    warnings.simplefilter("ignore", ResourceWarning)


def row(decode, cold=True, text_check="", first_ever=False, runtime="litert-lm-gpu",
        model_id="org/model", minute=0, campaign="results/raw/2026-10-06-fixture-android"):
    """One device-runs.csv row as csv.DictReader returns it (every value a string)."""
    return {
        "source": f"{campaign}/app-path-android/r{minute}.json", "campaign": campaign,
        "platform": "android", "timestamp": f"2026-10-06T06:{minute:02d}:00Z",
        "runtime": runtime, "schema_version": "1", "engine_version": "v0.16.0",
        "engine_artifact": "fixture-sha", "model_id": model_id,
        "quantization": "INT4 (fixture)", "task": "long-context-1024-gen256",
        "harness_stamp": "2026-08-android-cli-v1",
        "decode_tps": "" if decode is None else str(decode), "decode_tps_wall": "",
        "prefill_tps": "1000.0", "prompt_tokens": "1339", "gen_tokens": "256",
        "ttft_ms": "1400.0", "mem_footprint_median_mb": "", "mem_resident_median_mb": "800.0",
        "energy_j_per_tok": "", "thermal_initial": "nominal", "thermal_final": "nominal",
        "battery_state": "charging", "cold_run": str(cold),
        "first_ever": "True" if first_ever else "", "context_tokens": "2048",
        "device": "FIXTURE-PHONE", "os_version": "16", "mem_footprint_peak_mb": "",
        "mem_resident_peak_mb": "830.0", "text_check": text_check,
    }


def session(cold, warm, text, model_id="org/model", runtime="litert-lm-gpu"):
    """Three two-iteration launches (cold, warm) after a firstEver launch; text[i] is the
    text_check of launch i+1 (both iterations of one launch share the verdict here)."""
    rows = [row(cold[0] - 1, True, text[0], True, runtime, model_id, 0),
            row(warm[0], False, text[0], False, runtime, model_id, 1)]
    for i, (c, w) in enumerate(zip(cold[1:], warm[1:]), 1):
        rows += [row(c, True, text[i], False, runtime, model_id, 2 * i),
                 row(w, False, text[i], False, runtime, model_id, 2 * i + 1)]
    return rows


class ArmRow(unittest.TestCase):
    def test_every_run_failed_the_text_check(self):
        a = arm_row(session([25.7, 25.5, 26.0], [25.7, 26.1, 26.0], [OFF] * 3))
        self.assertIsNone(a["warm"])
        self.assertIsNone(a["cold_median"])
        self.assertEqual((a["n"], a["warm_n"], a["cold_n"]), (0, 0, 0))
        self.assertEqual(a["text_fail_n"], 5)        # the firstEver run was never in the pool
        self.assertEqual(a["text_checked_n"], 5)
        self.assertEqual(a["text_fail_flags"], "text-off-task-screen")
        self.assertIsNone(a["prefill"])              # no metric of a failed run survives
        self.assertIsNone(a["mem"])
        self.assertEqual(a["campaign"], "results/raw/2026-10-06-fixture-android")

    def test_partial_failure_pools_the_rest(self):
        a = arm_row(session([30.0, 30.0, 10.0], [31.0, 31.0, 9.0], ["PASS", "PASS", OFF]))
        self.assertEqual(a["cold_median"], 30.0)
        self.assertEqual(a["cold_n"], 1)
        self.assertEqual(a["warm"], 31.0)            # median of 31.0 / 31.0; the failed 9.0 is out
        self.assertEqual(a["warm_n"], 2)
        self.assertEqual((a["n"], a["text_fail_n"], a["text_checked_n"]), (3, 2, 5))
        # two warm iterations fail with different flags: the flags are the union, the
        # pools are the runs left (warm 20.0; cold 21.0 / 22.0)
        mixed = session([20.0, 21.0, 22.0], [20.0, 21.0, 22.0], ["PASS"] * 3)
        mixed[-1]["text_check"] = "FAIL:text-empty-or-degenerate,text-off-task-screen"
        mixed[-3]["text_check"] = "FAIL:text-repetition-loop"
        a = arm_row(mixed)
        self.assertEqual(a["text_fail_flags"],
                         "text-empty-or-degenerate, text-off-task-screen, text-repetition-loop")
        self.assertEqual((a["warm"], a["warm_n"], a["cold_median"], a["cold_n"]), (20.0, 1, 21.5, 2))

    def test_a_summary_without_the_column_and_an_unchecked_cell(self):
        rows = session([30.0, 30.0, 31.0], [31.0, 31.0, 32.0], [""] * 3)
        a = arm_row(rows)
        b = arm_row([{k: v for k, v in r.items() if k != "text_check"} for r in rows])
        self.assertEqual(a, b)                       # pre-2026-10-06 summaries read the same
        self.assertEqual((a["text_fail_n"], a["text_checked_n"], a["text_fail_flags"]), (0, 0, ""))
        self.assertEqual(a["cold_median"], 30.5)


class SummaryColumn(unittest.TestCase):
    def test_text_check_column_three_values(self):
        records = {
            "pass.json": {"textCheck": {"status": "PASS", "flags": []}},
            "fail.json": {"textCheck": {"status": "FAIL", "flags": ["text-empty-or-degenerate",
                                                                    "text-off-task-screen"]}},
            "unchecked.json": {},
        }
        with tempfile.TemporaryDirectory(prefix="render-rules-summary-") as tmp:
            folder = os.path.join(tmp, "results", "raw", "2026-10-06-fixture-android", "app-path-android")
            os.makedirs(folder)
            for i, (name, cond) in enumerate(records.items()):
                with open(os.path.join(folder, name), "w") as fh:
                    json.dump({"schemaVersion": 1, "id": f"fixture-{i}", "runtime": "litert-lm-gpu",
                               "timestamp": f"2026-10-06T06:0{i}:00Z", "task": "long-context-1024-gen256",
                               "model": {"id": "org/model"},
                               "device": {"systemName": "Android", "modelIdentifier": "FIXTURE-PHONE"},
                               "conditions": {"contextTokens": 2048, **cond},
                               "metrics": {"decodeTokensPerSecond": 25.0, "coldRun": True}}, fh)
            # a record whose conditions is not a dict reads as unchecked, never crashes
            with open(os.path.join(folder, "odd.json"), "w") as fh:
                json.dump({"id": "fixture-odd", "timestamp": "2026-10-06T06:09:00Z", "conditions": None,
                           "metrics": {"decodeTokensPerSecond": 1.0}}, fh)
            out = os.path.join(tmp, "summary")
            os.makedirs(out)
            with patch.object(build_summary, "ROOT", tmp), patch.object(build_summary, "OUT", out):
                path, n = build_summary.build_device()
            with open(path, newline="") as fh:
                got = list(csv.DictReader(fh))
                fh.seek(0)
                header = next(csv.reader(fh))
        self.assertEqual(n, 4)
        # appended: every earlier column keeps its place (text_check, then the CPU cap pair,
        # then backend_registered, then the cap's drop)
        self.assertEqual(header, FIELDS + CPU_FIELDS + BACKEND_FIELDS + DROP_FIELDS)
        by_name = {os.path.basename(r["source"]): r["text_check"] for r in got}
        self.assertEqual(by_name, {"pass.json": "PASS",
                                   "fail.json": "FAIL:text-empty-or-degenerate,text-off-task-screen",
                                   "unchecked.json": "", "odd.json": ""})

    def test_cpu_cap_drop_reads_the_engines_cpus(self):
        # cpu_cap_drop_of: the largest fall over the policies of the engine's CPUs, in
        # run_cell.cpu_conditions's order (allowed list, else launch mask, else every CPU)
        freq = {"policy0": {"min": 1425, "hw": 1704, "cpus": "0-3"},
                "policy4": {"min": 2130, "hw": 2367, "cpus": "4-7"},
                "policy8": {"min": 2914, "hw": 2914, "cpus": "8"}}

        def drop(**cond):
            return build_summary.cpu_cap_drop_of({"conditions": dict(cpuMaxFreqMHz=freq, **cond)})
        self.assertEqual(drop(cpusAllowedList="4-7"), "10.0")              # policy0's 16.4 is not the engine's
        self.assertEqual(drop(cpusAllowedList="0-8"), "16.4")
        self.assertEqual(drop(cpusAllowedList="8"), "0.0")                 # read, none of the engine's fell
        self.assertEqual(drop(cpuAffinity="taskset f0"), "10.0")           # no allowed list: the launch mask
        self.assertEqual(drop(cpuAffinity="none"), "16.4")                 # neither: every CPU
        self.assertEqual(drop(), "16.4")
        # flagged, but the last allowed list shows no fall (the runner flags against every list
        # it read): the fall over every policy
        self.assertEqual(drop(cpusAllowedList="8", protocolFlags=["cpu-capped"]), "16.4")
        self.assertEqual(build_summary.cpu_cap_drop_of({"conditions": {"exitCode": 0}}), "")   # not read
        self.assertEqual(build_summary.cpu_cap_drop_of({"conditions": None}), "")


class Dashboard(unittest.TestCase):
    CELLS = ("android litert-lm org/model long-context-1024-gen256 backend=gpu context-tokens=2048\n"
             "android litert-lm org/model long-context-1024-gen256 backend=cpu context-tokens=2048\n"
             "android llama.cpp org/gguf long-context-1024-gen256 context-tokens=2048\n"
             "android litert-lm org/other long-context-1024-gen256 backend=gpu context-tokens=2048 "
             "exclude=fixture-reason\n")

    def render(self, extra_cells="", extra_rows=()):
        rows = (session([25.7, 25.5, 26.0], [25.7, 26.1, 26.0], [OFF] * 3)
                + session([30.0, 30.0, 10.0], [31.0, 31.0, 9.0], ["PASS", "PASS", OFF], runtime="litert-lm-cpu")
                + [row(19.4, True, "", False, "llama.cpp", "org/gguf", m) for m in (40, 41, 42)]
                + session([5.0, 5.0, 5.0], [5.0, 5.0, 5.0], [OFF] * 3, model_id="org/other")
                + list(extra_rows))
        tmp = tempfile.TemporaryDirectory(prefix="render-rules-dashboard-")
        self.addCleanup(tmp.cleanup)
        summary = os.path.join(tmp.name, "device-runs.csv")
        with open(summary, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS + CPU_FIELDS + BACKEND_FIELDS + DROP_FIELDS)
            w.writeheader()
            w.writerows(rows)
        cells = os.path.join(tmp.name, "fixture.cells")
        with open(cells, "w") as fh:
            fh.write(self.CELLS + extra_cells)
        with patch.object(render_dashboard, "SUMMARY_CSV", summary), \
             patch.object(render_dashboard, "ROOT", tmp.name), \
             patch.object(render_dashboard_html, "SUMMARY_CSV", summary):
            out, _ = render_dashboard.build(cells, os.path.join(tmp.name, "no-schedule.json"), 10, TODAY)
            md = render_dashboard.render_md(out, cells, 10, TODAY)
            jcells = json.loads(json.dumps(out))
            history = render_dashboard_html.history_rows(jcells)
            page = render_dashboard_html.render(jcells, {}, "2026-10-06T00:00:00", 10, history, False, "")
        return {(c["arm"], c["model_id"]): c for c in out}, md, history, page

    def test_status_text_fail_and_the_partial_cell(self):
        out, md, history, page = self.render()
        gpu = out[("litert-lm-gpu", "org/model")]
        self.assertEqual(gpu["status"], "text-fail")
        self.assertEqual(gpu["reason"], "text check failed: text-off-task-screen (5 of 5 runs)")
        self.assertIsNone(gpu["decode_tps"])
        self.assertEqual((gpu["n"], gpu["text_fail"]), (0, "5/5"))
        self.assertEqual(gpu["campaign"], "results/raw/2026-10-06-fixture-android")
        cpu = out[("litert-lm-cpu", "org/model")]
        self.assertEqual((cpu["status"], cpu["decode_tps"], cpu["n"], cpu["text_fail"]),
                         ("measured", 30.0, 1, "2/5"))
        llama = out[("llama.cpp", "org/gguf")]
        self.assertEqual((llama["status"], llama["decode_tps"], llama["text_fail"]), ("measured", 19.4, ""))
        # an exclude= cell keeps its structural reason; the text rule never re-labels it
        self.assertEqual(out[("litert-lm-gpu", "org/other")]["status"], "excluded")

        self.assertIn("— (text check failed: text-off-task-screen (5 of 5 runs))", md)
        self.assertIn("2 of 4 cells measured, 1 excluded with a reason, 1 failed the text check", md)
        self.assertIn("text check failed: text-off-task-screen (5 of 5 runs)", page)
        self.assertNotIn("25.7", md.split("### ")[1].split("<details>")[0])   # the rate never shows
        # history: no row for the session the text check emptied, "k/N" on the kept one
        self.assertEqual({(h["arm"], h["model_id"]): h["text_fail"] for h in history},
                         {("litert-lm-cpu", "org/model"): "2/5", ("llama.cpp", "org/gguf"): ""})

    def test_every_run_cpu_capped_is_no_valid_run(self):
        # cpu-cap-rule, record -> summary column -> arm_row -> dashboard, in the shape of the
        # 2026-10-07 Pixel 8a: llama.cpp on the A715 cores (taskset f0), policy4 capped from
        # 2367 to 1418 MHz (a 40.1 % fall, past the line) in every run of the session -> no
        # valid run, never the rate
        record = {"conditions": {"cpuMaxFreqMHz": {"policy0": {"min": 1704, "hw": 1704, "cpus": "0-3"},
                                                    "policy4": {"min": 1418, "hw": 2367, "cpus": "4-7"}},
                                 "cpusAllowedList": "4-7", "protocolFlags": ["cpu-capped"]}}
        self.assertEqual(build_summary.cpu_cap_of(record), ("true", "p0 1704/1704 p4 1418/2367"))
        self.assertEqual(build_summary.cpu_cap_drop_of(record), "40.1")
        record["conditions"]["protocolFlags"] = []
        # caps read, no flag (the runner found no policy of the engine's CPUs below hw)
        self.assertEqual(build_summary.cpu_cap_of(record)[0], "false")
        self.assertEqual(build_summary.cpu_cap_of({"conditions": {"exitCode": 0}}), ("", ""))   # not read
        capped = [dict(row(v, True, "", False, "llama.cpp", "org/capped", m), cpu_capped="true",
                       cpu_max_freq="p0 1704/1704 p4 1418/2367 p8 2914/2914", cpu_cap_drop_pct="40.1")
                  for m, v in ((50, 3.3), (51, 3.6), (52, 2.9))]
        a = arm_row(capped)
        self.assertEqual((a["cold_median"], a["n"], a["cpu_capped_n"], a["cpu_capped_counted_n"],
                          a["cpu_read_n"]), (None, 0, 3, 0, 3))
        self.assertIsNone(a["prefill"])              # no metric of a capped run survives
        # a summary built before the line (no cpu_cap_drop_pct) keeps every flagged run out
        self.assertEqual(arm_row([{k: v for k, v in r.items() if k != "cpu_cap_drop_pct"}
                                  for r in capped]), a)
        out, md, history, page = self.render(
            "android llama.cpp org/capped long-context-1024-gen256 context-tokens=2048\n", capped)
        c = out[("llama.cpp", "org/capped")]
        self.assertEqual((c["status"], c["reason"], c["decode_tps"], c["n"], c["cpu_capped"],
                          c["cpu_capped_counted"]),
                         ("cpu-capped", "cpu-capped >15 % (3 of 3 runs)", None, 0, "3/3", "0/3"))
        self.assertEqual(c["campaign"], "results/raw/2026-10-06-fixture-android")   # the session stays the evidence
        grid = [ln for ln in md.split("<details>")[0].splitlines()
                if ln.startswith("| **") and "no valid run" in ln]
        self.assertEqual(len(grid), 1)
        self.assertIn("— (no valid run: cpu-capped >15 % (3 of 3 runs))", grid[0])
        self.assertFalse(any(v in grid[0] for v in ("3.3", "3.6", "2.9")))   # the rate never shows
        self.assertIn("2 of 5 cells measured, 1 excluded with a reason, 1 failed the text check, "
                      "1 had no valid run (cpu-capped >15 %)", md)
        self.assertIn("no valid run: cpu-capped &gt;15 % (3 of 3 runs)", page)
        self.assertNotIn(("llama.cpp", "org/capped"), {(h["arm"], h["model_id"]) for h in history})
        # the cells without a capped run read as before
        self.assertEqual(out[("litert-lm-gpu", "org/model")]["status"], "text-fail")
        self.assertEqual(out[("litert-lm-cpu", "org/model")]["cpu_capped"], "")

    def test_a_cap_within_the_line_pools_marked(self):
        # the line (render_leaderboard.CPU_CAP_MAX_DROP_PCT, 15): the Galaxy S26 Qwen3 1.7B
        # short-chat runs of 2026-10-08, the prime cluster capped 11.7-14.2 % -> the three
        # runs pool and the number carries the count; the boundary itself counts
        self.assertEqual(render_leaderboard.CPU_CAP_MAX_DROP_PCT, 15)
        shallow = [dict(row(v, True, "", False, "onnxruntime-genai-cpu", "org/shallow", m),
                        cpu_capped="true", cpu_max_freq=f"p0 3628.8/3628.8 p6 {low}/4742.4",
                        cpu_cap_drop_pct=drop, task="short-chat", context_tokens="2048")
                   for m, v, low, drop in ((53, 41.4, 4070.4, "14.2"), (54, 41.9, 4185.6, "11.7"),
                                           (55, 41.1, 4070.4, "15.0"))]
        a = arm_row(shallow)
        self.assertEqual((a["cold_median"], a["cold_n"], a["cpu_capped_n"], a["cpu_capped_counted_n"],
                          a["cpu_read_n"]), (41.4, 3, 0, 3, 3))
        # one run past the line leaves the pool; the other two stay, counted
        mixed = [dict(r) for r in shallow]
        mixed[2]["cpu_cap_drop_pct"] = "15.1"
        b = arm_row(mixed)
        self.assertEqual((b["cold_median"], b["cold_n"], b["cpu_capped_n"], b["cpu_capped_counted_n"]),
                         (41.65, 2, 1, 2))
        cells = ("android onnxruntime-genai org/shallow short-chat backend=cpu context-tokens=2048\n"
                 "android onnxruntime-genai org/mixed short-chat backend=cpu context-tokens=2048\n")
        mixed = [dict(r, model_id="org/mixed") for r in mixed]
        out, md, history, page = self.render(cells, shallow + mixed)
        c = out[("onnxruntime-genai-cpu", "org/shallow")]
        self.assertEqual((c["status"], c["decode_tps"], c["n"], c["cpu_capped"], c["cpu_capped_counted"]),
                         ("measured", 41.4, 3, "0/3", "3/3"))
        m = out[("onnxruntime-genai-cpu", "org/mixed")]
        self.assertEqual((m["status"], m["decode_tps"], m["n"], m["cpu_capped"], m["cpu_capped_counted"]),
                         ("measured", 41.65, 2, "1/3", "2/3"))
        self.assertEqual(render_dashboard.cap_mark(c), "◇ cpu-capped ≤15 % (3 of 3 runs)")
        grid = "\n".join(ln for ln in md.split("### `short-chat`")[1].split("<details>")[0].splitlines()
                         if ln.startswith("| **"))
        self.assertIn("| 41.4 ◇ cpu-capped ≤15 % (3 of 3 runs) |", grid)
        self.assertIn("| 41.6 ◇ cpu-capped ≤15 % (2 of 3 runs) |", grid)
        self.assertIn("4 of 6 cells measured (2 with runs cpu-capped ≤15 %, ◇), 1 excluded with a reason, "
                      "1 failed the text check", md)
        self.assertIn("◇ cpu-capped ≤15 % (3 of 3 runs)", page)
        self.assertIn("4 of 6 cells measured (2 with runs cpu-capped ≤15 %, ◇)", page)
        hist = {h["model_id"]: h["cpu_capped_counted"] for h in history if h["arm"] == "onnxruntime-genai-cpu"}
        self.assertEqual(hist, {"org/shallow": "3/3", "org/mixed": "2/3"})
        # a cell whose runs were read uncapped carries no mark
        self.assertEqual(render_dashboard.cap_mark(dict(c, cpu_capped_counted="0/3")), "")

    def test_an_accelerator_arm_counts_a_deep_cap(self):
        # the accelerator arms (owner decision 2026-10-08, render_leaderboard.CPU_CAP_EXEMPT_ARMS):
        # a Galaxy S26 llama.cpp NPU cell whose three runs fell as the arm's protocol launches
        # of 2026-10-08 did, both clusters capped past the line (53.0-58.3 %) -> the three runs
        # pool, counted, and the number carries the largest drop; the arm decides, not the row
        npu = [dict(row(v, True, "PASS", False, "llama.cpp-npu", "org/gguf", m), cpu_capped="true",
                    cpu_max_freq=f"p0 2227.2/3628.8 p6 {low}/4742.4", cpu_cap_drop_pct=drop,
                    backend_registered="true")
               for m, v, low, drop in ((56, 50.0, 2227.2, "53.0"), (57, 51.0, 1977.6, "58.3"),
                                       (58, 49.0, 2227.2, "53.0"))]
        a = arm_row(npu)
        self.assertEqual((a["cold_median"], a["cold_n"], a["cpu_capped_n"], a["cpu_capped_counted_n"],
                          a["cpu_read_n"]), (50.0, 3, 0, 3, 3))
        self.assertEqual(a["cpu_capped_counted_max_drop"], 58.3)
        self.assertTrue(render_leaderboard.shallow_cap(npu[1]))
        self.assertFalse(render_leaderboard.shallow_cap(npu[1], arm="llama.cpp"))   # the CPU arm keeps the line
        self.assertTrue(render_leaderboard.shallow_cap({k: v for k, v in npu[1].items() if k != "runtime"},
                                                       arm="llama.cpp-gpu"))
        self.assertFalse(render_leaderboard.shallow_cap(dict(npu[1], cpu_capped="false")))
        # a summary built before the drop column: the flagged runs still count, the drop unknown
        old = arm_row([{k: v for k, v in r.items() if k != "cpu_cap_drop_pct"} for r in npu])
        self.assertEqual((old["cold_n"], old["cpu_capped_counted_n"], old["cpu_capped_counted_max_drop"]),
                         (3, 3, None))
        cells = ("android llama.cpp org/gguf long-context-1024-gen256 backend=npu "
                 "engine-build=b11469-snapdragon context-tokens=2048\n")
        out, md, history, page = self.render(cells, npu)
        c = out[("llama.cpp-npu", "org/gguf")]
        self.assertEqual((c["status"], c["decode_tps"], c["n"], c["cpu_capped"], c["cpu_capped_counted"],
                          c["cpu_capped_counted_max_drop"]), ("measured", 50.0, 3, "0/3", "3/3", 58.3))
        mark = "◇ cpu-capped, counted (accelerator arm), max drop 58.3 % (3 of 3 runs)"
        self.assertEqual(render_dashboard.cap_mark(c), mark)
        self.assertEqual(render_dashboard.cap_mark(dict(c, cpu_capped_counted_max_drop=None)),
                         "◇ cpu-capped, counted (accelerator arm), max drop not recorded (3 of 3 runs)")
        grid = "\n".join(ln for ln in md.split("<details>")[0].splitlines() if ln.startswith("| **"))
        self.assertIn(f"| 50.0 {mark} |", grid)
        self.assertIn("3 of 5 cells measured (1 with runs cpu-capped on an accelerator arm, counted, ◇), "
                      "1 excluded with a reason, 1 failed the text check", md)
        self.assertIn(mark, page)
        self.assertIn("3 of 5 cells measured (1 with runs cpu-capped on an accelerator arm, counted, ◇)", page)
        self.assertEqual({h["model_id"]: h["cpu_capped_counted"] for h in history if h["arm"] == "llama.cpp-npu"},
                         {"org/gguf": "3/3"})

    def test_an_apple_cpu_row_is_the_cpu_arm(self):
        # Mac and iPhone LiteRT-LM rows with backend=cpu are the litert-lm-cpu arm (the records'
        # stamp); without backend= they stay the bare GPU arm (2026-10-19: the iOS branch was missing).
        # An iOS ynnpack=1 CPU row stamps litert-lm-cpu-ynnpack (run_ddp_ios_lm.lay_out) so it never
        # pools with XNNPACK CPU runs.
        for plat in ("mac", "ios"):
            self.assertEqual(render_dashboard.arm_of(plat, "litert-lm", {"backend": "cpu"}), "litert-lm-cpu")
            self.assertEqual(render_dashboard.arm_of(plat, "litert-lm", {}), "litert-lm")
        self.assertEqual(
            render_dashboard.arm_of("ios", "litert-lm", {"backend": "cpu", "ynnpack": "1"}),
            "litert-lm-cpu-ynnpack",
        )

    def test_a_cpu_arm_keeps_the_line(self):
        # the exemption is a list of arm names (render_leaderboard.CPU_CAP_EXEMPT_ARMS): the arms an
        # Android cells row names for an NPU or GPU backend, and no CPU arm -> a CPU arm's run
        # capped 50 % stays out of every pool, as before
        exempt = render_leaderboard.CPU_CAP_EXEMPT_ARMS
        accel = {render_dashboard.arm_of("android", rt, {"backend": b})
                 for rt, b in (("llama.cpp", "npu"), ("llama.cpp", "gpu"), ("litert-lm", "npu"),
                               ("litert-lm", "gpu"), ("executorch", "vulkan"), ("executorch", "qnn"))}
        self.assertEqual(set(exempt), accel)
        cpu_arms = {render_dashboard.arm_of("android", rt, opts)
                    for rt, opts in (("llama.cpp", {}), ("litert-lm", {"backend": "cpu"}),
                                     ("executorch", {"backend": "xnnpack"}),
                                     ("onnxruntime-genai", {"backend": "cpu"}))} | {"litert-cpu"}
        self.assertEqual(cpu_arms, {"llama.cpp", "litert-lm-cpu", "executorch-xnnpack",
                                    "onnxruntime-genai-cpu", "litert-cpu"})
        self.assertFalse(cpu_arms & exempt)
        for arm in sorted(cpu_arms):
            capped = [dict(row(v, True, "", False, arm, "org/cpu", m), cpu_capped="true",
                           cpu_max_freq="p0 1814.4/3628.8 p6 2371.2/4742.4", cpu_cap_drop_pct="50.0")
                      for m, v in ((60, 3.3), (61, 3.6), (62, 2.9))]
            a = arm_row(capped)
            self.assertEqual((a["cold_median"], a["cold_n"], a["cpu_capped_n"], a["cpu_capped_counted_n"],
                              a["cpu_capped_counted_max_drop"]), (None, 0, 3, 0, None), arm)

    def test_csv_carries_the_status_and_the_column(self):
        out, md, _, _ = self.render()
        with tempfile.TemporaryDirectory(prefix="render-rules-csv-") as tmp:
            render_dashboard.write_outputs(list(out.values()), md, os.path.join(tmp, "D.md"), tmp)
            with open(os.path.join(tmp, "dashboard-v1.csv"), newline="") as fh:
                got = {(r["arm"], r["model_id"]): r for r in csv.DictReader(fh)}
        # appended last: the text-check and CPU-cap counts, then (2026-10-08) a protocol cell's cold_tps
        self.assertEqual(render_dashboard.CSV_FIELDS[-4:], ["text_fail", "cpu_capped", "cpu_capped_counted", "cold_tps"])
        self.assertEqual(got[("litert-lm-gpu", "org/model")]["status"], "text-fail")
        self.assertEqual(got[("litert-lm-gpu", "org/model")]["decode_tps"], "")
        self.assertEqual(got[("litert-lm-cpu", "org/model")]["text_fail"], "2/5")


class SideBuild(unittest.TestCase):
    """A llama.cpp side build on the NPU / GPU (arms llama.cpp-npu / llama.cpp-gpu): the
    summary's backend_registered column, arm_row leaving a run whose device lines did not
    show the cell's device out of every pool, and the dashboard reading the npu cell from
    its own arm's rows — never the CPU arm's, whose cells row has no backend=."""

    def test_backend_registered_column_pool_and_cell(self):
        flagged = {"conditions": {"backendRegistered": [], "protocolFlags": ["backend-not-registered"]}}
        shown = {"conditions": {"backendRegistered": ["load_tensors: offloaded 29/29 layers to GPU"]}}
        self.assertEqual([build_summary.backend_registered_of(r) for r in (flagged, shown, {"conditions": {}}, {})],
                         ["false", "true", "", ""])
        npu = [dict(row(v, True, "PASS", False, "llama.cpp-npu", "org/gguf", m), backend_registered=b,
                    task="short-chat", context_tokens="")
               for m, v, b in ((60, 73.1, "true"), (61, 20.0, "false"), (62, 74.9, "true"))]
        a = arm_row(npu)
        self.assertEqual((a["cold_median"], a["cold_n"], a["n"], a["backend_off_n"]), (74.0, 2, 2, 1))
        b = arm_row(npu[:1] + npu[2:])   # the same session without the flagged run: the same pool
        pool = ("cold_median", "cold_n", "cold_spread", "n", "prefill", "ttft", "mem", "mem_peak")
        self.assertEqual({k: a[k] for k in pool}, {k: b[k] for k in pool})
        cpu = [dict(row(v, True, "", False, "llama.cpp", "org/gguf", m), task="short-chat", context_tokens="",
                    backend_registered="") for m, v in ((70, 30.0), (71, 31.0))]
        with tempfile.TemporaryDirectory(prefix="render-rules-side-") as tmp:
            summary = os.path.join(tmp, "device-runs.csv")
            with open(summary, "w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=FIELDS + CPU_FIELDS + BACKEND_FIELDS, extrasaction="ignore")
                w.writeheader()
                w.writerows(npu + cpu)
            cells = os.path.join(tmp, "fixture.cells")
            with open(cells, "w") as fh:
                fh.write("android llama.cpp org/gguf short-chat\n"
                         "android llama.cpp org/gguf short-chat backend=npu engine-build=b11469-snapdragon\n"
                         "android llama.cpp org/gguf short-chat backend=gpu engine-build=b11469-snapdragon\n")
            with patch.object(render_dashboard, "SUMMARY_CSV", summary), \
                 patch.object(render_dashboard, "ROOT", tmp):
                out, _ = render_dashboard.build(cells, os.path.join(tmp, "no-schedule.json"), 10, TODAY)
        got = {c["arm"]: (c["status"], c["decode_tps"], c["n"]) for c in out}
        self.assertEqual(got, {"llama.cpp": ("measured", 30.5, 2), "llama.cpp-npu": ("measured", 74.0, 2),
                               "llama.cpp-gpu": ("missing", None, 0)})



class ExecuTorchArm(unittest.TestCase):
    """executorch rows: backend= is the arm (executorch-<backend>) for the Android runner,
    the campaign driver and the dashboard alike; validate_cells keeps a row to an own export
    with its delegate, recipe alias and the export's allocation."""

    ROW = ("{plat} executorch own-export/Qwen3-0.6B-ET1.5.1-xnnpack-8da4w-emb8-ctx2048 {task} "
           "backend={backend} local=1 file=Qwen3-0.6B-ET1.5.1-xnnpack-8da4w-emb8-ctx2048.pte "
           "recipe=et1.5.1-xnnpack-8da4w-g128-emb8{extra}\n")

    def cells(self, text):
        tmp = tempfile.TemporaryDirectory(prefix="render-rules-et-")
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "et.cells")
        with open(path, "w") as fh:
            fh.write(text)
        return path, tmp.name

    def test_the_arm_carries_the_delegate(self):
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                        "android", "bench"))
        import run_campaign
        import run_cell
        for plat in ("android", "mac", "ios"):
            self.assertEqual(render_dashboard.arm_of(plat, "executorch", {"backend": "xnnpack"}), "executorch-xnnpack")
        self.assertEqual(render_dashboard.arm_of("android", "executorch", {"backend": "vulkan"}), "executorch-vulkan")
        self.assertEqual(run_cell.arm_name("executorch", "xnnpack"), "executorch-xnnpack")
        self.assertEqual(run_campaign.arm_of({"runtime": "executorch", "opts": {"backend": "qnn"}}), "executorch-qnn")
        self.assertTrue(run_cell.capture_stem("executorch", "xnnpack", "own-export/m", "short-chat")
                        .startswith("executorch-xnnpack_own-export_m_short-chat"))
        # the other runtimes' arms read as before
        self.assertEqual(render_dashboard.arm_of("mac", "litert-lm", {"backend": "gpu"}), "litert-lm")
        self.assertEqual(render_dashboard.arm_of("android", "llama.cpp", {}), "llama.cpp")

    def test_validate_cells_rows(self):
        good = (self.ROW.format(plat="android", task="short-chat", backend="xnnpack", extra="")
                + self.ROW.format(plat="android", task="long-context-1024-gen256", backend="xnnpack",
                                  extra=" context-tokens=2048")
                + self.ROW.format(plat="mac", task="short-chat", backend="xnnpack", extra=" runs=4")
                + self.ROW.format(plat="ios", task="short-chat", backend="xnnpack",
                                  extra=" context-tokens=2048 runs=4"))
        path, _ = self.cells(good)
        self.assertEqual(validate_cells.validate_file(path), ([], []))
        bad = {
            self.ROW.format(plat="android", task="short-chat", backend="gpu", extra=""): "backend=<qnn|vulkan|xnnpack>",
            self.ROW.format(plat="mac", task="short-chat", backend="vulkan", extra=""): "backend=<coreml|metal|mlx|xnnpack>",
            # the iPhone app links XNNPACK (project-executorch.yml; the lab build
            # project-ddp-executorch.yml also MLX) and records the cell's context-tokens= as the
            # run's allocation
            self.ROW.format(plat="ios", task="short-chat", backend="coreml", extra=" context-tokens=2048"):
                "backend=<mlx|xnnpack>",
            self.ROW.format(plat="ios", task="short-chat", backend="xnnpack", extra=""):
                "an ios executorch row needs context-tokens=",
            self.ROW.format(plat="ios", task="short-chat", backend="xnnpack", extra=" context-tokens=2048 runs=1"):
                "runs>=2",
            self.ROW.format(plat="android", task="long-context-1024-gen256", backend="xnnpack", extra=""):
                "needs context-tokens=",
            self.ROW.format(plat="android", task="long-context-1024-gen256", backend="xnnpack",
                            extra=" context-tokens=4096"): "the export allocates 2048",
            self.ROW.format(plat="mac", task="short-chat", backend="xnnpack", extra=" runs=1"): "runs>=2",
            self.ROW.format(plat="android", task="short-chat", backend="xnnpack", extra="").replace(
                "recipe=et1.5.1-xnnpack-8da4w-g128-emb8", "recipe=int4"): "not a bare bit width",
            self.ROW.format(plat="android", task="short-chat", backend="xnnpack", extra="").replace(
                " local=1", ""): "local=1 file=<name>.pte",
        }
        for line, want in bad.items():
            path, _ = self.cells(line)
            errors, _ = validate_cells.validate_file(path)
            self.assertTrue(any(want in e for e in errors), f"{want!r} not in {errors} for {line.strip()}")

    def test_the_dashboard_reads_the_arms_rows(self):
        mid = "own-export/Qwen3-0.6B-ET1.5.1-xnnpack-8da4w-emb8-ctx2048"
        et = [dict(row(v, True, "PASS", False, "executorch-xnnpack", mid, m), task="short-chat")
              for m, v in ((80, 124.5), (81, 135.0), (82, 120.0))]
        other = [dict(row(30.0, True, "PASS", False, "executorch-vulkan", mid, 83), task="short-chat")]
        path, tmp = self.cells(self.ROW.format(plat="android", task="short-chat", backend="xnnpack", extra="")
                               + self.ROW.format(plat="android", task="short-chat", backend="qnn", extra=""))
        summary = os.path.join(tmp, "device-runs.csv")
        with open(summary, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS + CPU_FIELDS)
            w.writeheader()
            w.writerows(et + other)
        with patch.object(render_dashboard, "SUMMARY_CSV", summary), patch.object(render_dashboard, "ROOT", tmp):
            out, _ = render_dashboard.build(path, os.path.join(tmp, "no-schedule.json"), 10, TODAY)
        got = {c["arm"]: (c["status"], c["decode_tps"], c["n"]) for c in out}
        self.assertEqual(got, {"executorch-xnnpack": ("measured", 124.5, 3), "executorch-qnn": ("missing", None, 0)})


class ProtocolRegime(unittest.TestCase):
    """A protocol cell (native-benchmark-*: one launch of an engine's own benchmark entry, its first
    call cold, the rest warm) headlines the agreed protocol's regime on every platform and for
    every arm: the warm median where its session has warm runs, the cold median only where it has
    none (render_dashboard.headline_regime); a warm protocol cell carries its cold first-call median
    beside it (cold_tps). A text-task cell keeps its platform's regime."""

    CELLS = ("mac core-ai core-ai/m-stock-ctx2048 native-benchmark-1024x256 backend=ane context-tokens=2048\n"
             "mac litert-lm org/model native-benchmark-1024x256 context-tokens=2048\n"
             "mac litert-lm org/model long-context-1024-gen256 context-tokens=2048\n"
             "android llama.cpp org/gguf native-benchmark-1024x256\n"
             "android litert-lm org/model native-benchmark-1024x256 backend=gpu context-tokens=2048\n"
             "android litert-lm org/model long-context-1024-gen256 backend=gpu context-tokens=2048\n")

    @staticmethod
    def prow(decode, cold, plat, runtime, model_id, minute, task="native-benchmark-1024x256"):
        r = row(decode, cold, "", False, runtime, model_id, minute,
                campaign=f"results/raw/2026-10-08-fixture-{plat}")
        r.update(platform=plat, task=task, device=f"FIXTURE-{plat.upper()}")
        return r

    def test_headline_regime(self):
        hr = render_dashboard.headline_regime
        both, cold_only, warm_only = {"warm_n": 3, "cold_n": 1}, {"warm_n": 0, "cold_n": 2}, {"warm_n": 3, "cold_n": 0}
        for plat in ("mac", "ios", "android"):
            self.assertEqual(hr(plat, "native-benchmark-1024x256", both), "warm")
            self.assertEqual(hr(plat, "native-benchmark-1024x256", warm_only), "warm")
            self.assertEqual(hr(plat, "native-benchmark-1024x256", cold_only), "cold")
        # a text task reads its platform's regime whatever its pools hold
        self.assertEqual(hr("android", "long-context-1024-gen256", both), "cold")
        self.assertEqual(hr("mac", "long-context-1024-gen256", cold_only), "warm")

    def test_the_dashboard_reads_protocol_cells_by_the_rule(self):
        p = self.prow
        rows = ([p(50.9, True, "mac", "core-ai-ane", "core-ai/m-stock-ctx2048", 0)]       # trial 0
                + [p(v, False, "mac", "core-ai-ane", "core-ai/m-stock-ctx2048", m)          # trials 1..3
                   for m, v in ((1, 51.8), (2, 52.0), (3, 51.9))]
                # an older sitting: one benchmark() call per launch, every record cold
                + [p(v, True, "mac", "litert-lm", "org/model", m) for m, v in ((10, 60.0), (11, 62.0))]
                + [p(v, m == 20, "mac", "litert-lm", "org/model", m, "long-context-1024-gen256")
                   for m, v in ((20, 40.0), (21, 44.0), (22, 45.0), (23, 46.0))]
                # llama-bench: in-process repeats, recorded warm
                + [p(v, False, "android", "llama.cpp", "org/gguf", m) for m, v in ((30, 20.0), (31, 21.0))]
                # one launch with --runs 3: call 1 cold, calls 2..3 warm
                + [p(v, m == 40, "android", "litert-lm-gpu", "org/model", m)
                   for m, v in ((40, 30.0), (41, 33.0), (42, 34.0))]
                + [p(v, m == 50, "android", "litert-lm-gpu", "org/model", m, "long-context-1024-gen256")
                   for m, v in ((50, 25.0), (51, 28.0))])
        tmp = tempfile.TemporaryDirectory(prefix="render-rules-protocol-")
        self.addCleanup(tmp.cleanup)
        summary = os.path.join(tmp.name, "device-runs.csv")
        with open(summary, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS + CPU_FIELDS + BACKEND_FIELDS + DROP_FIELDS)
            w.writeheader()
            w.writerows(rows)
        cells = os.path.join(tmp.name, "fixture.cells")
        with open(cells, "w") as fh:
            fh.write(self.CELLS)
        with patch.object(render_dashboard, "SUMMARY_CSV", summary), \
             patch.object(render_dashboard, "ROOT", tmp.name):
            out, _ = render_dashboard.build(cells, os.path.join(tmp.name, "no-schedule.json"), 10, TODAY)
            md = render_dashboard.render_md(out, cells, 10, TODAY)
        got = {(c["platform"], c["arm"], c["task"][:6]): (c["regime"], c["decode_tps"], c["n"], c["cold_tps"])
               for c in out}
        self.assertEqual(got, {
            # warm trials 1..3, the cold trial 0 beside them
            ("mac", "core-ai-ane", "native"): ("warm", 51.9, 3, 50.9),
            # no warm run in the session: the cold median, nothing beside it
            ("mac", "litert-lm", "native"): ("cold", 61.0, 2, None),
            ("mac", "litert-lm", "long-c"): ("warm", 45.0, 3, None),
            ("android", "llama.cpp", "native"): ("warm", 20.5, 2, None),
            ("android", "litert-lm-gpu", "native"): ("warm", 33.5, 2, 30.0),
            ("android", "litert-lm-gpu", "long-c"): ("cold", 25.0, 1, None),
        })
        # the grid says when a cell reads another regime than its device's header
        grid = md.split("<details>")
        self.assertIn("| 61.0 (cold) |", grid[0])
        self.assertTrue(any("20.5 (warm)" in g for g in grid))
        self.assertTrue(any("51.9 (cold first call 50.9)" in g for g in grid))


class CliAndUpstreamAdditions(unittest.TestCase):
    """CLI flags (--raw-dir, --out-dir, --summary-csv, --cells, --include-cpu-capped) and
    Windows matrix / cells validation."""

    def test_build_summary_cli_raw_dir_out_dir_and_windows(self):
        with tempfile.TemporaryDirectory(prefix="render-rules-cli-") as tmp:
            # 1) Empty raw dir produces a header-only device-runs.csv matching DEVICE_FIELDS
            empty_raw = os.path.join(tmp, "empty-raw")
            empty_out = os.path.join(tmp, "empty-out")
            os.makedirs(empty_raw)
            with patch.object(build_summary, "ROOT", tmp):
                self.assertIsNone(build_summary.main(["--raw-dir", empty_raw, "--out-dir", empty_out]))
            with open(os.path.join(empty_out, "device-runs.csv"), newline="") as fh:
                reader = csv.reader(fh)
                self.assertEqual(next(reader), build_summary.DEVICE_FIELDS)
                self.assertEqual(list(reader), [])

            # 2) Two-level --raw-dir (repeatable per parent) reads <raw-dir>/<campaign>/*.jsonl and
            #    app-path*/device-jsonl JSONs while ignoring deeper .jsonl files (e.g. DDP collections).
            raw_root = os.path.join(tmp, "custom-raw")
            win_root = os.path.join(raw_root, "qwen3.5", "windows")
            and_root = os.path.join(raw_root, "qwen3.5", "android")
            win_camp = os.path.join(win_root, "2026-10-29-windows")
            and_camp = os.path.join(and_root, "2026-10-29-android", "app-path-android")
            os.makedirs(os.path.join(win_camp, "ddp"))
            os.makedirs(and_camp)
            with open(os.path.join(win_camp, "ddp", "collection.jsonl"), "w") as fh:
                fh.write(json.dumps({
                    "id": "ddp-col-1", "model": "string-model", "device": "string-device",
                    "metrics": {"decodeTokensPerSecond": 999.0},
                }) + "\n")
            with open(os.path.join(win_camp, "litert-lm-gpu_org_model_short-chat.jsonl"), "w") as fh:
                fh.write(json.dumps({
                    "schemaVersion": 1, "id": "win-rec-1", "runtime": "litert-lm-gpu",
                    "engineVersion": "21f113ea6eba", "timestamp": "2026-10-29T10:00:00Z",
                    "task": "short-chat", "model": {"id": "org/model", "quantization": "wi4b32_afp32"},
                    "device": {"systemName": "Windows", "modelIdentifier": "Precision 7960"},
                    "conditions": {"contextTokens": 2048, "textCheck": {"status": "PASS", "flags": []}},
                    "metrics": {"decodeTokensPerSecond": 182.5, "promptTokensPerSecond": 1400.0,
                                "firstTokenLatencyMS": 35.0, "memoryPeakResidentMB": 910.0, "coldRun": True},
                }) + "\n")
            with open(os.path.join(and_camp, "r1.json"), "w") as fh:
                json.dump({
                    "schemaVersion": 1, "id": "and-rec-1", "runtime": "litert-lm-cpu-ynnpack",
                    "engineVersion": "21f113ea6eba", "timestamp": "2026-10-29T10:05:00Z",
                    "task": "short-chat", "model": {"id": "org/model", "quantization": "wi4b32_afp32"},
                    "device": {"systemName": "Android", "modelIdentifier": "SM-S942U",
                               "ddp": {"deviceId": "m1q-36"}},
                    "conditions": {"contextTokens": 2048, "protocolFlags": ["cpu-capped"],
                                   "cpuMaxFreqMHz": {"policy6": {"min": 3100, "hw": 4742, "cpus": "6-7"}},
                                   "cpusAllowedList": "6-7",
                                   "textCheck": {"status": "PASS", "flags": []}},
                    "metrics": {"decodeTokensPerSecond": 29.4, "coldRun": True},
                }, fh)
            out_dir = os.path.join(tmp, "custom-summary")
            with patch.object(build_summary, "ROOT", tmp):
                build_summary.main(["--raw-dir", win_root, "--raw-dir", and_root, "--out-dir", out_dir])
            with open(os.path.join(out_dir, "device-runs.csv"), newline="") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), 2)
            got = {r["platform"]: r for r in rows}
            self.assertEqual(set(got), {"windows", "android"})
            self.assertEqual(got["windows"]["device"], "Precision 7960")
            self.assertEqual(got["windows"]["campaign"], "2026-10-29-windows")
            self.assertEqual(got["android"]["campaign"], "2026-10-29-android")
            self.assertEqual(got["android"]["cpu_cap_drop_pct"], "34.6")

    def test_include_cpu_capped_pools_deep_cpu_cap_with_warning_badge(self):
        # Shared DDP Galaxy S26 (m1q-36) CPU arm capped 40.1% (>15%):
        # default excludes all 3 runs; --include-cpu-capped pools them with an explicit ⚠ badge.
        capped = [dict(row(v, True, "PASS", False, "litert-lm-cpu-ynnpack", "org/model", m),
                       cpu_capped="true", cpu_max_freq="p0 1704/1704 p4 1418/2367",
                       cpu_cap_drop_pct="40.1", task="short-chat", context_tokens="2048")
                  for m, v in ((10, 31.2), (11, 32.0), (12, 30.8))]
        with tempfile.TemporaryDirectory(prefix="render-rules-inccap-") as tmp:
            summary = os.path.join(tmp, "device-runs.csv")
            with open(summary, "w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=FIELDS + CPU_FIELDS + BACKEND_FIELDS + DROP_FIELDS)
                w.writeheader()
                w.writerows(capped)
            cells = os.path.join(tmp, "ddp.cells")
            with open(cells, "w") as fh:
                fh.write("android litert-lm org/model short-chat backend=cpu ynnpack=1 "
                         "engine-build=side context-tokens=2048\n")
            no_sched = os.path.join(tmp, "no-schedule.json")

            # Default: excluded under cpu-cap-rule, and CSV headers match main byte-for-byte
            def_dir = os.path.join(tmp, "dash-def")
            self.assertEqual(render_dashboard.main([
                "--cells", cells, "--summary-csv", summary, "--raw-dir", tmp,
                "--schedule", no_sched, "--md", os.path.join(def_dir, "DASHBOARD.md"),
                "--out-dir", def_dir,
            ]), 0)
            out_def = json.load(open(os.path.join(def_dir, "dashboard-v1.json")))["cells"]
            self.assertEqual(out_def[0]["status"], "cpu-capped")
            self.assertIsNone(out_def[0]["decode_tps"])
            with open(os.path.join(def_dir, "dashboard-v1.csv"), newline="") as fh:
                self.assertEqual(next(csv.reader(fh)), render_dashboard.CSV_FIELDS)
            self.assertEqual(render_dashboard_html.main([
                "--json", os.path.join(def_dir, "dashboard-v1.json"),
                "--summary-csv", summary, "--raw-dir", tmp,
                "--out", os.path.join(def_dir, "dashboard-v1.html"),
                "--history", os.path.join(def_dir, "dashboard-v1-history.csv"),
            ]), 0)
            with open(os.path.join(def_dir, "dashboard-v1-history.csv"), newline="") as fh:
                self.assertEqual(next(csv.reader(fh)), render_dashboard_html.HISTORY_FIELDS)

            # Opt-in --include-cpu-capped via CLI: render_dashboard -> render_dashboard_html
            out_dir = os.path.join(tmp, "dash")
            md_path = os.path.join(out_dir, "DASHBOARD.md")
            html_path = os.path.join(out_dir, "dashboard-v1.html")
            hist_path = os.path.join(out_dir, "dashboard-v1-history.csv")
            self.assertEqual(render_dashboard.main([
                "--cells", cells, "--summary-csv", summary, "--raw-dir", tmp,
                "--schedule", no_sched, "--md", md_path, "--out-dir", out_dir,
                "--include-cpu-capped",
            ]), 0)
            payload = json.load(open(os.path.join(out_dir, "dashboard-v1.json")))
            self.assertTrue(payload.get("include_cpu_capped"))
            c = payload["cells"][0]
            self.assertEqual((c["status"], c["decode_tps"], c["n"], c["cpu_capped_counted"]),
                             ("measured", 31.2, 3, "3/3"))
            want_mark = "⚠ cpu-capped >15 %, counted (--include-cpu-capped), max drop 40.1 % (3 of 3 runs)"
            self.assertEqual(render_dashboard.cap_mark(c), want_mark)
            dash_csv = list(csv.DictReader(open(os.path.join(out_dir, "dashboard-v1.csv"), newline="")))
            self.assertEqual(dash_csv[0]["cpu_capped_counted_max_drop"], "40.1")

            md = open(md_path).read()
            self.assertIn(want_mark, md)
            self.assertIn("`--include-cpu-capped` active", md)
            self.assertIn("1 with runs cpu-capped >15 % on a CPU arm, counted (--include-cpu-capped, ⚠)", md)

            self.assertEqual(render_dashboard_html.main([
                "--json", os.path.join(out_dir, "dashboard-v1.json"),
                "--summary-csv", summary, "--raw-dir", tmp,
                "--out", html_path, "--history", hist_path,
            ]), 0)
            page = open(html_path).read()
            self.assertIn("--include-cpu-capped active", page)
            self.assertIn("flag warn\">cpu-capped &gt;15 %, counted (--include-cpu-capped), max drop 40.1 % (3 of 3 runs)",
                          page)
            hist = list(csv.DictReader(open(hist_path, newline="")))
            self.assertEqual(len(hist), 1)
            self.assertEqual(
                (hist[0]["arm"], hist[0]["decode_tps"], hist[0]["cpu_capped_counted"],
                 hist[0]["cpu_capped_counted_max_drop"]),
                ("litert-lm-cpu-ynnpack", "31.2", "3/3", "40.1"),
            )

    def test_validate_windows_cells(self):
        good = (
            "windows litert-lm org/model short-chat backend=cpu ynnpack=1 context-tokens=2048\n"
            "windows litert-lm org/model long-context-1024-gen256 backend=gpu context-tokens=2048\n"
            "windows llama.cpp org/gguf short-chat context-tokens=2048\n"
            "windows llama.cpp org/gguf long-context-1024-gen256 backend=gpu context-tokens=2048\n"
            "windows llama.cpp org/gguf short-chat backend=cuda context-tokens=2048\n"
            # one GPU row on each GPU: two cells (the adapter is part of the cell's identity), not a duplicate
            "windows litert-lm org/model short-chat backend=gpu context-tokens=2048\n"
            "windows litert-lm org/model short-chat backend=gpu adapter=igpu context-tokens=2048\n"
        )
        with tempfile.TemporaryDirectory(prefix="render-rules-wincells-") as tmp:
            p = os.path.join(tmp, "win.cells")
            with open(p, "w") as fh:
                fh.write(good)
            # windows rows are exempt from --catalog just like android rows
            self.assertEqual(validate_cells.validate_file(p, catalog={"litert-lm": [], "llama.cpp": []}),
                             ([], []))
            bad = {
                "windows mlx-swift org/model short-chat context-tokens=2048\n":
                    "windows v1 rows are litert-lm or llama.cpp",
                "windows litert-lm org/model short-chat context-tokens=2048\n":
                    "windows litert-lm needs backend=cpu|gpu",
                "windows llama.cpp org/gguf short-chat backend=cpu context-tokens=2048\n":
                    "windows llama.cpp takes no backend= (CPU), backend=gpu (the Vulkan asset) or backend=cuda",
                "windows litert-lm org/model short-chat backend=cuda context-tokens=2048\n":
                    "backend='cuda' (want cpu|gpu|npu)",
                "android llama.cpp org/gguf short-chat backend=cuda engine-build=b1\n":
                    "backend='cuda' (want cpu|gpu|npu)",
                "windows litert-lm org/model short-chat backend=gpu ynnpack=1 context-tokens=2048\n":
                    "ynnpack= is read for android litert-lm rows and mac / ios / windows litert-lm backend=cpu rows only",
                "windows litert-lm org/model short-chat backend=gpu\n":
                    "windows rows need context-tokens=",
                "windows litert-lm org/model native-benchmark-1024x256 backend=gpu context-tokens=2048\n":
                    "windows v1 supports prompt tasks only",
                # adapter= names the GPU of a litert-lm GPU row, and only the integrated one so far
                "windows litert-lm org/model short-chat backend=cpu adapter=igpu context-tokens=2048\n":
                    "adapter= names the GPU of a windows litert-lm backend=gpu row only",
                "windows llama.cpp org/gguf short-chat backend=gpu adapter=igpu context-tokens=2048\n":
                    "adapter= names the GPU of a windows litert-lm backend=gpu row only",
                "windows litert-lm org/model short-chat backend=gpu adapter=dgpu context-tokens=2048\n":
                    "adapter='dgpu' (want igpu)",
                "android litert-lm org/model short-chat backend=gpu adapter=igpu\n":
                    "adapter= is a windows litert-lm backend=gpu row's word only",
            }
            for line, want in bad.items():
                with open(p, "w") as fh:
                    fh.write(line)
                errors, _ = validate_cells.validate_file(p)
                self.assertTrue(any(want in e for e in errors), f"{want!r} not in {errors} for {line.strip()}")

    def test_windows_matrix_runner_plan_and_records_to_dashboard(self):
        with tempfile.TemporaryDirectory(prefix="render-rules-winrun-") as tmp:
            cells_path = os.path.join(tmp, "win.cells")
            with open(cells_path, "w") as fh:
                fh.write(
                    "windows litert-lm org/model short-chat backend=cpu ynnpack=1 context-tokens=2048 runs=2\n"
                    "windows llama.cpp org/gguf short-chat backend=gpu context-tokens=2048 runs=2\n"
                    "windows llama.cpp org/gguf short-chat backend=cuda context-tokens=2048 runs=2\n"
                    "windows litert-lm org/model short-chat backend=gpu adapter=igpu context-tokens=2048 runs=2\n"
                )
            litert_file = os.path.join(tmp, "model.litertlm")
            gguf_file = os.path.join(tmp, "model-Q4_0.gguf")
            for fpath in (litert_file, gguf_file):
                with open(fpath, "wb") as fh:
                    fh.write(b"x" * 1024)
            pins = run_windows_matrix.load_pins()
            vk_label = run_windows_matrix.pinned_label(pins, "gpu")
            vk_pin = pins[vk_label]
            cuda_label = run_windows_matrix.pinned_label(pins, "cuda")
            cuda_pin = pins[cuda_label]
            litert_sha = "ab" * 32
            extra_pins_path = os.path.join(tmp, "extra-pins.json")
            with open(extra_pins_path, "w") as fh:
                json.dump({"windows_litert-lm": {
                    "21f113ea6eba": {"litert_lm_advanced_main_windows_sha256": litert_sha},
                }}, fh)

            def fake_executor(plan, campaign_dir, args):
                inv = "inv-1"
                logs = campaign_dir / "host-logs" / inv
                logs.mkdir(parents=True, exist_ok=True)
                binaries = {run_windows_matrix.LITERT_EXE: litert_sha}
                for k, v in (vk_pin.get("dll_files") or {}).items():
                    binaries[f"llama-gpu/{k}"] = v
                binaries["llama-gpu/llama-cli.exe"] = vk_pin["llama_cli_sha256"]
                for k, v in run_windows_matrix.llama_files(cuda_pin).items():
                    binaries[f"llama-cuda/{k}"] = v
                (logs / "host.json").write_text(json.dumps({
                    "model": "Precision 7960 Tower", "os": "Windows 11 Pro",
                    "cpu": "Intel Xeon w7-3455", "gpus": [{"name": "NVIDIA RTX 4090"}],
                    "memoryBytes": 64 * 2**30, "binaries": binaries,
                }))
                reply = ("Local on-device AI runs privately offline on your phone or workstation "
                         "without sending sensitive prompts to any cloud server.")
                litert_console = (
                    "I0000 00:00:1.0 1 litert_lm_lib.cc:1] Choose backend: cpu\n"
                    "max_tokens: 2048\nenable_ynnpack: 1\n"
                    "INFO: delegates/ynnpack/ynnpack_delegate.cc:1\n"
                    "I0000 00:00:1.1 1 litert_lm_lib.cc:2] Running single-turn conversation\n"
                    f"{reply}\n"
                    "BenchmarkInfo:\n  Time to first token: 0.050 s\n"
                    "  Prefill Turn 1: Processed 24 tokens in 20.0ms duration.\n"
                    "  Prefill Speed: 1200.0 tokens/sec\n"
                    "  Decode Turn 1: Processed 32 tokens in 400.0ms duration.\n"
                    "  Decode Speed: 80.0 tokens/sec\n"
                    "I0000 00:00:1.6 1 litert_lm_lib.cc:2] Running single-turn conversation\n"
                    f"{reply}\n"
                    "BenchmarkInfo:\n  Time to first token: 0.045 s\n"
                    "  Prefill Turn 1: Processed 24 tokens in 18.0ms duration.\n"
                    "  Prefill Speed: 1333.3 tokens/sec\n"
                    "  Decode Turn 1: Processed 32 tokens in 380.0ms duration.\n"
                    "  Decode Speed: 84.2 tokens/sec\n"
                )
                prompt_txt = run_windows_matrix.prompt_file("short-chat").read_text(encoding="utf-8")
                llama_console = (
                    "load_backend: using device Vulkan0 (NVIDIA RTX 4090)\n"
                    "load_tensors: Vulkan0 model buffer size = 512.00 MiB\n"
                    "load_tensors: offloaded 29/29 layers to GPU\n"
                    f"> {prompt_txt}\n{reply}\n"
                    "[ Prompt: 2500.0 t/s | Generation: 195.5 t/s ]\n"
                )
                cuda_console = (
                    "ggml_cuda_init: found 1 CUDA devices (Total VRAM: 24564 MiB):\n"
                    "  Device 0: NVIDIA RTX 4090, compute capability 8.9, VMM: yes, VRAM: 24564 MiB\n"
                    "llama_prepare_model_devices: using device CUDA0 (NVIDIA RTX 4090) (0000:01:00.0) - 23000 MiB free\n"
                    "load_tensors: CUDA0 model buffer size = 512.00 MiB\n"
                    "load_tensors: offloaded 29/29 layers to GPU\n"
                    f"> {prompt_txt}\n{reply}\n"
                    "[ Prompt: 3100.0 t/s | Generation: 210.5 t/s ]\n"
                )
                # the integrated GPU's run as the host's log carries it, run 1 the one that wrote the GPU caches
                igpu_console = litert_console.replace(
                    "Choose backend: cpu\nmax_tokens: 2048\nenable_ynnpack: 1\n"
                    "INFO: delegates/ynnpack/ynnpack_delegate.cc:1\n",
                    "Choose backend: gpu\nmax_tokens: 2048\n"
                    "I0000 00:00:1.05 1 environment.cc:526] Selected adapter: Intel(R) Graphics, arch=xe-3lpg, "
                    "vendor=intel, backend=Direct3D 12, adapterType=Integrated GPU\n"
                    "INFO: [gpu_registry.cc:121] Statically linked GPU accelerator registered.\n")
                self.assertNotEqual(igpu_console, litert_console)
                for r_idx, console in (("r00", litert_console), ("r01", llama_console), ("r02", cuda_console),
                                       ("r03", igpu_console)):
                    for run_i in (1, 2):
                        meta = {
                            "exitCode": 0, "timedOut": False,
                            # PowerShell Get-Date -Format o local offset with 7 fractional digits.
                            "start": f"2026-10-29T21:00:0{run_i}.1234567+09:00",
                            "elapsedSeconds": 1.2, "peakWorkingSetBytes": 800 * 2**20,
                            "command": "test.exe",
                        }
                        if r_idx == "r03":
                            meta.update(gpuPreference="GpuPreference=1;", gpuPreferenceRemoved=True,
                                        gpuCacheWrite=run_i == 1, gpuCachePurge=[])
                        (logs / f"{r_idx}_run{run_i}.json").write_text(json.dumps(meta))
                        (logs / f"{r_idx}_run{run_i}.log").write_text(console)
                clean, total = run_windows_matrix.write_records(
                    plan, campaign_dir, inv, litert_label="21f113ea6eba", pins=pins)
                # Also verify an unregistered litert_label lands as unknown (...).
                unpinned_dir = pathlib.Path(tmp) / "unpinned-camp"
                shutil.copytree(campaign_dir, unpinned_dir)
                run_windows_matrix.write_records(
                    plan, unpinned_dir, inv, litert_label="unpinned-label", pins=pins,
                    litert_pins={})
                unpinned_rec = json.loads(
                    (unpinned_dir / "litert-lm-cpu-ynnpack_org_model_short-chat.jsonl")
                    .read_text().splitlines()[-1]
                )
                self.assertTrue(unpinned_rec["engineVersion"].startswith("unknown ("))
                # the plan's launch of the igpu row carries what run_job.ps1 reads
                igpu_launch = plan.job["launches"][3]
                self.assertEqual((igpu_launch["adapter"], igpu_launch["gpuPreference"], igpu_launch["modelFile"]),
                                 ("igpu", "GpuPreference=1;", "model.litertlm"))
                self.assertIn("--preferred_device_substr=Intel", igpu_launch["args"])
                return 0 if clean == total == 8 else 1

            run_windows_matrix.register_executor("fake-lab", fake_executor)
            try:
                raw_dir = os.path.join(tmp, "raw")
                with patch.dict(os.environ, {
                    "BENCH_RAW_ROOT": raw_dir,
                    "BENCH_EXTRA_PINS": extra_pins_path,
                }):
                    rc = run_windows_matrix.main([
                        cells_path, "--executor", "fake-lab", "--campaign", "2026-10-29-win",
                        "--litert-label", "21f113ea6eba",
                        "--model-file", f"litert-lm:org/model={litert_file}",
                        "--model-file", f"llama.cpp:org/gguf={gguf_file}",
                    ])
                self.assertEqual(rc, 0)
            finally:
                run_windows_matrix.EXECUTORS.pop("fake-lab", None)

            litert_recs = [
                json.loads(ln) for ln in open(
                    os.path.join(
                        raw_dir, "2026-10-29-win",
                        "litert-lm-cpu-ynnpack_org_model_short-chat.jsonl",
                    )
                ) if ln.strip()
            ]
            llama_recs = [
                json.loads(ln) for ln in open(
                    os.path.join(
                        raw_dir, "2026-10-29-win",
                        "llama.cpp-gpu_org_gguf_short-chat.jsonl",
                    )
                ) if ln.strip()
            ]
            cuda_recs = [
                json.loads(ln) for ln in open(
                    os.path.join(raw_dir, "2026-10-29-win", "llama.cpp-cuda_org_gguf_short-chat.jsonl")
                ) if ln.strip()
            ]
            igpu_recs = [
                json.loads(ln) for ln in open(
                    os.path.join(raw_dir, "2026-10-29-win", "litert-lm-gpu-igpu_org_model_short-chat.jsonl")
                ) if ln.strip()
            ]
            self.assertEqual({r["runtime"] for r in igpu_recs}, {"litert-lm-gpu-igpu"})
            self.assertEqual(igpu_recs[0]["conditions"]["gpuAdapter"],
                             "Intel(R) Graphics, arch=xe-3lpg, vendor=intel, backend=Direct3D 12, "
                             "adapterType=Integrated GPU")
            self.assertEqual(igpu_recs[0]["conditions"]["gpuPreference"], "GpuPreference=1;")
            self.assertEqual([r["metrics"].get("firstEver", False) for r in igpu_recs], [True, False, False, False])
            self.assertEqual(cuda_recs[0]["engineVersion"], cuda_label)
            self.assertEqual(cuda_recs[0]["conditions"]["ggmlDevice"], "CUDA0")
            self.assertIn("Device 0: NVIDIA RTX 4090, compute capability 8.9",
                          cuda_recs[0]["conditions"]["backendRegistered"])
            self.assertEqual([r["metrics"].get("firstEver", False) for r in cuda_recs], [True, False])
            self.assertEqual(litert_recs[0]["engineVersion"], "21f113ea6eba")
            self.assertEqual(litert_recs[0]["timestamp"], "2026-10-29T12:00:01Z")
            self.assertEqual(
                litert_recs[0]["model"]["quantization"],
                "unrecorded (artifact name carries no quant label)",
            )
            self.assertEqual(llama_recs[0]["model"]["quantization"], "Q4_0")

            sum_dir = os.path.join(tmp, "summary")
            dash_dir = os.path.join(tmp, "dash")
            with patch.object(build_summary, "ROOT", tmp):
                build_summary.main(["--raw-dir", raw_dir, "--out-dir", sum_dir])
            self.assertEqual(render_dashboard.main([
                "--cells", cells_path, "--summary-csv", os.path.join(sum_dir, "device-runs.csv"),
                "--raw-dir", raw_dir, "--schedule", os.path.join(tmp, "no-sched.json"),
                "--md", os.path.join(dash_dir, "DASHBOARD.md"), "--out-dir", dash_dir,
            ]), 0)
            j = json.load(open(os.path.join(dash_dir, "dashboard-v1.json")))
            by_arm = {c["arm"]: (c["status"], c["decode_tps"], c["n"]) for c in j["cells"]}
            # run 1 of litert-lm is firstEver (dropped); run 2 iter 1 is cold (80.0)
            # run 1 of llama.cpp-gpu is firstEver (dropped); run 2 is cold (195.5); llama.cpp-cuda the same (210.5)
            self.assertEqual(by_arm, {
                "litert-lm-cpu-ynnpack": ("measured", 80.0, 1),
                "llama.cpp-gpu": ("measured", 195.5, 1),
                "llama.cpp-cuda": ("measured", 210.5, 1),
                # the dashboard keys the igpu row by the arm its records carry: a cell of its own
                "litert-lm-gpu-igpu": ("measured", 80.0, 1),
            })


class WindowsRunnerRows(unittest.TestCase):
    """The windows rows as a real machine meets them: a Gemma 4 GGUF, several files of one model id."""

    def cells(self, tmp, text):
        path = os.path.join(tmp, "win.cells")
        with open(path, "w") as fh:
            fh.write(text)
        return path

    def test_gemma4_gguf_thinking_off_is_one_cmd_safe_word(self):
        with tempfile.TemporaryDirectory(prefix="render-rules-wingguf-") as tmp:
            cells = self.cells(tmp, "windows llama.cpp unsloth/gemma-4-E2B-it-GGUF short-chat backend=gpu "
                                    "file=gemma-4-E2B-it-Q4_K_M.gguf context-tokens=2048\n")
            specs = run_windows_matrix.parse_model_specs(
                ["llama.cpp:unsloth/gemma-4-E2B-it-GGUF=gemma-4-E2B-it-Q4_K_M.gguf:3106738272"])
            plan = run_windows_matrix.plan_job([cells], "c", run_windows_matrix.load_pins(), specs)
        args = plan.job["launches"][0]["args"]
        at = args.index("--chat-template-kwargs")
        self.assertEqual(args[at + 1], r'"{\"enable_thinking\":false}"')
        self.assertNotIn("--device", args)

    def test_other_metacharacters_still_refused(self):
        row = run_windows_matrix.WinRow(0, "litert-lm", "cpu", "org/m", "short-chat", 1, 2048, False, "litert-lm-cpu")
        with self.assertRaisesRegex(ValueError, "metacharacter"):
            run_windows_matrix.lab_args(row, "a&b.litertlm", 128)

    def test_file_picks_among_the_files_of_one_id(self):
        with tempfile.TemporaryDirectory(prefix="render-rules-winfile-") as tmp:
            cells = self.cells(tmp, (
                "windows litert-lm org/m short-chat backend=cpu file=m.litertlm context-tokens=2048\n"
                "windows litert-lm org/m short-chat backend=gpu file=m-gpu.litertlm context-tokens=2048\n"))
            specs = run_windows_matrix.parse_model_specs(
                ["litert-lm:org/m=m.litertlm:10", "litert-lm:org/m=m-gpu.litertlm:20"])
            plan = run_windows_matrix.plan_job([cells], "c", run_windows_matrix.load_pins(), specs)
            self.assertEqual(sorted((m["name"], m["bytes"]) for m in plan.job["models"]),
                             [("m-gpu.litertlm", 20), ("m.litertlm", 10)])
            self.assertIn("--model_path={model:m-gpu.litertlm}", plan.job["launches"][1]["args"])
            # a row that names no file cannot pick among two
            bare = self.cells(tmp, "windows litert-lm org/m short-chat backend=cpu context-tokens=2048\n")
            with self.assertRaisesRegex(ValueError, "--model-file"):
                run_windows_matrix.plan_job([bare], "c", run_windows_matrix.load_pins(), specs)

    def test_two_files_of_one_arm_model_task_refused(self):
        with tempfile.TemporaryDirectory(prefix="render-rules-winstem-") as tmp:
            cells = self.cells(tmp, (
                "windows litert-lm org/m short-chat backend=gpu file=a.litertlm context-tokens=2048\n"
                "windows litert-lm org/m short-chat backend=gpu file=b.litertlm context-tokens=2048\n"))
            with self.assertRaisesRegex(ValueError, "share a capture file"):
                run_windows_matrix.load_rows([cells])

    def test_the_record_states_the_thread_count_its_log_states(self):
        head = "I0000 00:00:1.0 1 litert_lm_lib.cc:728] Choose backend: cpu\nnumber_of_threads: 4\nmax_tokens: 2048\n"
        with tempfile.TemporaryDirectory(prefix="render-rules-winthreads-") as tmp:
            clean, recs = self.records(tmp, "backend=cpu file=m.litertlm context-tokens=2048", head)
        self.assertEqual(clean, 1)
        self.assertEqual(recs[0]["conditions"]["threads"], 4)
        self.assertEqual(run_windows_matrix.engine_threads("x n_threads = 16 (n_threads_batch = 16) / 16"), 16)
        self.assertEqual(run_windows_matrix.engine_threads("no such line"), "engine default")

    def test_npu_row_runs_the_bundle_on_its_own_cache(self):
        with tempfile.TemporaryDirectory(prefix="render-rules-winnpu-") as tmp:
            cells = self.cells(tmp, "windows litert-lm org/m short-chat backend=npu file=m_intel_PTL.litertlm\n")
            specs = run_windows_matrix.parse_model_specs(["litert-lm:org/m=m_intel_PTL.litertlm:10"])
            plan = run_windows_matrix.plan_job([cells], "c", run_windows_matrix.load_pins(), specs)
            args = plan.job["launches"][0]["args"]
            self.assertIn("--backend=npu", args)
            self.assertIn("--litert_dispatch_lib_dir={tool_dir}", args)
            self.assertFalse([a for a in args if a.startswith("--max_num_tokens")])
            self.assertFalse([a for a in args if a.startswith("--use_hw_cache_update_for_npu")])
            # no file: nothing says which SoC's bundle; an allocation: a bundle has none to set
            for bad, want in (("backend=npu", "needs file="),
                              ("backend=npu file=m.litertlm context-tokens=2048", "no context-tokens=")):
                path = self.cells(tmp, f"windows litert-lm org/m short-chat {bad}\n")
                with self.assertRaisesRegex(ValueError, want):
                    run_windows_matrix.load_rows([path])

    # One engine process as the host's logs carry it (the line forms of LiteRT-LM v0.19.0's Windows tool).
    ITERATION = (
        "I0000 00:00:2.0 1 litert_lm_lib.cc:1310] Running single-turn conversation\n"
        "On-device AI means the model runs on your own phone or laptop, not on a server far away, so your words "
        "stay with you and the answers come back even with no network at all.\n"
        "I0000 00:00:3.0 1 litert_lm_lib.cc:461] BenchmarkInfo:\n"
        "  Time to first token: 0.26 s\n"
        "  Prefill Turns (Total 1 turns):\n"
        "    Prefill Turn 1: Processed 20 tokens in 231.7962ms duration.\n"
        "      Prefill Speed: 86.28 tokens/sec.\n"
        "  Decode Turns (Total 1 turns):\n"
        "    Decode Turn 1: Processed 128 tokens in 3.2842774s duration.\n"
        "      Decode Speed: 38.97 tokens/sec.\n")

    def records(self, tmp, row, head, model="m.litertlm", mid="org/m", start="2026-11-05T20:00:00.0000000+09:00",
                metas=({},)):
        """write_records over fake host logs of one row, one run per metas entry (its fields over the defaults):
        (clean runs, the row's records)."""
        cells = self.cells(tmp, f"windows litert-lm {mid} short-chat {row} runs={len(metas)}\n")
        specs = run_windows_matrix.parse_model_specs([f"litert-lm:{mid}={model}:10"])
        plan = run_windows_matrix.plan_job([cells], "c", run_windows_matrix.load_pins(), specs)
        camp = pathlib.Path(tmp) / "c"
        logs = camp / "host-logs" / "inv"
        logs.mkdir(parents=True)
        (logs / "host.json").write_text(json.dumps({"model": "PC", "os": "Windows 11", "cpu": "x", "binaries": {}}))
        for k, extra in enumerate(metas, 1):
            (logs / f"r00_run{k}.json").write_text(json.dumps({
                "exitCode": 0, "timedOut": False, "start": start, "elapsedSeconds": 10,
                "peakWorkingSetBytes": 1 << 30, "command": "tool", "before": {"quietGate": "quiet"},
                "after": {"cpuBusyPercent": 3}, **extra}))
            (logs / f"r00_run{k}.log").write_text(head + self.ITERATION + self.ITERATION)
        clean, _ = run_windows_matrix.write_records(plan, camp, "inv", litert_pins={}, harness="test")
        with open(camp / f"{plan.rows[0].stem}.jsonl") as fh:
            return clean, [json.loads(line) for line in fh]

    def test_a_file_replaced_on_the_hub_carries_the_replacements_label(self):
        # litert-community/Qwen3-0.6B's dynamic INT4 file was replaced under the same name on 2026-10-31
        # (bench_common.REPLACED_FILE_LABELS): a Windows run of it from that UTC date on carries the new content's
        # label in its record, a run before it the file name's label (run_cell.guess_quant)
        mid, fname = "litert-community/Qwen3-0.6B", "Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm"
        old = run_windows_matrix.run_cell.guess_quant(fname)
        new = [lb for m, f, _since, carried, lb in bench_common.REPLACED_FILE_LABELS if (m, f) == (mid, fname)
               and old in carried][0]
        head = "I0000 00:00:1.0 1 litert_lm_lib.cc:728] Choose backend: cpu\nnumber_of_threads: 4\nmax_tokens: 2048\n"
        for start, want in (("2026-11-07T03:00:00.0000000+09:00", new), ("2026-10-31T08:00:00.0000000+09:00", old)):
            with tempfile.TemporaryDirectory(prefix="render-rules-winrepl-") as tmp:
                clean, recs = self.records(tmp, f"backend=cpu file={fname} context-tokens=2048", head, model=fname,
                                           mid=mid, start=start)
            self.assertEqual(clean, 1)
            self.assertEqual(recs[0]["model"]["quantization"], want, start)
        # the summary's correction reads a windows row as it reads an android one, on both arms; a mac row keeps the
        # label its catalog wrote
        for arm in ("litert-lm-cpu", "litert-lm-gpu", "litert-lm-gpu-igpu"):
            row = {"platform": "windows", "timestamp": "2026-11-06T18:00:00Z", "model_file": fname}
            self.assertEqual(bench_common.corrected_quant(arm, mid, old, row), (new, True))
            self.assertEqual(bench_common.corrected_quant(arm, mid, new, row), (new, False))
            self.assertEqual(bench_common.corrected_quant(arm, mid, old, dict(row, platform="mac")), (old, False))

    def test_a_runs_host_reads_pass_into_each_of_its_records(self):
        # run_job.ps1 (2026-11-07) writes the SSH connections sshd accepted during the engine process and the logical
        # processors' counters over it: every iteration record of the run carries both as the job wrote them, a null
        # count with its reason too, and a run an older job script wrote carries neither key
        head = "I0000 00:00:1.0 1 litert_lm_lib.cc:728] Choose backend: cpu\nnumber_of_threads: 4\nmax_tokens: 2048\n"
        ssh = {"accepted": 2, "atSeconds": [12.5, 42.6]}
        cpu = {"seconds": 61.2, "busyPercent": {"0,0": 97.1, "_Total": 40.2}, "performancePercent": {"0,0": 88.0},
               "performanceLimitPercent": {"0,0": 100.0}, "performanceLimitFlags": {}}
        unread = ({"accepted": None, "reason": "the OpenSSH/Operational log was not read: x"},
                  {"reason": "Processor Information not read: y"})
        with tempfile.TemporaryDirectory(prefix="render-rules-winhost-") as tmp:
            clean, recs = self.records(tmp, "backend=cpu file=m.litertlm context-tokens=2048", head,
                                       metas=({"sshConnections": ssh, "hostCpu": cpu},
                                              {"sshConnections": unread[0], "hostCpu": unread[1]}, {}))
        self.assertEqual(clean, 3)
        runs = {}
        for r in recs:
            runs.setdefault(r["conditions"]["launchID"], []).append(r["conditions"])
        read, unreadable, older = runs.values()
        self.assertTrue(read and unreadable and older)
        for c in read:
            self.assertEqual((c["sshConnections"], c["hostCpu"]), (ssh, cpu))
        for c in unreadable:
            self.assertEqual((c["sshConnections"], c["hostCpu"]), unread)
        for c in older:
            self.assertNotIn("sshConnections", c)
            self.assertNotIn("hostCpu", c)
        # recorded, never judged: neither read adds a flag
        self.assertEqual({f for c in read + unreadable for f in c["protocolFlags"]}, set())

    NPU_HEAD = ("I0000 00:00:1.0 1 litert_lm_lib.cc:728] Choose backend: npu\nmax_tokens: 0\n"
                "RegisterAccelerator: ptr=000001C4D6DD87A0, name=NpuAccelerator\n"
                "INFO: [invocation_context.cc:297] OpenVINO partition '(unnamed)' using device: NPU\n")

    def test_npu_records_hold_the_device_not_an_allocation(self):
        with tempfile.TemporaryDirectory(prefix="render-rules-winnpurec-") as tmp:
            clean, recs = self.records(tmp, "backend=npu file=gemma-4-E2B-it_intel_PTL.litertlm", self.NPU_HEAD,
                                       model="gemma-4-E2B-it_intel_PTL.litertlm")
        self.assertEqual(clean, 1)
        cond = recs[0]["conditions"]
        self.assertEqual(cond["protocolFlags"], [])
        self.assertEqual(cond["contextTokens"], "aot-fixed-4096")
        self.assertIn("OpenVINO partition '(unnamed)' using device: NPU", cond["backendRegistered"])
        self.assertEqual(cond["hostBefore"], {"quietGate": "quiet"})
        self.assertEqual(cond["hostAfter"], {"cpuBusyPercent": 3})
        self.assertIn("Intel PTL NPU bundle", recs[0]["model"]["quantization"])

    def test_npu_record_of_a_bundle_on_another_device_is_flagged(self):
        with tempfile.TemporaryDirectory(prefix="render-rules-winnpuoff-") as tmp:
            clean, recs = self.records(tmp, "backend=npu file=other.litertlm",
                                       self.NPU_HEAD.replace("device: NPU", "device: CPU"), model="other.litertlm")
        self.assertEqual(clean, 0)
        self.assertIn("backend-not-registered", recs[0]["conditions"]["protocolFlags"])
        self.assertEqual(recs[0]["conditions"]["contextTokens"], "aot-fixed (cache length unrecorded)")

    def test_gpu_record_on_the_other_adapter_is_flagged(self):
        head = ("I0000 00:00:1.0 1 litert_lm_lib.cc:728] Choose backend: gpu\nmax_tokens: 2048\n"
                "I0000 00:00:1.5 1 environment.cc:526] Selected adapter: Intel(R) Graphics, vendor=intel, "
                "backend=Direct3D 12, adapterType=Integrated GPU\n"
                "INFO: [gpu_registry.cc:121] Statically linked GPU accelerator registered.\n")
        with tempfile.TemporaryDirectory(prefix="render-rules-wingpuoff-") as tmp:
            clean, recs = self.records(tmp, "backend=gpu file=m.litertlm context-tokens=2048", head)
        self.assertEqual(clean, 0)
        cond = recs[0]["conditions"]
        self.assertTrue(cond["backendOffReason"].startswith("Selected adapter: Intel"))
        self.assertIn("backend-not-registered", cond["protocolFlags"])
        self.assertEqual(cond["gpuAccelerator"], "static-source")
        self.assertTrue(cond["gpuAdapter"].startswith("Intel(R) Graphics"))
        self.assertIsNone(cond["gpuPreference"])

    GPU_HEAD = ("I0000 00:00:1.0 1 litert_lm_lib.cc:728] Choose backend: gpu\nmax_tokens: 2048\n"
                "I0000 00:00:1.5 1 environment.cc:526] Selected adapter: {adapter}\n"
                "INFO: [gpu_registry.cc:121] Statically linked GPU accelerator registered.\n")
    INTEL = "Intel(R) Graphics, arch=xe-3lpg, vendor=intel, backend=Direct3D 12, adapterType=Integrated GPU"
    NVIDIA = ("NVIDIA GeForce RTX 5080 Laptop GPU, arch=blackwell, vendor=nvidia, backend=Direct3D 12, "
              "adapterType=Discrete GPU")
    APPLIED = {"gpuPreference": "GpuPreference=1;", "gpuPreferenceRemoved": True}

    def test_adapter_row_is_its_own_arm_with_the_preference_in_its_launch(self):
        with tempfile.TemporaryDirectory(prefix="render-rules-winadapter-") as tmp:
            cells = self.cells(tmp, (
                "windows litert-lm org/m short-chat backend=gpu file=m.litertlm context-tokens=2048\n"
                "windows litert-lm org/m short-chat backend=gpu adapter=igpu file=m.litertlm context-tokens=2048\n"))
            specs = run_windows_matrix.parse_model_specs(["litert-lm:org/m=m.litertlm:10"])
            plan = run_windows_matrix.plan_job([cells], "c", run_windows_matrix.load_pins(), specs)
            # the same exe and file on two GPUs: two arms, two capture files (no "share a capture file" refusal)
            self.assertEqual([r.arm for r in plan.rows], ["litert-lm-gpu", "litert-lm-gpu-igpu"])
            dflt, igpu = plan.job["launches"]
            self.assertEqual((dflt["adapter"], dflt["modelFile"]), ("", "m.litertlm"))
            self.assertNotIn("gpuPreference", dflt)
            self.assertEqual((igpu["adapter"], igpu["gpuPreference"], igpu["modelFile"]),
                             ("igpu", "GpuPreference=1;", "m.litertlm"))
            self.assertIn("--preferred_device_substr=NVIDIA", dflt["args"])
            self.assertIn("--preferred_device_substr=Intel", igpu["args"])
            self.assertEqual([a for a in dflt["args"] if "preferred_device" not in a],
                             [a for a in igpu["args"] if "preferred_device" not in a])
            # the dashboard reads the cells file to the same arms
            self.assertEqual([render_dashboard.arm_of(*validate_cells.parse_line(ln)[0:2], validate_cells.parse_line(ln)[4])
                              for ln in open(cells).read().splitlines()], ["litert-lm-gpu", "litert-lm-gpu-igpu"])
            # adapter= on a row that is not a LiteRT-LM GPU row stops the plan
            bad = self.cells(tmp, "windows litert-lm org/m short-chat backend=cpu adapter=igpu file=m.litertlm "
                                  "context-tokens=2048\n")
            with self.assertRaisesRegex(ValueError, "adapter= is igpu on a litert-lm backend=gpu row only"):
                run_windows_matrix.load_rows([bad])

    def test_igpu_record_holds_the_adapter_its_log_selected(self):
        with tempfile.TemporaryDirectory(prefix="render-rules-winigpu-") as tmp:
            clean, recs = self.records(tmp, "backend=gpu adapter=igpu file=m.litertlm context-tokens=2048",
                                       self.GPU_HEAD.format(adapter=self.INTEL), metas=(self.APPLIED,))
        self.assertEqual(clean, 1)
        cond = recs[0]["conditions"]
        self.assertEqual((recs[0]["runtime"], cond["gpuAdapter"], cond["gpuPreference"]),
                         ("litert-lm-gpu-igpu", self.INTEL, "GpuPreference=1;"))
        self.assertEqual(cond["protocolFlags"], [])
        self.assertNotIn("backendOffReason", cond)

    def test_igpu_record_on_another_gpu_or_without_its_preference_is_not_counted(self):
        cases = (
            # the log selected the discrete GPU: the run measured that GPU
            (self.GPU_HEAD.format(adapter=self.NVIDIA), self.APPLIED, "Selected adapter: NVIDIA", "backend-not-registered"),
            # no adapter line: nothing says which GPU ran
            (self.GPU_HEAD.replace("I0000 00:00:1.5 1 environment.cc:526] Selected adapter: {adapter}\n", ""),
             self.APPLIED, "no Selected adapter: line", "backend-not-registered"),
            # the job script read no preference back (an older run_job.ps1, or the value did not stick): whatever
            # its log selected, the run is not a run of the cell
            (self.GPU_HEAD.format(adapter=self.INTEL), {}, "no GpuPreference=1; on the tool", "gpu-preference-not-applied"),
        )
        first = []
        for i, (head, meta, reason, flag) in enumerate(cases):
            with tempfile.TemporaryDirectory(prefix="render-rules-winigpuoff-") as tmp:
                clean, recs = self.records(tmp, "backend=gpu adapter=igpu file=m.litertlm context-tokens=2048", head,
                                           metas=(meta,))
            self.assertEqual(clean, 0, i)
            cond = recs[0]["conditions"]
            self.assertIn(flag, cond["protocolFlags"], i)
            self.assertIn("backend-not-registered", cond["protocolFlags"], i)
            if reason:
                self.assertTrue(cond["backendOffReason"].startswith(reason), (i, cond.get("backendOffReason")))
            first.append(recs[0])
        # the summary carries each as backend_registered false, which arm_row keeps out of the pool
        self.assertEqual([build_summary.backend_registered_of(r) for r in first], ["false"] * 3)
        self.assertEqual(arm_row([{"first_ever": "False", "cold_run": "True", "decode_tps": "40.0", "prefill_tps": "",
                                   "ttft_ms": "", "backend_registered": "false", "engine_version": "v", "campaign": "c",
                                   "timestamp": "2026-11-07T00:00:00Z", "runtime": "litert-lm-gpu-igpu",
                                   "model_id": "org/m", "quantization": "q", "mem_footprint_median_mb": "",
                                   "mem_resident_median_mb": "", "platform": "windows", "task": "short-chat"}])["n"], 0)

    def test_a_run_that_writes_the_gpu_caches_is_first_ever_wherever_it_falls(self):
        # run 2 found no GPU cache of its file (the job removed them when the adapter changed): it compiled and wrote
        # them, so its first conversation is the cache build, not the engine's speed
        with tempfile.TemporaryDirectory(prefix="render-rules-wincachewrite-") as tmp:
            clean, recs = self.records(tmp, "backend=gpu adapter=igpu file=m.litertlm context-tokens=2048",
                                       self.GPU_HEAD.format(adapter=self.INTEL),
                                       metas=(dict(self.APPLIED, gpuCacheWrite=True),
                                              dict(self.APPLIED, gpuCacheWrite=True,
                                                   gpuCachePurge=["m.litertlm_1_10_mldrift_program_cache.bin"]),
                                              dict(self.APPLIED, gpuCacheWrite=False)))
        self.assertEqual(clean, 3)
        self.assertEqual([(r["metrics"].get("firstEver", False), r["conditions"]["iterationIndex"]) for r in recs],
                         [(True, 1), (False, 2), (True, 1), (False, 2), (False, 1), (False, 2)])
        self.assertEqual(recs[2]["conditions"]["gpuCachePurge"], ["m.litertlm_1_10_mldrift_program_cache.bin"])
        self.assertNotIn("gpuCachePurge", recs[4]["conditions"])


class WindowsSshExecutor(unittest.TestCase):
    """scripts/windows_ssh_executor.py with its transport faked: the job goes up, its logs come down as records."""

    EXE_SHA, DLL_SHA = "a" * 64, "b" * 64

    def run_job(self, tmp, invocation=None, label="v", host_exe_sha=EXE_SHA, runs=1):
        import windows_ssh_executor as ex
        cells = os.path.join(tmp, "win.cells")
        with open(cells, "w") as fh:
            fh.write(f"windows litert-lm org/m short-chat backend=npu file=m_intel_PTL.litertlm runs={runs}\n")
        specs = run_windows_matrix.parse_model_specs(["litert-lm:org/m=m_intel_PTL.litertlm:10"])
        plan = run_windows_matrix.plan_job([cells], "c", run_windows_matrix.load_pins(), specs)
        seen = {"commands": [], "job": None, "waits": []}
        # the build's own registry entry, as build_litert_lm.ps1 writes it beside the tool
        extra = os.path.join(tmp, "pins-v.json")
        with open(extra, "w") as fh:
            json.dump({"windows_litert-lm": {"v": {"engine_version": "v0.19.0", "dll_files": {"x.dll": self.DLL_SHA},
                                                  "litert_lm_advanced_main_windows_sha256": self.EXE_SHA}}}, fh)

        def fake_ssh(command, timeout=300, check=True, runner=None):
            del timeout, check, runner
            seen["commands"].append(command)
            if "Win32_Process" in command:
                out = "0\n"
            elif "Get-FileHash" in command and "'FILE '" in command:
                out = f"FILE litert_lm_advanced_main_windows.exe {host_exe_sha}\nFILE x.dll {self.DLL_SHA}\n"
            elif "job.log" in command:
                raise AssertionError("the wait reads job.log through one ssh() per read again")
            else:
                out = ""
            return subprocess.CompletedProcess([], 0, out, "")

        def fake_stream(command, idle_seconds=None, popen=None):
            del idle_seconds, popen
            seen["waits"].append(command)
            yield from ["WAITING 2026-11-07T16:00:00 from line 0", "LOG [t] job c: 1 launches", "WAITSTAT 3 12 0.4 0",
                        "JOBDONE OK"]

        def fake_up(local, remote, runner=None):
            del remote, runner
            if pathlib.Path(local).is_dir():
                seen["job"] = json.loads((pathlib.Path(local) / "job.json").read_text())

        def fake_down(remote, local, runner=None):
            del runner
            logs = pathlib.Path(local) / remote.rsplit("\\", 1)[1]
            logs.mkdir(parents=True, exist_ok=True)
            (logs / "host.json").write_text(json.dumps({"model": "PC", "binaries": {}}))
            (logs / "r00_run1.json").write_text(json.dumps({
                "exitCode": 0, "timedOut": False, "start": "2026-11-05T20:00:00.0000000+09:00",
                "peakWorkingSetBytes": 1 << 30, "command": "tool"}))
            (logs / "r00_run1.log").write_text(WindowsRunnerRows.NPU_HEAD + WindowsRunnerRows.ITERATION * 2)

        args = argparse.Namespace(dry_run=False, litert_label=label, extra_catalog=None, engines_dir=None)
        env = {"BENCH_WINDOWS_ROOT": r"C:\b", "BENCH_WINDOWS_MODEL_DIR": r"C:\m", "BENCH_WINDOWS_INVOCATION": invocation or "",
               "BENCH_EXTRA_PINS": extra}
        with patch.dict(os.environ, env), patch.object(ex, "ssh", fake_ssh), patch.object(ex, "scp_up", fake_up), \
                patch.object(ex, "scp_down", fake_down), patch.object(ex, "ssh_stream", fake_stream):
            rc = ex.run(plan, pathlib.Path(tmp) / "c", args)
        return rc, seen, plan

    def test_job_lands_as_records(self):
        with tempfile.TemporaryDirectory(prefix="render-rules-winssh-") as tmp:
            rc, seen, plan = self.run_job(tmp)
            self.assertEqual(rc, 0)
            self.assertEqual(seen["job"]["launches"][0]["env"], {"Path": r"C:\b\engines\openvino;%PATH%"})
            started = [c for c in seen["commands"] if "Win32_Process" in c]
            self.assertEqual(len(started), 1)
            self.assertIn("-PurgeEngineCaches", started[0])
            # the start removes an earlier start's job.done in its own session, and the wait is one session
            self.assertRegex(started[0], r"^Remove-Item -LiteralPath 'C:\\b\\logs\\[^']+\\job\.done' "
                                         r"-ErrorAction SilentlyContinue; \$r = Invoke-CimMethod ")
            self.assertEqual(len(seen["waits"]), 1)
            with open(pathlib.Path(tmp) / "c" / f"{plan.rows[0].stem}.jsonl") as fh:
                recs = [json.loads(line) for line in fh]
            self.assertEqual(len(recs), 2)
            self.assertEqual(recs[0]["provenance"]["harness"], "scripts/windows_ssh_executor.py")
            self.assertEqual(recs[0]["conditions"]["protocolFlags"], [])

    def test_a_job_the_host_stopped_early_is_not_a_clean_sitting(self):
        # job.done says OK (a restart stops the job through its finally) but one run of the two planned came back
        with tempfile.TemporaryDirectory(prefix="render-rules-winstopped-") as tmp:
            out = io.StringIO()
            with redirect_stdout(out):
                rc, _, plan = self.run_job(tmp, runs=2)
            self.assertEqual(rc, 1)
            self.assertIn("== 1/1 runs clean", out.getvalue())
            self.assertIn("1 of 2 planned runs did not run on the host", out.getvalue())
            self.assertIn("retake it under a new --campaign", out.getvalue())
            with open(pathlib.Path(tmp) / "c" / f"{plan.rows[0].stem}.jsonl") as fh:
                self.assertEqual(len([json.loads(line) for line in fh]), 2)  # run 1's records are still written

    def test_the_gpu_read_interval_goes_to_the_job_and_a_bad_one_stops_before_the_host(self):
        started = lambda seen: [c for c in seen["commands"] if "Win32_Process" in c][0]
        for value in ("5", "0"):
            with tempfile.TemporaryDirectory(prefix="render-rules-wingpu-") as tmp:
                with patch.dict(os.environ, {"BENCH_WINDOWS_GPU_SAMPLE_SECONDS": value}):
                    rc, seen, _ = self.run_job(tmp)
                self.assertEqual(rc, 0)
                self.assertIn(f" -GpuSampleSeconds {value}", started(seen))
        with tempfile.TemporaryDirectory(prefix="render-rules-wingpu-") as tmp:
            rc, seen, _ = self.run_job(tmp)  # unset: the job's own default, no word on the command line
            self.assertEqual(rc, 0)
            self.assertNotIn("-GpuSampleSeconds", started(seen))
        with tempfile.TemporaryDirectory(prefix="render-rules-wingpu-") as tmp:
            with patch.dict(os.environ, {"BENCH_WINDOWS_GPU_SAMPLE_SECONDS": "5s"}):
                with self.assertRaises(RuntimeError) as cm:
                    self.run_job(tmp)
            self.assertIn("BENCH_WINDOWS_GPU_SAMPLE_SECONDS='5s'", str(cm.exception))
            self.assertFalse((pathlib.Path(tmp) / "c" / "host-logs").exists())

    def test_a_gpu_row_waits_two_seconds_after_the_gpu_read_before_its_engine(self):
        # run_job.ps1 runs only on the Windows host, so this reads the order of its steps from the script's text
        # (windows/README.md, Run and Reproducibility)
        text = (pathlib.Path(__file__).resolve().parent.parent / "windows" / "run_job.ps1").read_text(encoding="utf-8")
        self.assertIn("[int]$AfterGpuReadSeconds = 2,", text)
        body = text[text.index("function Invoke-Run"):]
        self.assertIn('$gpuRow = (($Launch.args -join " ") -match "--backend=gpu") -or '
                      '($Launch.tool -in "llama-gpu", "llama-cuda")', body)
        read = body.index("gpu = Get-GpuSample }")
        wait = body.index("if ($gpuRow) { Start-Sleep -Seconds $AfterGpuReadSeconds }")
        engine = body.index('$shell = Start-Process -FilePath "$env:SystemRoot\\System32\\cmd.exe"')
        self.assertLess(read, wait)
        self.assertLess(wait, engine)
        for other_read in ("Get-GpuSample", "Get-GpuMemoryMiB", "nvidia-smi"):
            self.assertNotIn(other_read, body[wait:engine])
        self.assertLess(body.index("$gpuReadToStart = [math]::Round($sinceGpuRead.Elapsed.TotalSeconds, 3)", wait), engine)
        self.assertIn("gpuReadToStartSeconds = $gpuReadToStart", body[engine:])

    def test_a_resumed_job_keeps_the_caches_and_its_records_are_written_once(self):
        with tempfile.TemporaryDirectory(prefix="render-rules-winresume-") as tmp:
            rc, seen, _ = self.run_job(tmp, invocation="inv1")
            self.assertEqual(rc, 0)
            self.assertNotIn("-PurgeEngineCaches", [c for c in seen["commands"] if "Win32_Process" in c][0])
            rc, seen, _ = self.run_job(tmp, invocation="inv1")
            self.assertEqual(rc, 2)
            self.assertEqual(seen["commands"], [])
            self.assertEqual(seen["waits"], [])

    def test_a_label_the_registries_do_not_hold_is_refused_before_the_host_is_touched(self):
        import windows_ssh_executor as ex
        with tempfile.TemporaryDirectory(prefix="render-rules-winlabel-") as tmp:
            with self.assertRaises(RuntimeError) as cm:
                self.run_job(tmp, label="v0.19.0-mine")
            self.assertIn("BENCH_EXTRA_PINS", str(cm.exception))
            self.assertIn("windows/README.md", str(cm.exception))
            with self.assertRaises(RuntimeError):
                self.run_job(tmp, label="unknown")  # the runner's default label
        self.assertTrue(callable(ex.check_litert_build))

    def test_a_host_build_that_is_not_the_label_is_refused_before_the_job(self):
        with tempfile.TemporaryDirectory(prefix="render-rules-winsha-") as tmp:
            seen_box = {}
            try:
                self.run_job(tmp, host_exe_sha="c" * 64)
            except RuntimeError as exc:
                seen_box["error"] = str(exc)
            self.assertIn("litert_lm_advanced_main_windows.exe", seen_box.get("error", ""))
            self.assertIn("not the build of --litert-label 'v'", seen_box.get("error", ""))
            self.assertFalse((pathlib.Path(tmp) / "c" / "host-logs").exists())

    def test_rows_without_litert_lm_skip_the_build_check(self):
        import windows_ssh_executor as ex
        with tempfile.TemporaryDirectory(prefix="render-rules-winnolitert-") as tmp:
            cells = os.path.join(tmp, "llama.cells")
            with open(cells, "w") as fh:
                fh.write("windows llama.cpp unsloth/gemma-4-E2B-it-GGUF short-chat file=g.gguf context-tokens=2048 runs=1\n")
            specs = run_windows_matrix.parse_model_specs(["llama.cpp:unsloth/gemma-4-E2B-it-GGUF=g.gguf:10"])
            plan = run_windows_matrix.plan_job([cells], "c", run_windows_matrix.load_pins(), specs)

            def no_ssh(*a, **k):
                raise AssertionError("the check must not reach the host for rows without LiteRT-LM")
            ex.check_litert_build(plan, "unknown", runner=no_ssh)


class WindowsSshWait(unittest.TestCase):
    """windows_ssh_executor.wait_job: one SSH session on the host until job.done, opened again after a drop, and the
    unreachable limit; ssh_stream, the session's transport, with a local process in place of ssh."""

    LOG_DIR = r"C:\b\logs\inv"

    @staticmethod
    def script_of(command):
        """The host script inside an encoded command line."""
        return base64.b64decode(command.rsplit(" ", 1)[1]).decode("utf-16-le")

    def wait(self, sessions):
        """wait_job over fake sessions (each a list of lines; an exception in it ends that session with it; the last
        list stands for every later session); returns (the result or the exception, the host scripts, the sleeps,
        stdout)."""
        import windows_ssh_executor as ex
        scripts, sleeps, now = [], [], [0.0]

        def stream(command):
            scripts.append(self.script_of(command))
            lines = sessions[min(len(scripts), len(sessions)) - 1]

            def session():
                for line in lines:
                    if isinstance(line, Exception):
                        raise line
                    yield line
            return session()

        def sleep(seconds):
            sleeps.append(seconds)
            now[0] += seconds

        out = io.StringIO()
        with redirect_stdout(out):
            try:
                result = ex.wait_job(self.LOG_DIR, stream=stream, sleep=sleep, clock=lambda: now[0])
            except RuntimeError as exc:
                result = exc
        return result, scripts, sleeps, out.getvalue()

    def test_the_wait_is_one_session_until_job_done(self):
        result, scripts, sleeps, out = self.wait([[
            "WAITING 2026-11-07T16:00:00 from line 0", "LOG [t1] job c: 2 launches", "ALIVE", "LOG [t2] r00_run1 exit=0",
            "WAITSTAT 40 200 0.52 0", "JOBDONE OK"]])
        self.assertEqual(result, "OK")
        self.assertEqual(len(scripts), 1)
        self.assertEqual(sleeps, [])
        self.assertIn("$skip = 0", scripts[0])
        self.assertIn(r"$log = 'C:\b\logs\inv\job.log'; $done = 'C:\b\logs\inv\job.done'", scripts[0])
        for wmi in ("Cim", "Wmi", "Win32_"):  # the loop reads two files and nothing else
            self.assertNotIn(wmi, scripts[0])
        self.assertEqual([ln for ln in out.splitlines() if ln.startswith("  host: ")],
                         ["  host: [t1] job c: 2 launches", "  host: [t2] r00_run1 exit=0"])
        self.assertIn("1 SSH session(s); the last one's loop read job.log and job.done 40 times over 200 s with "
                      "0.52 s of CPU", out)

    def test_a_dropped_session_is_opened_again_from_the_next_line(self):
        import windows_ssh_executor as ex
        result, scripts, sleeps, out = self.wait([
            ["WAITING t from line 0", "LOG a", "LOG b", RuntimeError("ssh winpc: exit 255: Connection reset")],
            ["WAITING t from line 2", "LOG c", "WAITSTAT 3 15 0.1 0", "JOBDONE FAILED model file missing"]])
        self.assertEqual(result, "FAILED model file missing")
        self.assertEqual([("$skip = 0" in scripts[0]), ("$skip = 2" in scripts[1])], [True, True])
        self.assertEqual(sleeps, [ex.WAIT_RECONNECT_SECONDS])
        self.assertEqual([ln for ln in out.splitlines() if ln.startswith("  host: ")],
                         ["  host: a", "  host: b", "  host: c"])
        self.assertIn("session 1 ended: ssh winpc: exit 255", out)
        self.assertIn("2 SSH session(s)", out)

    def test_a_session_whose_loop_ends_by_itself_is_opened_again(self):
        import windows_ssh_executor as ex
        result, scripts, sleeps, _ = self.wait([["WAITING t from line 0", "LOG a", "SESSIONEND"],
                                                ["WAITING t from line 1", "WAITSTAT 1 1 0 0", "JOBDONE OK"]])
        self.assertEqual(result, "OK")
        self.assertIn("$skip = 1", scripts[1])
        self.assertEqual(sleeps, [ex.WAIT_RECONNECT_SECONDS])

    def test_the_host_unreachable_past_the_limit_stops_the_wait(self):
        import windows_ssh_executor as ex
        result, scripts, sleeps, _ = self.wait([[RuntimeError("ssh winpc: exit 255: Operation timed out")]])
        self.assertIsInstance(result, RuntimeError)
        self.assertIn(f"host unreachable for {ex.UNREACHABLE_LIMIT_SECONDS} s: ssh winpc: exit 255", str(result))
        # as before the one session: one try every WAIT_RECONNECT_SECONDS until the limit has passed
        self.assertEqual(set(sleeps), {ex.WAIT_RECONNECT_SECONDS})
        self.assertEqual(len(scripts), ex.UNREACHABLE_LIMIT_SECONDS // ex.WAIT_RECONNECT_SECONDS + 2)

    def test_error_text_from_the_host_does_not_count_as_reaching_it(self):
        import windows_ssh_executor as ex
        result, _, _, _ = self.wait([["At line:3 char:5", "+ CategoryInfo : ParserError",
                                      RuntimeError("ssh winpc: exit 1: ParserError")]])
        self.assertIsInstance(result, RuntimeError)
        self.assertIn(f"host unreachable for {ex.UNREACHABLE_LIMIT_SECONDS} s", str(result))

    def local(self, script):
        """A popen for ssh_stream that runs script with sh in place of ssh."""
        procs = []

        def popen(argv, **kwargs):
            self.assertEqual(argv[0], "ssh")
            self.assertIn("ServerAliveInterval=30", argv)
            proc = subprocess.Popen(["sh", "-c", script], **kwargs)
            procs.append(proc)
            return proc
        return popen, procs

    def test_ssh_stream_yields_lines_as_they_come_and_raises_on_a_failed_exit(self):
        import windows_ssh_executor as ex
        popen, _ = self.local(r"printf 'WAITING x\r\nLOG a\r\nLOG b'")
        self.assertEqual(list(ex.ssh_stream("c", idle_seconds=10, popen=popen)), ["WAITING x", "LOG a", "LOG b"])
        popen, _ = self.local(r"printf 'LOG a\r\n'; echo 'an error' 1>&2; exit 3")
        got = []
        with self.assertRaises(RuntimeError) as cm:
            for line in ex.ssh_stream("c", idle_seconds=10, popen=popen):
                got.append(line)
        self.assertEqual(got, ["LOG a", "an error"])
        self.assertIn("exit 3: LOG a | an error", str(cm.exception))

    def test_ssh_stream_closes_a_session_that_sends_nothing(self):
        import windows_ssh_executor as ex
        popen, procs = self.local("printf 'WAITING x\\n'; exec sleep 30")
        got = []
        with self.assertRaises(RuntimeError) as cm:
            for line in ex.ssh_stream("c", idle_seconds=0.5, popen=popen):
                got.append(line)
        self.assertEqual(got, ["WAITING x"])
        self.assertIn("nothing came for 0.5 s", str(cm.exception))
        self.assertIsNotNone(procs[0].poll())


class WindowsCudaRow(unittest.TestCase):
    """The llama.cpp CUDA row (backend=cuda): its own arm, tool dir and release asset, the CUDA runtime zip beside it."""

    MAIN, CUDART = b"main zip", b"cudart zip"
    CLI, CUDA_DLL, RT_DLL = "c" * 64, "d" * 64, "e" * 64

    def pins(self):
        def sha(data):
            return hashlib.sha256(data).hexdigest()
        return {
            "vk": {"flavor": "vulkan", "artifact": "v.zip", "url": "https://example.invalid/v.zip", "size": 1,
                   "sha256": "f" * 64, "llama_cli_sha256": self.CLI, "dll_files": {"ggml-vulkan.dll": "a" * 64}},
            "cu": {"flavor": "cuda", "artifact": "llama-cuda.zip", "url": "https://example.invalid/llama-cuda.zip",
                   "size": len(self.MAIN), "sha256": sha(self.MAIN),
                   "cudart": {"artifact": "cudart.zip", "url": "https://example.invalid/cudart.zip",
                              "size": len(self.CUDART), "sha256": sha(self.CUDART)},
                   "llama_cli_sha256": self.CLI,
                   "dll_files": {"ggml-cuda.dll": self.CUDA_DLL, "cudart64_13.dll": self.RT_DLL}},
        }

    def plan(self, tmp, rows):
        cells = os.path.join(tmp, "win.cells")
        with open(cells, "w") as fh:
            fh.write("".join(f"windows llama.cpp org/gguf short-chat {r} file=g.gguf context-tokens=2048 runs=1\n"
                             for r in rows))
        specs = run_windows_matrix.parse_model_specs(["llama.cpp:org/gguf=g.gguf:10"])
        return run_windows_matrix.plan_job([cells], "c", self.pins(), specs)

    def test_the_cuda_row_is_its_own_arm_and_tool_on_the_gpu_rows_words(self):
        with tempfile.TemporaryDirectory(prefix="render-rules-wincuda-") as tmp:
            plan = self.plan(tmp, ["backend=gpu", "backend=cuda"])
        self.assertEqual([(r.arm, r.tool) for r in plan.rows],
                         [("llama.cpp-gpu", "llama-gpu"), ("llama.cpp-cuda", "llama-cuda")])
        self.assertEqual(plan.job["engines"], {"llama-gpu": "v.zip", "llama-cuda": "llama-cuda.zip"})
        vk, cu = (launch["args"] for launch in plan.job["launches"])
        self.assertEqual(vk, cu)
        self.assertNotIn("--device", cu)
        self.assertIn("-ngl", cu)

    def record(self, tmp, console, binaries):
        plan = self.plan(tmp, ["backend=cuda"])
        camp = pathlib.Path(tmp) / "c"
        logs = camp / "host-logs" / "inv"
        logs.mkdir(parents=True)
        (logs / "host.json").write_text(json.dumps({"model": "PC", "binaries": binaries}))
        (logs / "r00_run1.json").write_text(json.dumps({
            "exitCode": 0, "timedOut": False, "start": "2026-11-06T23:00:00.0000000+09:00", "elapsedSeconds": 5,
            "peakWorkingSetBytes": 1 << 30, "command": "llama-cli.exe"}))
        (logs / "r00_run1.log").write_text(console)
        clean, _ = run_windows_matrix.write_records(plan, camp, "inv", pins=self.pins(), harness="test")
        with open(camp / f"{plan.rows[0].stem}.jsonl") as fh:
            return clean, json.loads(fh.readline())

    def console(self, device="CUDA0"):
        prompt = run_windows_matrix.prompt_file("short-chat").read_text(encoding="utf-8")
        return ("ggml_cuda_init: found 1 CUDA devices (Total VRAM: 16303 MiB):\n"
                "  Device 0: NVIDIA GeForce RTX 5080 Laptop GPU, compute capability 12.0, VMM: yes, VRAM: 16303 MiB\n"
                "0.00.178.886 I cmn  common_param: system_info: n_threads = 16 (n_threads_batch = 16) / 16 | "
                "CUDA : ARCHS = 860,890,1200 | USE_GRAPHS = 1 | CPU : SSE3 = 1 |\n"
                f"llama_prepare_model_devices: using device {device} (NVIDIA GeForce RTX 5080 Laptop GPU) "
                "(0000:01:00.0) - 15232 MiB free\n"
                f"load_tensors:      {device} model buffer size =  1407.73 MiB\n"
                "load_tensors: offloaded 36/36 layers to GPU\n"
                f"> {prompt}\nOn-device AI keeps your words on your own laptop and answers with no network at all.\n"
                "[ Prompt: 1500.0 t/s | Generation: 200.0 t/s ]\n")

    def host_files(self, **drop):
        files = {f"llama-cuda/{k}": v for k, v in run_windows_matrix.llama_files(self.pins()["cu"]).items()}
        return {k: v for k, v in files.items() if k.split("/", 1)[1] not in drop.get("names", ())}

    def test_a_cuda_record_names_its_device_and_the_witness_reads_the_runtime_dlls(self):
        with tempfile.TemporaryDirectory(prefix="render-rules-wincudarec-") as tmp:
            clean, rec = self.record(tmp, self.console(), self.host_files())
        self.assertEqual(clean, 1)
        self.assertEqual((rec["runtime"], rec["engineVersion"]), ("llama.cpp-cuda", "cu"))
        cond = rec["conditions"]
        self.assertEqual((cond["ggmlDevice"], cond["protocolFlags"]), ("CUDA0", []))
        self.assertIn("Device 0: NVIDIA GeForce RTX 5080 Laptop GPU, compute capability 12.0", cond["backendRegistered"])
        self.assertIn("CUDA : ARCHS = 860,890,1200", cond["backendRegistered"])
        self.assertTrue(rec["metrics"]["firstEver"])
        with tempfile.TemporaryDirectory(prefix="render-rules-wincudart-") as tmp:
            _, rec = self.record(tmp, self.console(), self.host_files(names=("cudart64_13.dll",)))
        self.assertEqual(rec["engineVersion"], "unknown (cudart64_13.dll unmatched in cu)")

    def test_a_cuda_row_that_ran_on_vulkan_is_flagged(self):
        with tempfile.TemporaryDirectory(prefix="render-rules-wincudavk-") as tmp:
            clean, rec = self.record(tmp, self.console(device="Vulkan0"), self.host_files())
        self.assertEqual(clean, 0)
        self.assertIsNone(rec["conditions"]["ggmlDevice"])
        self.assertIn("backend-not-registered", rec["conditions"]["protocolFlags"])

    def test_fetch_engines_fetches_the_cuda_runtime_zip_beside_its_own(self):
        pins, fetched = self.pins(), []
        body = {pins["cu"]["url"]: self.MAIN, pins["cu"]["cudart"]["url"]: self.CUDART}

        def fetch(url, dest):
            fetched.append(url)
            pathlib.Path(dest).write_bytes(body[url])

        with tempfile.TemporaryDirectory(prefix="render-rules-wincudafetch-") as tmp, redirect_stdout(io.StringIO()):
            out = run_windows_matrix.fetch_engines(pathlib.Path(tmp), pins, ["cu"], fetch=fetch)
            self.assertEqual([p.name for p in out["cu"]], ["llama-cuda.zip", "cudart.zip"])
            self.assertEqual([p.read_bytes() for p in out["cu"]], [self.MAIN, self.CUDART])
            run_windows_matrix.fetch_engines(pathlib.Path(tmp), pins, ["cu"], fetch=fetch)
            self.assertEqual(len(fetched), 2)  # both verified on disk: nothing fetched again
            out["cu"][1].unlink()  # the runtime zip gone: the dir moves aside and both come again
            run_windows_matrix.fetch_engines(pathlib.Path(tmp), pins, ["cu"], fetch=fetch)
            self.assertEqual(len(fetched), 4)
            body[pins["cu"]["cudart"]["url"]] = b"tampered!!"
            with self.assertRaisesRegex(ValueError, "cudart.zip did not match its pin"):
                run_windows_matrix.fetch_engines(pathlib.Path(tmp) / "other", pins, ["cu"], fetch=fetch)
            self.assertFalse(list((pathlib.Path(tmp) / "other").rglob("*.download")))

    def stage(self, listings):
        """windows_ssh_executor.stage_llama with the host faked: each file listing it asks for is the next of
        `listings` (the names whose pinned sha256 the host holds). -> (scp targets, PowerShell commands)"""
        import windows_ssh_executor as ex
        pins, ups, commands = self.pins(), [], []
        want = run_windows_matrix.llama_files(pins["cu"])

        def fake_ssh(command, timeout=300, check=True, runner=None):
            del timeout, check, runner
            commands.append(command)
            out = ""
            if command.startswith("foreach ($n in "):
                out = "".join(f"FILE {n} {want[n]}\n" for n in listings.pop(0))
            return subprocess.CompletedProcess([], 0, out, "")

        plan = run_windows_matrix.Plan(rows=[], models={}, labels={"llama-cuda": "cu"}, job={})
        zips = {"cu": [pathlib.Path("/m/llama-cuda.zip"), pathlib.Path("/m/cudart.zip")]}
        with patch.dict(os.environ, {"BENCH_WINDOWS_ROOT": r"C:\b"}), patch.object(ex, "ssh", fake_ssh), \
                patch.object(ex, "scp_up", lambda local, remote, runner=None: ups.append(remote)), \
                patch.object(ex.rwm, "load_pins", lambda: pins), \
                patch.object(ex.rwm, "fetch_engines", lambda *a, **k: zips), redirect_stdout(io.StringIO()):
            ex.stage_llama(plan, argparse.Namespace(engines_dir=None))
        return ups, commands

    def test_stage_puts_both_zips_in_the_cuda_dir_and_checks_every_pinned_file(self):
        everything = ["llama-cli.exe", "ggml-cuda.dll", "cudart64_13.dll"]
        # only llama-cli.exe matches (b11721's three assets carry one exe): the dir is staged, both zips
        ups, commands = self.stage([["llama-cli.exe"], everything])
        self.assertEqual(ups, [r"C:\b\engines\llama-cuda\llama-cuda.zip", r"C:\b\engines\llama-cuda\cudart.zip"])
        self.assertEqual(len([c for c in commands if "Expand-Archive" in c]), 2)
        ups, _ = self.stage([everything])  # every pinned file on the host already: nothing goes up
        self.assertEqual(ups, [])
        import windows_ssh_executor as ex
        with self.assertRaisesRegex(RuntimeError, r"cudart64_13\.dll differ from cu after staging"):
            self.stage([[], ["llama-cli.exe", "ggml-cuda.dll"]])
        self.assertTrue(callable(ex.host_mismatch))


if __name__ == "__main__":
    unittest.main(verbosity=2)
