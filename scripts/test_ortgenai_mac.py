#!/usr/bin/env python3
"""Contract checks of scripts/ortgenai_mac.py's staging and --overlay (no engine, no model download).

  python3 scripts/test_ortgenai_mac.py
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ortgenai_mac  # noqa: E402

CONFIG = {"model": {"decoder": {"session_options": {"log_id": "onnxruntime-genai", "provider_options": []},
                                "filename": "model.onnx"},
                    "eos_token_id": [151645, 151643]},
          "search": {"max_length": 40960, "past_present_share_buffer": True, "top_p": 0.95}}


def hf_like_folder(root, external_data):
    """A GenAI folder laid out like the HF cache: snapshot entries are links into a blob store, and
    model.onnx / model.onnx.data resolve into two different directories (the r4-mac 4B WebGPU case)."""
    store_a, store_b, blobs = root / "store" / "33", root / "store" / "0c", root / "blobs"
    folder = root / "snapshots" / ("0" * 40) / "onnxruntime" / "cpu"
    for d in (store_a, store_b, blobs, folder):
        d.mkdir(parents=True)
    contents = {"genai_config.json": json.dumps(CONFIG).encode(), "model.onnx": b"onnx-bytes",
                "tokenizer.json": b"{}"}
    if external_data:
        contents["model.onnx.data"] = b"\x00" * 4096
    for name, data in contents.items():
        real = (store_b if name == "model.onnx.data" else store_a) / name
        real.write_bytes(data)
        (blobs / name).symlink_to(real)
        (folder / name).symlink_to(blobs / name)
    return folder, contents


class StagingTests(unittest.TestCase):
    def test_deep_merge_merges_dicts_and_replaces_everything_else(self):
        merged = ortgenai_mac.deep_merge(CONFIG, {
            "model": {"decoder": {"session_options": {"intra_op_num_threads": 12,
                                                      "provider_options": [{"webgpu": {"enableGraphCapture": "1"}}]}}},
            "search": {"past_present_share_buffer": False}})
        options = merged["model"]["decoder"]["session_options"]
        self.assertEqual(options["intra_op_num_threads"], 12)
        self.assertEqual(options["log_id"], "onnxruntime-genai")
        self.assertEqual(options["provider_options"], [{"webgpu": {"enableGraphCapture": "1"}}])
        self.assertEqual(merged["model"]["eos_token_id"], [151645, 151643])
        self.assertEqual(merged["model"]["decoder"]["filename"], "model.onnx")
        self.assertIs(merged["search"]["past_present_share_buffer"], False)
        self.assertEqual(merged["search"]["max_length"], 40960)
        self.assertNotIn("intra_op_num_threads", CONFIG["model"]["decoder"]["session_options"])  # base untouched

    def test_staging_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            plain, _ = hf_like_folder(Path(tmp) / "a", external_data=False)
            linked, _ = hf_like_folder(Path(tmp) / "b", external_data=True)
            self.assertIsNone(ortgenai_mac.staging_reason(plain, None))
            self.assertEqual(ortgenai_mac.staging_reason(plain, {"search": {}}), "genai_config overlay")
            self.assertEqual(ortgenai_mac.staging_reason(linked, None), "external data behind links")

    def test_stage_folder_gives_real_files_in_one_dir_and_leaves_the_cache_alone(self):
        overlay = {"model": {"decoder": {"session_options": {"intra_op_num_threads": 16}}}}
        with tempfile.TemporaryDirectory() as tmp:
            folder, contents = hf_like_folder(Path(tmp), external_data=True)
            before = {p.name: (p.resolve(), p.resolve().read_bytes()) for p in folder.iterdir()}
            stage, info = ortgenai_mac.stage_folder(folder, overlay, "genai_config overlay")
            try:
                self.assertEqual(sorted(p.name for p in stage.iterdir()), sorted(contents))
                for p in stage.iterdir():
                    self.assertFalse(p.is_symlink(), p)
                    self.assertEqual(p.resolve().parent, stage.resolve())  # both weights files in one real dir
                for name in ("model.onnx", "model.onnx.data", "tokenizer.json"):
                    self.assertEqual((stage / name).read_bytes(), contents[name])
                    self.assertIn(info["files"][name]["method"].split(" ")[0], ("clonefile", "hardlink"))
                staged = json.loads((stage / "genai_config.json").read_text())
                self.assertEqual(staged, ortgenai_mac.deep_merge(CONFIG, overlay))
                self.assertEqual(ortgenai_mac.threads_condition(staged), "intra_op_num_threads 16 (genai_config)")
                self.assertEqual(info["files"]["genai_config.json"]["method"], "written (overlay applied)")
            finally:
                import shutil
                shutil.rmtree(stage)
            after = {p.name: (p.resolve(), p.resolve().read_bytes()) for p in folder.iterdir()}
            self.assertEqual(before, after)  # the cache's links, targets and bytes are unchanged
            self.assertEqual(json.loads((folder / "genai_config.json").read_text()), CONFIG)
            self.assertEqual(ortgenai_mac.threads_condition(CONFIG), "engine default")

    def test_dry_run_prints_the_staged_config_diff_and_removes_the_copy(self):
        overlay = '{"search": {"past_present_share_buffer": false}}'
        with tempfile.TemporaryDirectory() as tmp:
            folder, _ = hf_like_folder(Path(tmp), external_data=False)
            out = subprocess.run(
                [sys.executable, str(Path(ortgenai_mac.__file__)), "--model-id", "onnx-community/Qwen3-0.6B-ONNX",
                 "--model-dir", str(folder), "--backend", "cpu", "--runs", "3", "--dry-run", "--overlay", overlay],
                capture_output=True, text=True, env=dict(os.environ, HF_HUB_OFFLINE="1"))
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertIn('-        "past_present_share_buffer": true,', out.stdout)
            self.assertIn('+        "past_present_share_buffer": false,', out.stdout)
            self.assertIn("staged copy removed: True", out.stdout)
            self.assertIn("past_present_share_buffer False", out.stdout)
            bad = subprocess.run(
                [sys.executable, str(Path(ortgenai_mac.__file__)), "--model-id", "x/y", "--model-dir", str(folder),
                 "--backend", "cpu", "--dry-run", "--overlay", "[1]"], capture_output=True, text=True)
            self.assertEqual(bad.returncode, 2)
            self.assertIn("--overlay must be a non-empty JSON object", bad.stderr)


if __name__ == "__main__":
    unittest.main()
