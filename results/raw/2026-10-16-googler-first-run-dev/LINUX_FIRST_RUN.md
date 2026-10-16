# Linux first run of the DDP route, 2026-10-16

The README section "Run the Android cells on a Developer Device Platform phone" was run as written on a
clean Linux machine (an Ubuntu 24.04 container), from a fresh clone of GitHub `main` up to the dry run, as a
normal user. No Device Run session was created, nothing was billed, and no phone was attached. Every number
below is copied from the log named on its row (`linux/` beside this file).

## Result

- README command lines that stopped on Linux: **0**, with the container-only packages of table 1 in place.
  Two lines stop on a stock Ubuntu 24.04 that lacks them (probes below): README.md:114 without the
  `python3-venv` package, and the `python3 -m pip install huggingface_hub` form outside a venv.
- `./android/ddp/selftest.py`: exit 0, `ddp selftest OK (73 checks)`, 17 s. CI's x86_64 Ubuntu runner prints
  the same count at this commit (GitHub Actions run 38745464632).
- Dry run of `matrices/dashboard-text-v1.cells` on `akita-35`: 8 jobs in 1 session, 22 rows skipped, the 3
  models `"uncached"`, exit 0. Dry run of `matrices/ddp-first-run.cells`: 1 job in 1 session, 0 rows skipped,
  the model `"uncached"`, exit 0. Neither called gcloud, and neither wrote a campaign directory.
- Changed after the run, then run again in the container as the changed files print them
  (`linux/10-verify-readme.log`): README.md step 2 now ends with the selftest (README.md:140-147; the section
  had no check before the dry run), and android/README.md "Engine acquisition" reads the pinned tag from
  `android/engine-pins.json` instead of naming v0.17.0 (android/README.md:26-29, the same lines as
  README.md:127-130).

## Environment

- Image `ubuntu:24.04` = `ubuntu@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55`,
  linux/arm64, created 2026-09-18T21:23:13Z; `/etc/os-release` in the container: `Ubuntu 24.04.5 LTS (Noble
  Numbat)` (`linux/01-admin.log`).
- An aarch64 container; an x86_64 host differs only in the package architecture (the engine binaries run on the
  phone, and the x86_64 CI runner passes the same 73 selftest checks).
- Container `--memory 6g` on Docker server 29.5.2 (client 28.3.2) in a colima 0.10.3 VM (lima 2.2.1; Ubuntu
  24.04.4 LTS, kernel 6.8.0-117-generic, 4 CPUs, 8,308,289,536 B) on a Mac (`linux/00-docker-info.txt`).
- Python 3.12.3 (`/usr/bin/python3`), pip 24.0 (system and venv), huggingface_hub 2.2.0 in the venv, Google Cloud
  SDK 589.0.0 (google-cloud-cli 589.0.0-0), git 2.43.0, curl 8.5.0, GNU tar 1.35, `/bin/sh` = dash, bash 5.2.21,
  sudo 1.9.15p5 (`linux/02-venv.log`, `linux/09-versions.log`).
- User `dev` (uid 1000, passwordless sudo, HOME `/home/dev`), `LANG=C.UTF-8`; the clone at
  `/home/dev/edge-llm-bench`, HEAD `0efecb019c8d346c941440f4faa6f87485689bd5` = `origin/main` on the day.

## How the steps were run

Each step is a file in `linux/steps/`, run by `linux/run_steps.sh` as
`docker exec -u dev -w /home/dev -e HOME=/home/dev -e USER=dev -e LOGNAME=dev -e SHELL=/bin/bash -e LANG=C.UTF-8
elb-googler-first-run bash -l <step file>` (the admin steps as root). The README lines in the step files are
byte-for-byte copies (`diff` against README.md:126-130, `grep -F` of line 114). Every step is a fresh shell, so
the steps after step 1 begin with `. ~/elb-venv/bin/activate` and `cd ~/edge-llm-bench`, which a terminal keeps.
The machine is shared: each step started only once the Mac's measurement lock was free (another project's GPU
timing). The waits (135 s before the first step, 60 s before README step 1; `linux/quiet_wait.log`) are not in
the durations below; a duration of `<1 s` is under one second.

## Table 1: container-only prerequisites

A gLinux workstation is expected to have python3, git, curl and gcloud already; that was not checked here, and
whether it has the `python3-venv` package is unverified.

