# ExecuTorch runner output fixtures (android/bench/selftest.py)

Verbatim output of ExecuTorch v1.5.1's runners, kept for the parser and runner checks of the
executorch arm (docs/executorch-arm-v1.md). Not measurements: smoke launches.

| file | what |
|---|---|
| `s26-short-chat.{stdout,stderr,sampler}.txt` | Galaxy S26, 2026-10-07 22:28, `llama_main` (android/bin/executorch-v1.5.1, XNNPACK) on the own Qwen3-0.6B export, short-chat, `--max_new_tokens 128`: stdout (prompt echo, text, PyTorchObserver line), stderr (ET_LOG), the on-device RSS / cpufreq sampler |
| `s26-long-context-1024-gen256.{stdout,stderr,sampler}.txt` | the same phone and binary, 22:30, the 1K text task, `--max_new_tokens 256` (a CPU cap held during it: not a valid run under cpu-cap-rule) |
| `short-chat.qwen3-chat.txt`, `long-context-1024-gen256.qwen3-chat.txt` | the prompts those launches read: `prompts/text/<task>.txt` rendered with the Qwen3-0.6B chat template (`scripts/executorch/make_prompts.py`, transformers 5.0.0rc1, Qwen/Qwen3-0.6B c1899de) |
| `mac-short-chat-cold-1.stdout.txt` | Mac Studio M4 Max, 2026-10-07 22:45, the stock Release `llama_main` (no ET_LOG), the same export and prompt, cold |
| `mac-gemma-4-E2B-it-short-chat.{stdout,stderr}.txt` | the same Mac, 2026-10-07 23:28, `gemma4_e2e_runner` (examples/models/gemma4) on the own Gemma 4 E2B export, `--prompt` = prompts/text/short-chat.txt, `--max_new_tokens 64`; stderr up to the end of the runner's report |
