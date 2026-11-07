#!/usr/bin/env python3
"""Device-free, network-free selftest of the DDP iPhone driver (ios/ddp/; design:
results/raw/2026-10-16-build-ref-iphone-lm-dev/DESIGN-D1.md).

  ./ios/ddp/selftest.py        # exit 0 = pass; the temp dir is kept on failure

1. ios/ddp/models.json against ModelCatalog.swift's LiteRT-LM entries (id -> hfRepoId, primaryFile).
2. --dry-run of the four D1 cells against a stand-in HF cache and archive, with a gcloud on PATH that
   must never run: the submit command's flags (the gs:// model object named by the blob's sha256,
   the push and pull paths, --xctest-timeout by backend, --xcode-version, the labels), the app's argv
   = the words scripts/bench_matrix_iphone.sh gives devicectl (its DRY_RUN mode, same cells),
   --flat-model-push, a host without huggingface_hub, an Xcode 26 FormatVersion 2 manifest; the
   refusals (exit 2).
3. the billed path against a stand-in gcloud (a temp dir as the bucket): the upload of the missing
   object only, the submission, the session found by its run label, the pull; the records named in
   records.txt (not a stale one) with device.ddp and conditions.ddp and every other key as the app
   wrote it, the console under the attached runner's name, ddp/<session>/ and ddp-raw/<session>/;
   --records-only writes the same files again; exit 4 (job failed), 5 (no record), 3 (no gcloud),
   2 (not an iPhone; a collected session of another cell); thermal_gate.txt (the harness's wait
   before run 1) -> three keys of conditions.ddp; plan.json writes the home directory as ~.
4. scripts/build_summary.py into a temp dir: the device column of a DDP iPhone row, never the
   attached iPhone's.
5. run_ddp_ios_matrix.py: the cells plan, register_archive_builder, BENCH_RAW_ROOT, --no-keep-raw.
6. native-benchmark-<P>x<D> rows: the app's argv and the refusals, the records the app writes for them
   through the billed path and build_summary, and a row's cool-wait= as --native-cool-wait.
"""
import contextlib
import csv
import glob
import hashlib
import io
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
import zipfile
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DRIVER = os.path.join(HERE, "run_ddp_ios_lm.py")
CATALOG = os.path.join(ROOT, "ios", "BenchmarkApp", "Sources", "Models", "ModelCatalog.swift")
RUNNER = os.path.join(ROOT, "scripts", "bench_matrix_iphone.sh")
# an attached-iPhone record of the same arm: the shape the app writes (schema v1)
TEMPLATE = os.path.join(ROOT, "results", "raw", "2026-10-09-iphone18pro-pin-check-ios", "device-jsonl",
                        "litert-lm_litert-community_Qwen3-0.6B_short-chat_2026-10-09T12-36-27Z.json")
DEVICE = "iphone16pro-18-3"
BUNDLE = "com.iosllmbenchmark.benchmarkapp.ddp"
PROJECT = "fake-project"
BUCKET = "gs://fake-bucket"
SID = "session-0123abcd"
PREFIX = f"gs://fake-bucket/automation/sessions/{SID}/job-000/execution-1111-2222/"
BUILD_INFO = ("litert_lm=v0.18.0\nlitert_lm_artifact=CLiteRTLM.xcframework.zip@v0.18.0 sha256:"
              "d765b99592d4ec3d0c9e2bd69469454af06c834861340672da1891c0c121c347\n"
              f"app={BUNDLE} (BenchmarkAppDDP, Release, iOS 18.0 floor)\nxcode=Xcode 26.1.1 Build version 17B100\n"
              "sdk=iphoneos26.1\ncommit=0000000000000000000000000000000000000000\nbuilt=2026-10-16T00:00:00Z\n")
CELLS = [("litert-community/Qwen3-1.7B", "gpu", "15m"), ("litert-community/Qwen3-1.7B/int8", "cpu", "30m"),
         ("litert-community/gemma-4-E2B-it-litert-lm", "gpu", "15m"),
         ("litert-community/gemma-4-E2B-it-litert-lm", "cpu", "30m")]
LABEL = re.compile(r"[a-z0-9_-]{1,63}")
NATIVE_TASK = "native-benchmark-1024x256"

FAKE_GCLOUD = r"""#!/bin/bash
# Stand-in gcloud for ios/ddp/selftest.py: answers from files in $FAKE_GCLOUD_DIR; every call is
# appended to $FAKE_GCLOUD_LOG; the bucket is the directory $FAKE_GCLOUD_DIR/bucket.
echo "$*" >> "$FAKE_GCLOUD_LOG"
D="$FAKE_GCLOUD_DIR"
case "$*" in
  "config get-value project") cat "$D/project" 2>/dev/null || true ;;
  *"devices list"*) cat "$D/devices.json" ;;
  "storage ls "*) [ -e "$D/bucket/${3#gs://}" ] ;;
  "storage cp -r "*)
    dest="${@: -1}"
    mkdir -p "$dest"
    cp -R "$D/execution/artifacts" "$dest/"
    cp "$D/execution/system.log" "$D/execution/junit.xml" "$dest/" ;;
  "storage cp "*) mkdir -p "$(dirname "$D/bucket/${4#gs://}")" && cp "$3" "$D/bucket/${4#gs://}" ;;
  *"sessions submit xctest"*) echo "[]" ;;
  *"sessions list"*)
    run="$(grep -o 'run=[0-9a-f]*' "$FAKE_GCLOUD_LOG" | tail -1)"
    sed "s/RUN_LABEL/${run#run=}/" "$D/list.json" ;;
  *"sessions describe"*) cat "$D/describe.json" ;;
  *) echo "unexpected gcloud call: $*" >&2; exit 1 ;;
esac
"""

_fails = []
_count = [0]


def ok(cond, msg):
    _count[0] += 1
    print(("  ok  " if cond else "  FAIL ") + msg)
    if not cond:
        _fails.append(msg)


def write(path, text, mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)
    os.chmod(path, mode)


def load_models():
    with open(os.path.join(HERE, "models.json")) as fh:
        return {k: v for k, v in json.load(fh).items() if not k.startswith("_")}


def hf_cache(root):
    """A stand-in hub cache: refs/main -> a snapshot whose files link to blobs named by their sha256."""
    shas = {}
    for mid, entry in load_models().items():
        repo = os.path.join(root, "models--" + entry["hfRepoId"].replace("/", "--"))
        body = f"weights of {entry['file']}\n".encode()
        sha = hashlib.sha256(body).hexdigest()
        os.makedirs(os.path.join(repo, "blobs"), exist_ok=True)
        with open(os.path.join(repo, "blobs", sha), "wb") as fh:
            fh.write(body)
        commit = hashlib.sha1(entry["hfRepoId"].encode()).hexdigest()
        write(os.path.join(repo, "refs", "main"), commit)
        snap = os.path.join(repo, "snapshots", commit)
        os.makedirs(snap, exist_ok=True)
        link = os.path.join(snap, entry["file"])
        if not os.path.lexists(link):
            os.symlink(os.path.join("..", "..", "blobs", sha), link)
        shas[mid] = (sha, len(body))
    return shas


def make_archive(path, format_version=1, bundle=BUNDLE, build_info=BUILD_INFO, manifest=True):
    if format_version == 1:
        plist = {"__xctestrun_metadata__": {"FormatVersion": 1},
                 "BenchmarkAppDDPTests": {"TestHostBundleIdentifier": bundle}}
    else:
        plist = {"__xctestrun_metadata__": {"FormatVersion": 2},
                 "TestConfigurations": [{"Name": "Test Scheme Action",
                                         "TestTargets": [{"BlueprintName": "BenchmarkAppDDPTests",
                                                          "TestHostBundleIdentifier": bundle}]}]}
    with zipfile.ZipFile(path, "w") as zf:
        if manifest:
            zf.writestr("BenchmarkAppDDP_iphoneos26.1-arm64.xctestrun", plistlib.dumps(plist))
        zf.writestr("Release-iphoneos/BenchmarkAppDDP.app/Info.plist", b"")
        if build_info is not None:
            zf.writestr("BUILD_INFO", build_info)


def env_for(tmp, gcloud=True, extra=None):
    fake = os.path.join(tmp, "fake")
    empty = os.path.join(tmp, "no-gcloud-bin")
    os.makedirs(empty, exist_ok=True)
    # HF_HUB_OFFLINE: no driver run of the selftest may reach the Hub, whatever path it takes
    env = {**os.environ, "FAKE_GCLOUD_DIR": fake, "FAKE_GCLOUD_LOG": os.path.join(tmp, "gcloud.log"),
           "BENCH_RAW_ROOT": os.path.join(tmp, "raw"), "HF_HUB_CACHE": os.path.join(tmp, "hf"),
           "HF_HUB_OFFLINE": "1", "PATH": f"{fake}:/usr/bin:/bin" if gcloud else empty}
    env.pop("HF_HOME", None)
    env.pop("BENCH_DDP_PROJECT", None)
    env.pop("BENCH_DDP_BUCKET", None)
    env.update(extra or {})
    return env


