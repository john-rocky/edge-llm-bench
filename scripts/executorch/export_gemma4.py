#!/usr/bin/env python3
"""Own export of a Gemma 4 (E2B / E4B) checkpoint to an ExecuTorch .pte, with a recipe sidecar.

This is NOT a published ExecuTorch artifact: it runs the pinned source tree's
example exporter (examples/models/gemma4/export_gemma4.py, the installed
wheel's byte-identical copy) on a cached HF snapshot, text decoder only
(--no-audio --no-vision), and records what ran.

--mode as-shipped        python -m executorch.examples.models.gemma4.export_gemma4 <args>
--mode config-from-tree  the same module through run_gemma4_export.py, which points
                         Gemma4Config.from_config at the tree's
                         examples/models/gemma4/config/ (the 1.5.1 wheel ships the
                         gemma4 package without that directory)

Writes into --out-dir:
  <name>.pte, <name>.recipe.json, <name>.tokenizer.json (the snapshot's tokenizer.json),
  runs/<UTC stamp>/ (export log, TMPDIR).
and symlinks the three from --link-dir. A failed export leaves its run dir and
no recipe; --prior-attempt names such run dirs in the recipe of the export that
succeeded.

The venv's python runs with the working directory set to the run dir, never the
source tree's parent: a directory named `executorch` on sys.path would shadow the
installed wheel.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_qwen3 import DEFAULTS, host_facts, hub_lfs_sha, run, sha256, venv_facts  # noqa: E402

EXPORTER = "examples/models/gemma4/export_gemma4.py"
# Wheel modules that must be byte-identical to the pinned tree (the export runs
# the wheel's copy; the recipe names the tree's tag).
SAME_AS_TREE = (
    EXPORTER,
    "examples/models/gemma4/quant_utils.py",
    "examples/models/gemma4/text_decoder/__init__.py",
    "examples/models/gemma4/text_decoder/convert_weights.py",
    "examples/models/gemma4/text_decoder/gemma4_attention.py",
    "examples/models/gemma4/text_decoder/gemma4_config.py",
    "examples/models/gemma4/text_decoder/gemma4_cross_decoder.py",
    "examples/models/gemma4/text_decoder/gemma4_decoder_layer.py",
    "examples/models/gemma4/text_decoder/gemma4_model.py",
    "examples/models/gemma4/text_decoder/gemma4_self_decoder.py",
    "examples/models/gemma4/text_decoder/gemma4_transformer.py",
    "extension/llm/export/quantize.py",
    "examples/models/llama/source_transformation/quantize.py",
)
LAUNCHER = Path(__file__).resolve().parent / "run_gemma4_export.py"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hf-repo", required=True, help="e.g. google/gemma-4-E2B-it")
    ap.add_argument("--revision", required=True, help="full HF commit sha of the cached snapshot")
    ap.add_argument("--variant", required=True, choices=["e2b", "e4b"])
    ap.add_argument("--name", required=True, help="output stem, e.g. gemma-4-E2B-it-ET1.5.1-xnnpack-8da4w-emb8-ctx2048")
    ap.add_argument("--mode", required=True, choices=["as-shipped", "config-from-tree"])
    ap.add_argument("--quantize", default="8da4w+emb8")
    ap.add_argument("--max-seq-len", type=int, default=2048)
    ap.add_argument("--prior-attempt", action="append", default=[], help="run dir of an earlier failed attempt")
    ap.add_argument("--tag", default="v1.5.1", help="tag the source tree must describe as")
    ap.add_argument("--et-dir", type=Path, default=DEFAULTS["et_dir"])
    ap.add_argument("--venv", type=Path, default=DEFAULTS["venv"])
    ap.add_argument("--out-dir", type=Path, default=DEFAULTS["out_dir"])
    ap.add_argument("--link-dir", type=Path, default=DEFAULTS["link_dir"])
    ap.add_argument("--hf-home", type=Path, default=Path(os.environ.get("HF_HOME", Path.home() / ".cache/huggingface")))
    args = ap.parse_args()

    et = args.et_dir.resolve()
    described = subprocess.run(["git", "-C", str(et), "describe", "--tags"], capture_output=True, text=True).stdout.strip()
    if described != args.tag:
        sys.exit(f"ERROR: {et} describes as {described!r}, expected {args.tag!r}")
    head = subprocess.run(["git", "-C", str(et), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    py = args.venv / "bin/python"
    snapshot = args.hf_home / "hub" / f"models--{args.hf_repo.replace('/', '--')}" / "snapshots" / args.revision
    if not (snapshot / "config.json").is_file():
        sys.exit(f"ERROR: no cached snapshot {snapshot} (this script never downloads)")
    variant_cfg = et / "examples/models/gemma4/config" / f"{args.variant}_config.json"
    for p in (et / EXPORTER, variant_cfg, LAUNCHER):
        if not p.is_file():
            sys.exit(f"ERROR: missing {p}")

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.out_dir
    rundir = out / "runs" / stamp
    (rundir / "tmp").mkdir(parents=True)
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    env.update(VIRTUAL_ENV=str(args.venv), PATH=f"{args.venv}/bin:{env.get('PATH', '')}",
               HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", TMPDIR=str(rundir / "tmp"))

    facts = venv_facts(py, env, rundir)
    print(f"venv: {json.dumps(facts)}", flush=True)
    if facts["executorch"] != args.tag.lstrip("v"):
        sys.exit(f"ERROR: venv executorch {facts['executorch']} != {args.tag}")
    site_et = Path(facts["executorch_dir"])
    if et in site_et.parents or site_et == et:
        sys.exit(f"ERROR: python imported executorch from the source tree {site_et}")
    same = {}
    for rel in SAME_AS_TREE:
        wheel_copy = site_et / rel
        same[rel] = {"tree": sha256(et / rel), "wheel": sha256(wheel_copy) if wheel_copy.is_file() else "absent"}
        same[rel]["identical"] = same[rel]["tree"] == same[rel]["wheel"]
    print("wheel vs tree: " + ", ".join(f"{k.rsplit('/', 1)[-1]}={'same' if v['identical'] else 'DIFF'}"
                                        for k, v in same.items()), flush=True)
    if not all(v["identical"] for v in same.values()):
        sys.exit("ERROR: the wheel's export sources differ from the tree; the recipe would name the wrong code")
    wheel_cfg = site_et / "examples/models/gemma4/config" / variant_cfg.name
    print(f"variant config: tree {variant_cfg} sha256 {sha256(variant_cfg)[:16]}…; "
          f"wheel copy {'present' if wheel_cfg.is_file() else 'absent'}", flush=True)

    files = {p.name: {"bytes": p.stat().st_size, "sha256": sha256(p)}
             for p in sorted(snapshot.iterdir()) if p.is_file() and not p.name.startswith(".")}
    for name in files:
        if name.endswith(".safetensors"):
            files[name]["hubLfsSha256"] = hub_lfs_sha(args.hf_repo, args.revision, name)
            files[name]["matchesHub"] = files[name]["hubLfsSha256"] == files[name]["sha256"]
            print(f"{name}: local {files[name]['sha256'][:16]}… hub match={files[name]['matchesHub']}", flush=True)

    pte = out / f"{args.name}.pte"
    if pte.exists():
        sys.exit(f"ERROR: {pte} exists; move it aside first (an export is never overwritten in place)")
    export_args = ["--checkpoint_path", snapshot, "--variant", args.variant, "--output_path", pte,
                   "--no-audio", "--no-vision", "--quantize", args.quantize, "--max_seq_len", str(args.max_seq_len)]
    if args.mode == "as-shipped":
        export_cmd = [py, "-m", "executorch.examples.models.gemma4.export_gemma4"] + export_args
    else:
        export_cmd = [py, LAUNCHER, variant_cfg.parent] + export_args
    print(f"export ({args.mode}): " + shlex.join(map(str, export_cmd)), flush=True)
    export_secs = run(export_cmd, rundir / "export_gemma4.log", rundir, env)
    if not pte.is_file():
        sys.exit(f"ERROR: export finished without {pte}")
    side = sorted(p.name for p in pte.parent.glob("*.ptd"))
    if side:
        print(f"note: tensor data files beside the pte: {side}", flush=True)

    tok_src = snapshot / "tokenizer.json"
    tok = out / f"{args.name}.tokenizer.json"
    if tok.exists() and sha256(tok) != files["tokenizer.json"]["sha256"]:
        sys.exit(f"ERROR: {tok} exists with different bytes")
    if not tok.exists():
        shutil.copyfile(tok_src, tok)

    recipe = {
        "recipeVersion": 1,
        "ownExport": True,
        "note": "own export with the ExecuTorch source tree's example exporter; not a published ExecuTorch artifact",
        "executorch": args.tag.lstrip("v"),
        "source_tag": args.tag,
        "source_commit": head,
        "source_tree": str(et),
        "exporter": {"tree_path": EXPORTER, "module": "executorch.examples.models.gemma4.export_gemma4",
                     "sha256": sha256(et / EXPORTER), "mode": args.mode,
                     "launcher": None if args.mode == "as-shipped" else
                     {"path": str(LAUNCHER), "sha256": sha256(LAUNCHER), "source": LAUNCHER.read_text()}},
        "variant": args.variant,
        "variant_config_json_path": str(variant_cfg.relative_to(et)),
        "variant_config_json": variant_cfg.read_text(),
        "variant_config_sha256": sha256(variant_cfg),
        "wheel_has_variant_config": wheel_cfg.is_file(),
        "export_args": {"quantize": args.quantize, "max_seq_len": args.max_seq_len, "variant": args.variant,
                        "no_audio": True, "no_vision": True},
        "exporter_defaults_in_effect": {"group_size": 128, "tied_embedding": False, "quantize_kv_cache": False,
                                        "use_custom_sdpa": True, "dtype": "float32",
                                        "source": "export_gemma4.py argparse defaults and _export_text_decoder"},
        "checkpoint": {"hf_repo": args.hf_repo, "revision": args.revision, "snapshot": str(snapshot), "files": files},
        "export_command": shlex.join(map(str, export_cmd)),
        "export_cwd": str(rundir),
        "export_env": {"TMPDIR": str(rundir / "tmp"), "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"},
        "export_seconds": round(export_secs, 1),
        "prior_attempts": [{"run_dir": p, "log": str(Path(p) / "export_gemma4.log")} for p in args.prior_attempt],
        "venv": {"path": str(args.venv), **{k: v for k, v in facts.items() if k != "executorch_dir"},
                 "executorch_dir": facts["executorch_dir"], "wheel_sources_vs_tree": same},
        "pte": str(pte),
        "pte_sha256": sha256(pte),
        "pte_bytes": pte.stat().st_size,
        "tensor_data_files": side,
        "tokenizer": {"file": str(tok), "sha256": sha256(tok), "from": str(tok_src)},
        "host": host_facts(),
        "exported_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "logs": {"export": str(rundir / "export_gemma4.log")},
    }
    recipe_path = out / f"{args.name}.recipe.json"
    recipe_path.write_text(json.dumps(recipe, indent=2, ensure_ascii=False) + "\n")
    print(f"pte {pte} {recipe['pte_bytes']} bytes sha256 {recipe['pte_sha256']}", flush=True)
    print(f"recipe {recipe_path}", flush=True)

    args.link_dir.mkdir(parents=True, exist_ok=True)
    for target in (pte, recipe_path, tok):
        link = args.link_dir / target.name
        if link.is_symlink() or link.exists():
            if link.is_symlink() and Path(os.readlink(link)) == target:
                continue
            sys.exit(f"ERROR: {link} exists and is not a link to {target}")
        link.symlink_to(target)
        print(f"link {link} -> {target}", flush=True)


if __name__ == "__main__":
    main()
