#!/usr/bin/env python3
"""Runs the ios rows of cells files on Developer Device Platform (one session per row).

The iOS counterpart of android/ddp/run_ddp.py and scripts/run_mac_matrix.py. Each `ios` row of
the cells files (matrices/README.md grammar; `manual=1` and `exclude=` rows skipped) is submitted
through ios/ddp/run_ddp_ios_lm.py against its runtime's signed XCTest archive
(`BenchmarkApp-ddp[-<engine>]-xctest.zip`), writing records into `<BENCH_RAW_ROOT>/<campaign>/device-jsonl/`.

Archive builders (`--archive-builder`, pluggable via `register_archive_builder`):
  prebuilt  (default) expects `BenchmarkApp-ddp[-<engine>]-xctest.zip` in `--archives-dir`
  local     runs `ios/ddp/build_xctest.sh --engine <engine> <out.zip>` on this Mac

Another harness (e.g. a Linux orchestrator that builds signed XCTest archives on a remote Mac)
can register its own archive builder:

  import run_ddp_ios_matrix
  run_ddp_ios_matrix.register_archive_builder("omnilab", fn)  # fn(engines, archives_dir, args) -> int

Local / own-export model files (`--model-dir <model_id>=<dir>` or `--models-root <dir>`) are passed
as `--model-file` to `run_ddp_ios_lm.py`; public Hub entries without a local directory are fetched
by `run_ddp_ios_lm.py` as usual.
"""

import argparse
import dataclasses
import datetime
import os
import pathlib
import shutil
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

import run_ddp_ios_lm  # noqa: E402
import validate_cells  # noqa: E402

ENGINE_OF_RUNTIME = {
    "litert-lm": "litert",
    "llama.cpp": "llamacpp",
    "executorch": "executorch",
    "mlx-swift": "mlx",
}
RUNTIME_OF_ENGINE = {v: k for k, v in ENGINE_OF_RUNTIME.items()}
ENGINES = tuple(ENGINE_OF_RUNTIME.values())
BACKEND_RUNTIMES = ("litert-lm", "llama.cpp")
DEFAULT_DEVICE = "iphone16pro-18-3"
DEFAULT_RUNS = 4


def raw_root() -> pathlib.Path:
    """Where campaigns live: BENCH_RAW_ROOT, else <repo>/results/raw."""
    return pathlib.Path(os.environ.get("BENCH_RAW_ROOT") or REPO / "results" / "raw")


@dataclasses.dataclass(frozen=True)
class IosCell:
    """One runnable ios row from a cells file and its resolved local model files (if any)."""

    runtime: str
    model_id: str
    task: str
    opts: dict
    files: tuple

    @property
    def engine(self) -> str:
        return ENGINE_OF_RUNTIME[self.runtime]

    @property
    def name(self) -> str:
        backend = self.opts.get("backend")
        return f"{self.runtime}-{backend}" if backend else self.runtime

    @property
    def app_args(self) -> tuple:
        if self.opts.get("ynnpack") == "1":
            return ("--litert-ynnpack", "on")
        return ()


def parse_model_dirs(pairs: list) -> dict:
    """`--model-dir <model_id>=<dir>` -> {model_id.lower(): Path}."""
    out = {}
    for item in pairs or []:
        mid, sep, d = item.partition("=")
        if not sep or not mid or not d:
            raise ValueError(f"--model-dir {item!r}: want <model_id>=<dir>")
        out[mid.lower()] = pathlib.Path(d).expanduser().resolve()
    return out


def resolve_local_files(runtime: str, model_id: str, entry: dict, model_dirs: dict,
                        models_root: pathlib.Path | None, dry_run: bool = False) -> tuple:
    """Local files for a catalog entry when staged locally, else () so run_ddp_ios_lm pulls from HF."""
    names = entry["files"]
    d = model_dirs.get(model_id.lower())
    if d is not None:
        paths = tuple(d / n for n in names)
        missing = [str(p) for p in paths if not p.is_file()]
        if missing and not dry_run:
            raise ValueError(f"{runtime} {model_id}: missing local file(s): {', '.join(missing)}")
        return paths
    if models_root is not None:
        cand = models_root / runtime / entry["hfRepoId"].replace("/", "__")
        if dry_run or (cand.is_dir() and all((cand / n).is_file() for n in names)):
            return tuple(cand / n for n in names)
    if model_id.startswith(("own-export/", "litert-local/", "local/")):
        raise ValueError(f"{runtime} {model_id}: own/local export requires --model-dir {model_id}=<dir> "
                         "or --models-root")
    return ()


