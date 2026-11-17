# Runs behind the desktop-start sentences of `windows/README.md` (Setup)

Engine logs of one measurement on the PC the dashboard's Windows column runs on, 09:26 to 09:31 JST on 2026-11-16. A
PowerShell script in a console window on the PC's desktop started every run. The benchmark job and the executor took no
part, and the runs have no records in this repo, so they pool into no number.

`logs/runs.tsv` has one line per run, written by the script, and `logs/console.log` is the script's own log.
`logs/w00.log` and each `logs/rNN.log` are the tool's output for one run: its settings echo and its rates. Each
`logs/jcmd_rNN.txt` is the command line of a J run. The script is not in this repo. The user name in paths is scrubbed.

Tool: `litert_lm_advanced_main_windows.exe` in `<root>\engines\litert`, where the LiteRT-LM rows' build is. Model:
`gemma-4-E2B-it.litertlm`. Flags on every run, the ones the job passes for Gemma 4 E2B's `litert-lm-cpu` row:

```
--backend=cpu --model_path=gemma-4-E2B-it.litertlm --input_prompt_file=short-chat.txt --max_num_tokens=2048
--max_output_tokens=128 --num_iterations=2 --async=false --benchmark --benchmark_prefill_tokens=0
--benchmark_decode_tokens=0 --use_session=false
```

Three ways of starting the engine, the `arm` column of `runs.tsv`:

| arm | how the engine was started | set on the engine process |
|---|---|---|
| D | the script started `cmd.exe /d /s /c` with no new window, so the engine ran under the console in the foreground | nothing |
| H | as D | High QoS with the job's value (`ControlMask` 1, `StateMask` 0), set 0.07 to 0.082 s after the engine started and read back: `qos` reads `ok-read-1/0` |
| J | the script called WMI, `Win32_Process.Create`, which started a PowerShell, which started `cmd.exe` hidden. A job's engine is started through the same chain (the executor's WMI call, the job's PowerShell, `cmd.exe`) | nothing |

The J runs differ from a job's in where the WMI call came from. Here it came from the console in the desktop's session:
the launcher and the engine are in session 1, as `info` in `runs.tsv` shows. For a job it comes from an SSH session,
session 0. So the J runs do not show how an engine started from session 0 runs.

One run per launch, 5 s apart. The first, `w00`, a D run, is a warm-up that is not counted: it wrote the XNNPACK cache
the others read. Then came `r01` to `r18` in the order D H J, H J D, J D H, D H J, H J D, J D H. Every run exited 0,
with the engine in session 1 at priority Normal.

Before and after each run the script read the foreground window and the power settings: `fg_before`, `fg_after`,
`power_before` and `power_after` in `runs.tsv`. Every read of the window gave the script's own console. Every read of
the power settings gave MSI Center's User Scenario Mode 2 (Balanced), the power mode overlay all zeros, the Windows
power plan Balanced, and AC power. Before its first step the script waited until the CPU read quiet, `GATE` in
`console.log`. A helper process the script started held Windows' display-required and system-required flags, set with
`SetThreadExecutionState`, through every run, `FLAG` in `console.log`.

`cold_decode` and `cold_prefill` are the rates of a run's first conversation and `warm_decode` and `warm_prefill` those
of its second, in tokens per second, as the run's log prints them in its first and second `Decode Speed` and `Prefill
Speed` lines. Each conversation has 20 prompt tokens and 128 output tokens. The third pair of speed lines in each log is
the tool's own figure over both conversations and is not used. Medians of the six counted runs per arm, with the lowest
and highest:

| arm | cold decode | warm decode | warm prefill | cold prefill |
|---|---|---|---|---|
| D | 29.59 (29.25 to 29.66) | 30.01 (29.68 to 30.16) | 70.935 (68.32 to 71.95) | 55.44 (54.54 to 55.91) |
| H | 29.54 (29.27 to 29.60) | 29.825 (29.75 to 29.99) | 71.45 (70.19 to 71.81) | 55.17 (54.89 to 56.00) |
| J | 29.135 (29.10 to 29.19) | 29.645 (29.51 to 29.86) | 71.025 (70.37 to 72.03) | 53.945 (53.65 to 54.15) |

| ratio of medians | cold decode | warm decode | warm prefill | cold prefill |
|---|---|---|---|---|
| D / H | 1.002 | 1.006 | 0.993 | 1.005 |
| J / H | 0.986 | 0.994 | 0.994 | 0.978 |
| D / J | 1.016 | 1.012 | 0.999 | 1.028 |

`zsh med.sh logs/runs.tsv` prints both tables' numbers.

What this does not show. It is one measurement with six runs per arm, and its numbers compare only with each other.
Whether the desktop was locked, and whether the PC was in Modern Standby, was not recorded. The sha256 of the tool and
of the model file were not read during it.

D and H are engines a script started under a foreground console, not an engine a person starts by hand. With D and J
both at the level of H, the runs do not show what setting High QoS changes. The `PROBE` lines of `console.log` belong
to three short timing loops the script ran before `w00`. Their files are not here.
