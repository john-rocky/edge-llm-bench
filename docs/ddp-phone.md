# Android on a Developer Device Platform phone

## Quickstart

- Needs: no phone and no adb; gcloud signed in, a Cloud project with the Device Run API enabled and a bucket in it you can read and write, and python3 >= 3.10 with `huggingface_hub` (step 1 of the DDP section below).
- Clone: `git clone https://github.com/john-rocky/edge-llm-bench && cd edge-llm-bench`
- Put the pinned LiteRT-LM Android files in place (the lines of step 2 below; 7 s with the clone on a fresh Ubuntu 24.04, 2026-10-16):
  ```bash
  TAG=$(python3 -c 'import json; print(json.load(open("android/engine-pins.json"))["android_pins"]["litert-lm"])')
  mkdir -p android/bin
  curl -fL https://github.com/john-rocky/edge-llm-bench/releases/download/android-litert-lm-$TAG/litert-lm-$TAG-android-arm64.tar.gz \
    | tar xz -C android/bin && mv android/bin/litert-lm-$TAG-android-arm64 android/bin/$TAG
  ```
- Check: `./bench doctor --platform ddp` (gcloud and its sign-in, `huggingface_hub`, the 9 engine files) and `./android/ddp/selftest.py` (no network, nothing billed; 17 s).
- Run, billed to your project (8 jobs in one session, 37 min on 2026-10-15): `./bench matrix matrices/dashboard-text-v1.cells --ddp akita-35 --project <your project> --bucket gs://<your bucket>`
- A first check of one job and two runs: the same command on `matrices/ddp-first-run.cells` (7 min from the command to the records on 2026-10-16).
- Read: the records in `results/raw/<date>-ddp-akita-35-android/app-path-android/*.json`; in `results/summary/device-runs.csv` their device is `Pixel 8a (DDP akita-35)`.
- More: "Run the Android cells on a Developer Device Platform phone" below (the dry run, the cost, what this route does not carry).

## Step by step (fresh Linux or macOS host, no adb)

The Android LiteRT-LM cells also run on a lab phone of Google's Developer
Device Platform (DDP): the host uploads the pinned engine files, the model and
the prompt to a Cloud Storage bucket, Device Run executes the same engine
command on a lab unit, and the host pulls the output and writes the same
schema-v1 records. No phone is attached, so the host needs no adb and no
Android SDK.

**1. What the machine needs.**

- gcloud, signed in, with your project set:
  `gcloud auth login && gcloud config set project <your project>`. The driver
  uses `gcloud auth print-access-token` and `gcloud storage`. A run takes its
  project from `--project`, then `$BENCH_DDP_PROJECT`, then gcloud's active project.
- A Cloud project where the Device Run API is enabled
  (`gcloud services enable devicerun.googleapis.com --project <your project>`),
  your account allowed to create sessions there, and a bucket in it you can
  read and write (`gs://<your project>-devicerun` is the name
  `gcloud beta device-run` uses, and the run's default without `--bucket` or
  `$BENCH_DDP_BUCKET`). A dry run calls no gcloud: without the flag or the
  variable its plan shows `$PROJECT`.
- python3 >= 3.10 as `python3` on the PATH (`bench` starts with
  `#!/usr/bin/env python3`) and `huggingface_hub`, for instance in a venv:
  `python3 -m venv ~/elb-venv && . ~/elb-venv/bin/activate && pip install huggingface_hub`
  (a stock Debian / Ubuntu needs the `python3-venv` package first: `sudo apt install python3-venv`).
  A gated model repo needs your Hugging Face token on the host.
