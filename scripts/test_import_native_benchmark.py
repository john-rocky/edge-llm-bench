#!/usr/bin/env python3
"""Device-free checks of `import_native_benchmark.py --schema-v1` (CI: leaderboard-check).

The importer turns the native benchmark's console lines into schema-v1 records. Two things it
must not get wrong, because both end in a number that looks right:
  - a line of an older app build (no run / cold / thermal fields) imports as it always did;
  - a line of the 2026-10-07 build keeps what it says: the thermal states and the wall time
    reach metrics, `cold=0` is a warm run (never pooled as cold), and the N lines of one launch
    share that launch's index and start time.

Fixtures live in a temp dir; results/ is neither read nor written.

  python3 scripts/test_import_native_benchmark.py
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "import_native_benchmark.py"
MODEL = "litert-community/Qwen3-0.6B"
LIKE = {
    "schemaVersion": 1, "runtime": "litert-lm", "engineVersion": "v0.16.0", "task": "short-chat",
    "timestamp": "2026-10-06T00:00:00Z", "model": {"id": MODEL, "primaryFile": "m.litertlm"},
    "device": {"modelIdentifier": "iPhone19,2", "systemVersion": "27.2", "batteryLevel": 0.8,
               "batteryState": "charging", "initialThermalState": "fair"},
    "metrics": {"coldRun": True},
}
BEGIN = f"YARDSTICK_BEGIN native_benchmark model={MODEL} prefill=1024 decode=256 context_tokens=2048\n"
BASE = ("prefill_tokens=1024 prefill_tok_s=1600.5 decode_tokens=256 decode_tok_s={tps} ttft_ms=640.0 "
        "init_s=1.5 context_tokens=2048 peak_mb=800 median_mb=777 samples=47")
OLD = BEGIN + "".join(f"YARDSTICK_NATIVE_OK {BASE.format(tps=t)} harness=h1\n" for t in (80.0, 79.0))
NEW = BEGIN + "".join(
    f"YARDSTICK_NATIVE_OK run={run} runs={runs} cold={cold} {BASE.format(tps=tps)} "
    f"thermal_initial={t0} thermal_final={t1} wall_s={wall} harness=h1\n"
    for run, runs, cold, tps, t0, t1, wall in (
        (1, 2, 1, 80.0, "nominal", "fair", 4.8),
        (2, 2, 0, 70.0, "fair", "serious", 5.5),
        (1, 1, 1, 81.0, "nominal", "nominal", 4.7)))
T1, T2 = "2026-10-07T00:00:00Z", "2026-10-07T00:05:00Z"

# Core AI (CoreAIRuntime.nativeBenchmarkStock): one load, then trial 0 (cold=1, the first
# generate after the load) and the timed trials. A record of the same arm is the --like.
CAI_MODEL = "core-ai/gemma4-e2b-stock-ctx2048"
CAI_LIKE = {
    "schemaVersion": 1, "runtime": "core-ai-ane", "engineVersion": "1.0.0-10-gbd3c539",
    "task": "long-context-1024-gen256", "timestamp": "2026-10-08T00:00:00Z",
    "model": {"id": CAI_MODEL, "primaryFile": ""},
    "device": {"modelIdentifier": "Mac16,9", "systemVersion": "27.0", "batteryLevel": -1,
               "batteryState": "unknown", "initialThermalState": "nominal"},
    "metrics": {"coldRun": True},
}
CAI_BEGIN = f"YARDSTICK_BEGIN native_benchmark model={CAI_MODEL} prefill=1024 decode=256 runtime=core-ai trials={{n}}\n"
CAI_LINE = ("YARDSTICK_NATIVE_OK runtime=core-ai trial={trial}{cold} trials={n} prefill_tokens=1024 "
            "prefill_tok_s={p} decode_tokens=256 decode_tok_s=52.4 ttft_ms=278.2 decode_s=4.86 init_s={init} "
            "prepare_cached={cached} prepare_peak_mb=369 engine_warmup_s=0.033 warmup_trial_s=5.354 "
            "context_tokens=2048 peak_mb=658 median_mb=646 median_resident_mb=1188 samples=50 "
            "thermal_initial=nominal thermal_peak=nominal thermal_final=fair seed=0 harness=h1\n")


def cai_launch(trials, cached, first_trial=0, with_cold=True):
    """One launch's console: BEGIN, then trial first_trial..trials."""
    text = CAI_BEGIN.format(n=trials)
    for t in range(first_trial, trials + 1):
        cold = f" cold={1 if t == 0 else 0}" if with_cold else ""
        text += CAI_LINE.format(trial=t, cold=cold, n=trials, p=2400.0 if t == 0 else 3700.0,
                                init=40.2 if cached == 0 else 0.05, cached=cached)
    return text