def driver(args, env):
    return subprocess.run([sys.executable, DRIVER, *args], capture_output=True, text=True, env=env)


def json_lines(out):
    rows = {}
    for line in out.splitlines():
        if line.startswith("{"):
            rows.update(json.loads(line))
    return rows


def gcloud_calls(tmp):
    path = os.path.join(tmp, "gcloud.log")
    return open(path).read().splitlines() if os.path.exists(path) else []


def flag(cmd, name):
    return next((c.split("=", 1)[1] for c in cmd if c.startswith(name + "=")), None)


# ---------------------------------------------------------------- 1. models.json

def check_models():
    print("--- 1. ios/ddp/models.json against ModelCatalog.swift (ModelCatalog.liteRTLM)")
    text = open(CATALOG).read()
    # the list literal, bare or wrapped in withExtra("litert-lm", [...]) (the extra catalog)
    start = text.index("public static let liteRTLM: [ModelInfo] = ")
    block = text[start:text.index("\n    ]", start)]
    catalog = {}
    for m in re.finditer(r"ModelInfo\((.*?)\n        \)", block, re.S):
        fields = dict(re.findall(r'(\w+): "([^"]*)"', m.group(1)))
        if "id" in fields:
            catalog[fields["id"]] = fields
    models = load_models()
    ok(set(models) == {c[0] for c in CELLS}, f"models.json holds the three D1 ids ({sorted(models)})")
    for mid, entry in sorted(models.items()):
        c = catalog.get(mid, {})
        ok(c.get("hfRepoId") == entry["hfRepoId"] and c.get("primaryFile") == entry["file"],
           f"{mid}: hfRepoId / file = the catalog's ({c.get('hfRepoId')}, {c.get('primaryFile')})")


# ---------------------------------------------------------------- 2. dry runs

def runner_argv(tmp):
    """scripts/bench_matrix_iphone.sh's devicectl argv after `--` for the four cells (DRY_RUN mode)."""
    cells = os.path.join(tmp, "d1.cells")
    write(cells, "".join(f"ios litert-lm {mid} short-chat backend={be} runs=4\n" for mid, be, _ in CELLS))
    env = {**os.environ, "DRY_RUN": "1", "CAMPAIGN": "selftest-ios-ddp-runner"}
    r = subprocess.run(["bash", RUNNER, "run", cells], capture_output=True, text=True, env=env, cwd=ROOT)
    out = []
    for line in r.stdout.splitlines():
        if line.startswith("DRY-RUN xcrun devicectl device process launch") and " -- " in line:
            out.append(line.split(" -- ", 1)[1].split())
    return r, out


def check_dry_runs(tmp, shas):
    print("--- 2. --dry-run: the command, the app's argv, the refusals; gcloud never runs")
    fake = os.path.join(tmp, "fake")
    write(os.path.join(fake, "gcloud"), "#!/bin/bash\necho \"$*\" >> \"$FAKE_GCLOUD_LOG\"\nexit 1\n", 0o755)
    archive = os.path.join(tmp, "BenchmarkApp-ddp-xctest.zip")
    make_archive(archive)
    archive_sha = hashlib.sha256(open(archive, "rb").read()).hexdigest()
    env = env_for(tmp)
    r_runner, runner = runner_argv(tmp)
    ok(r_runner.returncode == 0 and len(runner) == 4,
       f"bench_matrix_iphone.sh DRY_RUN printed 4 launches (rc {r_runner.returncode}, {len(runner)}; {r_runner.stderr[-300:]!r})")
    models = load_models()
    for i, (mid, be, timeout) in enumerate(CELLS):
        r = driver(["--device", DEVICE, "--model-id", mid, "--backend", be, "--archive", archive,
                    "--campaign", "selftest-ios-ddp", "--project", PROJECT, "--bucket", BUCKET, "--dry-run"], env)
        rows = json_lines(r.stdout)
        cmd = rows.get("command") or []
        sha, size = shas[mid]
        entry = models[mid]
        push = (flag(cmd, "--other-files-to-push") or "").split(",")
        model_src, _, model_dst = push[0].partition("=")
        args_src, _, args_dst = (push[1] if len(push) > 1 else "").partition("=")
        labels = dict(kv.split("=", 1) for kv in (flag(cmd, "--labels") or "").split(",") if "=" in kv)
        ok(r.returncode == 0 and cmd[:6] == ["gcloud", "beta", "device-run", "sessions", "submit", "xctest"],
           f"{mid} {be}: rc 0, a sessions submit xctest command (rc {r.returncode}, {r.stderr[-200:]!r})")
        ok(flag(cmd, "--device") == DEVICE
           and flag(cmd, "--test") == f"{BUCKET}/automation/inputs/edge-llm-bench/ios-xctest/{archive_sha}/"
                                      "BenchmarkApp-ddp-xctest.zip",
           f"{mid} {be}: --device, --test = the archive's content-addressed object ({flag(cmd, '--test')})")
        ok(len(push) == 2
           and model_src == f"{BUCKET}/automation/inputs/edge-llm-bench/models/{sha}/{entry['file']}"
           and model_dst == f"{BUNDLE}:/Documents/models/litert-lm/{entry['hfRepoId'].replace('/', '__')}/{entry['file']}"
           and args_dst == f"{BUNDLE}:/Documents/yardstick_args.json"
           and args_src.startswith("raw/selftest-ios-ddp/ddp/args-") is False,
           f"{mid} {be}: push 2 = the gs:// model object named by the blob's sha256 -> the app's model dir, "
           f"the argv file -> Documents/yardstick_args.json ({push})")
        ok(flag(cmd, "--paths-to-pull") == f"{BUNDLE}:/Documents/results,{BUNDLE}:/Documents/out"
           and flag(cmd, "--xctest-timeout") == timeout and flag(cmd, "--xcode-version") == "xcode-26-2"
           and "--async" in cmd and f"--project={PROJECT}" in cmd and "--format=json" in cmd,
           f"{mid} {be}: pull 2 paths, --xctest-timeout {timeout}, --xcode-version xcode-26-2, --async, the project")
        ok(len(labels) <= 16 and all(LABEL.fullmatch(v) for v in labels.values())
           and labels.get("runtime") == ("litert-lm" if be == "gpu" else "litert-lm-cpu")
           and labels.get("engine") == "v0-18-0" and labels.get("deviceid") == DEVICE and labels.get("backend") == be
           and re.fullmatch(r"[0-9a-f]{12}", labels.get("run", "")),
           f"{mid} {be}: {len(labels)} labels in the GCP label form (runtime, engine, deviceid, backend, run) ({labels})")
        expected = ["--yardstick-autorun", "--runtime", "litert-lm", "--model-id", mid, "--task", "short-chat",
                    "--runs", "4", "--litert-backend", be]
        ok(rows.get("args") == expected and i < len(runner) and runner[i] == expected,
           f"{mid} {be}: the app's argv = bench_matrix_iphone.sh's devicectl argv ({rows.get('args')})")
        ok(os.path.expanduser("~") not in r.stdout, f"{mid} {be}: no home path in the printed plan")
    ok(gcloud_calls(tmp) == [], f"four dry runs called gcloud 0 times ({gcloud_calls(tmp)[:2]})")
    # no --project, no --bucket: the placeholders in the printed command, still no gcloud
    r = driver(["--device", DEVICE, "--model-id", CELLS[0][0], "--backend", CELLS[0][1], "--archive", archive,
                "--campaign", "x", "--dry-run"], env)
    cmd = json_lines(r.stdout).get("command") or []
    ok(r.returncode == 0 and "--project=$PROJECT" in cmd and any("gs://$PROJECT-devicerun/" in c for c in cmd)
       and gcloud_calls(tmp) == [],
       f"no --project, no --bucket: the dry run prints $PROJECT and gs://$PROJECT-devicerun, gcloud 0 times (rc {r.returncode})")
    # --flat-model-push, --context-tokens, --timeout
    r = driver(["--device", DEVICE, "--model-id", CELLS[2][0], "--backend", "gpu", "--archive", archive,
                "--campaign", "x", "--flat-model-push", "--context-tokens", "2048", "--timeout", "45m", "--dry-run"], env)
    rows = json_lines(r.stdout)
    push = (flag(rows.get("command") or [], "--other-files-to-push") or "").split(",")
    ok(r.returncode == 0 and push[0].endswith(f"={BUNDLE}:/Documents/gemma-4-E2B-it.litertlm")
       and rows["args"][-4:] == ["--context-tokens", "2048", "--litert-backend", "gpu"]
       and flag(rows["command"], "--xctest-timeout") == "45m",
       f"--flat-model-push -> Documents/<file>; --context-tokens before --litert-backend; --timeout 45m ({push[0]})")
    # a host without huggingface_hub (the CI runner): the cache is read directly
    stub = os.path.join(tmp, "nohub")
    write(os.path.join(stub, "huggingface_hub", "__init__.py"), "raise ImportError('selftest: no huggingface_hub')\n")
    r = driver(["--device", DEVICE, "--model-id", CELLS[0][0], "--backend", "gpu", "--archive", archive,
                "--campaign", "x", "--dry-run"], env_for(tmp, extra={"PYTHONPATH": stub}))
    rows = json_lines(r.stdout)
    ok(r.returncode == 0 and (rows.get("model") or {}).get("sha256") == shas[CELLS[0][0]][0],
       f"without huggingface_hub the dry run reads the cache's refs/main -> blob ({(rows.get('model') or {}).get('sha256')})")
    # Xcode 26's FormatVersion 2 manifest
    fv2 = os.path.join(tmp, "fv2.zip")
    make_archive(fv2, format_version=2, bundle="com.example.CoreMLLLMChat")
    r = driver(["--device", DEVICE, "--model-id", CELLS[0][0], "--backend", "gpu", "--archive", fv2,
                "--campaign", "x", "--dry-run"], env)
    ok(r.returncode == 0 and (json_lines(r.stdout).get("plan") or {}).get("bundleId") == "com.example.CoreMLLLMChat",
       "an .xctestrun of FormatVersion 2 (TestConfigurations[].TestTargets[]) gives the bundle id too")
    # refusals
    no_manifest = os.path.join(tmp, "no-manifest.zip")
    make_archive(no_manifest, manifest=False)
    no_info = os.path.join(tmp, "no-build-info.zip")
    make_archive(no_info, build_info=None)
    base = ["--device", DEVICE, "--backend", "gpu", "--campaign", "x", "--dry-run"]
    for extra, why in ((["--model-id", "litert-community/Qwen3-4B", "--archive", archive], "a model id not in models.json"),
                       (["--model-id", CELLS[0][0], "--archive", archive, "--timeout", "2h"], "--timeout 2h"),
                       (["--model-id", CELLS[0][0], "--archive", archive, "--timeout", "0m"], "--timeout 0m"),
                       (["--model-id", CELLS[0][0], "--archive", os.path.join(tmp, "missing.zip")], "no archive"),
                       (["--model-id", CELLS[0][0], "--archive", no_manifest], "an archive without a manifest"),
                       (["--model-id", CELLS[0][0], "--archive", no_info], "an archive without BUILD_INFO"),
                       (["--model-id", CELLS[0][0], "--archive", archive, "--runs", "0"], "--runs 0")):
        r = driver(base + extra, env)
        ok(r.returncode == 2 and "run_ddp_ios_lm.py:" in r.stderr, f"exit 2 for {why} ({r.returncode}: {r.stderr.strip()[-120:]!r})")
    r = driver(["--device", "iPhone 16", "--model-id", CELLS[0][0], "--backend", "gpu", "--archive", archive, "--dry-run"], env)
    ok(r.returncode == 2, f"exit 2 for a device id that is not a catalog id ({r.returncode})")
    r = driver(["--records-only", tmp, "--device", DEVICE], env)
    ok(r.returncode == 2 and "takes the session dir alone" in r.stderr, f"--records-only with other flags: exit 2 ({r.returncode})")
    ok(gcloud_calls(tmp) == [], "the refusals called gcloud 0 times")
    check_extra_catalog(tmp, archive, env)
    return archive


