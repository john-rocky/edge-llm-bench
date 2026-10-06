#!/usr/bin/env python3
"""Device-free checks of the text-check-rule on the summary -> arm_row -> dashboard path
(CI: leaderboard-check).

A run whose decoded text failed the Android runner's text check (record
conditions.textCheck status FAIL) stays a row of results/summary/device-runs.csv — column
text_check — and pools into no number: render_leaderboard.arm_row drops it the way it drops
a firstEver run, and render_dashboard renders a cell left without a headline for that
reason as "text-fail" with the reason, never the rate (methodology/fairness-rules.md).

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
from render_leaderboard import arm_row  # noqa: E402

OFF = "FAIL:text-off-task-screen"
TODAY = datetime.date(2026, 10, 6)
FIELDS = ["source", "campaign", "platform", "timestamp", "runtime", "schema_version",
          "engine_version", "engine_artifact", "model_id", "quantization", "task",
          "harness_stamp", "decode_tps", "decode_tps_wall", "prefill_tps", "prompt_tokens",
          "gen_tokens", "ttft_ms", "mem_footprint_median_mb", "mem_resident_median_mb",
          "energy_j_per_tok", "thermal_initial", "thermal_final", "battery_state", "cold_run",
          "first_ever", "context_tokens", "device", "os_version", "mem_footprint_peak_mb",
          "mem_resident_peak_mb", "text_check"]


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
        self.assertEqual(header[-1], "text_check")   # appended: every earlier column keeps its place
        self.assertEqual(header[:-1], FIELDS[:-1])
        by_name = {os.path.basename(r["source"]): r["text_check"] for r in got}
        self.assertEqual(by_name, {"pass.json": "PASS",
                                   "fail.json": "FAIL:text-empty-or-degenerate,text-off-task-screen",
                                   "unchecked.json": "", "odd.json": ""})


class Dashboard(unittest.TestCase):
    CELLS = ("android litert-lm org/model long-context-1024-gen256 backend=gpu context-tokens=2048\n"
             "android litert-lm org/model long-context-1024-gen256 backend=cpu context-tokens=2048\n"
             "android llama.cpp org/gguf long-context-1024-gen256 context-tokens=2048\n"
             "android litert-lm org/other long-context-1024-gen256 backend=gpu context-tokens=2048 "
             "exclude=fixture-reason\n")

    def render(self):
        rows = (session([25.7, 25.5, 26.0], [25.7, 26.1, 26.0], [OFF] * 3)
                + session([30.0, 30.0, 10.0], [31.0, 31.0, 9.0], ["PASS", "PASS", OFF], runtime="litert-lm-cpu")
                + [row(19.4, True, "", False, "llama.cpp", "org/gguf", m) for m in (40, 41, 42)]
                + session([5.0, 5.0, 5.0], [5.0, 5.0, 5.0], [OFF] * 3, model_id="org/other"))
        tmp = tempfile.TemporaryDirectory(prefix="render-rules-dashboard-")
        self.addCleanup(tmp.cleanup)
        summary = os.path.join(tmp.name, "device-runs.csv")
        with open(summary, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(rows)
        cells = os.path.join(tmp.name, "fixture.cells")
        with open(cells, "w") as fh:
            fh.write(self.CELLS)
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

    def test_csv_carries_the_status_and_the_column(self):
        out, md, _, _ = self.render()
        with tempfile.TemporaryDirectory(prefix="render-rules-csv-") as tmp:
            render_dashboard.write_outputs(list(out.values()), md, os.path.join(tmp, "D.md"), tmp)
            with open(os.path.join(tmp, "dashboard-v1.csv"), newline="") as fh:
                got = {(r["arm"], r["model_id"]): r for r in csv.DictReader(fh)}
        self.assertEqual(render_dashboard.CSV_FIELDS[-1], "text_fail")
        self.assertEqual(got[("litert-lm-gpu", "org/model")]["status"], "text-fail")
        self.assertEqual(got[("litert-lm-gpu", "org/model")]["decode_tps"], "")
        self.assertEqual(got[("litert-lm-cpu", "org/model")]["text_fail"], "2/5")


if __name__ == "__main__":
    unittest.main(verbosity=2)
