#!/usr/bin/env python3
"""litert_warm2.py <litert args...>: the litert CLI (litert-cli-nightly 0.3.0.dev20261006) with one constant changed.

The CLI's device-side run script for a .litertlm bundle on --ddp runs LiteRT-LM's benchmark binary twice: the first
(warm-up) process gets `--num_iterations=1 --metric_proto_file_path=` appended (ddp._LM_WARMUP_ARGS), the measured
process the arguments as given. For the warm-shape round the first process has to run two cycles in one process
(cold start, cycle 1 writes the caches, cycle 2 is the measurement that matches a same-process warm-up pass), so this
wrapper sets the appended arguments to `--num_iterations=2 --metric_proto_file_path=` before the CLI builds the run
script. Nothing else changes: same binary (bucket latest), same bundle, same measured-process arguments, same
provenance.txt. The first process still writes no metrics file; its two BenchmarkInfo blocks are read from the logcat.
"""
import sys
from litert_cli.commands.benchmark import ddp
assert ddp._LM_WARMUP_ARGS == "--num_iterations=1 --metric_proto_file_path=", ddp._LM_WARMUP_ARGS
ddp._LM_WARMUP_ARGS = "--num_iterations=2 --metric_proto_file_path="
from litert_cli.litert import cli
sys.argv[0] = "litert"
sys.exit(cli())