def check_extra_catalog(tmp, archive, env):
    """--extra-catalog / BENCH_EXTRA_CATALOG: another harness's ids added add-only, the file pushed to
    Documents/models/extra-catalog.json (before the argv); ModelCatalog.swift reads the same file."""
    text = open(CATALOG).read()
    ok(all(f'public static let {name}: [ModelInfo] = withExtra("{rt}", [' in text
           for name, rt in (("mlx", "mlx-swift"), ("llamaCpp", "llama.cpp"), ("liteRTLM", "litert-lm"),
                            ("executorch", "executorch")))
       and 'appendingPathComponent("extra-catalog.json")' in text and 'environment["BENCH_EXTRA_CATALOG"]' in text,
       "ModelCatalog.swift: mlx / llamaCpp / liteRTLM / executorch take the extra catalog's entries (withExtra), "
       "read from BENCH_EXTRA_CATALOG or Documents/models/extra-catalog.json")
    extra = os.path.join(tmp, "extra-catalog.json")
    pte, tok = os.path.join(tmp, "x-ctx2048.pte"), os.path.join(tmp, "tokenizer.json")
    write(pte, "stand-in pte\n")
    write(tok, "{}\n")
    entry = {"id": "own-export/X-ctx2048", "displayName": "X", "quantization": "q", "hfRepoId": "own-export/X-ctx2048",
             "hfFilePatterns": ["*.pte", "tokenizer.json"], "primaryFile": "x-ctx2048.pte",
             "files": ["x-ctx2048.pte", "tokenizer.json"]}
    write(extra, json.dumps({"_doc": "selftest", "executorch": [entry]}))
    base = ["--device", DEVICE, "--runtime", "executorch", "--model-id", entry["id"], "--model-file", pte,
            "--model-file", tok, "--archive", archive, "--campaign", "x", "--project", PROJECT, "--bucket", BUCKET,
            "--dry-run"]
    for how, argv, e in (("--extra-catalog", base + ["--extra-catalog", extra], env),
                         ("BENCH_EXTRA_CATALOG", base, {**env, "BENCH_EXTRA_CATALOG": extra})):
        r = driver(argv, e)
        rows = json_lines(r.stdout)
        push = (flag(rows.get("command") or [], "--other-files-to-push") or "").split(",")
        dests = [x.partition("=")[2] for x in push]
        ok(r.returncode == 0 and len(push) == 4
           and dests[:2] == [f"{BUNDLE}:/Documents/models/executorch/own-export__X-ctx2048/x-ctx2048.pte",
                             f"{BUNDLE}:/Documents/models/executorch/own-export__X-ctx2048/tokenizer.json"]
           and push[2] == f"{os.path.realpath(extra)}={BUNDLE}:/Documents/models/extra-catalog.json"
           and dests[3] == f"{BUNDLE}:/Documents/yardstick_args.json"
           and rows.get("args", [])[:6] == ["--yardstick-autorun", "--runtime", "executorch", "--model-id", entry["id"],
                                            "--task"],
           f"{how}: the extra id runs; push = its 2 files, the catalog -> Documents/models/extra-catalog.json, "
           f"the argv ({r.returncode}; {dests}; {r.stderr[-200:]!r})")
    r = driver(base, env)
    ok(r.returncode == 2 and "is not in" in r.stderr, f"without the extra catalog the id is unknown: exit 2 ({r.returncode})")
    dup = {**entry, "id": CELLS[0][0]}
    for bad, want in (({"litert-lm": [dup]}, "is already in"), ({"mlx": [entry]}, "is not a list under a runtime"),
                      ({"executorch": [{"id": "x"}]}, "without id, hfRepoId and primaryFile"),
                      ({"executorch": [entry, entry]}, "twice")):
        write(extra, json.dumps(bad))
        r = driver(base + ["--extra-catalog", extra], env)
        ok(r.returncode == 2 and want in r.stderr,
           f"--extra-catalog refuses {want!r}: exit 2 ({r.returncode}; {r.stderr.strip()[-120:]!r})")
    write(extra, "{not json")
    r = driver(base + ["--extra-catalog", extra], env)
    ok(r.returncode == 2 and "--extra-catalog" in r.stderr, f"a file that does not parse: exit 2 ({r.returncode})")
    ok(gcloud_calls(tmp) == [], "the extra-catalog dry runs called gcloud 0 times")


# ---------------------------------------------------------------- 3. the billed path

def describe_json(result="PASSED", device=DEVICE, labels=None, pulled=True):
    files = [{"gcsOutputFile": {"path": f"{PREFIX}system.log"}}, {"gcsOutputFile": {"path": f"{PREFIX}junit.xml"}}]
    if pulled:
        files += [{"gcsOutputFile": {"path": f"{PREFIX}artifacts/console.txt"}}]
    return {
        "name": f"projects/{PROJECT}/locations/global/sessions/{SID}",
        "sessionConfig": {"jobConfigs": [{
            "action": {"iosXcTest": {"xcTestTimeout": "900s", "xcodeVersion": "xcode-26-2"}},
            "allocationConfig": {"deviceConfigs": [{"requirement": {"deviceId": device}}]},
            "labels": labels or {"harness": "edge-llm-bench", "model": "litert-community--qwen3-1-7b",
                                 "backend": "gpu", "task": "short-chat", "run": "abc"}}]},
        "sessionReport": {
            "startTime": "2026-10-17T00:00:00Z", "endTime": "2026-10-17T00:09:00Z",
            "status": {"statusType": "DONE"}, "result": {"resultType": result},
            "jobReports": [{"displayName": "job-000", "id": "job-000", "startTime": "2026-10-17T00:01:00Z",
                            "endTime": "2026-10-17T00:08:00Z", "status": {"statusType": "DONE"},
                            "result": {"resultType": result},
                            "executionReports": [{"id": "execution-1111-2222", "outputFiles": files,
                                                  "result": {"resultType": result},
                                                  "status": {"statusType": "DONE"}}]}]}}


