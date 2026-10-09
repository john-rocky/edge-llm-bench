#!/usr/bin/env python3
"""Offline contracts for the p1024 / d256 / ctx-2048 cells (task long-context-1024-gen256)
of the dashboard job, and for the Android runner's gate on their two-iteration launches.

Nothing touches adb: launches, sleeps and thermal reads are mocked; the gate is the real
scripts/cell_gate.py. The cells contract is read from the committed files: the weekly set
(matrices/dashboard-text-v1.cells and its Android storage halves) and the 1024-only set
(matrices/dashboard-longctx1024-v1*.cells) carry the same 1024 rows.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import parsers
import run_campaign as campaign
import run_cell as cell

ROOT = Path(cell.ROOT)
TASK = "long-context-1024-gen256"
CTX = 2048
BUDGET = 256
WEEKLY = ROOT / "matrices/dashboard-text-v1.cells"
HALVES = {h: ROOT / f"matrices/dashboard-text-v1-android-{h}.cells" for h in ("a", "b1", "b2")}
ONLY_1024 = [ROOT / "matrices/dashboard-longctx1024-v1.cells"] + [
    ROOT / f"matrices/dashboard-longctx1024-v1-android-{h}.cells" for h in ("a", "b1", "b2")]
GATE = ROOT / "scripts/cell_gate.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATE = load_module("validate_cells", ROOT / "scripts/validate_cells.py")


def rows(path):
    """(line, platform, runtime, model id, task, opts) per active or excluded row."""
    out = []
    for raw in Path(path).read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            out.append((line, *VALIDATE.parse_line(line)))
    return out


def android_cell(line):
    parts = line.split()
    return {"runtime": parts[1], "model_id": parts[2], "task": parts[3],
            "opts": dict(kv.split("=", 1) for kv in parts[4:])}


# ------------------------------------------------------------------ the task

class TaskContract(unittest.TestCase):
    def test_prompt_matches_the_swift_task_and_its_budget(self):
        generator = load_module("prompt_generator", ROOT / "scripts/gen_task_prompts.py")
        swift = (ROOT / "ios/BenchmarkApp/Sources/Benchmark/Tasks/LongContextTask.swift").read_text()
        raw_lorem = re.search(r'let lorem = """\n(.*?)\n\s*"""', swift, re.S).group(1)
        lorem = "".join(line.strip().removesuffix("\\") for line in raw_lorem.splitlines())
        tail_branch = swift.split("if forceLongOutput {")[1].split("} else {")[0]
        tail = "".join(json.loads('"' + s + '"') for s in re.findall(r'"((?:\\.|[^"\\])*)"', tail_branch))
        per_block = int(re.search(r"tokensPerBlock = (\d+)", swift).group(1))
        registry = (ROOT / "ios/BenchmarkApp/Sources/Benchmark/BenchmarkTask.swift").read_text()
        definition = re.search(r'LongContextTask\(id: "' + TASK + r'"(.*?)\)', registry, re.S).group(1)
        self.assertIn("forceLongOutput: true", definition)
        self.assertNotIn("blocks:", definition)          # the block count is the estimate
        target = int(re.search(r"targetTokens: (\d+)", definition).group(1))
        blocks = max(1, target // per_block)
        self.assertEqual(blocks, 18)
        expected = "\n".join([f"[{i}] {lorem}" for i in range(blocks)] + [tail])
        text, budget = generator.PROMPTS[TASK]
        self.assertEqual(text.encode(), expected.encode())
        self.assertEqual((ROOT / "prompts/text" / f"{TASK}.txt").read_bytes(), expected.encode())
        self.assertEqual(budget, int(re.search(r"maxTokens: (\d+)", definition).group(1)))
        self.assertEqual(budget, BUDGET)
        budgets = dict(line.split("\t") for line in (ROOT / "prompts/text/budgets.tsv").read_text().splitlines())
        self.assertEqual(int(budgets[TASK]), BUDGET)

    def test_a_protocol_launch_parses_clean_and_overruns_are_flagged(self):
        def iteration(p, g, rate):
            return (f"BenchmarkInfo:\n  Time to first token: 0.9 s\n"
                    f"  Prefill Turn 1: Processed {p} tokens in 1s duration.\n"
                    f"    Prefill Speed: {p}.0 tokens/sec.\n"
                    f"  Decode Turn 1: Processed {g} tokens in 1s duration.\n"
                    f"    Decode Speed: {rate} tokens/sec.\n")
        clean = f"executor_settings:\nmax_tokens: {CTX}\n" + iteration(1339, 256, 40.0) + iteration(1339, 256, 41.0)
        samples, check = parsers.context_prompt_results(clean, CTX, BUDGET)
        self.assertEqual(check["protocolFlags"], [])     # 1,339 + 256 fits the 2,048 allocation
        self.assertEqual([s["promptTokenCount"] for s in samples], [1339, 1339])
        over = clean.replace("Processed 256", "Processed 257", 1)
        self.assertIn("iteration-1-output-budget-exceeded",
                      parsers.context_prompt_results(over, CTX, BUDGET)[1]["protocolFlags"])


# ------------------------------------------------------------------ the cells

class CellsContract(unittest.TestCase):
    TWIN_RUNTIMES = ("litert-lm", "llama.cpp", "mlx-swift", "executorch", "onnxruntime-genai")

    def test_every_short_chat_row_has_one_1024_twin(self):
        weekly = rows(WEEKLY)
        twins = [r for r in weekly if r[4] == TASK]
        expected = 0
        for line, plat, rt, mid, task, opts in weekly:
            if task != "short-chat":
                continue
            # one arm = runtime + backend (Android litert cpu and gpu share the model id)
            matches = [t for t in twins if t[1:4] == (plat, rt, mid)
                       and t[5].get("backend") == opts.get("backend")]
            if rt not in self.TWIN_RUNTIMES:
                self.assertEqual(matches, [], f"no 1024 row for {rt}: {line}")
                continue
            expected += 1
            self.assertEqual(len(matches), 1, line)
            twin = matches[0][5]
            for key in ("backend", "file", "cooldown", "exclude"):
                self.assertEqual(twin.get(key), opts.get(key), f"{key}: {matches[0][0]}")
            self.assertNotIn("anchor", twin)               # the anchor stays the short-chat cell
            self.assertNotIn("runs", twin)
            if rt == "mlx-swift":                          # mlx-swift-lm grows its cache: no flag
                self.assertNotIn("context-tokens", twin)
            else:
                self.assertEqual(twin.get("context-tokens"), str(CTX))
        self.assertEqual(len(twins), expected)
        # 15 per platform on LiteRT-LM / llama.cpp / MLX, the Mac's 10 executorch rows (XNNPACK and
        # the MLX delegate, the Gemma 4 ones excluded), the Mac's 6 onnxruntime-genai rows (CPU EP and
        # the WebGPU plugin EP, Qwen3 only; weekly since 2026-10-09) and the iPhone's 3 (CPU EP, Qwen3
        # only; weekly since 2026-10-09, the pinned app build carries the adapter)
        self.assertEqual(len(twins), 64)

    def test_weekly_rows_are_the_1024_set(self):
        weekly = {r[0] for r in rows(WEEKLY) if r[4] == TASK}
        defined = {r[0] for path in ONLY_1024 for r in rows(path) if r[4] == TASK}
        self.assertEqual(weekly, defined)

    def test_android_halves_mirror_the_parent(self):
        parent = [r[0] for r in rows(WEEKLY) if r[1] == "android"]
        union = []
        for half, path in HALVES.items():
            lines = [r[0] for r in rows(path)]
            self.assertTrue(set(lines) <= set(parent), half)
            anchors = [r for r in rows(path) if r[5].get("anchor") == "1"]
            self.assertEqual(len(anchors), 1, half)
            union += [line for line in lines if "anchor=1" not in line]
        self.assertEqual(sorted(union), sorted(line for line in parent if "anchor=1" not in line))
        # a model's 1024 rows run in the half that pushes its short-chat files
        for half, path in HALVES.items():
            half_rows = rows(path)
            models = {r[3] for r in half_rows if r[4] == "short-chat" and "anchor" not in r[5]}
            if half == "a":
                models.add("unsloth/Qwen3-0.6B-GGUF")   # the anchor model's own 1024 row
            self.assertEqual({r[3] for r in half_rows if r[4] == TASK}, models, half)


# ------------------------------------------------------------------ the Android launch

class AndroidLaunchContract(unittest.TestCase):
    def android_1024(self):
        return [android_cell(r[0]) for r in rows(WEEKLY) if r[1] == "android" and r[4] == TASK]

    def test_litert_rows_run_the_two_iteration_path_with_the_256_budget(self):
        cells = [c for c in self.android_1024() if c["runtime"] == "litert-lm"]
        self.assertEqual(len(cells), 10)
        for c in cells:
            o = c["opts"]
            model = f"{cell.DEV_DIR}/models/{c['model_id'].replace('/', '_')}_{o['file']}"
            prompt = f"{cell.DEV_DIR}/prompts/{TASK}.txt"
            command, binary, sampler, note = cell.engine_command(
                "litert-lm", o["backend"], model, TASK, prompt, BUDGET, None, int(o["context-tokens"]))
            self.assertEqual(binary, "litert_lm_advanced_main")
            self.assertEqual(note, CTX)
            for flag in (f"--backend={o['backend']}", f"--model_path={model}", f"--input_prompt_file={prompt}",
                         f"--max_num_tokens={CTX}", f"--max_output_tokens={BUDGET}", "--num_iterations=2",
                         "--benchmark_prefill_tokens=0", "--benchmark_decode_tokens=0", "--use_session=false"):
                self.assertIn(flag, command)
            stem = cell.capture_stem("litert-lm", o["backend"], c["model_id"], TASK, o["file"], CTX)
            self.assertTrue(stem.endswith(f"__ctx{CTX}_file" + hashlib.sha256(o["file"].encode()).hexdigest()))
            self.assertEqual(campaign.records_per_launch(c), 2)
            planned, planned_binary, _ = campaign.planned_command(c)
            self.assertTrue(planned.endswith(command))
            self.assertEqual(planned_binary, binary)

    def test_llama_rows_allocate_2048_and_write_one_record(self):
        cells = [c for c in self.android_1024() if c["runtime"] == "llama.cpp"]
        self.assertEqual(len(cells), 5)
        for c in cells:
            model = f"{cell.DEV_DIR}/models/{c['model_id'].replace('/', '_')}_{c['opts']['file']}"
            prompt = f"{cell.DEV_DIR}/prompts/{TASK}.txt"
            self.assertEqual(cell.engine_command("llama.cpp", None, model, TASK, prompt, BUDGET, None, CTX),
                             (f"./llama-cli -m {model} -t 4 -c {CTX} -f {prompt} -n {BUDGET} "
                              "--temp 0 --top-p 1 -st", "llama-cli", "greedy", CTX))
            self.assertEqual(campaign.records_per_launch(c), 1)
            self.assertIn(f"__ctx{CTX}_file", cell.capture_stem("llama.cpp", None, c["model_id"], TASK,
                                                                c["opts"]["file"], CTX))

    def test_short_chat_rows_keep_the_plain_main(self):
        for line, plat, rt, mid, task, opts in rows(WEEKLY):
            if plat != "android" or rt != "litert-lm" or task != "short-chat":
                continue
            c = android_cell(line)
            self.assertEqual(campaign.records_per_launch(c), 1)
            planned, binary, _ = campaign.planned_command(c)
            self.assertEqual(binary, "litert_lm_main")
            self.assertIn("--max_output_tokens=128 --async=false", planned)
            self.assertNotIn("--max_num_tokens", planned)

    def test_dry_run_plan_lists_the_1024_cells_without_a_device(self):
        with patch.dict(os.environ, {"ROUNDS": "1"}), \
             patch.object(sys, "argv", ["run_campaign.py", str(HALVES["a"]), "--dry-run"]), \
             patch.object(campaign.subprocess, "run", side_effect=AssertionError("subprocess forbidden")), \
             patch.object(campaign.subprocess, "call", side_effect=AssertionError("subprocess forbidden")), \
             patch.object(campaign, "thermal_status", side_effect=AssertionError("device forbidden")), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(campaign.main(), 0)
        plan = [json.loads(line) for line in output.getvalue().splitlines()]
        long = [p for p in plan if TASK in p.get("cell", "")]
        self.assertEqual(len(long), 9)
        for p in long:
            self.assertIn(f"context-tokens={CTX}", p["cell"])
            if p["binary"] == "litert_lm_advanced_main":
                self.assertIn(f"--max_num_tokens={CTX} --max_output_tokens={BUDGET} --num_iterations=2",
                              p["command"])
            else:
                self.assertIn(f"-c {CTX} -f {cell.DEV_DIR}/prompts/{TASK}.txt -n {BUDGET}", p["command"])


# ------------------------------------------------------------------ the gate

PAIRED = {"runtime": "litert-lm", "model_id": "litert-community/Qwen3-0.6B", "task": TASK,
          "opts": {"backend": "gpu", "file": "qwen3_0_6b_mixed_int4.litertlm", "context-tokens": str(CTX)}}
STEM = cell.capture_stem("litert-lm", "gpu", PAIRED["model_id"], TASK, PAIRED["opts"]["file"], CTX)


def write_launch(folder, minute, cold, warm, tag):
    """One launch as run_cell's context-prompt path stores it: two records, iteration 1
    cold and iteration 2 warm, one stem, one stamp."""
    for iteration, rate in ((1, cold), (2, warm)):
        rec = {"schemaVersion": 1, "task": TASK, "timestamp": f"2026-10-06T01:{minute:02d}:00Z",
               "capture": tag,
               "metrics": {"decodeTokensPerSecond": rate, "coldRun": iteration == 1,
                           "initialThermalState": "nominal", "promptTokenCount": 1339,
                           "generatedTokenCount": 256},
               "conditions": {"iterationIndex": iteration, "regime": "cold" if iteration == 1 else "warm"}}
        name = f"{STEM}_2026-10-06T01-{minute:02d}-00.000000_run1_iter{iteration}.json"
        (folder / name).write_text(json.dumps(rec))


class PairedGate(unittest.TestCase):
    def gated(self, first, retry):
        """apply_gate on a three-launch capture `first`; a retry writes `retry`.
        -> (live records, quarantined records, FLAGGED.txt, relaunch count)"""
        tmp = tempfile.TemporaryDirectory(prefix="longctx1024-gate-")
        self.addCleanup(tmp.cleanup)
        folder = Path(tmp.name)
        minutes = iter(range(60))
        for cold, warm in first:
            write_launch(folder, next(minutes), cold, warm, "first")

        def relaunch(cell_, out_dir, runs, *args, **kwargs):
            self.assertEqual(runs, 3)
            for cold, warm in retry:
                write_launch(Path(out_dir), next(minutes), cold, warm, "retry")
            return 0

        with patch.object(campaign, "run_cell_once", side_effect=relaunch) as launches, \
             patch.object(campaign.time, "sleep"), \
             patch.object(campaign, "wait_nominal", return_value="nominal"), \
             contextlib.redirect_stdout(io.StringIO()):
            campaign.apply_gate(PAIRED, str(folder), 3)
        live = [json.loads(p.read_text()) for p in sorted(folder.glob(STEM + "_*.json"))]
        quarantined = sorted(folder.glob("*.json.attempt1"))
        flagged = folder / "FLAGGED.txt"
        return live, quarantined, flagged.read_text() if flagged.exists() else "", launches.call_count

    def test_a_flagged_capture_is_replaced_whole(self):
        # cold 10 beside 30 / 30: COLLAPSE on the launch that matters
        live, quarantined, flagged, relaunched = self.gated(
            [(30.0, 31.0), (30.0, 31.0), (10.0, 31.0)], [(29.0, 30.0), (30.0, 31.0), (31.0, 31.5)])
        self.assertEqual(relaunched, 1)
        self.assertEqual(len(quarantined), 6)               # both records of all three launches
        self.assertEqual(len(live), 6)
        self.assertEqual({r["capture"] for r in live}, {"retry"})   # nothing of the first capture pools
        self.assertEqual(flagged, "")

    def test_warm_spread_alone_is_information(self):
        first = [(30.0, 30.0), (30.5, 30.0), (31.0, 40.0)]  # cold within 3 %, warm 33 % apart
        live, quarantined, flagged, relaunched = self.gated(first, [])
        self.assertEqual((relaunched, len(quarantined), len(live), flagged), (0, 0, 6, ""))
        with tempfile.TemporaryDirectory(prefix="longctx1024-auto-") as tmp:
            for minute, (cold, warm) in enumerate(first):
                write_launch(Path(tmp), minute, cold, warm, "first")
            files = sorted(str(p) for p in Path(tmp).glob("*.json"))
            auto = subprocess.run([sys.executable, str(GATE), "--runs", "3"] + files,
                                  capture_output=True, text=True).stdout
            cold = subprocess.run([sys.executable, str(GATE), "--runs", "3", "--basis", "cold"] + files,
                                  capture_output=True, text=True).stdout
        self.assertTrue(auto.startswith("SPREAD"), auto)    # the old reading: 1.5 launches, two warm values
        self.assertEqual(cold.strip(), "OK")

    def test_level_is_read_on_the_cold_records(self):
        # the retry is uniformly slow on its cold iteration while its warm one looks normal
        live, quarantined, flagged, relaunched = self.gated(
            [(30.0, 30.0), (30.0, 30.0), (9.0, 30.0)], [(12.0, 30.0), (12.0, 30.0), (13.0, 30.0)])
        self.assertEqual((relaunched, len(quarantined), len(live)), (1, 6, 6))
        self.assertIn("retry='LEVEL 40'", flagged)

    def test_gate_command_carries_the_basis_only_for_two_record_launches(self):
        cases = [
            (PAIRED, 2, True),
            ({**PAIRED, "runtime": "llama.cpp", "opts": {"file": "x.gguf", "context-tokens": str(CTX)}}, 1, False),
            ({**PAIRED, "task": "short-chat", "opts": {"backend": "gpu", "file": "x.litertlm"}}, 1, False),
            ({**PAIRED, "task": "native-benchmark-1024x256"}, 1, False),
            ({**PAIRED, "task": "endurance-chat-30m"}, 1, False),
        ]
        for c, per_launch, cold_basis in cases:
            self.assertEqual(campaign.records_per_launch(c), per_launch, c)
            with tempfile.TemporaryDirectory(prefix="longctx1024-cmd-") as tmp, \
                 patch.object(campaign.subprocess, "run", return_value=SimpleNamespace(stdout="OK\n")) as run:
                campaign.gate_verdict(c, tmp, 3)
            argv = run.call_args.args[0]
            self.assertEqual("--basis" in argv, cold_basis, c)
            if cold_basis:
                self.assertEqual(argv[argv.index("--basis") + 1], "cold")


if __name__ == "__main__":
    unittest.main(verbosity=2)
