# First DDP run from a Cloudtop (gLinux, x86_64): edge-llm-bench, one billed job

Six steps from a home directory to two records from a lab Pixel 8a (`akita-35`): the README section "Run the Android
cells on a Developer Device Platform phone" as it ran on a clean Ubuntu 24.04 machine on 2026-10-16 (record:
`results/raw/2026-10-16-googler-first-run-dev/LINUX_FIRST_RUN.md`). Assumed present: gcloud, python3, git, curl. Steps
1-5 bill nothing; step 6 bills device time to project litert-edge-portal. The steps need the repo's main with the DDP
changes of 2026-10-16 (`./bench doctor --platform ddp`, a selftest of 76 checks).

If git clone, curl or pip stops on a network error, the machine reaches the internet through a proxy: set `https_proxy`
to it in the shell and run the step again. The steps reach github.com and a githubusercontent.com host (clone, release
file), pypi.org (pip), huggingface.co (the model, step 6) and the googleapis.com endpoints of gcloud and Device Run.

## 1. Clone, from your home directory
    git clone https://github.com/john-rocky/edge-llm-bench && cd edge-llm-bench
Expected: `Cloning into 'edge-llm-bench'...`; the shell is in `~/edge-llm-bench`.

## 2. The pinned LiteRT-LM Android files (the repo's GitHub release; 7 s with step 1 on 2026-10-16)
    TAG=$(python3 -c 'import json; print(json.load(open("android/engine-pins.json"))["android_pins"]["litert-lm"])')
    mkdir -p android/bin
    curl -fL https://github.com/john-rocky/edge-llm-bench/releases/download/android-litert-lm-$TAG/litert-lm-$TAG-android-arm64.tar.gz \
      | tar xz -C android/bin && mv android/bin/litert-lm-$TAG-android-arm64 android/bin/$TAG
Expected: curl's progress up to 40.6M and 11 lines `tar: Ignoring unknown extended header keyword
'LIBARCHIVE.xattr.com.apple.provenance'` (macOS metadata, harmless); `echo $TAG` prints `v0.18.0`;
`ls android/bin/v0.18.0` lists `SHA256SUMS`, `litert_lm_main`, `litert_lm_advanced_main` and 7 `.so` files.
If it stops: a `curl: (22)` line means the release file was not found: check `echo $TAG` and the URL.

## 3. Python and huggingface_hub
    python3 --version
    python3 -m venv ~/elb-venv && . ~/elb-venv/bin/activate && pip install huggingface_hub
Expected: Python 3.10 or newer; pip ends with `Successfully installed ...` naming `huggingface_hub-2.2.0` or newer.
In every new terminal: `. ~/elb-venv/bin/activate && cd ~/edge-llm-bench`.
If it stops: below 3.10, make the venv with a newer interpreter instead (`python3.11 -m venv ~/elb-venv`, or 3.12);
`ensurepip is not available` means the venv package is missing: `sudo apt install python3-venv`, then the line again.

## 4. Check the machine (nothing billed; the selftest uses no network)
    ./bench doctor --platform ddp
    ./android/ddp/selftest.py
Expected: four `ok` lines, `gcloud`, `gcloud sign-in`, `huggingface_hub` and `ddp engine files  v0.18.0: 9 files =
android/engine-pins.json`, then `ready` (warn lines for Mac, iPhone and adb tools are normal here); the selftest
ends with `ddp selftest OK (76 checks)`, exit 0, in about 20 s.
If it stops: `FAIL  gcloud sign-in` means run `gcloud auth login`; every other `FAIL` line prints its own fix; an
`invalid choice: 'ddp'` error means the clone predates the DDP check: `git pull` once main has it.

## 5. Dry run (no gcloud call, no network, nothing billed)
    ./bench matrix matrices/ddp-first-run.cells --ddp akita-35 --dry-run --project litert-edge-portal --bucket gs://litert-edge-portal-devicerun
Expected: `1 job(s) in 1 session(s) on akita-35, 0 row(s) skipped; upload candidates 12 object(s), 152,882,610 bytes
(existence not checked)`; the model's file name after `"uncached"` (step 6 downloads it); exit 0.

## 6. The run (billed: one job of two runs on a lab Pixel 8a)
The account you are signed in as must be allowed to create Device Run sessions in project litert-edge-portal and to
write gs://litert-edge-portal-devicerun; today only the project owner's account has that, so the owner grants it first
(roles/editor on the project), or the run uses a project of your own with the Device Run API enabled and its
`gs://<project>-devicerun` bucket.
    ./bench matrix matrices/ddp-first-run.cells --ddp akita-35 --project litert-edge-portal --bucket gs://litert-edge-portal-devicerun
Expected: the model download (977 MB), 12 lines `in bucket: gs://litert-edge-portal-devicerun/...`, `session 1:
operation projects/litert-edge-portal/...`, `session 1: not done (07:18:11)` and the like every 30 s, a `run 1/2 OK` and
a `run 2/2 OK` line, exit 0: 6 to 7 min on 2026-10-16 (the unit's thermal gate can add up to 10 min before each run).
Records: `results/raw/` + today's date + `-ddp-akita-35-android/app-path-android/*.json`; its `ddp/session-1.json` reads `PASSED`.
If it stops with an access error (401 or 403 from gcloud or Device Run; a Device Run answer is kept in
`ddp/error-1.json`): run `gcloud auth login`, then check the grant above.