def fixture_records(template):
    """Four records of the Qwen3-1.7B GPU cell as the app writes them, and one stale record of an
    earlier session left in Documents/results/."""
    model = {"displayName": "Qwen3 1.7B (.litertlm)", "hfFilePatterns": ["Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm"],
             "hfRepoId": "litert-community/Qwen3-1.7B", "id": "litert-community/Qwen3-1.7B", "onDiskSizeMB": 932,
             "parameterCountB": 1.7, "primaryFile": "Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm",
             "quantization": "INT4 (dynamic, block-32 weights, FP32 act; GPU-graph build)"}
    recs = []
    for i, stamp in enumerate(["2026-10-17T00-02-05Z", "2026-10-17T00-02-20Z", "2026-10-17T00-02-34Z",
                               "2026-10-17T00-02-49Z", "2026-10-16T09-00-00Z"]):
        rec = json.loads(json.dumps(template))
        rec.update({"id": str(uuid.uuid4()).upper(), "timestamp": stamp[:13] + ":" + stamp[14:16] + ":" + stamp[17:],
                    "runtime": "litert-lm", "model": model, "task": "short-chat", "engineVersion": "v0.18.0",
                    "engineArtifact": "CLiteRTLM.xcframework.zip@v0.18.0 sha256:d765b99592d4ec3d0c9e2bd69469454af06c834861340672da1891c0c121c347"})
        rec["device"] = {**rec["device"], "modelIdentifier": "iPhone17,1", "systemVersion": "18.3.1"}
        rec["metrics"] = {**rec["metrics"], "coldRun": i == 0}
        recs.append((f"litert-lm_litert-community_Qwen3-1.7B_short-chat_{stamp}.json", rec))
    return recs[:4], recs[4]


def stage_execution(tmp, recs, stale, records_txt=True, done="0", gate=None):
    fake = os.path.join(tmp, "fake")
    art = os.path.join(fake, "execution", "artifacts")
    shutil.rmtree(os.path.join(fake, "execution"), ignore_errors=True)
    for name, rec in recs + [stale]:
        write(os.path.join(art, name), json.dumps(rec, indent=2, sort_keys=True))
    if records_txt:
        write(os.path.join(art, "records.txt"), "".join(n + "\n" for n, _ in recs))
    if done is not None:
        write(os.path.join(art, "yardstick.done"), done + "\n")
    if gate is not None:  # DDPHarness's Documents/out/thermal_gate.txt
        write(os.path.join(art, "thermal_gate.txt"), gate)
    write(os.path.join(art, "console.txt"), "YARDSTICK_METAL_DEVICE name=Apple A18 Pro GPU registry_id=1\n"
          "YARDSTICK_BEGIN runtime=litert-lm model=litert-community/Qwen3-1.7B task=short-chat runs=4\n"
          + "".join(f"YARDSTICK_RUN_OK run={i}\n" for i in range(1, 5)) + "YARDSTICK_ALL_DONE\n")
    write(os.path.join(fake, "execution", "system.log"), "lab device log\n")
    write(os.path.join(fake, "execution", "junit.xml"), "<testsuites><testsuite failures=\"0\"/></testsuites>\n")


def stage_fake(tmp, describe, devices_platform="IOS"):
    fake = os.path.join(tmp, "fake")
    write(os.path.join(fake, "gcloud"), FAKE_GCLOUD, 0o755)
    write(os.path.join(fake, "devices.json"), json.dumps([
        {"displayName": "Pixel 9 Pro", "osVersion": "35", "platform": "ANDROID",
         "name": f"projects/{PROJECT}/locations/global/devices/caiman-35"},
        {"displayName": "iPhone 16 Pro", "osVersion": "18.3", "platform": devices_platform, "modelCode": "iphone16pro",
         "name": f"projects/{PROJECT}/locations/global/devices/{DEVICE}"}]))
    write(os.path.join(fake, "list.json"), json.dumps([
        {"name": f"projects/{PROJECT}/locations/global/sessions/session-other",
         "sessionConfig": {"jobConfigs": [{"labels": {"run": "000000000000"}}]}},
        {"name": f"projects/{PROJECT}/locations/global/sessions/{SID}",
         "sessionConfig": {"jobConfigs": [{"labels": {"run": "RUN_LABEL"}}]}}]))
    write(os.path.join(fake, "describe.json"), json.dumps(describe))


def billed(tmp, archive, campaign, extra=()):
    return driver(["--device", DEVICE, "--model-id", "litert-community/Qwen3-1.7B", "--backend", "gpu",
                   "--archive", archive, "--campaign", campaign, "--project", PROJECT, "--bucket", BUCKET, *extra],
                  env_for(tmp))