| what | command | start (JST) | duration | result | log |
|---|---|---|---|---|---|
| image | `docker pull ubuntu:24.04` | 15:07:54 | 6 s | the digest above | `linux/01-admin.log` |
| container | `docker run -d --name elb-googler-first-run --memory 6g ubuntu:24.04 sleep infinity` | 15:08:00 | <1 s | running | `linux/01-admin.log` |
| base packages (root) | `apt-get update`, `apt-get install -y sudo git curl ca-certificates gnupg python3 procps` | 15:08:00 | 16 s | ok; the image had no sudo, git, curl, gpg or python3 (pgrep / ps were there) | `linux/01-admin.log` |
| user (root) | `useradd -m -u 1000 -s /bin/bash dev`, `/etc/sudoers.d/dev` = `dev ALL=(ALL) NOPASSWD:ALL` | 15:08:16 | <1 s | `useradd: UID 1000 is not unique`: the image ships user `ubuntu` at uid 1000; `userdel -r ubuntu`, then `useradd` again -> `uid=1000(dev) gid=1000(dev)` | `linux/01-admin.log` |
| venv and pip (root) | `apt-get install -y python3-venv python3-pip` | 15:08:16 | 17 s | ok | `linux/01-admin.log` |
| gcloud (dev, sudo) | the five lines of https://docs.cloud.google.com/sdk/docs/install, "Debian/Ubuntu", newer distributions (`gpg --dearmor` key, `signed-by` source line, `apt-get update && apt-get install google-cloud-cli`), with `-y` added (no terminal) | 15:08:33 | 18 s | google-cloud-cli 589.0.0-0 (arm64), 53.8 MB download | `linux/01-admin.log`, `linux/09-versions.log` |
| sign-in | an existing gcloud sign-in copied into `/home/dev/.config/gcloud` (without its `logs/` and the application-default credentials file), owned by dev | 15:09:56 | <1 s | 22 entries | `linux/02-gcloud.log` |

## Table 2: the README section, step by step

| step | command (verbatim) | start | end | duration | result | what stopped and the fix (file:line) |
|---|---|---|---|---|---|---|
| 1 python | `python3 -m venv ~/elb-venv && . ~/elb-venv/bin/activate && pip install huggingface_hub` (README.md:114) | 15:09:51 | 15:09:56 | 5 s | rc 0; huggingface_hub 2.2.0 (`linux/02-venv.log`) | nothing |
| 1 gcloud | `gcloud auth login` (README.md:103) | - | - | - | not run: it needs a browser; the sign-in of table 1 stands in | not exercised |
| 1 gcloud | `gcloud config set project litert-edge-portal` (README.md:103, the placeholder filled), then two checks that are not README lines: `gcloud auth print-access-token > /dev/null && echo TOKEN_OK` and `gcloud storage ls gs://litert-edge-portal-devicerun/automation/inputs/edge-llm-bench/` | 15:09:56 | 15:09:58 | 2 s | `Updated property [core/project].`, `TOKEN_OK` (the token not printed), the input prefixes listed (read only) (`linux/02-gcloud.log`) | nothing |
| 1 API | `gcloud services enable devicerun.googleapis.com --project <your project>` (README.md:107) | - | - | - | not run: the project has the API on | not exercised |
| 2 | README.md:126-130 at 0efecb0, the block below the table | 15:09:58 | 15:10:05 | 7 s | rc 0; HEAD 0efecb0, TAG v0.18.0, the asset 40.6 MiB; `sha256sum -c SHA256SUMS` OK for the 9 engine files; GNU tar printed 11 warnings and left 10 AppleDouble files (finding 1) (`linux/03-clone-asset.log`) | nothing stopped; finding 1 |
| check | `./android/ddp/selftest.py` (not in the section at 0efecb0) | 15:10:05 | 15:10:22 | 17 s | exit 0, `ddp selftest OK (73 checks)`, among them `the 9 engine files' sha256 = android/engine-pins.json litert-lm v0.18.0` (`linux/05-selftest.log`) | the section had no check before the dry run: added as the end of step 2 (README.md:140-147) |
| check | `./bench doctor` (README.md:59, "Setup") | 15:10:05 | 15:10:05 | <1 s | exit 0, `ready`: 2 ok, 7 warn (matplotlib, HF auth, the onnxruntime-genai venv, xcodebuild, gtimeout, devicectl, adb) (`linux/04-doctor.log`) | nothing stopped; finding 2 |
| 3 | `./bench matrix matrices/dashboard-text-v1.cells --ddp akita-35 --dry-run --project litert-edge-portal --bucket gs://litert-edge-portal-devicerun` (README.md:145-146 at 0efecb0, the placeholders filled) | 15:10:22 | 15:10:22 | <1 s | exit 0; `8 job(s) in 1 session(s) on akita-35, 22 row(s) skipped; upload candidates 15 object(s), 152,887,829 bytes`; skipped: 10 `runtime-not-wired-on-ddp` (llama.cpp), 8 + 4 `exclude-on=pixel8a`; `"uncached": ["Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm", "Qwen3_1.7B.litertlm", "gemma-4-E2B-it.litertlm"]` (`LocalEntryNotFoundError`); `deviceMinutes` 153.5; gcloud's log files 5 before and after, `results/raw` 297 entries before and after (`linux/06-dryrun-dashboard.log`) | nothing |
| 3 | the same command on `matrices/ddp-first-run.cells` (new in this change; copied into the clone, `scripts/validate_cells.py` OK) | 15:10:22 | 15:10:23 | 1 s | exit 0; `1 job(s) in 1 session(s) on akita-35, 0 row(s) skipped; upload candidates 12 object(s), 152,882,610 bytes`; runs 2, cooldown 120 s, `executionTimeout` 3600 s; estimate 541 s (`deviceMinutes` 9.0, basis "max of 6 local Pixel 8a runs at v0.18.0"); the model `"uncached"`; gcloud's log files 5 / 5 (`linux/07-dryrun-first-run.log`) | nothing |