- The pinned LiteRT-LM Android binaries: the files (`litert_lm_main`,
  `litert_lm_advanced_main` and the tag's `.so` files: 7 in all at v0.19.0) of the tag that
  `android/engine-pins.json` `android_pins` `litert-lm` names, in
  `android/bin/<tag>/` (or `$BENCH_ANDROID_BIN_DIR/<tag>/`). They come from
  this repo's GitHub release `android-litert-lm-<tag>`; the release for the
  pinned tag is published with the pin bump. Step 2 puts them in place.

**2. Clone, and put the pinned binaries in place.**

```bash
git clone https://github.com/john-rocky/edge-llm-bench && cd edge-llm-bench
TAG=$(python3 -c 'import json; print(json.load(open("android/engine-pins.json"))["android_pins"]["litert-lm"])')
mkdir -p android/bin
curl -fL https://github.com/john-rocky/edge-llm-bench/releases/download/android-litert-lm-$TAG/litert-lm-$TAG-android-arm64.tar.gz \
  | tar xz -C android/bin && mv android/bin/litert-lm-$TAG-android-arm64 android/bin/$TAG
```

Without the release, `LITERTLM_TAG=$TAG ANDROID_NDK_HOME=<NDK r28b+> android/scripts/build_litert_lm_main.sh`
builds the tag from source (bazelisk; it writes that build's sha256 into
`android/engine-pins.json`, so the driver's check passes with it and the
records carry its sha256 in `engineArtifact`). Before anything is uploaded,
the driver checks each of the files against the sha256 that
`android/engine-pins.json` pins for the tag. LiteRT-LM main, a pull request or
a build made elsewhere runs with `--engine-build <label>` instead:
[`android/README.md`](../android/README.md), "Build from head or a PR".

Then check the checkout with no network and nothing billed: the selftest runs
the plan, the job wrapper, the billed path and the records against a fake
gcloud, a temp dir as the bucket and a fake Device Run server on localhost, and
checks the files against `android/engine-pins.json`.

```bash
./android/ddp/selftest.py      # last line: ddp selftest OK (<N> checks); exit 0
```

**3. Dry run** (no gcloud call, no network, nothing billed): the jobs, the
sessions, the pushes with their sizes and sha256, the timeouts and an
estimate of the device-minutes. It already checks the 9 engine files.

```bash
./bench matrix matrices/dashboard-text-v1.cells --ddp akita-35 --dry-run \
    --project <your project> --bucket gs://<your bucket>
```

`--ddp` takes a DDP catalog id from `android/ddp/devices.json` (`akita-35` =
Pixel 8a, `m1q-36` = Galaxy S26, …). On `akita-35` this cells file makes 8 jobs
in one session: Qwen3-1.7B and Gemma 4 E2B, short chat and the 1K text task,
CPU and GPU, 3 runs each. A model not yet in your Hugging Face cache shows as
`"uncached"`; the billed run downloads it.

**4. The run** (billed to your project):

```bash
./bench matrix matrices/dashboard-text-v1.cells --ddp akita-35 \
    --project <your project> --bucket gs://<your bucket>
```

It downloads the models into the local Hugging Face cache, uploads the inputs
the bucket does not hold yet (content-addressed under
`automation/inputs/edge-llm-bench/`), creates one Device Run session per 8
jobs, polls it every 30 s until it finishes, pulls the session's output from
the bucket, replaces the lab network's identifiers in the pulled logcats, and
writes the records (one per run; two for a 1K run, its cold and its warm
iteration). On 2026-10-15 the 8-job session took 37 min on
`akita-35`; its 8 jobs ran side by side on 8 units.

**5. Where the rows land.** `results/raw/<date>-ddp-<id>-android/app-path-android/`
(the records, `*.json`, beside their raw logs) and `results/raw/<date>-ddp-<id>-android/ddp/`
(request, operation, session report, the pulled files, `scrub.json`).
`bench` then rebuilds `results/summary/device-runs.csv`, where these rows carry
the device `<model> (DDP <id>)`, e.g. `Pixel 8a (DDP akita-35)`; `./bench dashboard`
renders them into the local `DASHBOARD.md` as a column of their own.

**6. What this route does not carry.** Mac and iPhone cells; the Android
llama.cpp rows (their build is not wired for DDP; they are skipped with the
reason); session anchors, so a DDP row gets no anchor-normalized comparison
across sessions, and it is never pooled with an attached phone's rows (its
device name differs); control of which unit runs a job, its temperature and
its CPU clock caps (each record names its unit by build fingerprint and serial,
and carries its thermal and cap readings and flags).

**7. Cost.** Device Run bills device time to the project you pass. The dry
run prints an estimate; the session report (`ddp/session-<n>.json`) gives the
real start and end of every job and execution; the price is in your project's
billing.

**8. More.** What is pushed, run and recorded, and how a DDP row differs from
an attached phone's: [`docs/ddp-integration.md`](ddp-integration.md),
"Route C as `bench matrix --ddp`". The step-by-step runbook (resume, checking
the outputs, committing): [`docs/OPERATIONS.md`](OPERATIONS.md), "Run
cells on DDP". The iPhone app's LiteRT-LM rows run on a DDP iPhone through
XCTest: [`ios/ddp/README.md`](../ios/ddp/README.md).

**One command: the autopilot.** `./bench autopilot` runs steps 3 to 5 and what
follows them on the bench host every night: the checks and the plan, the billed
run, the check of the records, one local commit of the campaign dir and
`results/summary` when every rule passes (`REVIEW.md` in the dir when one does
not), the local `DASHBOARD.md`, the red points of the dashboard page's regression
rule and the pending retake and bisect requests; its last screen says what to
do next.

```bash
./bench autopilot --ddp akita-35 --dry-run --project <your project> --bucket gs://<your bucket>
```

The dry run calls no network and bills nothing; without `--dry-run` it is the
billed run, `--no-commit` stops after the check, `--cells` replaces
`matrices/ddp-first-run.cells` (one job, two runs; `m1q-36` takes its weekly
file). The commit is made with git's `user.name` and `user.email`. Left out on
your host: the private dashboard page, any push (the commit stays local), retakes
(they run on the bench host's attached phones) and the bisect itself
(`scripts/engine_bisect.py` comes after PR #4). Design:
[`docs/dashboard-autopilot-v1.md`](dashboard-autopilot-v1.md), section 10.
