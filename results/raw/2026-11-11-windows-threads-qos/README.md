# Runs behind item 4's table in `windows/NOTES-v0.19.0.md`

Engine logs of one sitting on the PC of `2026-11-05-windows`, 12:56 to 13:11 JST on 2026-11-11. The benchmark job
(`windows/run_job.ps1`) and the executor of commit f8716b58 started its runs from a plan written for this sitting, not
a cells file. Their records are not in this repo, so the sitting pools into no number. Each `rNN_run1.log` in `logs/`
holds the tool's settings echo and its rates; the engine's INFO lines carry the epoch. `logs/job.log` gives each run's
command, start, exit and the High QoS the job set on its engine process, and names the sitting
`2026-11-11-windows-l29-threads`, the name it ran under. Each `rNN_run1.json` is what the job wrote about that run, and
`host.json` what it wrote about the machine; `head.txt` and `mode.txt` are reads taken on the PC just before and just
after the sitting. The user name in paths is scrubbed.

Tool: `litert_lm_advanced_main_windows.exe`, `v0.19.0` in `windows/engine-pins.json`. Model: `gemma-4-E2B-it.litertlm`,
sha256 `181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c`, read on the machine before the sitting.
Flags on every run:

```
--backend=cpu --model_path=gemma-4-E2B-it.litertlm --input_prompt_file=short-chat.txt --max_num_tokens=2048
--max_output_tokens=128 --num_iterations=2 --async=false --benchmark --benchmark_prefill_tokens=0
--benchmark_decode_tokens=0 --use_session=false
```

The runs at 4 threads pass nothing more: 4 is the tool's default, and their logs echo `number_of_threads: 4`. The others
add `--num_cpu_threads=N`. One run per launch, in this order:

| logs | threads, in order | |
|---|---|---|
| `r00_run1` | 4 | warm-up, not counted: it wrote the XNNPACK cache the others read |
| `r01_run1` to `r05_run1` | 4, 2, 6, 1, 3 | first round |
| `r06_run1` to `r10_run1` | 2, 1, 4, 3, 6 | second round |
| `r11_run1` to `r15_run1` | 3, 4, 1, 6, 2 | third round |

The job set High QoS on every engine process, 0.07 to 0.177 s after it started, and read it back (`ControlMask` 1,
`StateMask` 0). Before and after the sitting, MSI Center's scenario read Balanced (User Scenario Mode 2, the power mode
overlay all zeros). The PC was on AC, on the Windows power plan Balanced, build 26200.9711. Every run exited 0, the job's
quiet gate read quiet before each, and no SSH connection opened during a run.

The rule for reading the first conversation's decode was set before the sitting. A count is compared with the default
only when the spread of each, (highest - lowest) / median over its three runs, is at most 5 %. It is faster than the
default when all its runs are above all the default's and its median is at least 3 % above the default's, slower in
the mirror case, and otherwise not separated from it.