def check_billed(tmp, archive, shas):
    print("--- 3. the billed path against a stand-in gcloud: upload, submit, wait, pull, records")
    template = json.load(open(TEMPLATE))
    recs, stale = fixture_records(template)
    stage_fake(tmp, describe_json())
    stage_execution(tmp, recs, stale, gate="waited_s=600\nstate=serious\ntimed_out=1\n")
    sha, _ = shas["litert-community/Qwen3-1.7B"]
    model_obj = f"automation/inputs/edge-llm-bench/models/{sha}/Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm"
    write(os.path.join(tmp, "fake", "bucket", "fake-bucket", model_obj), "already there\n")  # the model is in the bucket
    open(os.path.join(tmp, "gcloud.log"), "w").close()
    r = billed(tmp, archive, "selftest-ios-ddp")
    calls = gcloud_calls(tmp)
    camp = os.path.join(tmp, "raw", "selftest-ios-ddp")
    sdir = os.path.join(camp, "ddp", SID)
    raw = os.path.join(camp, "ddp-raw", SID)
    out = sorted(glob.glob(os.path.join(camp, "device-jsonl", "*.json")))
    ok(r.returncode == 0, f"rc 0 ({r.returncode}; {r.stderr[-300:]!r})")
    cps = [c for c in calls if c.startswith("storage cp ") and not c.startswith("storage cp -r")]
    ok(len(cps) == 1 and "/ios-xctest/" in cps[0] and any(model_obj in c for c in calls if c.startswith("storage ls")),
       f"uploads: the archive only (the model object was in the bucket) ({cps})")
    submit = next((c for c in calls if "sessions submit xctest" in c), "")
    ok(f"--device={DEVICE}" in submit and f"gs://fake-bucket/{model_obj}={BUNDLE}:/Documents/models/litert-lm/"
       "litert-community__Qwen3-1.7B/Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm" in submit
       and f"--project={PROJECT}" in submit and "--format=json" in submit,
       "one submission with the gs:// model push and the project")
    ok(any("sessions list" in c for c in calls) and any(f"sessions describe {SID} --full" in c for c in calls)
       and any(c.startswith("storage cp -r " + PREFIX) for c in calls),
       f"the session found by its run label, described, its execution pulled ({len(calls)} calls)")
    names = [os.path.basename(f) for f in out]
    ok(names == sorted(n for n, _ in recs) and stale[0] not in names,
       f"device-jsonl/ = the 4 records named in records.txt, not the stale one ({names})")
    by_name = {os.path.basename(f): json.load(open(f)) for f in out}
    good = True
    for idx, (name, rec) in enumerate(recs, 1):
        got = by_name.get(name) or {}
        cond = (got.get("conditions") or {}).get("ddp") or {}
        dd = (got.get("device") or {}).get("ddp")
        rest = {k: v for k, v in got.items() if k != "conditions"}
        rest["device"] = {k: v for k, v in (got.get("device") or {}).items() if k != "ddp"}
        good &= (dd == {"deviceId": DEVICE, "displayName": "iPhone 16 Pro", "osVersion": "18.3"}
                 and cond.get("runIndex") == idx and cond.get("sessionId") == SID and cond.get("jobId") == "job-000"
                 and cond.get("executionId") == "execution-1111-2222" and cond.get("xctestTimeout") == "900s"
                 and cond.get("xcodeVersion") == "xcode-26-2" and cond.get("resultType") == "PASSED"
                 and cond.get("modelSha256") == sha and cond.get("archiveBuildInfo", {}).get("litert_lm") == "v0.18.0"
                 and cond.get("argv", [])[:2] == ["--yardstick-autorun", "--runtime"]
                 and rest == json.loads(json.dumps(rec)) and set(got) - set(template) == {"conditions"})
    ok(good, "each record: device.ddp {deviceId, displayName, osVersion}, conditions.ddp (session, job, execution, "
             "timeout, Xcode, result, runIndex 1-4 in timestamp order, model sha, BUILD_INFO, argv); every other key "
             "as the app wrote it; id kept")
    console = os.path.join(camp, "console_litert-lm_litert-community_Qwen3-1_7B_short-chat.txt")
    text = open(console).read() if os.path.exists(console) else ""
    ok(text.startswith(f"=== DDP session {SID}: {DEVICE}, litert-lm, litert-community/Qwen3-1.7B") and
       text.count("YARDSTICK_RUN_OK") == 4, f"console under bench_matrix_iphone.sh's name, one header ({os.path.basename(console)})")
    plan = json.load(open(os.path.join(sdir, "plan.json"))) if os.path.exists(os.path.join(sdir, "plan.json")) else {}
    ok(sorted(os.listdir(sdir)) == ["args.json", "console.txt", "ddp_session.json", "plan.json", "records.txt",
                                    "yardstick.done"]
       and json.load(open(os.path.join(sdir, "args.json")))[-2:] == ["--litert-backend", "gpu"]
       and "local" not in plan.get("model", {}) and "local" not in plan.get("archive", {})
       and plan.get("catalog", {}).get("displayName") == "iPhone 16 Pro",
       f"ddp/{SID}/ holds the plan (no host path), the session, the argv, console, records.txt, yardstick.done "
       f"({sorted(os.listdir(sdir))})")
    ok(os.path.exists(os.path.join(raw, "system.log")) and os.path.exists(os.path.join(raw, "junit.xml"))
       and os.path.isdir(os.path.join(raw, "artifacts")) and not glob.glob(os.path.join(camp, "ddp", "args-*.json")),
       "ddp-raw/<session>/ holds the pulled tree and the lab's logs; the argv file moved into the session dir")
    before = {f: open(f, "rb").read() for f in out + [console]}
    r2 = driver(["--records-only", sdir], env_for(tmp, gcloud=False))
    after = {f: open(f, "rb").read() for f in out + [console]}
    ok(r2.returncode == 0 and before == after, f"--records-only (no gcloud on PATH) writes the same files, "
       f"the console not appended twice ({r2.returncode}; {r2.stderr[-200:]!r})")
    # exit 4: the job did not pass; its records are still written
    stage_fake(tmp, describe_json(result="FAILED"))
    stage_execution(tmp, recs, stale, gate="waited_s=0\nstate=nominal\ntimed_out=0\n")
    r = billed(tmp, archive, "selftest-ios-ddp-failed")
    ok(r.returncode == 4 and len(glob.glob(os.path.join(tmp, "raw", "selftest-ios-ddp-failed", "device-jsonl", "*.json"))) == 4
       and "<testsuites>" in r.stderr, f"a FAILED job: exit 4, records written, junit's tail shown ({r.returncode})")
    # exit 5: passed, no record
    stage_fake(tmp, describe_json())
    stage_execution(tmp, [], stale, done=None)
    r = billed(tmp, archive, "selftest-ios-ddp-empty")
    ok(r.returncode == 5 and "no record" in r.stderr, f"a passed job with no record: exit 5 ({r.returncode}; {r.stderr[-150:]!r})")
    # exit 3: no gcloud
    r = driver(["--device", DEVICE, "--model-id", "litert-community/Qwen3-1.7B", "--backend", "gpu", "--archive", archive,
                "--campaign", "selftest-ios-ddp-nogcloud"], env_for(tmp, gcloud=False))
    ok(r.returncode == 3 and "gcloud is not on PATH" in r.stderr, f"no gcloud: exit 3 ({r.returncode})")
    # no --project, no --bucket: gcloud's active project, gs://<project>-devicerun; none active: refused
    no_flags = ["--device", DEVICE, "--model-id", "litert-community/Qwen3-1.7B", "--backend", "gpu",
                "--archive", archive, "--campaign", "selftest-ios-ddp-gcloud-project"]
    stage_fake(tmp, describe_json())
    stage_execution(tmp, recs, stale)
    write(os.path.join(tmp, "fake", "project"), PROJECT + "\n")
    open(os.path.join(tmp, "gcloud.log"), "w").close()
    r = driver(no_flags, env_for(tmp))
    calls = gcloud_calls(tmp)
    ok(r.returncode == 0 and "config get-value project" in calls
       and any("device-run sessions submit xctest" in c and f"--project={PROJECT}" in c
               and f"gs://{PROJECT}-devicerun/" in c for c in calls),
       f"no --project, no --bucket: the submit carries gcloud's active project and its devicerun bucket (rc {r.returncode}, {r.stderr[-300:]!r})")
    os.remove(os.path.join(tmp, "fake", "project"))
    open(os.path.join(tmp, "gcloud.log"), "w").close()
    r = driver(no_flags[:-1] + ["selftest-ios-ddp-no-project"], env_for(tmp))
    ok(r.returncode == 2 and "--project: none named" in r.stderr and gcloud_calls(tmp) == ["config get-value project"],
       f"no active project: exit 2 before any other gcloud call (rc {r.returncode}, {gcloud_calls(tmp)})")
    # exit 2: the catalog says the id is not an iPhone
    stage_fake(tmp, describe_json(), devices_platform="ANDROID")
    r = billed(tmp, archive, "selftest-ios-ddp-android")
    ok(r.returncode == 2 and "not an iPhone" in r.stderr, f"a catalog id that is not an iPhone: exit 2 ({r.returncode})")
    # --collect: a session of another cell is refused; the matching one is written
    stage_fake(tmp, describe_json(labels={"model": "litert-community--gemma-4-e2b-it-litert-lm", "backend": "gpu",
                                          "task": "short-chat", "run": "def"}))
    stage_execution(tmp, recs, stale)
    open(os.path.join(tmp, "gcloud.log"), "w").close()
    r = billed(tmp, archive, "selftest-ios-ddp-collect", extra=("--collect", SID))
    ok(r.returncode == 2 and "not what the flags say" in r.stderr
       and not any("sessions submit" in c for c in gcloud_calls(tmp)),
       f"--collect of another cell's session: exit 2, nothing submitted ({r.returncode})")
    stage_fake(tmp, describe_json())
    r = billed(tmp, archive, "selftest-ios-ddp-collect", extra=("--collect", SID))
    ok(r.returncode == 0 and len(glob.glob(os.path.join(tmp, "raw", "selftest-ios-ddp-collect", "device-jsonl", "*.json"))) == 4
       and not any("sessions submit" in c for c in gcloud_calls(tmp)),
       f"--collect of the cell's session: rc 0, 4 records, nothing submitted ({r.returncode}; {r.stderr[-200:]!r})")
    # Documents/out/thermal_gate.txt (DDPHarness's wait before run 1) -> 3 keys of every record's conditions.ddp
    gates = {c: [((json.load(open(f)).get("conditions") or {}).get("ddp") or {})
                 for f in sorted(glob.glob(os.path.join(tmp, "raw", c, "device-jsonl", "*.json")))]
             for c in ("selftest-ios-ddp", "selftest-ios-ddp-failed", "selftest-ios-ddp-collect")}
    keys = ("thermalGateWaitedSeconds", "thermalGateTimedOut", "thermalGateState")
    ok([len(v) for v in gates.values()] == [4, 4, 4]
       and all(tuple(g.get(k) for k in keys) == (600, True, "serious") for g in gates["selftest-ios-ddp"])
       and all(tuple(g.get(k) for k in keys) == (0, False, "nominal") for g in gates["selftest-ios-ddp-failed"])
       and not any(k in g for g in gates["selftest-ios-ddp-collect"] for k in keys),
       "thermal_gate.txt -> conditions.ddp thermalGateWaitedSeconds / thermalGateTimedOut / thermalGateState in "
       "every record (600, true, serious; 0, false, nominal); a session without the file: none of the 3 keys "
       f"({ {c: [tuple(g.get(k) for k in keys) for g in v][:1] for c, v in gates.items()} })")
    # plan.json is committed: the same billed run with HOME = the temp dir that holds the campaign
    stage_fake(tmp, describe_json())
    stage_execution(tmp, recs, stale)
    r = driver(["--device", DEVICE, "--model-id", "litert-community/Qwen3-1.7B", "--backend", "gpu", "--archive",
                archive, "--campaign", "selftest-ios-ddp-home", "--project", PROJECT, "--bucket", BUCKET],
               env_for(tmp, extra={"HOME": tmp}))
    path = os.path.join(tmp, "raw", "selftest-ios-ddp-home", "ddp", SID, "plan.json")
    text = open(path).read() if os.path.exists(path) else ""
    plan = json.loads(text) if text else {}
    ok(r.returncode == 0 and text and tmp not in text and os.path.expanduser("~") not in text
       and not re.search(r"/(Users|home)/", text)
       and plan.get("campaignDir") == "~/raw/selftest-ios-ddp-home"
       and plan.get("argsFile", "").startswith("~/raw/selftest-ios-ddp-home/ddp/args-")
       and [x.get("source") for x in plan.get("push", [])][1:] == [plan.get("argsFile")],
       f"plan.json with HOME = the temp dir: the campaign dir, the argv file and its push source start with ~; "
       f"no home path, no /(Users|home)/ path ({r.returncode}; {plan.get('campaignDir')}, {plan.get('argsFile')})")
    return camp, template


