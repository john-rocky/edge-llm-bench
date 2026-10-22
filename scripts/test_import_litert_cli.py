#!/usr/bin/env python3
"""Device-free checks of `import_litert_cli.py` (the Mac LiteRT-LM CLI consoles -> schema-v1 records).

What it must not get wrong, because each ends in a number that looks right:
  - the arm: --enable_ynnpack=true is litert-lm-cpu-ynnpack, without it litert-lm-cpu, and a launch whose YNNPACK
    lines say otherwise is flagged backend-not-registered (a row, never a measurement);
  - the allocation: a console whose `target_number` is not the launch's --max_num_tokens is no number (.offtarget,
    exit 3);
  - the overlap verdicts: a superseded try and a launch overlapped twice stay out of the *.json glob;
  - the device snapshot keeps the machine, not the yardstick record's per-run or app-build fields.

Fixtures live in a temp dir; results/ is neither read nor written.

  python3 scripts/test_import_litert_cli.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "import_litert_cli.py"
MODEL = "litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32_gpucomposites_e2_ctx4096"
LIKE = {
    "schemaVersion": 1, "runtime": "mlx-swift", "engineVersion": "60bd0d78", "task": "short-chat",
    "timestamp": "2026-10-23T00:00:00Z", "model": {"id": "mlx-community/Qwen3-0.6B-4bit"},
    "device": {"modelIdentifier": "Mac16,9", "systemName": "macOS", "systemVersion": "Version 27.0 (Build 26A428)",
               "physicalMemoryMB": 131072, "processorCount": 16, "batteryLevel": -1, "batteryState": "unknown",
               "isLowPowerModeEnabled": False, "buildConfiguration": "Release", "initialThermalState": "nominal"},
    "metrics": {"coldRun": False},
}
HOME = os.path.expanduser("~")


def console(target=4096, ynn_lines=0, decode=48.5, rc=0):
    """A litert_lm_advanced_main --benchmark console as the Mac CLI prints it, /usr/bin/time -l appended."""
    ynn = "".join("ERROR: external/litert/tflite/delegates/ynnpack/dot.cc:385 IsTensorSupported(weights, true) "
                  "was not true.\n" for _ in range(ynn_lines))
    return (f"max_tokens: {target}\nenable_ynnpack: {'true' if ynn_lines else 'false'}\n"
            f"INFO: [magic_number_utils.cc:120]   config[0]: magic_number=32771, target_number={target}, "
            f"signature_prefix=null\n{ynn}"
            "INFO: [cpu_registry.cc:73] XNNPACK CPU accelerator registered.\n"
            "I0000 00:00:1792525260.586637 321887345 litert_lm_lib.cc:433] BenchmarkInfo:\n"
            "  Init Phases (7):\n    - Init Total: 250.09 ms\n  Time to first token: 1.94 s\n"
            "  Prefill Turns (Total 1 turns):\n    Prefill Turn 1: Processed 1024 tokens in 1.91976625s duration.\n"
            "      Prefill Speed: 533.40 tokens/sec.\n"
            "  Decode Turns (Total 1 turns):\n    Decode Turn 1: Processed 256 tokens in 5.02s duration.\n"
            f"      Decode Speed: {decode} tokens/sec.\n"
            "        7.22 real        18.09 user         2.20 sys\n"
            "          2171650048  maximum resident set size\n             2163168  peak memory footprint\n"
            f"EXIT_CODE={rc}\n")


def argv(ctx, ynn):
    return (["./litert_lm_advanced_main", "--backend=cpu", f"--model_path={HOME}/k/ctx{ctx}/e2.litertlm",
             "--benchmark", "--benchmark_prefill_tokens=1024", "--benchmark_decode_tokens=256", "--async=false",
             f"--max_num_tokens={ctx}"] + (["--enable_ynnpack=true"] if ynn else []))


class ImportLitertCli(unittest.TestCase):
    def run_import(self, entries, consoles, like=LIKE, device="Mac16,9"):
        d = Path(tempfile.mkdtemp())
        (d / "like.json").write_text(json.dumps(like))
        for name, text in consoles.items():
            (d / name).write_text(text)
        (d / "manifest.jsonl").write_text("".join(json.dumps(e) + "\n" for e in entries))
        out = d / "out"
        p = subprocess.run([sys.executable, str(SCRIPT), str(d / "manifest.jsonl"), "--out", str(out),
                            "--like", str(d / "like.json"), "--device", device, "--model-id", MODEL,
                            "--quantization", "INT4 (test label)", "--engine", "head-test",
                            "--engine-artifact", "litert_lm_advanced_main sha256:00", "--engine-build", "test build",
                            "--instrument", "litert_lm_advanced_main --benchmark (test)"],
                           capture_output=True, text=True)
        files = {f.name: f for f in out.iterdir()} if out.exists() else {}
        return p.returncode, files, p.stderr

    @staticmethod
    def entry(log, ctx, ynn, i, verdict="clean", first=False):
        return {"log": log, "command": argv(ctx, ynn), "start": f"2026-10-23T05:0{i}:00Z", "launchIndex": i,
                "cellLaunch": 1 if first else 2, "firstEver": first, "engineCache": "a cache line",
                "verdict": verdict, "hostSamples": log + ".samp", "modelFile": f"{HOME}/k/ctx{ctx}/e2.litertlm",
                "modelSha256": "fb" * 32}

    def test_arms_flags_and_fields(self):
        entries = [self.entry("off.log", 4096, False, 1, first=True), self.entry("on.log", 4096, True, 2),
                   self.entry("onbare.log", 4096, True, 3)]
        rc, files, err = self.run_import(entries, {"off.log": console(), "on.log": console(ynn_lines=339),
                                                   "onbare.log": console()})
        self.assertEqual(rc, 0, err)
        recs = {f.name: json.loads(f.read_text()) for f in files.values()}
        self.assertEqual(len(recs), 3)
        self.assertTrue(all(n.endswith(".json") for n in recs))
        off = next(r for r in recs.values() if r["runtime"] == "litert-lm-cpu")
        on = [r for r in recs.values() if r["runtime"] == "litert-lm-cpu-ynnpack"]
        self.assertEqual(off["task"], "native-benchmark-1024x256")
        self.assertEqual(off["conditions"]["contextTokens"], 4096)
        self.assertEqual(off["conditions"]["kvAllocation"], [{"magicNumber": 32771, "targetNumber": 4096}])
        self.assertEqual(off["metrics"]["promptTokenCount"], 1024)
        self.assertEqual(off["metrics"]["generatedTokenCount"], 256)
        self.assertEqual(off["metrics"]["decodeTokensPerSecond"], 48.5)
        self.assertEqual(off["metrics"]["promptTokensPerSecond"], 533.4)
        self.assertEqual(off["metrics"]["firstTokenLatencyMS"], 1940.0)
        self.assertEqual(off["metrics"]["memoryPeakResidentMB"], 2071.0)
        self.assertTrue(off["metrics"]["coldRun"] and off["metrics"]["firstEver"])
        self.assertEqual(off["conditions"]["protocolFlags"], [])
        self.assertEqual(off["conditions"]["ynnpackLines"], {"ops": 0, "partitions": 0})
        self.assertEqual(off["model"]["file"], "e2.litertlm")
        self.assertNotIn(HOME, off["conditions"]["engineCommand"])
        self.assertEqual(sorted(off["device"]), sorted(["modelIdentifier", "systemName", "systemVersion",
                                                         "physicalMemoryMB", "processorCount", "batteryLevel",
                                                         "batteryState", "isLowPowerModeEnabled"]))
        good = next(r for r in on if r["conditions"]["ynnpackLines"]["ops"] == 339)
        self.assertEqual(good["conditions"]["protocolFlags"], [])
        self.assertNotIn("firstEver", good["metrics"])
        bare = next(r for r in on if r["conditions"]["ynnpackLines"]["ops"] == 0)
        self.assertEqual(bare["conditions"]["protocolFlags"], ["backend-not-registered"])
        self.assertEqual(bare["conditions"]["backendOffReason"], "no YNNPACK line")

    def test_offtarget_and_overlap_suffixes(self):
        entries = [self.entry("wrong.log", 4096, False, 1), self.entry("try1.log", 4096, False, 2, "superseded"),
                   self.entry("twice.log", 4096, True, 3, "overlap-twice")]
        rc, files, err = self.run_import(entries, {"wrong.log": console(target=2048), "try1.log": console(),
                                                   "twice.log": console(ynn_lines=339)})
        self.assertEqual(rc, 3, err)
        suffixes = sorted(n[n.index(".json"):] for n in files)
        self.assertEqual(suffixes, [".json.attempt1", ".json.offtarget", ".json.overlapped"])
        self.assertIn("is not --max_num_tokens 4096", err)

    def test_first_launch_overlapped(self):
        # a cell's first launch (the cache build) another process overlapped stands as a firstEver row; the verdict on
        # any other launch is a manifest error
        first = self.entry("first.log", 4096, False, 1, "first-overlapped", first=True)
        rc, files, err = self.run_import([first], {"first.log": console()})
        self.assertEqual(rc, 0, err)
        rec = json.loads(next(iter(files.values())).read_text())
        self.assertTrue(rec["metrics"]["firstEver"])
        self.assertEqual(rec["conditions"]["hostOverlap"]["verdict"], "first-overlapped")
        rc, files, err = self.run_import([self.entry("late.log", 4096, False, 2, "first-overlapped")],
                                         {"late.log": console()})
        self.assertEqual(rc, 2)
        self.assertEqual(files, {})

    def test_like_of_another_device(self):
        rc, files, err = self.run_import([self.entry("off.log", 4096, False, 1)], {"off.log": console()},
                                         device="Mac15,8")
        self.assertEqual(rc, 2)
        self.assertEqual(files, {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