def plan_cells(cells_files: list, extra_catalog: str | None, engines_csv: str | None,
               model_dirs: dict, models_root: pathlib.Path | None, dry_run: bool = False) -> list:
    """Parse ios rows from cells_files, filter by selected engines, and resolve local model files."""
    wanted = set(ENGINES)
    if engines_csv and engines_csv != "all":
        tokens = [e.strip() for e in engines_csv.split(",") if e.strip()]
        mapped = set()
        for t in tokens:
            if t in ENGINE_OF_RUNTIME:
                mapped.add(ENGINE_OF_RUNTIME[t])
            elif t in ENGINES:
                mapped.add(t)
            else:
                matches = {eng for rt, eng in ENGINE_OF_RUNTIME.items() if rt.startswith(t)}
                if not matches:
                    raise ValueError(f"unknown engine {t!r} (want {', '.join(ENGINES)})")
                mapped |= matches
        wanted = mapped

    catalog = {k.lower(): (k, v) for k, v in run_ddp_ios_lm.load_models(extra_catalog).items()}
    planned = []
    for path in cells_files:
        for lineno, raw in enumerate(pathlib.Path(path).read_text(encoding="utf-8").splitlines(), 1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            plat, rt, mid, task, opts = validate_cells.parse_line(line)
            if plat != "ios" or opts.get("manual") == "1" or opts.get("exclude"):
                continue
            if rt not in ENGINE_OF_RUNTIME:
                raise ValueError(f"{path}:{lineno}: ios runtime {rt!r} has no DDP lab build")
            if ENGINE_OF_RUNTIME[rt] not in wanted:
                continue
            hit = catalog.get(mid.lower())
            if hit is None:
                raise ValueError(f"{path}:{lineno}: {mid!r} is not in ios/ddp/models*.json "
                                 "(pass --extra-catalog for non-compiled ids)")
            canonical_id, entry = hit
            files = resolve_local_files(rt, canonical_id, entry, model_dirs, models_root, dry_run=dry_run)
            planned.append(IosCell(rt, canonical_id, task, opts, files))
    return planned


def archive_path(archives_dir: pathlib.Path, engine: str) -> pathlib.Path:
    """Archive path in `archives_dir` for `engine` (build_xctest.sh's default, or -litert- alias)."""
    default_name = run_ddp_ios_lm.RUNTIMES[RUNTIME_OF_ENGINE[engine]]["archive"]
    primary = archives_dir / default_name
    if engine == "litert" and not primary.is_file():
        alt = archives_dir / "BenchmarkApp-ddp-litert-xctest.zip"
        if alt.is_file():
            return alt
    return primary


def session_argv(cell: IosCell, archive: pathlib.Path, args) -> list:
    """`run_ddp_ios_lm.py` argv for one planned cell."""
    argv = [
        "--device", args.device,
        "--runtime", cell.runtime,
        "--model-id", cell.model_id,
    ]
    if cell.runtime in BACKEND_RUNTIMES:
        argv += ["--backend", cell.opts.get("backend", "gpu")]
    for f in cell.files:
        argv += ["--model-file", str(f)]
    if args.extra_catalog:
        argv += ["--extra-catalog", str(args.extra_catalog)]
    for word in cell.app_args:
        argv.append(f"--app-arg={word}")
    if cell.opts.get("context-tokens"):
        argv += ["--context-tokens", str(cell.opts["context-tokens"])]
    cool_wait = int(cell.opts.get("cool-wait", args.cool_wait))
    if cool_wait > 0:
        argv += ["--app-arg=--cool-wait", f"--app-arg={cool_wait}", "--timeout", "30m"]
    runs = int(cell.opts.get("runs", args.runs))
    argv += [
        "--task", cell.task,
        "--runs", str(runs),
        "--archive", str(archive),
        "--project", args.project,
        "--bucket", args.bucket,
        "--campaign", args.campaign,
    ]
    if args.dry_run:
        argv.append("--dry-run")
    return argv


def build_prebuilt(engines: list, archives_dir: pathlib.Path, args) -> int:
    if args.dry_run and all(not archive_path(archives_dir, e).is_file() for e in engines):
        return 0
    missing = [str(archive_path(archives_dir, e)) for e in engines
               if not archive_path(archives_dir, e).is_file()]
    if missing:
        print("run_ddp_ios_matrix: missing XCTest archive(s): " + ", ".join(missing), file=sys.stderr)
        return 2
    return 0


def build_local(engines: list, archives_dir: pathlib.Path, args) -> int:
    archives_dir.mkdir(parents=True, exist_ok=True)
    script = HERE / "build_xctest.sh"
    for eng in engines:
        out_zip = archives_dir / run_ddp_ios_lm.RUNTIMES[RUNTIME_OF_ENGINE[eng]]["archive"]
        cmd = ["bash", str(script), "--engine", eng, str(out_zip)]
        print("+", " ".join(cmd), flush=True)
        if args.dry_run:
            continue
        rc = subprocess.run(cmd, check=False).returncode
        if rc:
            return rc
    return 0


ARCHIVE_BUILDERS = {"prebuilt": build_prebuilt, "local": build_local}


def register_archive_builder(name: str, fn) -> None:
    """Register `fn(engines, archives_dir, args) -> exit_code` for `--archive-builder <name>`."""
    ARCHIVE_BUILDERS[name] = fn


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cells", nargs="+", type=pathlib.Path, help="cells files; their ios rows run")
    ap.add_argument("--campaign", help="campaign dir name (default: <date>-ddp-ios)")
    ap.add_argument("--device", default=os.environ.get("BENCH_IOS_DDP_DEVICE", DEFAULT_DEVICE))
    ap.add_argument("--project", default=os.environ.get("BENCH_DDP_PROJECT", "litert-edge-portal"))
    ap.add_argument("--bucket", default=os.environ.get("BENCH_DDP_BUCKET", "gs://litert-edge-portal-devicerun"))
    ap.add_argument("--runs", type=int, default=DEFAULT_RUNS,
                    help="default runs per cell when the row sets no runs= (default: %(default)s)")
    ap.add_argument("--cool-wait", type=int, default=0,
                    help="default --cool-wait seconds before warm runs when row sets none")
    ap.add_argument("--cooldown", type=int, default=0,
                    help="seconds to sleep between DDP sessions (default: 0)")
    ap.add_argument("--engines", default="all",
                    help="comma list of engines or runtimes to run (default: all)")
    ap.add_argument("--archives-dir", type=pathlib.Path, default=HERE / "out",
                    help="directory holding BenchmarkApp-ddp[-<engine>]-xctest.zip")
    ap.add_argument("--archive-builder", default="prebuilt", choices=sorted(ARCHIVE_BUILDERS),
                    help="how XCTest archives are prepared (default: %(default)s)")
    ap.add_argument("--model-dir", action="append", default=[], metavar="ID=DIR",
                    help="local directory holding a model id's files (repeatable)")
    ap.add_argument("--models-root", type=pathlib.Path, default=None,
                    help="optional HFDownloader-style root (<root>/<runtime>/<hfRepoId, / as __>/)")
    ap.add_argument("--extra-catalog", default=os.environ.get("BENCH_EXTRA_CATALOG") or None,
                    help="extra catalog JSON pushed to Documents/models/extra-catalog.json")
    ap.add_argument("--no-keep-raw", action="store_true",
                    help="remove <campaign>/ddp-raw/ raw pull dirs after records are written")
    ap.add_argument("--dry-run", action="store_true", help="plan every session, submit nothing")
    args = ap.parse_args(argv)

    for c in args.cells:
        if not c.is_file():
            ap.error(f"{c}: no such cells file")
    if not args.campaign:
        args.campaign = os.environ.get("CAMPAIGN") or f"{datetime.date.today().isoformat()}-ddp-ios"

    try:
        model_dirs = parse_model_dirs(args.model_dir)
        planned = plan_cells(args.cells, args.extra_catalog, args.engines, model_dirs, args.models_root,
                             dry_run=args.dry_run)
    except (ValueError, run_ddp_ios_lm.InputError) as exc:
        print(f"run_ddp_ios_matrix: {exc}", file=sys.stderr)
        return 2

    if not planned:
        print("run_ddp_ios_matrix: no matching ios rows to run", file=sys.stderr)
        return 0

    needed_engines = sorted({c.engine for c in planned})
    rc = ARCHIVE_BUILDERS[args.archive_builder](needed_engines, args.archives_dir, args)
    if rc:
        return rc

    campaign_dir = raw_root() / args.campaign
    print(f"== [iOS DDP {args.device}] {len(planned)} sessions -> {campaign_dir}", flush=True)
    failures = []
    for idx, cell in enumerate(planned, 1):
        if idx > 1 and args.cooldown > 0 and not args.dry_run:
            time.sleep(args.cooldown)
        arch = archive_path(args.archives_dir, cell.engine)
        s_argv = session_argv(cell, arch, args)
        print(f"-- [{idx}/{len(planned)}] {cell.name} {cell.model_id} {cell.task}", flush=True)
        if args.dry_run and not arch.is_file():
            print("   dry-run argv: run_ddp_ios_lm.py " + " ".join(s_argv), flush=True)
            continue
        saved_env = os.environ.get("BENCH_RAW_ROOT")
        os.environ["BENCH_RAW_ROOT"] = str(campaign_dir.parent)
        try:
            rc = run_ddp_ios_lm.main(s_argv)
        finally:
            if saved_env is None:
                os.environ.pop("BENCH_RAW_ROOT", None)
            else:
                os.environ["BENCH_RAW_ROOT"] = saved_env
        if rc != 0:
            failures.append(f"{cell.name} {cell.model_id} {cell.task} (exit {rc})")

    if args.no_keep_raw and not args.dry_run and (campaign_dir / "ddp-raw").is_dir():
        shutil.rmtree(campaign_dir / "ddp-raw", ignore_errors=True)

    if failures:
        print("run_ddp_ios_matrix: failed sessions: " + "; ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
