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


class SchemaV1Import(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        (self.dir / "like.json").write_text(json.dumps(LIKE))

    def tearDown(self):
        self._tmp.cleanup()

    def run_import(self, text, times, *extra):
        log = self.dir / "console_x.txt"
        log.write_text(text)
        out = self.dir / "out"
        p = subprocess.run(
            [sys.executable, str(SCRIPT), "--schema-v1", str(log), "--out", str(out),
             "--like", str(self.dir / "like.json"), "--launch-times", times,
             "--device", "iPhone19,2", "--instrument", "test", *extra],
            capture_output=True, text=True)
        recs = [json.loads(f.read_text()) for f in sorted(out.glob("native_x_*.json"))] \
            if p.returncode == 0 else []
        return p.returncode, recs

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


if __name__ == "__main__":
    unittest.main()
