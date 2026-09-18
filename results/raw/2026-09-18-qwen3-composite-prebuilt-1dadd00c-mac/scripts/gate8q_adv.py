#!/usr/bin/env python3
"""8-question gate through litert_lm_advanced_main (LiteRT-LM v0.17.0 tag build) on the Metal accelerator path.
Same questions/regexes as qwen3_gpuopt_work/gate8q_cli.py; one process per question, /no_think appended,
max_num_tokens 4096, --disable_cache=true. RUN dir = binary + the three Metal-path dylibs (DYLD_LIBRARY_PATH).
    python3 gate8q_adv.py --run <run-dir> --label L --json out.json model.litertlm
"""
import argparse, json, os, re, subprocess, sys, time
sys.path.insert(0, os.path.expanduser("~/code/litertlm-convert/scripts/cardbench"))
from gate_backend import looks_degenerate  # noqa: E402
SUFFIX = " Answer briefly."
QUESTIONS = [
    ("17+25=42", "What is 17 + 25?", r"\b42\b"),
    ("capital=Tokyo", "What is the capital of Japan?", r"tokyo"),
    ("opp(hot)=cold", 'What is the opposite of "hot"?', r"\bcold\b"),
    ("days/week=7", "How many days are in a week?", r"\bseven\b|\b7\b"),
    ("thanks(fr)=merci", 'How do you say "thank you" in French?', r"merci"),
    ("8*7=56", "What is 8 times 7?", r"\b56\b"),
    ("0.9>0.11", "Which is larger: 0.9 or 0.11?", r"0\.9"),
    ("rhyme=blue", 'Complete the rhyme: "Roses are red, violets are ___"', r"\bblue\b"),
]
def ask(run, model, question):
  cmd = [os.path.join(run, "litert_lm_advanced_main"), "--backend=gpu", "--model_path=" + model,
         "--input_prompt=" + question + SUFFIX + " /no_think", "--max_num_tokens=4096", "--disable_cache=true"]
  env = dict(os.environ); env["DYLD_LIBRARY_PATH"] = run
  t0 = time.time()
  p = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=900, env=env, cwd=run)
  out = p.stdout
  if "advanced_settings:" in out:
    out = out.split("advanced_settings:", 1)[1].split("\n", 1)[1]
  if "BenchmarkInfo:" in out:
    out = out.split("BenchmarkInfo:", 1)[0]
  return out.strip(), p.stderr, time.time() - t0, p.returncode
def main():
  ap = argparse.ArgumentParser(); ap.add_argument("model"); ap.add_argument("--run", required=True)
  ap.add_argument("--label", default=None); ap.add_argument("--json", default=None); a = ap.parse_args()
  label = a.label or os.path.basename(os.path.dirname(os.path.abspath(a.model)))
  rows, correct = [], 0
  print(f"== {label}  {a.model}  run={a.run}")
  for key, q, rx in QUESTIONS:
    out, err, dt, rc = ask(a.run, a.model, q)
    text = out.strip(); deg = looks_degenerate(text); sm = err.count("Shape mismatch"); verr = err.count("Validation error")
    ok = bool(re.search(rx, text, re.IGNORECASE)) and not deg and rc == 0
    correct += ok
    print(f"  {'PASS' if ok else 'FAIL'}  {key:<18} rc={rc} sm={sm} verr={verr} {dt:4.1f}s  {text.replace(chr(10), ' ')[:90]!r}")
    rows.append({"key": key, "question": q, "pass": ok, "rc": rc, "shape_mismatch": sm, "validation_errors": verr,
                 "degenerate": deg, "seconds": round(dt, 2), "answer": text[:600]})
  print(f"  => {correct}/8 correct")
  if a.json:
    json.dump({"label": label, "model": a.model, "run": a.run, "correct": correct, "rows": rows},
              open(a.json, "w"), indent=1, ensure_ascii=False)
  return 0 if correct >= 6 else 1
if __name__ == "__main__":
  sys.exit(main())
