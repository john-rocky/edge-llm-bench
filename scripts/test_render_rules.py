#!/usr/bin/env python3
"""Device-free checks of the text-check-rule and the cpu-cap-rule on the summary -> arm_row ->
dashboard path (CI: leaderboard-check).

A run whose decoded text failed the Android runner's text check (record
conditions.textCheck status FAIL) stays a row of results/summary/device-runs.csv — column
text_check — and pools into no number: render_leaderboard.arm_row drops it the way it drops
a firstEver run, and render_dashboard renders a cell left without a headline for that
reason as "text-fail" with the reason, never the rate (methodology/fairness-rules.md). A run
during which the phone capped a CPU the engine ran on (record protocolFlags cpu-capped; column
cpu_capped) is kept out the same way, and a cell left without a headline for that reason renders
as "cpu-capped": no valid run, with the count. So is a llama.cpp side build's run whose own
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
import validate_cells  # noqa: E402
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
# appended after text_check on 2026-10-07 (cpu-cap-rule)
CPU_FIELDS = ["cpu_capped", "cpu_max_freq"]
# appended after them the same day (a llama.cpp side build's device lines)
BACKEND_FIELDS = ["backend_registered"]


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
        # then backend_registered)
        self.assertEqual(header, FIELDS + CPU_FIELDS + BACKEND_FIELDS)
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
            w = csv.DictWriter(fh, fieldnames=FIELDS + CPU_FIELDS)
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
        # 2367 to 1418 MHz in every run of the session -> no valid run, never the rate
        record = {"conditions": {"cpuMaxFreqMHz": {"policy0": {"min": 1704, "hw": 1704, "cpus": "0-3"},
                                                    "policy4": {"min": 1418, "hw": 2367, "cpus": "4-7"}},
                                 "protocolFlags": ["cpu-capped"]}}
        self.assertEqual(build_summary.cpu_cap_of(record), ("true", "p0 1704/1704 p4 1418/2367"))
        record["conditions"]["protocolFlags"] = []
        # caps read, no flag (the runner found no policy of the engine's CPUs below hw)
        self.assertEqual(build_summary.cpu_cap_of(record)[0], "false")
        self.assertEqual(build_summary.cpu_cap_of({"conditions": {"exitCode": 0}}), ("", ""))   # not read
        capped = [dict(row(v, True, "", False, "llama.cpp", "org/capped", m), cpu_capped="true",
                       cpu_max_freq="p0 1704/1704 p4 1418/2367 p8 2914/2914")
                  for m, v in ((50, 3.3), (51, 3.6), (52, 2.9))]
        a = arm_row(capped)
        self.assertEqual((a["cold_median"], a["n"], a["cpu_capped_n"], a["cpu_read_n"]), (None, 0, 3, 3))
        self.assertIsNone(a["prefill"])              # no metric of a capped run survives
        out, md, history, page = self.render(
            "android llama.cpp org/capped long-context-1024-gen256 context-tokens=2048\n", capped)
        c = out[("llama.cpp", "org/capped")]
        self.assertEqual((c["status"], c["reason"], c["decode_tps"], c["n"], c["cpu_capped"]),
                         ("cpu-capped", "cpu-capped (3 of 3 runs)", None, 0, "3/3"))
        self.assertEqual(c["campaign"], "results/raw/2026-10-06-fixture-android")   # the session stays the evidence
        grid = [ln for ln in md.split("<details>")[0].splitlines()
                if ln.startswith("| **") and "no valid run" in ln]
        self.assertEqual(len(grid), 1)
        self.assertIn("— (no valid run: cpu-capped (3 of 3 runs))", grid[0])
        self.assertFalse(any(v in grid[0] for v in ("3.3", "3.6", "2.9")))   # the rate never shows
        self.assertIn("2 of 5 cells measured, 1 excluded with a reason, 1 failed the text check, "
                      "1 had no valid run (cpu-capped)", md)
        self.assertIn("no valid run: cpu-capped (3 of 3 runs)", page)
        self.assertNotIn(("llama.cpp", "org/capped"), {(h["arm"], h["model_id"]) for h in history})
        # the cells without a capped run read as before
        self.assertEqual(out[("litert-lm-gpu", "org/model")]["status"], "text-fail")
        self.assertEqual(out[("litert-lm-cpu", "org/model")]["cpu_capped"], "")

    def test_csv_carries_the_status_and_the_column(self):
        out, md, _, _ = self.render()
        with tempfile.TemporaryDirectory(prefix="render-rules-csv-") as tmp:
            render_dashboard.write_outputs(list(out.values()), md, os.path.join(tmp, "D.md"), tmp)
            with open(os.path.join(tmp, "dashboard-v1.csv"), newline="") as fh:
                got = {(r["arm"], r["model_id"]): r for r in csv.DictReader(fh)}
        self.assertEqual(render_dashboard.CSV_FIELDS[-2:], ["text_fail", "cpu_capped"])
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
        for plat in ("android", "mac"):
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
                + self.ROW.format(plat="mac", task="short-chat", backend="xnnpack", extra=" runs=4"))
        path, _ = self.cells(good)
        self.assertEqual(validate_cells.validate_file(path), ([], []))
        bad = {
            self.ROW.format(plat="android", task="short-chat", backend="gpu", extra=""): "backend=<qnn|vulkan|xnnpack>",
            self.ROW.format(plat="mac", task="short-chat", backend="vulkan", extra=""): "backend=<coreml|metal|mlx|xnnpack>",
            self.ROW.format(plat="ios", task="short-chat", backend="xnnpack", extra=""): "rows are android / mac",
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
