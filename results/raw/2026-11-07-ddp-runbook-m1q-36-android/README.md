# DDP runbook run, `m1q-36`, 2026-11-07

The record behind `docs/ddp-integration.md`, "Measure a model on a lab phone with gcloud and LiteRT CLI". It proves a route and holds no `result.v1` record, so the summary layer ignores it. The same run on `akita-35`: `results/raw/2026-11-07-ddp-runbook-akita-35-android/`.

| Session | Command | Job here | Result |
|---|---|---|---|
| `session-41f7fb49` | `litert benchmark "$MODEL" --ddp --cpu --devices "m1q-36, akita-35" --gcp-project "$PROJECT"` | `cpu-m1q-36` | PASSED |
| `session-2c5772b3` | `litert benchmark "$MODEL" --ddp --gpu --devices "m1q-36, akita-35" --gcp-project "$PROJECT"` | `gpu-m1q-36` | PASSED |
| `session-92f7197a-2475-4bcb-aa44-56a9d6395025` | `gcloud beta device-run sessions submit android-executable ... --executable ./reply_check.sh` | `job-000` | PASSED |

`MODEL` = `litert-community/Qwen3-0.6B` `Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm`, Hub commit `bd47201734`, sha256 `bf1aba9ce8d963124407353c6aa4cbf72eba78db21ae133de983eac672ce83e0`. Tools: `litert-cli-nightly` 0.3.0.dev20261106, Google Cloud SDK 587.0.0 (beta 2026.09.25). The phone: SM-S942U1, Android 16, `BP4A.251205.006`.

- `cli-output-cpu.txt`, `cli-output-gpu.txt`: the command's output with this phone's job block only. `START` / `END` / `EXIT` are the wrapper's lines (JST).
- `session-cpu.json`, `session-gpu.json`: the session resource from the API (request and report; both jobs).
- `cpu-m1q-36/`, `gpu-m1q-36/`: `provenance.txt` and `metrics.pb` as the CLI pulled them.
- `reply-check/`: the script, gcloud's output, the session resource, and `replies.txt`, each process's backend line and reply from the execution's logcat.

Left out: the executions' `logcat.txt`, the unit's whole log. The CPU rows carry the mark `lab-capped` in the doc: the CLI reads no CPU clock ceilings.

Replaced in these files: the Cloud project id (`$PROJECT`), the bucket (`$BUCKET`), the account, the local paths, the lab network's identifiers (`android/ddp/scrub.py`). Otherwise verbatim.