# ---------------------------------------------------------------- 4. build_summary

def check_summary(tmp, camp, template):
    print("--- 4. build_summary into a temp dir: the DDP iPhone row's device column, never the attached iPhone's")
    sum_root = os.path.join(tmp, "sumroot")
    dst = os.path.join(sum_root, "results", "raw", "selftest-ios-ddp")
    shutil.copytree(os.path.join(camp, "device-jsonl"), os.path.join(dst, "device-jsonl"))
    att = json.loads(json.dumps(template))
    att["device"]["modelIdentifier"] = "iPhone17,1"
    write(os.path.join(sum_root, "results", "raw", "selftest-ios-attached", "device-jsonl", "attached.json"),
          json.dumps(att))
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import build_summary
    with patch.object(build_summary, "ROOT", sum_root), patch.object(build_summary, "OUT", os.path.join(sum_root, "summary")):
        os.makedirs(build_summary.OUT, exist_ok=True)
        with contextlib.redirect_stdout(io.StringIO()):
            path, _ = build_summary.build_device()
    rows = list(csv.DictReader(open(path)))
    ddp = [r for r in rows if r["campaign"] == "results/raw/selftest-ios-ddp"]
    att_rows = [r for r in rows if r["campaign"] == "results/raw/selftest-ios-attached"]
    ok(len(ddp) == 4 and {r["device"] for r in ddp} == {"iPhone17,1 (DDP iphone16pro-18-3)"}
       and {r["platform"] for r in ddp} == {"ios"} and {r["engine_version"] for r in ddp} == {"v0.18.0"}
       and {r["runtime"] for r in ddp} == {"litert-lm"},
       f"device column 'iPhone17,1 (DDP iphone16pro-18-3)', platform ios, engine v0.18.0 "
       f"({sorted({r['device'] for r in ddp})})")
    ok(att_rows and {r["device"] for r in att_rows} == {"iPhone17,1"},
       f"the attached iPhone's record keeps its own device ({sorted({r['device'] for r in att_rows})})")


# ---------------------------------------------------------------- 5. run_ddp_ios_matrix

