#!/usr/bin/env python3
"""Own export of a Qwen3 checkpoint to an ExecuTorch .pte, with a recipe sidecar.

This is NOT a published ExecuTorch artifact: it runs the pinned source tree's
example recipe (examples/models/qwen3: convert_weights.py, then export_llm with
the tree's config yaml, verbatim) under the export venv, and records what ran.

Writes into --out-dir:
  <name>.pte, <name>.recipe.json, tokenizer.json (copied from the HF snapshot),
  checkpoints/<repo>-<rev12>.meta.pth (convert_weights output, reusable),
  runs/<UTC stamp>/ (convert / export logs and hydra's resolved config).
and symlinks <name>.pte, <name>.recipe.json and tokenizer.json from --link-dir.

The venv's python runs with the working directory set to the run dir, never the
source tree's parent: a directory named `executorch` on sys.path would shadow the
installed wheel.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import time
import urllib.request

HOME = Path.home()
DEFAULTS = {
    "et_dir": HOME / "code/executorch-convert/et-v1.5.1/executorch",
    "venv": HOME / "code/executorch-convert/.venv-et151",
    "out_dir": Path("/Volumes/HD-SGDA/work/edge-llm-bench/models/executorch"),
    "link_dir": HOME / "code/edge-llm-bench/models/executorch",
}
# Wheel modules that must be byte-identical to the pinned tree (the export runs
# the wheel's copy; the recipe names the tree's tag).
SAME_AS_TREE = (
    "extension/llm/export/export_llm.py",
    "extension/llm/export/config/llm_config.py",
    "examples/models/llama/export_llama_lib.py",
    "examples/models/llama/source_transformation/quantize.py",
    "examples/models/qwen3/convert_weights.py",
)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd, log, cwd, env):
    """Run one step; the full output goes to log, the exit code is fatal."""
    t0 = time.monotonic()
    with open(log, "w") as f:
        f.write(f"$ {shlex.join(map(str, cmd))}\n# cwd {cwd}\n")
        f.flush()
        rc = subprocess.run(list(map(str, cmd)), cwd=cwd, env=env, stdout=f, stderr=subprocess.STDOUT).returncode
    secs = time.monotonic() - t0
    print(f"  rc={rc} {secs:.0f}s log={log}", flush=True)
    if rc != 0:
        sys.exit(f"ERROR: step failed (rc={rc}); tail of {log}:\n" + "".join(open(log).readlines()[-30:]))
    return secs


def venv_facts(py, env, cwd):
    # executorch is a namespace package (no __init__.py): __file__ is None, __path__ is the dir.
    code = ("import importlib.metadata as m, json, executorch;"
            "print(json.dumps({k: m.version(k) for k in ('executorch','torch','torchao','transformers')}"
            " | {'executorch_dir': list(executorch.__path__)[0]}))")
    out = subprocess.run([str(py), "-c", code], cwd=cwd, env=env, capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def hub_lfs_sha(repo, rev, filename):
    """sha256 the Hub records for an LFS file at a revision (read-only API call)."""
    url = f"https://huggingface.co/api/models/{repo}/tree/{rev}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            for entry in json.load(r):
                if entry.get("path") == filename and entry.get("lfs"):
                    return entry["lfs"].get("oid") or entry["lfs"].get("sha256")
    except Exception as e:  # recorded, not fatal: the local sha256 is still stored
        return f"unavailable: {type(e).__name__}: {e}"
    return "unavailable: not an LFS file in the tree listing"


def host_facts():
    def cmd(*a):
        try:
            return subprocess.run(a, capture_output=True, text=True, check=True).stdout.strip()
        except Exception as e:
            return f"unavailable: {e}"
    return {"sw_vers": cmd("sw_vers"), "chip": cmd("sysctl", "-n", "machdep.cpu.brand_string"),
            "model": cmd("sysctl", "-n", "hw.model"), "memBytes": cmd("sysctl", "-n", "hw.memsize"),
            "platform": platform.platform()}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model-class", required=True, help="export_llm base.model_class, e.g. qwen3_0_6b")
    ap.add_argument("--hf-repo", required=True, help="e.g. Qwen/Qwen3-0.6B")
    ap.add_argument("--revision", required=True, help="full HF commit sha of the cached snapshot")
    ap.add_argument("--params", required=True, help="params json, relative to the source tree")
    ap.add_argument("--config", required=True, help="export_llm config yaml, relative to the source tree")
    ap.add_argument("--name", required=True, help="output stem, e.g. Qwen3-0.6B-ET1.5.1-xnnpack-8da4w-emb8-ctx2048")
    ap.add_argument("--tag", default="v1.5.1", help="tag the source tree must describe as")
    ap.add_argument("--et-dir", type=Path, default=DEFAULTS["et_dir"])
    ap.add_argument("--venv", type=Path, default=DEFAULTS["venv"])
    ap.add_argument("--out-dir", type=Path, default=DEFAULTS["out_dir"])
    ap.add_argument("--link-dir", type=Path, default=DEFAULTS["link_dir"])
    ap.add_argument("--hf-home", type=Path, default=Path(os.environ.get("HF_HOME", HOME / ".cache/huggingface")))
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
    config, params = et / args.config, et / args.params
    for p in (config, params, et / "examples/models/qwen3/convert_weights.py"):
        if not p.is_file():
            sys.exit(f"ERROR: missing {p}")

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.out_dir
    rundir = out / "runs" / stamp
    (out / "checkpoints").mkdir(parents=True, exist_ok=True)
    rundir.mkdir(parents=True)
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    env.update(VIRTUAL_ENV=str(args.venv), PATH=f"{args.venv}/bin:{env.get('PATH', '')}",
               HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")

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

    files = {p.name: {"bytes": p.stat().st_size, "sha256": sha256(p)}
             for p in sorted(snapshot.iterdir()) if p.is_file() and not p.name.startswith(".")}
    for name in files:
        if name.endswith(".safetensors"):
            files[name]["hubLfsSha256"] = hub_lfs_sha(args.hf_repo, args.revision, name)
            files[name]["matchesHub"] = files[name]["hubLfsSha256"] == files[name]["sha256"]
            print(f"{name}: local {files[name]['sha256'][:16]}… hub match={files[name]['matchesHub']}", flush=True)

    pth = out / "checkpoints" / f"{args.hf_repo.split('/')[-1]}-{args.revision[:12]}.meta.pth"
    convert_cmd = [py, et / "examples/models/qwen3/convert_weights.py", snapshot, pth]
    if pth.is_file():
        print(f"convert: reuse {pth}", flush=True)
        convert_secs = None
    else:
        print("convert: " + shlex.join(map(str, convert_cmd)), flush=True)
        convert_secs = run(convert_cmd, rundir / "convert_weights.log", rundir, env)

    pte = out / f"{args.name}.pte"
    if pte.exists():
        sys.exit(f"ERROR: {pte} exists; move it aside first (an export is never overwritten in place)")
    export_cmd = [py, "-m", "executorch.extension.llm.export.export_llm", "--config", config,
                  f"+base.model_class={args.model_class}", f"+base.params={params}",
                  f"+base.checkpoint={pth}", f"+export.output_name={pte}"]
    print("export: " + shlex.join(map(str, export_cmd)), flush=True)
    export_secs = run(export_cmd, rundir / "export_llm.log", rundir, env)
    if not pte.is_file():
        sys.exit(f"ERROR: export finished without {pte}")

    tok_src = snapshot / "tokenizer.json"
    tok = out / "tokenizer.json"
    if tok.exists() and sha256(tok) != files["tokenizer.json"]["sha256"]:
        sys.exit(f"ERROR: {tok} exists with different bytes (one tokenizer.json per dir)")
    if not tok.exists():
        shutil.copyfile(tok_src, tok)

    resolved = sorted(rundir.glob("outputs/*/*/.hydra/config.yaml"))
    recipe = {
        "recipeVersion": 1,
        "ownExport": True,
        "note": "own export with the ExecuTorch source tree's example recipe; not a published ExecuTorch artifact",
        "executorch": args.tag.lstrip("v"),
        "source_tag": args.tag,
        "source_commit": head,
        "source_tree": str(et),
        "model_class": args.model_class,
        "config_yaml_path": args.config,
        "config_yaml": config.read_text(),
        "params_json_path": args.params,
        "params_json": params.read_text(),
        "resolved_config_yaml": resolved[-1].read_text() if resolved else None,
        "checkpoint": {"hf_repo": args.hf_repo, "revision": args.revision, "snapshot": str(snapshot),
                       "files": files, "converted": {"path": str(pth), "bytes": pth.stat().st_size,
                                                     "sha256": sha256(pth)}},
        "convert_command": shlex.join(map(str, convert_cmd)),
        "export_command": shlex.join(map(str, export_cmd)),
        "export_cwd": str(rundir),
        "export_seconds": round(export_secs, 1),
        "convert_seconds": None if convert_secs is None else round(convert_secs, 1),
        "venv": {"path": str(args.venv), **{k: v for k, v in facts.items() if k != "executorch_dir"},
                 "executorch_dir": facts["executorch_dir"], "wheel_sources_vs_tree": same},
        "pte": str(pte),
        "pte_sha256": sha256(pte),
        "pte_bytes": pte.stat().st_size,
        "tokenizer": {"file": str(tok), "sha256": sha256(tok), "from": str(tok_src)},
        "host": host_facts(),
        "exported_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "logs": {"convert": str(rundir / "convert_weights.log"), "export": str(rundir / "export_llm.log")},
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
