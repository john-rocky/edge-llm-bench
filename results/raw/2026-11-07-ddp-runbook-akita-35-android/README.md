# DDP runbook run, `akita-35`, 2026-11-07

The record behind `docs/ddp-integration.md`, "Measure a model on a lab phone with gcloud and LiteRT CLI". It proves a route and holds no `result.v1` record, so the summary layer ignores it. The same run on `m1q-36`: `results/raw/2026-11-07-ddp-runbook-m1q-36-android/`.

| Session | Command | Job here | Result |
|---|---|---|---|
| `session-41f7fb49` | `litert benchmark "$MODEL" --ddp --cpu --devices "m1q-36, akita-35" --gcp-project "$PROJECT"` | `cpu-akita-35` | PASSED |
| `session-2c5772b3` | `litert benchmark "$MODEL" --ddp --gpu --devices "m1q-36, akita-35" --gcp-project "$PROJECT"` | `gpu-akita-35`, thrown out | PASSED, decode spread 17.3 % (iterations 43.35, 42.94, 36.01, 43.49) |
| `session-b1839860` | `litert benchmark "$MODEL" --ddp --gpu --device akita-35 --gcp-project "$PROJECT"` | `gpu-akita-35`, the doc's row | PASSED, decode spread 1.6 % |
| `session-92f7197a-2475-4bcb-aa44-56a9d6395025` | `gcloud beta device-run sessions submit android-executable ... --executable ./reply_check.sh` | `job-001` | PASSED |
| `session-b1f64979` | `litert benchmark models/mobilenet/mobilenet_v2.tflite --ddp --cpu --device akita-35 --gcp-project "$PROJECT"` | `cpu-akita-35` | PASSED |

`MODEL` = `litert-community/Qwen3-0.6B` `Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm`, Hub commit `bd47201734`, sha256 `bf1aba9ce8d963124407353c6aa4cbf72eba78db21ae133de983eac672ce83e0`. MobileNet: `litert-community/MobileNet-v2` `mobilenet_v2.tflite`, Hub commit `48e55de476`, sha256 `34853c702f8da7298c6ae6c100b8a23df98b11d4fb41aa200e6fa45e96d52ea6`. Tools: `litert-cli-nightly` 0.3.0.dev20261106, Google Cloud SDK 587.0.0 (beta 2026.09.25). The phone: Pixel 8a, Android 15, `BP1A.250405.007.B1`.

- `cli-output-cpu.txt`, `cli-output-gpu.txt`: the command's output with this phone's job block only. `START` / `END` / `EXIT` are the wrapper's lines (JST).
- `session-cpu.json`, `session-gpu.json`: the session resource from the API (request and report).
- `cpu-akita-35/`, `gpu-akita-35/`: `provenance.txt` and `metrics.pb` as the CLI pulled them.
- `*.attempt1`: the GPU capture the spread rule threw out, kept as audit trail.
- `reply-check/`: the script, gcloud's output, the session resource, and `replies.txt`, each process's backend line and reply from the execution's logcat.
- `tflite-cpu/`: the `.tflite` session.
- `failures/`: `f1` a device id that does not exist (CLI, gcloud); `f2` the Device Run API off on the project (gcloud asking, gcloud with no answer, `--quiet`, CLI); `f3` and `f4` a bucket that does not exist (gcloud refuses, the CLI creates it).

Left out: the executions' `logcat.txt`, the unit's whole log. The CPU rows carry the mark `lab-capped` in the doc: the CLI reads no CPU clock ceilings.

Replaced in these files: the Cloud project id (`$PROJECT`, and `$PROJECT_NO_API` for the project with the API off), the project numbers, the bucket (`$BUCKET`), the account, the local paths, the lab network's identifiers (`android/ddp/scrub.py`). Otherwise verbatim.