def check_matrix(tmp, archive, shas, template):
    print("--- 5. run_ddp_ios_matrix: cells plan, register_archive_builder, BENCH_RAW_ROOT, --no-keep-raw")
    sys.path.insert(0, HERE)
    import run_ddp_ios_matrix as mat
    cells_file = os.path.join(tmp, "matrix.cells")
    write(cells_file, (
        "mac litert-lm litert-community/Qwen3-1.7B short-chat backend=gpu runs=4\n"
        "ios core-ai apple/Foundation-Models short-chat backend=ane\n"
        "ios litert-lm litert-community/Qwen3-1.7B short-chat backend=gpu context-tokens=2048 runs=4\n"
        "ios litert-lm litert-community/Qwen3-1.7B/int8 short-chat backend=cpu ynnpack=1 runs=2\n"
        "ios litert-lm litert-community/gemma-4-E2B-it-litert-lm short-chat backend=gpu exclude=skip-me\n"
        "ios litert-lm litert-community/gemma-4-E2B-it-litert-lm energy backend=gpu manual=1\n"
    ))
    planned = mat.plan_cells([cells_file], None, "litert", {}, None)
    ok(len(planned) == 2 and [c.name for c in planned] == ["litert-lm-gpu", "litert-lm-cpu-ynnpack"]
       and planned[1].app_args == ("--litert-ynnpack", "on"),
       f"plan_cells (--engines litert) skips core-ai, picks the 2 runnable ios rows and names ynnpack=1 ({[c.name for c in planned]})")
    try:
        mat.plan_cells([cells_file], None, "all", {}, None)
        ok(False, "plan_cells (--engines all) must still reject core-ai")
    except ValueError as exc:
        ok("has no DDP lab build" in str(exc), f"plan_cells (--engines all) rejects core-ai ({exc})")
    # --model-dir with unstaged paths succeeds in dry_run and fails outside dry_run.
    unstaged = {"litert-community/qwen3-1.7b": mat.pathlib.Path(tmp) / "not-yet-staged"}
    ok(len(mat.plan_cells([cells_file], None, "litert", unstaged, None, dry_run=True)) == 2,
       "plan_cells dry_run=True allows unstaged --model-dir paths")
    try:
        mat.plan_cells([cells_file], None, "litert", unstaged, None, dry_run=False)
        ok(False, "plan_cells dry_run=False must reject missing --model-dir files")
    except ValueError as exc:
        ok("missing local file(s)" in str(exc), f"plan_cells dry_run=False rejects missing files ({exc})")
    recs, stale = fixture_records(template)
    stage_fake(tmp, describe_json())
    stage_execution(tmp, recs, stale)
    sha, _ = shas["litert-community/Qwen3-1.7B"]
    model_obj = f"automation/inputs/edge-llm-bench/models/{sha}/Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm"
    write(os.path.join(tmp, "fake", "bucket", "fake-bucket", model_obj), "already there\n")

    built_calls = []

    def custom_builder(engines, archives_dir, args):
        built_calls.append(tuple(engines))
        os.makedirs(archives_dir, exist_ok=True)
        shutil.copyfile(archive, os.path.join(archives_dir, "BenchmarkApp-ddp-litert-xctest.zip"))
        return 0

    mat.register_archive_builder("custom", custom_builder)
    one_cell = os.path.join(tmp, "one.cells")
    write(one_cell, "ios litert-lm litert-community/Qwen3-1.7B short-chat backend=gpu context-tokens=2048 runs=4\n")
    raw_dir = os.path.join(tmp, "matrix-raw")
    arch_dir = os.path.join(tmp, "matrix-archives")
    with patch.dict(os.environ, env_for(tmp, extra={"BENCH_RAW_ROOT": raw_dir}), clear=True):
        with contextlib.redirect_stdout(io.StringIO()):
            rc = mat.main([one_cell, "--device", DEVICE, "--project", PROJECT, "--bucket", BUCKET,
                           "--campaign", "mat-camp", "--archives-dir", arch_dir,
                           "--archive-builder", "custom", "--no-keep-raw"])
    camp_dir = os.path.join(raw_dir, "mat-camp")
    plan_path = os.path.join(camp_dir, "ddp", SID, "plan.json")
    plan_data = json.load(open(plan_path)) if os.path.exists(plan_path) else {}
    ok(rc == 0 and built_calls == [("litert",)]
       and len(glob.glob(os.path.join(camp_dir, "device-jsonl", "*.json"))) == 4
       and "--context-tokens" in plan_data.get("args", [])
       and not os.path.exists(os.path.join(camp_dir, "ddp-raw")),
       f"register_archive_builder + BENCH_RAW_ROOT + --no-keep-raw: rc={rc}, 4 records, --context-tokens forwarded, "
       "ddp-raw removed")

    # ynnpack=1 cpu session stamps litert-lm-cpu-ynnpack on records after matching litert-lm-cpu;
    # and --no-keep-raw keeps ddp-raw/ when a session fails so --records-only can still read it back.
    cpu_recs = []
    for name, rec in recs[:2]:
        crec = json.loads(json.dumps(rec))
        crec["runtime"] = "litert-lm-cpu"
        crec["model"]["id"] = "litert-community/Qwen3-1.7B/int8"
        cname = name.replace("litert-lm_", "litert-lm-cpu_").replace("Qwen3-1.7B_", "Qwen3-1.7B_int8_")
        cpu_recs.append((cname, crec))
    sha_i8, _ = shas["litert-community/Qwen3-1.7B/int8"]
    i8_obj = f"automation/inputs/edge-llm-bench/models/{sha_i8}/Qwen3_1.7B.litertlm"
    write(os.path.join(tmp, "fake", "bucket", "fake-bucket", i8_obj), "already there\n")
    ynn_cell = os.path.join(tmp, "ynn.cells")
    write(ynn_cell, "ios litert-lm litert-community/Qwen3-1.7B/int8 short-chat backend=cpu ynnpack=1 runs=2\n")
    stage_fake(tmp, describe_json(result="FAILED"))
    stage_execution(tmp, cpu_recs, stale)
    with patch.dict(os.environ, env_for(tmp, extra={"BENCH_RAW_ROOT": raw_dir}), clear=True):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc_fail = mat.main([ynn_cell, "--device", DEVICE, "--project", PROJECT, "--bucket", BUCKET,
                                "--campaign", "mat-ynn-fail", "--archives-dir", arch_dir,
                                "--archive-builder", "prebuilt", "--no-keep-raw"])
    ynn_camp = os.path.join(raw_dir, "mat-ynn-fail")
    ynn_written = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(ynn_camp, "device-jsonl", "*.json")))]
    ok(rc_fail == 1 and len(ynn_written) == 2
       and {r["runtime"] for r in ynn_written} == {"litert-lm-cpu-ynnpack"}
       and os.path.isdir(os.path.join(ynn_camp, "ddp-raw", SID)),
       f"ynnpack=1 stamps litert-lm-cpu-ynnpack and --no-keep-raw keeps ddp-raw on failure "
       f"(rc={rc_fail}, runtimes={[r['runtime'] for r in ynn_written]})")

    # --jobs: rejects <1, and runs sessions concurrently while deduplicating shared archive/model/device checks.
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            mat.main([one_cell, "--jobs", "0"])
            ok(False, "--jobs 0 must exit 2")
        except SystemExit as exc:
            ok(exc.code == 2, f"--jobs 0 exits 2 ({exc.code})")

    par_cells = os.path.join(tmp, "par.cells")
    write(par_cells, (
        "ios litert-lm litert-community/Qwen3-1.7B short-chat backend=gpu runs=2\n"
        "ios litert-lm litert-community/Qwen3-1.7B native-benchmark-1024x256 backend=gpu context-tokens=2048 runs=2\n"
    ))
    nat_recs, _ = native_records(template)
    par_art_short = os.path.join(tmp, "par-short")
    par_art_nat = os.path.join(tmp, "par-nat")
    for adir, cell_recs in ((par_art_short, recs[:2]), (par_art_nat, nat_recs)):
        os.makedirs(os.path.join(adir, "artifacts"), exist_ok=True)
        for n, rec in cell_recs:
            write(os.path.join(adir, "artifacts", n), json.dumps(rec))
        write(os.path.join(adir, "artifacts", "records.txt"), "".join(n + "\n" for n, _ in cell_recs))
        write(os.path.join(adir, "artifacts", "yardstick.done"), "0\n")
        write(os.path.join(adir, "artifacts", "console.txt"), "YARDSTICK_ALL_DONE\n")
        write(os.path.join(adir, "system.log"), "ok\n")
        write(os.path.join(adir, "junit.xml"), "<testsuites/>\n")

    # Wipe the fake bucket so both archive + model must be uploaded once across the 2 concurrent cells.
    shutil.rmtree(os.path.join(tmp, "fake", "bucket"), ignore_errors=True)
    par_barrier = threading.Barrier(2, timeout=5.0)
    par_counts = {"devices": 0, "ls": 0, "upload": 0}
    par_lock = threading.Lock()
    par_sessions = {}

    def fake_object_exists(url):
        with par_lock:
            par_counts["ls"] += 1
        return os.path.exists(os.path.join(tmp, "fake", "bucket", url.removeprefix("gs://")))

    def fake_gcloud(*args):
        if args[:2] == ("storage", "cp") and args[2] != "-r":
            src, url = args[2], args[3]
            dst = os.path.join(tmp, "fake", "bucket", url.removeprefix("gs://"))
            with par_lock:
                par_counts["upload"] += 1
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(src, dst)
            return ""
        if args[:3] == ("storage", "cp", "-r"):
            sid_match = re.search(r"/sessions/(session-[^/]+)/", args[3])
            sid_here = sid_match.group(1)
            src_dir = par_art_nat if par_sessions[sid_here] == NATIVE_TASK else par_art_short
            dst_dir = args[-1].rstrip("/")
            shutil.copytree(os.path.join(src_dir, "artifacts"), os.path.join(dst_dir, "artifacts"))
            shutil.copyfile(os.path.join(src_dir, "system.log"), os.path.join(dst_dir, "system.log"))
            shutil.copyfile(os.path.join(src_dir, "junit.xml"), os.path.join(dst_dir, "junit.xml"))
            return ""
        raise AssertionError(f"unexpected gcloud call: {args}")

    def fake_gcloud_json(*args, project=None):
        if args[:4] == ("beta", "device-run", "devices", "list"):
            with par_lock:
                par_counts["devices"] += 1
            return [{"displayName": "iPhone 16 Pro", "osVersion": "18.3", "platform": "IOS",
                     "modelCode": "iphone16pro", "name": f"projects/{PROJECT}/locations/global/devices/{DEVICE}"}]
        if args[:5] == ("beta", "device-run", "sessions", "submit", "xctest"):
            par_barrier.wait()  # proves both cells execute concurrently in the ThreadPoolExecutor
            labels = dict(kv.split("=", 1) for kv in (flag(args, "--labels") or "").split(",") if "=" in kv)
            sid_here = f"session-{labels['run']}"
            with par_lock:
                par_sessions[sid_here] = labels["task"]
            return [{"name": f"projects/{PROJECT}/locations/global/sessions/{sid_here}"}]
        if args[:4] == ("beta", "device-run", "sessions", "describe"):
            sid_here = args[4]
            desc = describe_json()
            desc["name"] = f"projects/{PROJECT}/locations/global/sessions/{sid_here}"
            pfx = f"gs://fake-bucket/automation/sessions/{sid_here}/job-000/execution-1111-2222/"
            desc["sessionReport"]["jobReports"][0]["executionReports"][0]["outputFiles"] = [
                {"gcsOutputFile": {"path": f"{pfx}system.log"}},
                {"gcsOutputFile": {"path": f"{pfx}junit.xml"}},
                {"gcsOutputFile": {"path": f"{pfx}artifacts/console.txt"}},
            ]
            return desc
        raise AssertionError(f"unexpected gcloud_json call: {args}")

    with patch.dict(os.environ, env_for(tmp, extra={"BENCH_RAW_ROOT": raw_dir}), clear=True), \
         patch.object(mat.run_ddp_ios_lm, "object_exists", side_effect=fake_object_exists), \
         patch.object(mat.run_ddp_ios_lm, "gcloud", side_effect=fake_gcloud), \
         patch.object(mat.run_ddp_ios_lm, "gcloud_json", side_effect=fake_gcloud_json), \
         contextlib.redirect_stdout(io.StringIO()):
        rc_par = mat.main([par_cells, "--device", DEVICE, "--project", PROJECT, "--bucket", BUCKET,
                           "--campaign", "mat-par", "--archives-dir", arch_dir,
                           "--archive-builder", "prebuilt", "--jobs", "2", "--no-keep-raw"])
    par_camp = os.path.join(raw_dir, "mat-par")
    par_written = sorted(glob.glob(os.path.join(par_camp, "device-jsonl", "*.json")))
    ok(rc_par == 0 and len(par_written) == 4 and par_counts == {"devices": 1, "ls": 2, "upload": 2}
       and not os.path.exists(os.path.join(par_camp, "ddp-raw")),
       f"--jobs 2 runs 2 sessions concurrently, deduplicates device/model/archive checks ({par_counts}), "
       f"writes all 4 records and removes ddp-raw (rc={rc_par})")


# ---------------------------------------------------------------- 6. native-benchmark rows

def native_records(template):
    """Two records of the Qwen3-1.7B GPU native-benchmark-1024x256 cell in the shape the app writes
    (NativeBenchmarkRecord in ios/BenchmarkApp/Sources/BenchmarkApp.swift: no parameters, no outputSample,
    in metrics what the call measured), and one stale record of an earlier session."""
    base = fixture_records(template)[0][0][1]
    recs = []
    for i, stamp in enumerate(["2026-10-17T00-03-05.120Z", "2026-10-17T00-04-20.340Z", "2026-10-16T09-00-00.000Z"]):
        rec = {"id": str(uuid.uuid4()).upper(), "schemaVersion": 1,
               "timestamp": f"{stamp[:13]}:{stamp[14:16]}:{stamp[17:19]}Z", "device": base["device"],
               "runtime": "litert-lm", "engineVersion": base["engineVersion"], "engineArtifact": base["engineArtifact"],
               "model": base["model"], "task": NATIVE_TASK,
               "metrics": {"coldRun": i == 0, "promptTokenCount": 1024, "generatedTokenCount": 256,
                           "promptTokensPerSecond": 900.0, "decodeTokensPerSecond": 40.0, "firstTokenLatencyMS": 1200.5,
                           "loadTimeSeconds": 6.1, "memoryPeakDuringDecodeMB": 2100.0, "memoryMedianMB": 1800.0,
                           "memoryMedianResidentMB": 2500.0, "memorySampleCount": 120,
                           "memoryPostTeardownFootprintMB": 300.0, "contextTokensConfigured": 2048, "wallSeconds": 20.5,
                           "initialThermalState": "nominal", "finalThermalState": "nominal",
                           "harnessStamp": "2026-07-30-agreed-protocol-r4"},
               "conditions": {"instrument": f"litert-lm native benchmark() via BenchmarkApp --task {NATIVE_TASK}",
                              "run": i + 1, "runs": 2}}
        recs.append((f"litert-lm_litert-community_Qwen3-1.7B_{NATIVE_TASK}_{stamp}.json", rec))
    return recs[:2], recs[2]


