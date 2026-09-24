#!/usr/bin/env python3
"""Contract checks only; these tests do not claim physical-device inference."""
import contextlib
import asyncio
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import uzu_mac
from validate_cells import validate_file


class UzuContractTests(unittest.TestCase):
    def temporary_directory(self):
        # Keep test writes local even when the caller has a system TMPDIR.
        root = uzu_mac.REPO / ".cache" / "uzu" / "contract-tests"
        root.mkdir(parents=True, exist_ok=True)
        return tempfile.TemporaryDirectory(dir=root)

    def test_downloaded_registry_model_is_local_and_uses_sdk_downloader(self):
        class Downloaded:
            pass
        class Error:
            pass
        state = SimpleNamespace(phase=Downloaded(), progress=1.0, downloaded_bytes=42, total_bytes=42)
        class Stream:
            async def iterator(self):
                yield state
        engine = SimpleNamespace(download_state=AsyncMock(return_value=state),
                                 download=AsyncMock(return_value=Stream()),
                                 model_path=AsyncMock(return_value="/local/sdk/model"))
        model = SimpleNamespace(identifier="registry:model", is_local=True, is_remote=False, is_downloadable=True)
        payload = {}
        result = asyncio.run(uzu_mac.ensure_local_model(engine, model, payload,
                                                      SimpleNamespace(Downloaded=Downloaded, Error=Error)))
        self.assertEqual(str(result), "/local/sdk/model")
        self.assertEqual(engine.download_state.await_count, 2)
        engine.download.assert_awaited_once_with(model)
        self.assertEqual(payload["downloadAfter"]["phase"], "Downloaded")

    def test_cloud_model_is_refused_before_download_or_chat(self):
        engine = SimpleNamespace(download_state=AsyncMock(), download=AsyncMock(), model_path=AsyncMock())
        model = SimpleNamespace(identifier="cloud:model", is_local=False, is_remote=True, is_downloadable=False)
        with self.assertRaisesRegex(RuntimeError, "cloud/remote execution"):
            asyncio.run(uzu_mac.ensure_local_model(engine, model, {}, None))
        engine.download.assert_not_awaited()
        engine.download_state.assert_not_awaited()
        engine.model_path.assert_not_awaited()

    def test_incomplete_registry_download_cannot_become_a_local_run(self):
        class Downloaded:
            pass
        class Paused:
            pass
        class Error:
            pass
        state = SimpleNamespace(phase=Paused(), progress=0.5, downloaded_bytes=21, total_bytes=42)
        class Stream:
            async def iterator(self):
                yield state
        engine = SimpleNamespace(download_state=AsyncMock(return_value=state),
                                 download=AsyncMock(return_value=Stream()), model_path=AsyncMock())
        model = SimpleNamespace(identifier="registry:model", is_local=True, is_remote=False, is_downloadable=True)
        with self.assertRaisesRegex(RuntimeError, "download incomplete"):
            asyncio.run(uzu_mac.ensure_local_model(engine, model, {},
                                                  SimpleNamespace(Downloaded=Downloaded, Error=Error)))
        engine.model_path.assert_not_awaited()

    def test_dry_run_has_one_engine_per_run_and_task_budget(self):
        with self.temporary_directory() as temp:
            output = Path(temp) / "no-capture.jsonl"
            argv = ["uzu_mac.py", "--model-id", "trymirai/Qwen3.5-0.8B-M", "--recipe", "Mirai-M",
                    "--runs", "2", "--pause", "7", "--thinking", "off", "--output", str(output), "--dry-run"]
            text = io.StringIO()
            with patch.object(sys, "argv", argv), contextlib.redirect_stdout(text):
                self.assertEqual(uzu_mac.main(), 0)
            self.assertEqual(text.getvalue().count("Engine.create("), 2)
            self.assertEqual(text.getvalue().count("with_token_limit(128)"), 2)
            self.assertIn("pause=7.0s", text.getvalue())
            self.assertIn("ReasoningEffort.Disabled", text.getvalue())
            self.assertFalse(output.exists())

    def test_long_context_budget_and_allocation_are_independent(self):
        with self.temporary_directory() as temp:
            argv = ["uzu_mac.py", "--model-path", temp, "--recipe", "bfloat16",
                    "--task", "long-context-2048-gen256", "--context-tokens", "8192",
                    "--output", str(Path(temp) / "none.jsonl"), "--dry-run"]
            text = io.StringIO()
            with patch.object(sys, "argv", argv), contextlib.redirect_stdout(text):
                self.assertEqual(uzu_mac.main(), 0)
            self.assertIn("model_by_path(", text.getvalue())
            self.assertIn("ContextLength.Custom(8192)", text.getvalue())
            self.assertIn("with_token_limit(256)", text.getvalue())

    def test_validator_rejects_unsupported_cells(self):
        cases = [
            "ios uzu trymirai/Qwen3.5-0.8B-M short-chat recipe=Mirai-M",
            "android uzu trymirai/Qwen3.5-0.8B-M short-chat recipe=Mirai-M",
            "mac uzu trymirai/Qwen3.5-0.8B-M short-chat recipe=int4",
            "mac uzu trymirai/Qwen3.5-0.8B-M short-chat",
            "mac uzu own-export/Qwen3-0.6B-lalamo-bfloat16 short-chat recipe=bfloat16",
            "mac uzu trymirai/Qwen3.5-0.8B-M long-context-2048-gen256 recipe=Mirai-M",
            "mac uzu trymirai/Qwen3.5-0.8B-M energy recipe=Mirai-M manual=1",
            "mac uzu trymirai/Qwen3.5-0.8B-M short-chat recipe=Mirai-M thinking=auto",
        ]
        with self.temporary_directory() as temp:
            path = Path(temp) / "test.cells"
            for line in cases:
                with self.subTest(line=line):
                    path.write_text(line + "\n")
                    self.assertTrue(validate_file(path)[0])

    def test_failed_worker_is_stored_without_fake_metrics(self):
        # Synthetic process exit, not a device or SDK gate. Verify failed-runs-stay.
        with self.temporary_directory() as temp:
            out = Path(temp) / "failed.jsonl"
            argv = ["uzu_mac.py", "--model-id", "trymirai/Qwen3.5-0.8B-M", "--recipe", "Mirai-M",
                    "--output", str(out), "--cache-dir", str(Path(temp) / "cache"), "--sdk-store", "normal"]
            with patch.object(sys, "argv", argv), patch.dict(os.environ, {"CFFIXED_USER_HOME": "/stale/private"}), patch.object(uzu_mac.subprocess, "run") as launch:
                launch.return_value = subprocess.CompletedProcess([], 17)
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(uzu_mac.main(), 1)
                self.assertNotIn("CFFIXED_USER_HOME", launch.call_args.kwargs["env"])
            record = json.loads(out.read_text())
            self.assertEqual(record["status"], "failed")
            self.assertFalse(record["checks"]["finiteNonnegativeMetrics"])
            self.assertNotIn("decodeTokensPerSecond", record["metrics"])
            self.assertEqual(record["metrics"]["exitCode"], 17)
            self.assertIn("unavailable", record["engineVersion"])
            self.assertNotIn("memoryPeakResidentMB", record["metrics"])
            self.assertEqual(record["provenance"]["hostBefore"]["snapshot"]["thermal"], "unknown")

    def test_matrix_dispatch_dry_run_local_and_registry(self):
        with self.temporary_directory() as temp:
            cells = Path(temp) / "dispatch.cells"
            cells.write_text(
                "mac uzu own-export/Qwen3-0.6B-lalamo-bfloat16 short-chat "
                "recipe=bfloat16 file=Qwen3-0.6B-lalamo-bfloat16 runs=2 thinking=off\n"
                "mac uzu trymirai/Qwen3.5-0.8B-M short-chat recipe=Mirai-M runs=1\n")
            result = subprocess.run(["bash", str(uzu_mac.REPO / "scripts/bench_matrix_mac.sh"),
                                     "run", str(cells), "--dry-run"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.count("model_by_path("), 2)
            self.assertIn("engine.model('trymirai/Qwen3.5-0.8B-M')", result.stdout)
            self.assertEqual(result.stdout.count("ReasoningEffort.Disabled"), 2)
            self.assertNotIn("no yardstick", result.stderr)

    def test_missing_sdk_memory_keeps_a_failed_schema_valid_record(self):
        with self.temporary_directory() as temp:
            out = Path(temp) / "missing-memory.jsonl"
            argv = ["uzu_mac.py", "--model-id", "trymirai/Qwen3.5-0.8B-M", "--recipe", "Mirai-M",
                    "--output", str(out), "--cache-dir", str(Path(temp) / "cache")]

            def simulated_reply(cmd, **kwargs):
                Path(cmd[cmd.index("--worker-result") + 1]).write_text(json.dumps({
                    "ok": True, "engineVersion": "synthetic fixture", "text": "A test fixture only.",
                    "stats": {"duration": 1.0, "time_to_first_token": 0.1,
                              "generate_tokens_per_second": 1.0, "prefill_tokens_per_second": 1.0,
                              "tokens_count_input": 10, "tokens_count_output": 5,
                              "memory_used_bytes": None}}))
                Path(cmd[cmd.index("--rss-result") + 1]).write_text(json.dumps({"childPeakRSSBytes": 123000000}))
                return subprocess.CompletedProcess(cmd, 0)

            with patch.object(sys, "argv", argv), patch.object(uzu_mac.subprocess, "run", side_effect=simulated_reply):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(uzu_mac.main(), 1)
            rec = json.loads(out.read_text())
            self.assertEqual(rec["status"], "failed")
            self.assertNotIn("memoryPeakAllocatedMB", rec["metrics"])
            self.assertEqual(rec["metrics"]["memoryPeakResidentMB"], 123)

    def test_memory_counters_have_distinct_units_and_raw_sidecars(self):
        with self.temporary_directory() as temp:
            out = Path(temp) / "memory.jsonl"
            argv = ["uzu_mac.py", "--model-id", "trymirai/Qwen3.5-0.8B-M", "--recipe", "Mirai-M",
                    "--output", str(out), "--cache-dir", str(Path(temp) / "cache")]

            def simulated_reply(cmd, **kwargs):
                Path(cmd[cmd.index("--worker-result") + 1]).write_text(json.dumps({
                    "ok": True, "engineVersion": "synthetic fixture", "text": "A test fixture only.",
                    "stats": {"time_to_first_token": 0.1, "generate_tokens_per_second": 1.0,
                              "prefill_tokens_per_second": 1.0, "tokens_count_input": 10,
                              "tokens_count_output": 5, "memory_used_bytes": 42000000}}))
                Path(cmd[cmd.index("--rss-result") + 1]).write_text(json.dumps({"childPeakRSSBytes": 123000000}))
                return subprocess.CompletedProcess(cmd, 0)

            with patch.object(sys, "argv", argv), patch.object(uzu_mac.subprocess, "run", side_effect=simulated_reply):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(uzu_mac.main(), 0)
            rec = json.loads(out.read_text())
            self.assertEqual(rec["metrics"]["memoryPeakAllocatedMB"], 42)
            self.assertEqual(rec["metrics"]["memoryPeakResidentMB"], 123)
            for name in ("memory_used_bytes", "uzuMemoryUsedBytes", "processPeakRSSBytes"):
                self.assertNotIn(name, rec["metrics"])
            raw = json.loads(Path(rec["provenance"]["sdkReply"]).read_text())
            rss = json.loads(Path(rec["provenance"]["rssReport"]).read_text())
            self.assertEqual(raw["stats"]["memory_used_bytes"], 42000000)
            self.assertEqual(rss["childPeakRSSBytes"], 123000000)


if __name__ == "__main__":
    unittest.main()
