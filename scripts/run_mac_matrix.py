#!/usr/bin/env python3
"""Runs the mac rows of cells files through a pluggable executor.

The Mac counterpart of android/ddp/run_ddp.py's executor registry. The job description is
the cells file (matrices/README.md grammar; only `mac` rows are run) and the records are
scripts/bench_matrix_mac.sh's own: results/raw/<campaign>/<slug>.jsonl plus
session_provenance.txt and SKIPPED.txt. What changes between executors is only where that
runner runs:

  local   (default) scripts/bench_matrix_mac.sh run <cells...> on this Mac, as before.

Another harness can register its own executor, e.g. one that ships the repo to a lab Mac,
runs the same runner there and brings results/raw/<campaign>/ back:

  import run_mac_matrix
  run_mac_matrix.register_executor("lab", fn)   # fn(cells, campaign, campaign_dir, args) -> int
  sys.exit(run_mac_matrix.main(["--executor", "lab", "matrices/x.cells"]))

An executor must leave the campaign's records in `campaign_dir` (the same files the local
runner writes) and return the runner's exit status. The runner's environment knobs (RUNS,
BASE_COOLDOWN, ROUNDS, GATE_RETRY, ET_MODEL_DIR, YS_BIN, ...) are the executor's to pass on.

  scripts/run_mac_matrix.py <cells> --campaign <date>-<name>-mac
  scripts/run_mac_matrix.py <cells> --dry-run

A cells file may live anywhere (another harness's own matrices included): it is read from the
path given, relative to the current directory.
"""

import argparse
import datetime
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNNER = REPO / "scripts" / "bench_matrix_mac.sh"


def raw_root() -> Path:
    """Where campaigns live: BENCH_RAW_ROOT (as android/ddp/run_ddp.py reads it), else results/raw."""
    return Path(os.environ.get("BENCH_RAW_ROOT") or REPO / "results" / "raw")


def mac_rows(cells_path: Path) -> list:
    """The cells file's mac rows (comments and blank lines dropped)."""
    rows = []
    for line in cells_path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line and line.split()[0] == "mac":
            rows.append(line)
    return rows


def run_local(cells: list, campaign: str, campaign_dir: Path, args) -> int:
    """bench_matrix_mac.sh on this Mac, once per cells file (its `run` takes one), in order, into
    the one campaign. It writes <repo>/results/raw/<campaign>/ itself."""
    if campaign_dir != REPO / "results" / "raw" / campaign:
        print(f"run_mac_matrix: the local runner writes {REPO / 'results' / 'raw' / campaign}, "
              f"not BENCH_RAW_ROOT ({campaign_dir})", file=sys.stderr)
        return 2
    env = dict(os.environ, CAMPAIGN=campaign)
    for cells_file in cells:
        cmd = ["bash", str(RUNNER), "run", str(cells_file)] + (["--dry-run"] if args.dry_run else [])
        rc = subprocess.run(cmd, env=env, check=False).returncode
        if rc:
            return rc
    return 0


EXECUTORS = {"local": run_local}


def register_executor(name, fn):
    """Register an executor fn(cells, campaign, campaign_dir, args) -> exit status."""
    EXECUTORS[name] = fn


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("cells", nargs="+", type=Path, help="cells files; their mac rows run")
    ap.add_argument("--campaign", help="campaign dir name (default: env CAMPAIGN, else <date>-mac-matrix)")
    ap.add_argument("--executor", default="local", choices=sorted(EXECUTORS),
                    help="where the runner runs (default: %(default)s)")
    ap.add_argument("--dry-run", action="store_true", help="the runner's --dry-run: print, write nothing")
    args = ap.parse_args(argv)
    for c in args.cells:
        if not c.is_file():
            ap.error(f"{c}: no such cells file")
    if not any(mac_rows(c) for c in args.cells):
        ap.error("no mac rows in " + ", ".join(map(str, args.cells)))
    campaign = args.campaign or os.environ.get("CAMPAIGN") or f"{datetime.date.today().isoformat()}-mac-matrix"
    campaign_dir = raw_root() / campaign
    return EXECUTORS[args.executor](args.cells, campaign, campaign_dir, args)


if __name__ == "__main__":
    sys.exit(main())