def check_native(tmp, archive, template):
    print("--- 6. native-benchmark rows: the argv, the refusals, the records, the summary, the matrix's cool-wait")
    sys.path.insert(0, HERE)
    import run_ddp_ios_matrix as mat
    import validate_cells
    mid = "litert-community/Qwen3-1.7B"
    env = env_for(tmp)
    # the app's map: the same words as the cells grammar, and the counts the engine reports, not the request
    app = open(os.path.join(ROOT, "ios", "BenchmarkApp", "Sources", "BenchmarkApp.swift")).read()
    ok('let prefix = "native-benchmark-"' in app and "promptTokenCount: info.prefillTokenCount" in app
       and "generatedTokenCount: info.decodeTokenCount" in app,
       "BenchmarkApp.swift maps the task and records the engine's token counts")
    ok(mat.run_ddp_ios_lm.NATIVE_TASK.fullmatch(NATIVE_TASK) and validate_cells.NATIVE_TASK.match(NATIVE_TASK),
       "the driver and scripts/validate_cells.py read one task name")
    # the dry run: the task goes to the app as it stands
    r = driver(["--device", DEVICE, "--model-id", mid, "--backend", "gpu", "--archive", archive, "--campaign", "x",
                "--task", NATIVE_TASK, "--context-tokens", "2048", "--runs", "2", "--dry-run"], env)
    rows = json_lines(r.stdout)
    labels = dict(kv.split("=", 1) for kv in (flag(rows.get("command") or [], "--labels") or "").split(",") if "=" in kv)
    ok(r.returncode == 0 and rows.get("args") == ["--yardstick-autorun", "--runtime", "litert-lm", "--model-id", mid,
                                                  "--task", NATIVE_TASK, "--runs", "2", "--context-tokens", "2048",
                                                  "--litert-backend", "gpu"]
       and labels.get("task") == NATIVE_TASK,
       f"the app's argv and the task label carry {NATIVE_TASK} ({rows.get('args')})")
    # the refusals, before any gcloud call
    open(os.path.join(tmp, "gcloud.log"), "w").close()
    base = ["--device", DEVICE, "--archive", archive, "--campaign", "x", "--dry-run"]
    litert = ["--model-id", mid, "--backend", "gpu"]
    for extra, why in ((litert + ["--task", "native-benchmark-1024"], "a task with no decode count"),
                       (litert + ["--task", "native-benchmark-0x256"], "a zero token count"),
                       (["--runtime", "llama.cpp", "--model-id", "unsloth/Qwen3.5-0.8B-GGUF/Q4_0", "--backend", "gpu",
                         "--task", NATIVE_TASK], "another runtime")):
        r = driver(base + extra, env)
        ok(r.returncode == 2 and "native-benchmark" in r.stderr, f"exit 2 for {why} ({r.returncode}: {r.stderr.strip()[-120:]!r})")
    ok(gcloud_calls(tmp) == [], "the refusals called gcloud 0 times")
    # the billed path: the records as the app writes them, none added, none lost
    recs, stale = native_records(template)
    stage_fake(tmp, describe_json())
    stage_execution(tmp, recs, stale)
    write(os.path.join(tmp, "fake", "execution", "artifacts", "console.txt"),
          "YARDSTICK_BEGIN native_benchmark model=litert-community/Qwen3-1.7B prefill=1024 decode=256 runs=2\n"
          + "".join(f"YARDSTICK_NATIVE_OK run={i} runs=2 prefill_tokens=1024 decode_tokens=256\n" for i in (1, 2)))
    r = billed(tmp, archive, "selftest-ios-ddp-native", extra=("--task", NATIVE_TASK, "--context-tokens", "2048", "--runs", "2"))
    camp = os.path.join(tmp, "raw", "selftest-ios-ddp-native")
    written = {os.path.basename(f): json.load(open(f)) for f in glob.glob(os.path.join(camp, "device-jsonl", "*.json"))}
    ok(r.returncode == 0 and sorted(written) == sorted(n for n, _ in recs),
       f"rc 0; device-jsonl/ = the 2 records named in records.txt ({r.returncode}, {sorted(written)}, {r.stderr[-200:]!r})")
    good = True
    for idx, (name, rec) in enumerate(recs, 1):
        got = written.get(name) or {}
        cond = dict(got.get("conditions") or {})
        ddp = cond.pop("ddp", {})
        good &= (got.get("metrics") == rec["metrics"] and cond == rec["conditions"] and ddp.get("runIndex") == idx
                 and got.get("task") == NATIVE_TASK and "parameters" not in got and "outputSample" not in got)
    ok(good, "each record: metrics and conditions as the app wrote them, plus conditions.ddp; no parameters, no outputSample")
    ok("YARDSTICK_NATIVE_OK run=2" in r.stdout
       and os.path.isfile(os.path.join(camp, "console_litert-lm_litert-community_Qwen3-1_7B_native-benchmark-1024x256.txt")),
       "the driver prints the native lines; the console keeps the attached runner's name")
    # the summary: the row build_summary makes of them
    sum_root = os.path.join(tmp, "sumroot-native")
    shutil.copytree(os.path.join(camp, "device-jsonl"),
                    os.path.join(sum_root, "results", "raw", "selftest-ios-ddp-native", "device-jsonl"))
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import build_summary
    with patch.object(build_summary, "ROOT", sum_root), patch.object(build_summary, "OUT", os.path.join(sum_root, "summary")):
        os.makedirs(build_summary.OUT, exist_ok=True)
        with contextlib.redirect_stdout(io.StringIO()):
            path, _ = build_summary.build_device()
    rows = list(csv.DictReader(open(path)))
    ok(len(rows) == 2 and {r["task"] for r in rows} == {NATIVE_TASK} and {r["prompt_tokens"] for r in rows} == {"1024"}
       and {r["gen_tokens"] for r in rows} == {"256"} and {r["context_tokens"] for r in rows} == {"2048"}
       and {r["device"] for r in rows} == {"iPhone17,1 (DDP iphone16pro-18-3)"}
       and sorted(r["cold_run"] for r in rows) == ["False", "True"],
       f"build_summary: 2 rows, 1024 / 256 at context 2048, the DDP device column, one cold ({rows[:1]})")
    # the matrix: a row's cool-wait= is the native path's flag there, the task path's elsewhere
    cells = os.path.join(tmp, "native.cells")
    write(cells, f"ios litert-lm {mid} {NATIVE_TASK} backend=gpu context-tokens=2048 runs=2 cool-wait=60\n"
                 f"ios litert-lm {mid} short-chat backend=gpu runs=2\n")
    native_cell, task_cell = mat.plan_cells([cells], None, "litert", {}, None)
    ns = mat.argparse.Namespace(device=DEVICE, extra_catalog=None, cool_wait=45, runs=4, project=PROJECT, bucket=BUCKET,
                                campaign="x", dry_run=True)
    argv = mat.session_argv(native_cell, mat.pathlib.Path(archive), ns)
    ok(argv[argv.index("--task") + 1] == NATIVE_TASK and "--app-arg=--native-cool-wait" in argv and "--app-arg=60" in argv
       and "--app-arg=--cool-wait" not in argv,
       f"session_argv: {NATIVE_TASK} with --native-cool-wait 60 ({argv})")
    argv = mat.session_argv(task_cell, mat.pathlib.Path(archive), ns)
    ok("--app-arg=--cool-wait" in argv and "--app-arg=--native-cool-wait" not in argv,
       f"session_argv: a task row keeps --cool-wait ({argv})")


def main():
    tmp = tempfile.mkdtemp(prefix="ios-ddp-selftest-")
    try:
        check_models()
        shas = hf_cache(os.path.join(tmp, "hf"))
        archive = check_dry_runs(tmp, shas)
        camp, template = check_billed(tmp, archive, shas)
        check_summary(tmp, camp, template)
        check_matrix(tmp, archive, shas, template)
        check_native(tmp, archive, template)
    except Exception as exc:  # noqa: BLE001 — a crash is a failure with the temp dir kept
        import traceback
        traceback.print_exc()
        ok(False, f"selftest crashed: {exc!r}")
    if _fails:
        print(f"\n{len(_fails)} of {_count[0]} check(s) failed; temp dir kept: {tmp}")
        return 1
    shutil.rmtree(tmp)
    print(f"\nios ddp selftest OK ({_count[0]} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
