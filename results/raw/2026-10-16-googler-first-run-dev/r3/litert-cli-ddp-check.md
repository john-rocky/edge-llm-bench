# LiteRT-CLI main: does `litert benchmark --ddp` push a prompt for a `.litertlm` bundle? (round 3, 2026-10-16)

Read for the fifth Watch-for bullet of litert-samples `skills/benchmark-on-ddp/SKILL.md` ("outside this CLI's DDP
target (fixed benchmark flags, no prompt push)"). Source: `git -C ~/Downloads/litert-upstream/LiteRT-CLI-tflite-cache-wt
fetch origin` at 16:40 JST (main 9a14848 -> 59d612e, "Merge pull request #102 …", 2026-10-12), then
`git show origin/main:litert_cli/commands/benchmark/ddp.py` (1378 lines; last change to the file on main: 7dd77d9,
2026-09-29). Answer: **still true** — the bullet stands as written.

| what | where (origin/main 59d612e) | reads |
|---|---|---|
| the bundle's job arguments | `litert_cli/commands/benchmark/ddp.py:526-553` `_build_lm_benchmark_args` | a fixed list: `--backend`, `--model_path`, `--benchmark=true`, `--benchmark_prefill_tokens`, `--benchmark_decode_tokens`, `--max_num_tokens`, `--num_iterations`, `--report_peak_memory_footprint=true`, `--metric_proto_file_path`; no prompt flag |
| what a bundle's job pushes | `ddp.py:556-587` `_lm_pushes`, `ddp.py:625` in `_build_session_request` | the bundle, then `litert_lm_advanced_main` and every `.so` of the binary directory (`gs://litert/binaries/<version>/android_arm64/litert_lm/`); nothing else |
| the bundle branch of `run_ddp` | `ddp.py:1192-1223` | uploads the run script, builds the args above, `extra_pushes=lm_pushes`; no prompt option reaches it |
| the run script | `ddp.py:196-232` `_LM_RUN_SCRIPT` | two processes of the binary (a warm-up with `--num_iterations=1`, then the measured one, `ddp.py:234`); no prompt file |
| the word `prompt` | every file of `litert_cli/commands/benchmark/` on main (`__init__.py`, `android.py`, `cli.py`, `ddp.py`, `desktop.py`, `gcp.py`, `model_caches.py` and the 3 tests) | 0 hits in each |

The edge-llm-bench side of the same sentence: `docs/ddp-integration.md:456` (written against litert-cli 0.2.1) says
the same; this check moves the reading to the CLI's main of 2026-10-12.
