#!/usr/bin/env python3
"""Run the installed wheel's Gemma 4 exporter with the variant config read from a source tree.

usage: run_gemma4_export.py <tree>/examples/models/gemma4/config <export_gemma4.py args...>

ExecuTorch 1.5.1's wheel ships executorch/examples/models/gemma4/ without its
config/ directory, so Gemma4Config.from_config("e2b"|"e4b") cannot find
config/<variant>_config.json next to the installed module. This launcher points
from_config at the pinned source tree's copy of that directory, then runs
executorch.examples.models.gemma4.export_gemma4 as __main__ with the remaining
arguments. Nothing else changes: the exporter, the model code and the
quantization are the wheel's (export_gemma4.py checks they are byte-identical
to the tree).
"""
from pathlib import Path
import runpy
import sys


def main():
    if len(sys.argv) < 2 or not Path(sys.argv[1], "e2b_config.json").is_file():
        sys.exit(__doc__)
    config_dir = Path(sys.argv[1]).resolve()
    sys.argv = ["export_gemma4.py"] + sys.argv[2:]

    from executorch.examples.models.gemma4.text_decoder import gemma4_config

    def from_config(cls, variant="e2b"):
        return cls.from_json(str(config_dir / f"{variant}_config.json"))

    gemma4_config.Gemma4Config.from_config = classmethod(from_config)
    print(f"run_gemma4_export: Gemma4Config.from_config reads {config_dir}/<variant>_config.json", flush=True)
    runpy.run_module("executorch.examples.models.gemma4.export_gemma4", run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    main()
