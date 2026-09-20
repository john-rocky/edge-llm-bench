#!/usr/bin/env python3
"""Offline long-context contracts; all device functions are mocked, never adb."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

import device_probe
import parsers
import run_campaign as campaign
import run_cell as cell

ROOT = Path(cell.ROOT)
TASK = "long-context-2048-gen256"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def iteration(p, g, rate):
    return (f"BenchmarkInfo:\n  Time to first token: 1.2 s\n"
            f"  Prefill Turn 1: Processed {p} tokens in 1s duration.\n"
            f"    Prefill Speed: {p}.0 tokens/sec.\n"
            f"  Decode Turn 1: Processed {g} tokens in 1s duration.\n"
            f"    Decode Speed: {rate} tokens/sec.\n")


TWO = "executor_settings:\nmax_tokens: 4096\n" + iteration(1986, 256, 31.0) + iteration(1986, 93, 35.0)


class LongContextTests(unittest.TestCase):
    def test_two_iterations_do_not_sum_counts_or_reuse_last_rate(self):
        samples, check = parsers.context_prompt_results(TWO, 4096, 256)
        self.assertEqual([s["generatedTokenCount"] for s in samples], [256, 93])
        self.assertEqual([s["promptTokenCount"] for s in samples], [1986, 1986])
        self.assertEqual([s["decodeTokensPerSecond"] for s in samples], [31.0, 35.0])
        self.assertEqual(check["protocolFlags"], [])

    def test_stored_three_iteration_log(self):
        path = ROOT / "results/raw/2026-09-18-dashboard-longctx-v1-m4max-mac/cli-crosscheck/gemma-4-e2b_cpu_ctx8192_p2.log"
        samples = parsers.parse_litert_iterations(path.read_text())
        self.assertEqual(len(samples), 3)
        self.assertEqual([s["promptTokenCount"] for s in samples], [2048] * 3)
        self.assertEqual([s["generatedTokenCount"] for s in samples], [256] * 3)
        self.assertGreater(len(set(s["decodeTokensPerSecond"] for s in samples)), 1)

    def test_invalid_missing_witness_and_budget_fail_closed(self):
        for text, ctx, flag in [
            (TWO + "Invalid decode and sample result\n", 4096, "invalid-decode"),
            (TWO.replace("max_tokens: 4096", ""), 4096, "allocation-witness-missing"),
            (TWO, 8192, "allocation-witness-mismatch"),
            (TWO.replace("Processed 256", "Processed 257"), 4096, "iteration-1-output-budget-exceeded"),
        ]:
            self.assertIn(flag, parsers.context_prompt_results(text, ctx, 256)[1]["protocolFlags"])
        self.assertTrue(parsers.context_prompt_results("crash before metrics", 4096, 256)[1]["protocolFlags"])

    def test_legacy_commands_identical_to_base(self):
        # Frozen from run_cell.py at ec4b0e8 (before the context-prompt path):
        # cells without context-tokens= and native-benchmark tasks must keep
        # building exactly these commands.
        frozen = [
            (("litert-lm", "cpu", "short-chat", None),
             ("./litert_lm_main --backend=cpu --model_path=MODEL --input_prompt_file=PROMPT "
              "--max_output_tokens=128 --async=false", "litert_lm_main", "engine-default", "bundle-default")),
            (("litert-lm", "gpu", "short-chat", None),
             ("./litert_lm_main --backend=gpu --model_path=MODEL --input_prompt_file=PROMPT "
              "--max_output_tokens=128 --async=false", "litert_lm_main", "engine-default", "bundle-default")),
            (("llama.cpp", None, "short-chat", None),
             ("./llama-cli -m MODEL -t 4 -c 4096 -f PROMPT -n 128 --temp 0 --top-p 1 -st",
              "llama-cli", "greedy", 4096)),
            (("litert-lm", "gpu", "native-benchmark-128x256", 4096),
             ("./litert_lm_advanced_main --backend=gpu --model_path=MODEL --benchmark "
              "--benchmark_prefill_tokens=128 --benchmark_decode_tokens=256 --async=false "
              "--max_num_tokens=4096", "litert_lm_advanced_main", "engine-default", 4096)),
            (("llama.cpp", None, "native-benchmark-128x256", 4096),
             ("./llama-bench -m MODEL -t 4 -p 128 -n 256 -o json", "llama-bench",
              "n/a (llama-bench)", "llama-bench-managed")),
        ]
        for (runtime, backend, task, ctx), expected in frozen:
            self.assertEqual(cell.engine_command(runtime, backend, "MODEL", task, "PROMPT", 128, None, ctx), expected)
        # A literal dashboard row with its real device paths stays on the plain main.
        _, dashboard, _ = campaign.parse_cells(ROOT / "matrices/dashboard-text-v1-android-a.cells")
        row = next(c for c in dashboard if c["opts"].get("backend") == "gpu")
        model = f"{cell.DEV_DIR}/models/{row['model_id'].replace('/', '_')}_{row['opts']['file']}"
        prompt = f"{cell.DEV_DIR}/prompts/short-chat.txt"
        command, binary, _, note = cell.engine_command(row["runtime"], "gpu", model, row["task"], prompt, 128, None, None)
        self.assertEqual(command, f"./litert_lm_main --backend=gpu --model_path={model} "
                                  f"--input_prompt_file={prompt} --max_output_tokens=128 --async=false")
        self.assertEqual((binary, note), ("litert_lm_main", "bundle-default"))

    def test_advanced_prompt_command_keeps_real_input(self):
        command, binary, sampler, _ = cell.engine_command("litert-lm", "cpu", "MODEL", TASK, "PROMPT", 256, None, 4096)
        self.assertEqual(binary, "litert_lm_advanced_main")
        self.assertEqual(sampler, "engine-default")
        for flag in ("--num_iterations=2", "--benchmark_prefill_tokens=0", "--benchmark_decode_tokens=0",
                     "--input_prompt_file=PROMPT", "--max_num_tokens=4096", "--max_output_tokens=256", "--use_session=false"):
            self.assertIn(flag, command)

    def test_prompt_matches_swift_literals_and_27_blocks(self):
        generator = load_module("prompt_generator", ROOT / "scripts/gen_task_prompts.py")
        swift = (ROOT / "ios/BenchmarkApp/Sources/Benchmark/Tasks/LongContextTask.swift").read_text()
        raw_lorem = re.search(r'let lorem = """\n(.*?)\n\s*"""', swift, re.S).group(1)
        lorem = "".join(line.strip().removesuffix("\\") for line in raw_lorem.splitlines())
        tail_branch = swift.split("if forceLongOutput {")[1].split("} else {")[0]
        strings = re.findall(r'"((?:\\.|[^"\\])*)"', tail_branch)
        tail = "".join(json.loads('"' + s + '"') for s in strings)
        registry = (ROOT / "ios/BenchmarkApp/Sources/Benchmark/BenchmarkTask.swift").read_text()
        definition = re.search(r'LongContextTask\(id: "' + TASK + r'"(.*?)\)', registry, re.S).group(1)
        blocks = int(re.search(r"blocks: (\d+)", definition).group(1))
        swift_budget = int(re.search(r"maxTokens: (\d+)", definition).group(1))
        self.assertIn("forceLongOutput: true", definition)
        self.assertEqual(blocks, 27)
        expected = "\n".join([f"[{i}] {lorem}" for i in range(blocks)] + [tail])
        actual, budget = generator.PROMPTS[TASK]
        self.assertEqual(actual.encode(), expected.encode())
        self.assertEqual((ROOT / "prompts/text" / (TASK + ".txt")).read_bytes(), expected.encode())
        self.assertEqual(budget, swift_budget)
        self.assertEqual(budget, 256)
        self.assertEqual(len(re.findall(r"^\[\d+\]", actual, re.M)), 27)

    def test_battery_temperature_conversion_and_absence(self):
        with patch.object(device_probe, "adb", return_value="level: 91\nstatus: 2\nUSB powered: true\ntemperature: 367\n"):
            self.assertEqual(device_probe.battery("NEVER-CONNECT")["temperatureC"], 36.7)
        with patch.object(device_probe, "adb", return_value="level: 91"):
            self.assertIsNone(device_probe.battery("NEVER-CONNECT")["temperatureC"])

    def test_round_order_and_adjacency_all_sittings(self):
        for suffix in ("", "-qwen06", "-qwen17", "-qwen4", "-gemmae2b", "-gemmae4b"):
            path = ROOT / "matrices" / f"dashboard-longctx-v1-android-s26{suffix}.cells"
            anchors, payload, _ = campaign.parse_cells(path)
            schedule = list(campaign.round_schedule(anchors, payload, 2))
            one = [c for r, l, c in schedule if r == 1]
            two = [c for r, l, c in schedule if r == 2]
            self.assertEqual(two, list(reversed(one)))
            for order in (one, two):
                self.assertEqual(sum(c["opts"].get("anchor") == "1" for c in order), 1)
                keys = [(c["runtime"], c["model_id"], c["opts"].get("backend"), c["opts"].get("file"))
                        for c in order if not c["opts"].get("anchor")]
                for key in set(keys):
                    positions = [i for i, k in enumerate(keys) if k == key]
                    self.assertEqual(positions, list(range(min(positions), max(positions) + 1)))

    def test_dry_run_never_touches_device_or_subprocess(self):
        path = ROOT / "matrices/dashboard-longctx-v1-android-s26-gemmae2b.cells"
        with patch.dict(os.environ, {"ROUNDS": "2"}), patch.object(sys, "argv", ["run_campaign.py", str(path), "--dry-run"]), \
             patch.object(campaign.subprocess, "run", side_effect=AssertionError("subprocess forbidden")), \
             patch.object(campaign.subprocess, "call", side_effect=AssertionError("subprocess forbidden")), \
             patch.object(campaign, "thermal_status", side_effect=AssertionError("device forbidden")), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(campaign.main(), 0)
        plan = [json.loads(line) for line in output.getvalue().splitlines()]
        launches = [p for p in plan if "launch" in p]
        self.assertEqual(len(launches), 20)
        self.assertEqual([p["cell"] for p in launches[10:]], [p["cell"] for p in launches[:10]][::-1])

    def test_capture_identity_includes_file_backend_allocation(self):
        stems = {cell.capture_stem("litert-lm", backend, "repo/model", TASK, file, ctx)
                 for backend in ("cpu", "gpu") for ctx in (2304, 4096, 8192) for file in ("one.litertlm", "two.litertlm")}
        self.assertEqual(len(stems), 12)

    def test_gate_selection_does_not_mix_allocations_or_files(self):
        with tempfile.TemporaryDirectory(prefix="longctx-identity-") as tmp:
            for filename in ("one.litertlm", "two.litertlm"):
                for ctx in (2304, 4096, 8192):
                    name = cell.capture_stem("litert-lm", "cpu", "repo/model", TASK, filename, ctx)
                    (Path(tmp) / (name + "_stamp_run1_iter1.json")).write_text("{}")
            target = {"runtime": "litert-lm", "model_id": "repo/model", "task": TASK,
                      "opts": {"backend": "cpu", "file": "one.litertlm", "context-tokens": "4096"}}
            selected = campaign.cell_records(target, tmp)
            self.assertEqual(len(selected), 1)
            self.assertIn("__ctx4096_", selected[0])

    def run_mocked_cell(self, output, runtime="litert-lm", hot=False, exit_code=0):
        tmp = tempfile.TemporaryDirectory(prefix="longctx-unit-")
        self.addCleanup(tmp.cleanup)
        folder = Path(tmp.name)
        model = folder / "model.litertlm"
        model.write_bytes(b"offline fixture")
        argv = ["run_cell.py", "--runtime", runtime, "--model-id", "fixture/model", "--task", TASK,
                "--runs", "1", "--context-tokens", "4096", "--file", str(model), "--out", str(folder),
                "--round-index", "2", "--launch-index", "7", "--serial", "NEVER-CONNECT"]
        if runtime == "litert-lm": argv += ["--backend", "gpu"]
        if hot: argv += ["--gate-timed-out"]
        with patch.object(sys, "argv", argv), \
             patch.object(cell, "ensure_model", return_value=("/fixture/model", str(model))), \
             patch.object(cell, "push_prompt", return_value=("/fixture/prompt", 256)), \
             patch.object(cell, "observed_engine", return_value=("b8999" if runtime == "llama.cpp" else "v0.16.0", "fixture-sha")), \
             patch.object(cell, "adb", return_value="present"), \
             patch.object(cell, "device_info", return_value={"systemName": "Android", "modelIdentifier": "OFFLINE-FIXTURE"}), \
             patch.object(cell, "thermal_status", return_value=(1, "light") if hot else (0, "nominal")), \
             patch.object(cell, "battery", side_effect=[{"batteryLevel": 1.0, "batteryState": "charging", "temperatureC": 31.2},
                                                       {"batteryLevel": 0.99, "batteryState": "charging", "temperatureC": 32.4}]), \
             patch.object(cell, "run_once", return_value=(output, exit_code, 512.0)) as launch:
            rc = cell.main()
        self.assertEqual(launch.call_count, 1)
        rows = [json.loads(p.read_text()) for p in sorted(folder.glob("*.json"))]
        for r in rows:
            self.assertEqual((folder / r["provenance"]["rawLog"]).read_text(), output)
            self.assertEqual(r["conditions"]["roundIndex"], 2)
            self.assertEqual(r["conditions"]["launchIndex"], 7)
        return rc, rows

    def test_two_records_regimes_temperature_and_thermal_timeout(self):
        rc, rows = self.run_mocked_cell(TWO, hot=True)
        self.assertEqual(rc, 0)  # thermal admission is the session reviewer's decision
        self.assertEqual([r["conditions"]["regime"] for r in rows], ["cold", "warm"])
        self.assertEqual([r["metrics"]["generatedTokenCount"] for r in rows], [256, 93])
        self.assertEqual([r["metrics"]["coldRun"] for r in rows], [True, False])
        self.assertEqual(len({r["conditions"]["launchID"] for r in rows}), 1)
        for r in rows:
            self.assertEqual(r["conditions"]["batteryTemperatureInitialC"], 31.2)
            self.assertEqual(r["conditions"]["batteryTemperatureFinalC"], 32.4)
            self.assertTrue(r["conditions"]["thermalGateTimeoutNonNominal"])

    def test_missing_second_iteration_keeps_failed_record_without_borrowing_counts(self):
        rc, rows = self.run_mocked_cell("max_tokens: 4096\n" + iteration(1986, 256, 31.0))
        self.assertEqual(rc, 1)
        self.assertEqual(len(rows), 2)
        self.assertNotIn("generatedTokenCount", rows[1]["metrics"])

    def test_nonzero_exit_retains_both_records_and_flags_the_launch(self):
        rc, rows = self.run_mocked_cell(TWO, exit_code=139)
        self.assertEqual(rc, 1)
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(row["conditions"]["exitCode"], 139)
            self.assertIn("engine-exit-139", row["conditions"]["protocolFlags"])

    def test_llama_control_has_one_cold_process_record(self):
        rc, rows = self.run_mocked_cell("[ Prompt: 200.0 t/s | Generation: 20.0 t/s ]", runtime="llama.cpp")
        self.assertEqual(rc, 0)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["conditions"]["regime"], "cold-process")
        self.assertNotIn("generatedTokenCount", rows[0]["metrics"])

    def test_report_reads_android_layout_and_preserves_regimes(self):
        report = load_module("longctx_report", ROOT / "scripts/longctx_ab_report.py")
        _, rows = self.run_mocked_cell(TWO)
        _, control = self.run_mocked_cell("[ Prompt: 200.0 t/s | Generation: 20.0 t/s ]", runtime="llama.cpp")
        with tempfile.TemporaryDirectory(prefix="longctx-report-") as tmp:
            folder = Path(tmp) / "app-path-android"
            folder.mkdir()
            for i, row in enumerate(rows + control):
                (folder / f"{i}.json").write_text(json.dumps(row))
            (folder / "excluded.json.attempt1").write_text(json.dumps(rows[0]))
            loaded = report.load(tmp, TASK)
            self.assertEqual([r["regime"] for r in loaded], ["cold", "warm", "cold-process"])
            self.assertEqual([r["ctx"] for r in loaded], [4096] * 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
