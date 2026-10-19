#!/usr/bin/env python3
"""Run tools/omni-eval/score.py unchanged, with its normalizer import satisfied.

score.py imports `leaderboard.normalizer`; the vendored copy is the package
tools/omni-eval/leaderboard_normalizer (see its SOURCE.txt). This registers that
package under the name score.py asks for and runs score.py with the same arguments:

  python -I tools/asr-sherpa/run_score.py --manifest <set>/manifest-S4.jsonl --pred <tag>.jsonl [--details out.jsonl]
"""
import pathlib
import runpy
import sys

sys.dont_write_bytecode = True  # no __pycache__ inside tools/omni-eval
omni = pathlib.Path(__file__).resolve().parents[1] / "omni-eval"
sys.path.insert(0, str(omni))
import leaderboard_normalizer  # noqa: E402
from leaderboard_normalizer import normalizer  # noqa: E402

sys.modules["leaderboard"] = leaderboard_normalizer
sys.modules["leaderboard.normalizer"] = normalizer
sys.argv = [str(omni / "score.py")] + sys.argv[1:]
runpy.run_path(str(omni / "score.py"), run_name="__main__")