class SchemaV1Import(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        (self.dir / "like.json").write_text(json.dumps(LIKE))

    def tearDown(self):
        self._tmp.cleanup()

    def run_import(self, text, times, *extra, like="like.json", device="iPhone19,2"):
        log = self.dir / "console_x.txt"
        log.write_text(text)
        out = self.dir / "out"
        p = subprocess.run(
            [sys.executable, str(SCRIPT), "--schema-v1", str(log), "--out", str(out),
             "--like", str(self.dir / like), "--launch-times", times,
             "--device", device, "--instrument", "test", *extra],
            capture_output=True, text=True)
        recs = [json.loads(f.read_text())
                for f in sorted(out.glob("native_x_*.json"), key=lambda f: int(f.stem.rsplit("_", 1)[1]))] \
            if p.returncode == 0 else []
        return p.returncode, recs

    def run_core_ai(self, text, times, *extra):
        (self.dir / "cai_like.json").write_text(json.dumps(CAI_LIKE))
        return self.run_import(text, times, *extra, like="cai_like.json", device="Mac16,9")

    def test_older_line_imports_as_before(self):
        rc, recs = self.run_import(OLD, f"{T1},{T2}")
        self.assertEqual(rc, 0)
        self.assertEqual([r["timestamp"] for r in recs], [T1, T2])
        for i, r in enumerate(recs, 1):
            self.assertEqual(r["conditions"], {"instrument": "test", "launchIndex": i})
            self.assertIs(r["metrics"]["coldRun"], True)
            for key in ("initialThermalState", "finalThermalState", "peakThermalState", "wallSeconds"):
                self.assertNotIn(key, r["metrics"])
            # the --like snapshot's per-run readings never reach a native record
            self.assertEqual(sorted(r["device"]), ["modelIdentifier", "systemVersion"])
            self.assertEqual(r["task"], "native-benchmark-1024x256")

    def test_new_line_keeps_thermal_wall_and_regime(self):
        rc, recs = self.run_import(NEW, f"{T1},{T2}", "--first-ever", "1")
        self.assertEqual(rc, 0)
        self.assertEqual([r["conditions"]["launchIndex"] for r in recs], [1, 1, 2])
        self.assertEqual([r["conditions"]["run"] for r in recs], [1, 2, 1])
        self.assertEqual([r["conditions"]["runs"] for r in recs], [2, 2, 1])
        self.assertEqual([r["timestamp"] for r in recs], [T1, T1, T2])
        m = [r["metrics"] for r in recs]
        self.assertEqual([x["coldRun"] for x in m], [True, False, True])
        self.assertEqual([x["initialThermalState"] for x in m], ["nominal", "fair", "nominal"])
        self.assertEqual([x["finalThermalState"] for x in m], ["fair", "serious", "nominal"])
        self.assertEqual([x["wallSeconds"] for x in m], [4.8, 5.5, 4.7])
        self.assertEqual([x.get("firstEver") for x in m], [True, None, None])
        self.assertTrue(all("peakThermalState" not in x for x in m))  # the line has no peak
        self.assertEqual([x["decodeTokensPerSecond"] for x in m], [80.0, 70.0, 81.0])

    def test_launch_times_and_first_ever_count_launches(self):
        self.assertEqual(self.run_import(NEW, f"{T1},{T1},{T2}")[0], 2)   # 3 lines, 2 launches
        self.assertEqual(self.run_import(NEW, T1)[0], 2)
        self.assertEqual(self.run_import(NEW, f"{T1},{T2}", "--first-ever", "3")[0], 2)
        self.assertEqual(self.run_import(OLD, T1)[0], 2)                  # 2 lines, 2 launches

    def test_core_ai_trials_of_one_load_are_one_launch(self):
        rc, recs = self.run_core_ai(cai_launch(2, cached=1), T1)
        self.assertEqual(rc, 0)
        self.assertEqual([r["runtime"] for r in recs], ["core-ai-ane"] * 3)  # the --like arm
        self.assertEqual([r["conditions"]["trial"] for r in recs], [0, 1, 2])
        self.assertEqual([r["conditions"]["launchIndex"] for r in recs], [1, 1, 1])
        self.assertEqual([r["timestamp"] for r in recs], [T1] * 3)
        for r in recs:
            self.assertEqual({k: r["conditions"][k] for k in ("trials", "seed", "warmupTrials", "sampler")},
                             {"trials": 2, "seed": 0, "warmupTrials": 1, "sampler": "greedy"})
            self.assertEqual(r["task"], "native-benchmark-1024x256")
            self.assertEqual(r["engineVersion"], "1.0.0-10-gbd3c539")
        m = [r["metrics"] for r in recs]
        self.assertEqual([x["coldRun"] for x in m], [True, False, False])
        self.assertEqual([x["promptTokensPerSecond"] for x in m], [2400.0, 3700.0, 3700.0])
        self.assertTrue(all(x.get("firstEver") is None for x in m))      # cached load
        for x in m:
            self.assertEqual((x["decodeSeconds"], x["prepareCacheHit"], x["prepareFootprintPeakMB"],
                              x["engineWarmupSeconds"], x["warmupTrialSeconds"]),
                             (4.86, True, 369.0, 0.033, 5.354))
            self.assertEqual((x["initialThermalState"], x["peakThermalState"], x["finalThermalState"]),
                             ("nominal", "nominal", "fair"))
            self.assertEqual(x["contextTokensConfigured"], 2048)

    def test_core_ai_launches_split_on_trial_and_specialization_marks_first_ever(self):
        text = cai_launch(1, cached=0) + cai_launch(1, cached=1)
        rc, recs = self.run_core_ai(text, f"{T1},{T2}")
        self.assertEqual(rc, 0)
        self.assertEqual([r["conditions"]["launchIndex"] for r in recs], [1, 1, 2, 2])
        self.assertEqual([r["timestamp"] for r in recs], [T1, T1, T2, T2])
        self.assertEqual([r["metrics"]["coldRun"] for r in recs], [True, False, True, False])
        # prepare_cached=0: that load specialized, so its launch's first line is first-ever
        self.assertEqual([r["metrics"].get("firstEver") for r in recs], [True, None, None, None])
        self.assertEqual(self.run_core_ai(text, T1)[0], 2)               # 4 lines, 2 launches

    def test_core_ai_line_of_an_older_build_is_a_timed_trial(self):
        # before 2026-10-07: no trial 0 line and no cold=; trial 1 starts the launch
        rc, recs = self.run_core_ai(cai_launch(2, cached=1, first_trial=1, with_cold=False), T1)
        self.assertEqual(rc, 0)
        self.assertEqual([r["conditions"]["launchIndex"] for r in recs], [1, 1])
        self.assertEqual([r["metrics"]["coldRun"] for r in recs], [False, False])

    def test_like_must_be_the_lines_arm(self):
        self.assertEqual(self.run_import(cai_launch(1, cached=1), T1)[0], 2)  # litert-lm --like
        (self.dir / "cai_like.json").write_text(json.dumps(CAI_LIKE))
        self.assertEqual(self.run_import(NEW, f"{T1},{T2}", like="cai_like.json")[0], 2)
        self.assertEqual(self.run_core_ai(cai_launch(1, cached=1) + NEW, f"{T1},{T2},{T2}")[0], 2)


if __name__ == "__main__":
    unittest.main()
