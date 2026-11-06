#!/usr/bin/env python3
"""render_leaderboard.arm_row reads prefill and TTFT over the runs of the regime the cell headlines
(headline_regime), as the surfaces read decode (cold-warm-split; D-719, 2026-11-06). Pooled over both
regimes, a cell whose cold and warm prefill read apart moved with the mix of its runs: the Pixel 11 Pro
Qwen3 0.6B CPU long-context-1024 cell read 168.6 tok/s on 2026-11-05 and 119.3 on the 2026-11-06 retake
(prefill-drop held the post) where cold against cold read -3.5 %.

  python3 scripts/test_prefill_regime.py

Synthetic rows only (no device, no summary, no network)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_dashboard  # noqa: E402
import render_leaderboard  # noqa: E402
from render_leaderboard import arm_row  # noqa: E402


def row(prefill, cold, first_ever=False, platform="android", task="long-context-1024-gen256",
        minute=0, ttft=None):
    """One device-runs.csv row as csv.DictReader returns it (every value a string): the columns
    arm_row reads, one session (one campaign), a fixed decode."""
    campaign = "results/raw/2026-11-06-fixture-android"
    return {
        "source": f"{campaign}/app-path-android/r{minute}.json", "campaign": campaign,
        "platform": platform, "timestamp": f"2026-11-06T09:{minute:02d}:00Z",
        "runtime": "litert-lm-cpu", "engine_version": "v0.19.0", "model_id": "org/model",
        "model_file": "model.litertlm", "quantization": "INT4 (fixture)", "task": task,
        "decode_tps": "20.0", "prefill_tps": str(prefill),
        "ttft_ms": str(ttft if ttft is not None else round(1339 / prefill * 1000, 1)),
        "mem_footprint_median_mb": "", "mem_resident_median_mb": "800.0",
        "mem_footprint_peak_mb": "", "mem_resident_peak_mb": "830.0",
        "thermal_initial": "nominal", "cold_run": str(cold),
        "first_ever": "True" if first_ever else "", "text_check": "PASS",
        "cpu_capped": "false", "cpu_cap_drop_pct": "0.0", "backend_registered": "",
    }


def launches(pairs, first_ever_first=False):
    """Two-iteration launches, (cold prefill, warm prefill) each, in order."""
    rows = []
    for i, (c, w) in enumerate(pairs):
        rows += [row(c, True, first_ever=first_ever_first and i == 0, minute=2 * i),
                 row(w, False, minute=2 * i + 1)]
    return rows


class PrefillRegime(unittest.TestCase):
    def test_the_pixel_11_pro_case_reads_cold_against_cold(self):
        # the Qwen3 0.6B CPU long-context-1024 cell (results/raw/2026-11-05-dashboard-v1-pixel11pro-
        # a-android: its first-ever cold run 114.1 out of the pool; results/raw/2026-11-06-dashboard-
        # v1-pixel11pro-retake-4cells-android: no first-ever run, one warm run at 115.21)
        nov5 = arm_row(launches([(114.1, 169.05), (119.15, 172.38), (120.36, 168.62)], True))
        nov6 = arm_row(launches([(122.99, 115.21), (113.17, 176.23), (115.52, 175.88)]))
        self.assertEqual(nov5["prefill_regime"], "cold")
        self.assertAlmostEqual(nov5["prefill"], 119.755)   # pooled with the warm runs: 168.62
        self.assertAlmostEqual(nov6["prefill"], 115.52)    # pooled: 119.255
        self.assertAlmostEqual((nov6["prefill"] / nov5["prefill"] - 1) * 100, -3.54, places=2)
        # TTFT is read over the same runs
        self.assertAlmostEqual(nov6["ttft"], round(1339 / 115.52 * 1000, 1))

    def test_apple_text_cells_read_warm(self):
        rows = [row(p, c, platform="ios", task="short-chat", minute=i)
                for i, (p, c) in enumerate([(50.0, True), (300.0, False), (310.0, False), (320.0, False)])]
        a = arm_row(rows)
        self.assertEqual((a["prefill_regime"], a["prefill"]), ("warm", 310.0))

    def test_a_protocol_cell_reads_warm_where_its_session_has_warm_runs(self):
        task = "native-benchmark-1024x256"
        warm = [row(p, c, task=task, minute=i)
                for i, (p, c) in enumerate([(700.0, True), (900.0, False), (910.0, False)])]
        a = arm_row(warm)
        self.assertEqual((a["prefill_regime"], a["prefill"]), ("warm", 905.0))
        cold = [row(p, True, task=task, minute=i) for i, p in enumerate([700.0, 720.0, 740.0])]
        a = arm_row(cold)
        self.assertEqual((a["prefill_regime"], a["prefill"]), ("cold", 720.0))

    def test_a_cold_only_cell_does_not_move(self):
        rows = [row(p, True, task="short-chat", minute=i) for i, p in enumerate([20.4, 26.9, 11.2])]
        a = arm_row(rows)
        self.assertEqual((a["prefill_regime"], a["prefill"]), ("cold", 20.4))

    def test_a_session_of_two_platforms_keeps_the_pool_of_all_its_runs(self):
        rows = [row(100.0, True, minute=0), row(300.0, False, platform="ios", minute=1),
                row(200.0, True, minute=2)]
        a = arm_row(rows)
        self.assertEqual((a["prefill_regime"], a["prefill"]), ("", 200.0))

    def test_the_rule_is_render_dashboards(self):
        # one rule: render_dashboard's names are render_leaderboard's objects
        self.assertIs(render_dashboard.headline_regime, render_leaderboard.headline_regime)
        self.assertIs(render_dashboard.REGIME, render_leaderboard.REGIME)
        self.assertIs(render_dashboard.PROTOCOL_TASK_PREFIX, render_leaderboard.PROTOCOL_TASK_PREFIX)


if __name__ == "__main__":
    unittest.main()
