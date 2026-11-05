# Runs behind `windows/NOTES-v0.19.0.md`

Engine logs of one-off runs on the PC of `2026-11-05-windows`, on the evening of 2026-11-05 (JST). A hand-written script
started them, not the executor, so they are not schema records and pool into no number. Each log holds the tool's settings
echo and its rates; the engine's INFO lines carry the epoch. The user name in paths is scrubbed.

Tool: `litert_lm_advanced_main_windows.exe`, `v0.19.0` in `windows/engine-pins.json`. Flags on every tool run:

```
--input_prompt_file=short-chat.txt --max_output_tokens=128 --num_iterations=2 --async=false --benchmark
--benchmark_prefill_tokens=0 --benchmark_decode_tokens=0 --use_session=false
```

CPU runs add `--backend=cpu --model_path=gemma-4-E2B-it.litertlm --max_num_tokens=2048`.

| logs | started | what differs |
|---|---|---|
| `cpu-default-run*` | 20:32 | nothing: the tool's default of 4 threads |
| `cpu-t8-run*`, `cpu-t16-run*` | 20:34 | `--num_cpu_threads=N` |
| `cpu-t6-run*`, `cpu-t12-run*` | 20:42 | `--num_cpu_threads=N` |
| `cpu-t2-run*`, `cpu-t3-run*`, `cpu-t1-run*` | 21:25 | `--num_cpu_threads=N` |
| `aff-default-t4-run*` | 21:55 | `--num_cpu_threads=4` |
| `aff-p-t2-run*`, `aff-p-t3-run*`, `aff-p-t4-run*` | 21:55 | `--num_cpu_threads=N` under `cmd /c start "" /b /wait /affinity F` |
| `igpu-flat-run1` | 20:55 | `--backend=gpu --model_path=gemma-4-E2B-it.litertlm --max_num_tokens=2048 --preferred_device_substr=Intel` |
| `igpu-pref-run1` | 22:18 | `--backend=gpu`, same file, under the registry value `GpuPreference=1;` in `HKCU:\Software\Microsoft\DirectX\UserGpuPreferences`, named the tool's path |
| `npu-jit-universal-run1` | 20:54 | `--backend=npu --model_path=gemma-4-E2B-it.litertlm --litert_dispatch_lib_dir=<engine dir>` |
| `wheel-gpu-universal-run*` | 20:26 | `wheel_bench.py gemma-4-E2B-it.litertlm gpu`, Google's PyPI wheel `litert-lm-api` 0.19.0, with no output cap: 573 tokens |
| `wheel-npu-run*` | 20:41 | `wheel_bench.py gemma-4-E2B-it_intel_PTL.litertlm npu --ctx 0 --dispatch <dir>`, no output cap: 463 tokens |

`cpu-topology.txt` is `GetSystemCpuSetInformation` on this CPU: logical processor, core, last-level cache, efficiency class.
