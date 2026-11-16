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


REPLY = ("On-device AI lets a phone answer offline: the model runs locally, so private text "
         "never reaches a cloud server and replies keep coming without a network.")
OFF_TASK = ("Please share the document you want summarised and the questions you have about it, "
            "and I will answer each of them in order.")


def turn(text):
    """advanced_main's preamble to one iteration: the turn's log line, then the decoded text
    (the runner's text check reads it; on by default for this path)."""
    return f"I0000 00:00:1.000000 1 litert_lm_lib.cc:868] Running single-turn conversation\n{text}\n"


TWO = ("executor_settings:\nmax_tokens: 4096\n" + turn(REPLY) + iteration(1986, 256, 31.0)
       + turn(REPLY) + iteration(1986, 93, 35.0))


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
             patch.object(cell, "screen_conditions", return_value={"screen": "on-usb", "screenSource": "measured"}), \
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

    def test_text_check_is_on_by_default_and_a_fail_keeps_its_records(self):
        # text-check-rule: no env -> checked; off-task text -> the launch fails (FAILURES.txt
        # in a campaign) while both records stay with their rate, flagged; =0 turns it off
        off = TWO.replace(REPLY, OFF_TASK)
        with patch.dict(os.environ):
            os.environ.pop("BENCH_TEXT_CHECK", None)
            rc, rows = self.run_mocked_cell(TWO)
            self.assertEqual(rc, 0)
            self.assertEqual([r["conditions"]["textCheck"]["status"] for r in rows], ["PASS", "PASS"])
            rc, rows = self.run_mocked_cell(off)
            self.assertEqual(rc, 1)
            self.assertEqual(len(rows), 2)
            for r in rows:
                self.assertEqual(r["conditions"]["textCheck"]["flags"], ["text-off-task-screen"])
                self.assertIn("text-off-task-screen", r["conditions"]["protocolFlags"])
                self.assertTrue(r["metrics"]["decodeTokensPerSecond"])
            os.environ["BENCH_TEXT_CHECK"] = "0"
            rc, rows = self.run_mocked_cell(off)
            self.assertEqual(rc, 0)
            self.assertFalse(any("textCheck" in r["conditions"] for r in rows))

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

    def test_llama_bench_two_launch_commands(self):
        # a llama.cpp native-benchmark run = the prefill launch, then the decode launch at the
        # prefill's depth; a side build's flags on both; without a phase the one-process form
        task, side = "native-benchmark-1024x256", f"{cell.ENGINES_DIR}/b1"
        want = {
            (None, None): ("./llama-bench -m MODEL -t 4 -p 1024 -n 0 -o json",
                           "./llama-bench -m MODEL -t 4 -p 0 -n 256 -d 1024 -o json"),
            (None, side): (f"{side}/bin/llama-bench -m MODEL -t 4 -p 1024 -n 0 -o json",
                           f"{side}/bin/llama-bench -m MODEL -t 4 -p 0 -n 256 -d 1024 -o json"),
            ("gpu", side): (f"{side}/bin/llama-bench -m MODEL -t 6 -p 1024 -n 0 -o json -ngl 99 --device GPUOpenCL",
                            f"{side}/bin/llama-bench -m MODEL -t 6 -p 0 -n 256 -d 1024 -o json -ngl 99 "
                            "--device GPUOpenCL"),
            ("npu", side): (f"{side}/bin/llama-bench -m MODEL -t 6 -p 1024 -n 0 -o json -ngl 99 -ub 1024 --device HTP0",
                            f"{side}/bin/llama-bench -m MODEL -t 6 -p 0 -n 256 -d 1024 -o json -ngl 99 -ub 1024 "
                            "--device HTP0"),
        }
        self.assertEqual(cell.LLAMA_BENCH_PHASES, ("prefill", "decode"))
        for (backend, engine_dir), launches in want.items():
            got = [cell.engine_command("llama.cpp", backend, "MODEL", task, None, None, None, None,
                                       engine_dir=engine_dir, bench_phase=phase) for phase in cell.LLAMA_BENCH_PHASES]
            self.assertEqual(tuple(g[0] for g in got), launches)
            self.assertEqual({g[1:] for g in got}, {("llama-bench", "n/a (llama-bench)", "llama-bench-managed")})
            one = cell.engine_command("llama.cpp", backend, "MODEL", task, None, None, None, None, engine_dir=engine_dir)
            self.assertEqual(one[0], launches[0].replace(" -p 1024 -n 0 ", " -p 1024 -n 256 "))
        with self.assertRaises(ValueError):
            cell.llama_bench_counts(task, "both")

    def test_llama_bench_launch_test_reads_counts_and_depth(self):
        def t(p, g, d):
            return {"n_prompt": p, "n_gen": g, "n_depth": d, "avg_ts": 1.0}
        check = parsers.llama_bench_launch_test
        self.assertEqual(check([t(1024, 0, 0)], "prefill", 1024, 256), (t(1024, 0, 0), []))
        self.assertEqual(check([t(1024, 0, None)], "prefill", 1024, 256), (t(1024, 0, None), []))
        self.assertEqual(check([t(0, 256, 1024)], "decode", 1024, 256), (t(0, 256, 1024), []))
        for tests, phase, flag in [
            ([t(1024, 0, 0), t(0, 256, 0)], "prefill", "prompt-token-count-mismatch"),   # the one-process form
            ([t(512, 0, 0)], "prefill", "prompt-token-count-mismatch"),
            ([], "decode", "decode-token-count-mismatch"),
            ([t(0, 128, 1024)], "decode", "decode-token-count-mismatch"),
            ([t(0, 256, 0)], "decode", "decode-depth-mismatch"),                         # -d not applied
            ([t(0, 256, None)], "decode", "decode-depth-mismatch"),
        ]:
            self.assertEqual(check(tests, phase, 1024, 256), (None, [flag]))

    @staticmethod
    def bench_console(tests, policy6_khz=4742400):
        """A llama-bench launch's console as run_cell.run_once returns it: the sampler's CPU lines
        (policy6 read at policy6_khz), its memory reads, the engine's JSON, the exit line."""
        return ("CPUPOLICY policy0 3628800 0 1 2 3 4 5\nCPUPOLICY policy6 4742400 6 7\n"
                f"VmHWM:\t  400000 kB\nVmRSS:\t  380000 kB\nCpus_allowed_list:\t0-7\nCPUMAX 3628800 {policy6_khz}\n"
                "===ENGINE_OUTPUT===\n" + json.dumps(tests, indent=2) + "\nEXIT_CODE=0\n")

    def run_mocked_bench(self, consoles, backend=None, thermal=((0, "nominal"),) * 3):
        """run_cell.main on a llama.cpp native-benchmark-1024x256 row, runs=1, --launch-cooldown 120:
        consoles = {phase: console} (the launch's command picks it); every device read mocked."""
        tmp = tempfile.TemporaryDirectory(prefix="llama-bench-unit-")
        self.addCleanup(tmp.cleanup)
        folder = Path(tmp.name)
        model = folder / "model.gguf"
        model.write_bytes(b"offline fixture")
        argv = ["run_cell.py", "--runtime", "llama.cpp", "--model-id", "fixture/model", "--task",
                "native-benchmark-1024x256", "--runs", "1", "--file", str(model), "--out", str(folder),
                "--serial", "NEVER-CONNECT", "--launch-cooldown", "120"]
        if backend:
            argv += ["--backend", backend, "--engine-build", "b1"]

        def launch(cmd, *rest, **kw):
            return consoles["decode" if " -d 1024 " in cmd else "prefill"], 0, 371.0

        with patch.object(sys, "argv", argv), patch.dict(os.environ), \
             patch.object(cell, "ensure_model", return_value=("/fixture/model.gguf", str(model))), \
             patch.object(cell, "observed_engine", return_value=("b11721", "fixture-sha")), \
             patch.object(cell, "adb", return_value="present"), \
             patch.object(cell, "device_info", return_value={"systemName": "Android", "modelIdentifier": "OFFLINE-FIXTURE"}), \
             patch.object(cell, "thermal_status", side_effect=list(thermal)), \
             patch.object(cell, "screen_conditions", return_value={"screen": "on-usb", "screenSource": "measured"}), \
             patch.object(cell, "battery", return_value={"batteryLevel": 0.9, "batteryState": "charging", "temperatureC": 31.0}), \
             patch.object(cell, "wait_cpu_uncapped", return_value=False) as cap_wait, \
             patch.object(cell.time, "sleep") as sleep, \
             patch.object(cell, "run_once", side_effect=launch) as run:
            os.environ.pop("BENCH_SESSION_DEADLINE", None)
            rc = cell.main()
        rows = [json.loads(p.read_text()) for p in sorted(folder.glob("*.json"))]
        self.assertEqual(len(rows), 1)
        self.assertEqual(cap_wait.call_count, 2)                     # the cpu-cap wait before each launch
        self.assertEqual([c.args for c in sleep.call_args_list], [(120,)])   # the cooldown between them
        return rc, rows[0], [c.args[0] for c in run.call_args_list], (folder / rows[0]["provenance"]["rawLog"]).read_text()

    def bench_test(self, p, g, d, rate, **fields):
        return {"n_prompt": p, "n_gen": g, "n_depth": d, "avg_ts": rate, "stddev_ts": 0.5, **fields}

    def test_llama_bench_run_is_two_launches_flat(self):
        # the flat build: prefill rate from the prefill launch, decode rate from the decode launch
        # at depth 1024; both commands and each launch's cap reads in the record; the decode
        # launch's capped policy flags the run; its start off nominal makes the run's start state
        consoles = {"prefill": self.bench_console([self.bench_test(1024, 0, 0, 495.5)]),
                    "decode": self.bench_console([self.bench_test(0, 256, 1024, 151.25)], policy6_khz=4000000)}
        rc, row, cmds, log = self.run_mocked_bench(consoles, thermal=[(0, "nominal"), (1, "light"), (1, "light")])
        self.assertEqual(rc, 0)   # a cap and a start state are conditions, not engine failures (cpu-cap-rule)
        self.assertEqual(cmds, ["./llama-bench -m /fixture/model.gguf -t 4 -p 1024 -n 0 -o json",
                                "./llama-bench -m /fixture/model.gguf -t 4 -p 0 -n 256 -d 1024 -o json"])
        m, c = row["metrics"], row["conditions"]
        self.assertEqual((m["promptTokensPerSecond"], m["promptTokenCount"], m["decodeTokensPerSecond"],
                          m["generatedTokenCount"], m["coldRun"]), (495.5, 1024, 151.25, 256, False))
        self.assertEqual([(x["phase"], x["engineCommand"]) for x in c["launches"]], list(zip(("prefill", "decode"), cmds)))
        self.assertEqual(c["launches"][1]["cooldownBeforeSeconds"], 120)
        self.assertNotIn("cooldownBeforeSeconds", c["launches"][0])
        self.assertEqual([x["cpuMaxFreqMHz"]["policy6"]["min"] for x in c["launches"]], [4742.4, 4000])
        self.assertEqual([bool(x["cpuCapped"]) for x in c["launches"]], [False, True])
        self.assertEqual([x["llamaBenchTests"][0]["n_depth"] for x in c["launches"]], [0, 1024])
        self.assertEqual(c["cpuMaxFreqMHz"]["policy6"], {"min": 4000, "hw": 4742.4, "cpus": "6-7"})
        self.assertEqual(c["cpusAllowedList"], "0-7")
        self.assertIn("cpu-capped", c["protocolFlags"])
        self.assertEqual((m["initialThermalState"], c["thermalRawStatus"]), ("light", 1))
        self.assertEqual([x["initialThermalState"] for x in c["launches"]], ["nominal", "light"])
        self.assertNotIn("engineCommand", c)   # the flat build's record names its commands per launch
        self.assertEqual(log.count("===ENGINE_OUTPUT==="), 2)
        self.assertTrue(log.startswith("===LAUNCH 1/2 prefill===\n") and "\n===LAUNCH 2/2 decode===\n" in log)

    def test_llama_bench_run_is_two_launches_side_build(self):
        # a GPU side build: its flags and env on both launches, the device read from both JSONs
        dev = {"devices": "GPUOpenCL", "backends": "OpenCL", "gpu_info": "Adreno", "n_gpu_layers": 99,
               "flash_attn": -1, "n_ubatch": 512}
        consoles = {"prefill": self.bench_console([self.bench_test(1024, 0, 0, 900.0, **dev)]),
                    "decode": self.bench_console([self.bench_test(0, 256, 1024, 40.0, **dev)])}
        rc, row, cmds, _ = self.run_mocked_bench(consoles, backend="gpu")
        self.assertEqual(rc, 0)
        side = f"{cell.ENGINES_DIR}/b1"
        self.assertEqual(cmds, [f"{side}/bin/llama-bench -m /fixture/model.gguf -t 6 -p 1024 -n 0 -o json -ngl 99 "
                                "--device GPUOpenCL",
                                f"{side}/bin/llama-bench -m /fixture/model.gguf -t 6 -p 0 -n 256 -d 1024 -o json -ngl 99 "
                                "--device GPUOpenCL"])
        c, env = row["conditions"], cell.launch_env(side, "gpu", "llama.cpp")
        self.assertEqual(row["runtime"], "llama.cpp-gpu")
        self.assertEqual([x["engineCommand"] for x in c["launches"]], [f"{env} {cmd}" for cmd in cmds])
        self.assertEqual(c["engineCommand"], f"{env} {cmds[0]} ; {env} {cmds[1]}")
        self.assertEqual(len(c["backendRegistered"]), 1)
        self.assertNotIn("protocolFlags", c)
        self.assertEqual((row["metrics"]["promptTokensPerSecond"], row["metrics"]["decodeTokensPerSecond"]), (900.0, 40.0))

    def test_llama_bench_decode_off_its_depth_gives_no_decode_rate(self):
        consoles = {"prefill": self.bench_console([self.bench_test(1024, 0, 0, 495.5)]),
                    "decode": self.bench_console([self.bench_test(0, 256, 0, 190.0)])}
        rc, row, _, _ = self.run_mocked_bench(consoles)
        self.assertEqual(rc, 1)
        self.assertEqual(row["conditions"]["protocolFlags"], ["decode-depth-mismatch"])
        self.assertNotIn("decodeTokensPerSecond", row["metrics"])
        self.assertEqual(row["metrics"]["promptTokensPerSecond"], 495.5)

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