The upload byte counts leave out the uncached models (no size before the download).

Step 2 as run (README.md:126-130 at 0efecb0, verbatim; `linux/steps/30-readme2-clone.sh`):

```bash
git clone https://github.com/john-rocky/edge-llm-bench && cd edge-llm-bench
TAG=$(python3 -c 'import json; print(json.load(open("android/engine-pins.json"))["android_pins"]["litert-lm"])')
mkdir -p android/bin
curl -fL https://github.com/john-rocky/edge-llm-bench/releases/download/android-litert-lm-$TAG/litert-lm-$TAG-android-arm64.tar.gz \
  | tar xz -C android/bin && mv android/bin/litert-lm-$TAG-android-arm64 android/bin/$TAG
```

## Probes (not README steps)

| probe | command | result | log |
|---|---|---|---|
| venv before the `python3-venv` package | `python3 -m venv ~/probe-venv` | rc 1: "The virtual environment was not created successfully because ensurepip is not available. On Debian/Ubuntu systems, you need to install the python3-venv package …" (it names `apt install python3.12-venv`) | `linux/01-admin.log` |
| pip outside a venv | `python3 -m pip install huggingface_hub` (the form docs/OPERATIONS.md:261 prints for this route) and `pip install huggingface_hub` | rc 1 both: `error: externally-managed-environment` (PEP 668) | `linux/01-admin.log` |
| no network | the selftest and both dry runs with the container disconnected from its network (no DNS answer and no HTTPS to github.com first) | selftest exit 0 (73 checks), both dry runs exit 0 with the same jobs and skips; reconnected after | `linux/08-offline.log` |
| the fixed lines | README.md step 2's new block, and android/README.md:26-29 in a fresh directory that holds only `android/engine-pins.json` | selftest exit 0 (73 checks); the fast path exit 0, its files byte for byte those of README step 2 | `linux/10-verify-readme.log` |

## Findings that did not stop the run

1. The release asset `litert-lm-v0.18.0-android-arm64.tar.gz` was packed with macOS metadata. GNU tar prints
   `tar: Ignoring unknown extended header keyword 'LIBARCHIVE.xattr.com.apple.provenance'` 11 times and
   extracts 10 AppleDouble files (`._<name>`, 163 B each) beside the 9 engine files and `SHA256SUMS`. Nothing
   reads them: the driver names its 9 files, and `sha256sum -c SHA256SUMS` passes. A repack with
   `COPYFILE_DISABLE=1 tar --no-mac-metadata --no-xattrs` would drop both; the asset was not changed here.
2. `./bench doctor` checks nothing of this route: on Linux it reports Mac, iPhone and adb tools as warnings and
   says `ready`, and it does not look at gcloud, the 9 engine files or huggingface_hub (its `huggingface_hub`
   line sits behind the adb check).
3. docs/OPERATIONS.md:261 prints `python3 -m pip install huggingface_hub` for this route; on Ubuntu 24.04 that
   stops with `externally-managed-environment` (probe above). The README's venv line passes.
4. On a stock Ubuntu, README.md:114 needs the `python3-venv` package first (probe above).
5. `bench` echoes `$ <command>` before it runs a tool; in a file that line lands after the tool's output for
   `doctor` (`linux/04-doctor.log`), because stdout is block-buffered when redirected (`matrix --ddp` sets line
   buffering, `doctor` does not).

## Not exercised here

- `gcloud auth login` (a browser step) and `gcloud services enable devicerun.googleapis.com`.
- README step 4 (the billed run) and steps 5-7.
- The source build (README.md:133; android/README.md:37 still names `LITERTLM_TAG=v0.17.0`, left as it is
  because it was not run), `android/scripts/fetch_llama_android.sh` (llama.cpp rows do not run on DDP), and a
  gated model (no Hugging Face token).

## Log hygiene

No log carries a token, an account name or a gcloud credential file name. In the driver's own output files
(`linux/run_steps.out`, `linux/run_steps-verify.out`, `linux/quiet_wait.log`) the Mac home directory is
redacted to `USER` and other projects' lock labels to `<another lane's window>`; one bucket prefix that is not
this route's is redacted in `linux/02-gcloud.log`.
