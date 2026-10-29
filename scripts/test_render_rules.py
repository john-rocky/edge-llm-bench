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
import csv
import datetime
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
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
        # stamp); without backend= they stay the bare GPU arm (2026-10-19: the iOS branch was missing)
        for plat in ("mac", "ios"):
            self.assertEqual(render_dashboard.arm_of(plat, "litert-lm", {"backend": "cpu"}), "litert-lm-cpu")
            self.assertEqual(render_dashboard.arm_of(plat, "litert-lm", {}), "litert-lm")

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

            # 2) Nested Windows JSONL + Android app-path JSON in custom --raw-dir -> --out-dir
            raw_root = os.path.join(tmp, "custom-raw")
            win_camp = os.path.join(raw_root, "qwen3.5", "windows", "2026-10-29-windows")
            and_camp = os.path.join(raw_root, "qwen3.5", "android", "2026-10-29-android", "app-path-android")
            os.makedirs(win_camp)
            os.makedirs(and_camp)
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
                build_summary.main(["--raw-dir", raw_root, "--out-dir", out_dir])
            with open(os.path.join(out_dir, "device-runs.csv"), newline="") as fh:
                got = {r["platform"]: r for r in csv.DictReader(fh)}
            self.assertEqual(set(got), {"windows", "android"})
            self.assertEqual(got["windows"]["device"], "Precision 7960")
            self.assertEqual(got["windows"]["campaign"], "qwen3.5/windows/2026-10-29-windows")
            self.assertEqual(got["android"]["campaign"], "qwen3.5/android/2026-10-29-android")
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

            # Default: excluded under cpu-cap-rule
            out_def, _ = render_dashboard.build(cells, no_sched, 10, TODAY, summary_csv=summary, raw_dirs=[tmp])
            self.assertEqual(out_def[0]["status"], "cpu-capped")
            self.assertIsNone(out_def[0]["decode_tps"])

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
            self.assertEqual((hist[0]["arm"], hist[0]["decode_tps"], hist[0]["cpu_capped_counted"]),
                             ("litert-lm-cpu-ynnpack", "31.2", "3/3"))

    def test_validate_windows_cells(self):
        good = (
            "windows litert-lm org/model short-chat backend=cpu ynnpack=1 context-tokens=2048\n"
            "windows litert-lm org/model long-context-1024-gen256 backend=gpu context-tokens=2048\n"
            "windows llama.cpp org/gguf short-chat context-tokens=2048\n"
            "windows llama.cpp org/gguf long-context-1024-gen256 backend=gpu context-tokens=2048\n"
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
                    "windows llama.cpp takes no backend= (CPU) or backend=gpu (Vulkan)",
                "windows litert-lm org/model short-chat backend=gpu ynnpack=1 context-tokens=2048\n":
                    "ynnpack= is read for android litert-lm rows and mac / ios / windows litert-lm backend=cpu rows only",
                "windows litert-lm org/model short-chat backend=gpu\n":
                    "windows rows need context-tokens=",
                "windows litert-lm org/model native-benchmark-1024x256 backend=gpu context-tokens=2048\n":
                    "windows v1 supports prompt tasks only",
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
                )
            litert_file = os.path.join(tmp, "model.litertlm")
            gguf_file = os.path.join(tmp, "model-Q4_0.gguf")
            for fpath in (litert_file, gguf_file):
                with open(fpath, "wb") as fh:
                    fh.write(b"x" * 1024)
            pins = run_windows_matrix.load_pins()
            vk_label = run_windows_matrix.pinned_label(pins, "gpu")
            vk_pin = pins[vk_label]

            def fake_executor(plan, campaign_dir, args):
                inv = "inv-1"
                logs = campaign_dir / "omnilab" / inv
                logs.mkdir(parents=True, exist_ok=True)
                binaries = {run_windows_matrix.LITERT_EXE: "deadbeef"}
                for k, v in (vk_pin.get("dll_files") or {}).items():
                    binaries[f"llama-gpu/{k}"] = v
                binaries["llama-gpu/llama-cli.exe"] = vk_pin["llama_cli_sha256"]
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
                for r_idx, console in (("r00", litert_console), ("r01", llama_console)):
                    for run_i in (1, 2):
                        (logs / f"{r_idx}_run{run_i}.json").write_text(json.dumps({
                            "exitCode": 0, "timedOut": False,
                            "start": f"2026-10-29T12:00:0{run_i}Z",
                            "elapsedSeconds": 1.2, "peakWorkingSetBytes": 800 * 2**20,
                            "command": "test.exe",
                        }))
                        (logs / f"{r_idx}_run{run_i}.log").write_text(console)
                clean, total = run_windows_matrix.write_records(
                    plan, campaign_dir, inv, litert_label="21f113ea6eba", pins=pins)
                return 0 if clean == total == 4 else 1

            run_windows_matrix.register_executor("fake-omnilab", fake_executor)
            try:
                raw_dir = os.path.join(tmp, "raw")
                with patch.dict(os.environ, {"BENCH_RAW_ROOT": raw_dir}):
                    rc = run_windows_matrix.main([
                        cells_path, "--executor", "fake-omnilab", "--campaign", "2026-10-29-win",
                        "--litert-label", "21f113ea6eba",
                        "--model-file", f"litert-lm:org/model={litert_file}",
                        "--model-file", f"llama.cpp:org/gguf={gguf_file}",
                    ])
                self.assertEqual(rc, 0)
            finally:
                run_windows_matrix.EXECUTORS.pop("fake-omnilab", None)

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
            # run 1 of llama.cpp-gpu is firstEver (dropped); run 2 is cold (195.5)
            self.assertEqual(by_arm, {
                "litert-lm-cpu-ynnpack": ("measured", 80.0, 1),
                "llama.cpp-gpu": ("measured", 195.5, 1),
            })


if __name__ == "__main__":
    unittest.main(verbosity=2)
