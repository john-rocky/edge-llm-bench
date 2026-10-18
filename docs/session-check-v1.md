# Session checker v1 — the commit review of a job sitting, as code

Status: written 2026-10-18 (stage 1 of the bench-autopilot lane), not yet wired into the job.
Code: `scripts/session_check.py`; selftest `scripts/session_check_selftest.py` (CI, data
pipeline); allow-list `ops/session-check/allow-list.tsv`. Validation record:
`results/raw/2026-10-18-bench-autopilot-dev/ROUND1.md`.

The dashboard job (`scripts/dashboard_job.py`, `docs/dashboard-recurring-job-v1.md`) never
commits: a person reads each campaign dir it made and commits it with a message that says what
ran and what reproduced (§6 of the job doc). This checker does that reading for the points the
212 commits under `results/raw` show people checked, and says per dir:

| verdict | meaning |
|---|---|
| PASS | commit as is — every rule passed, or each finding is excused by an allow-list line |
| HOLD | a person decides (and says so in the commit message) |
| FAIL | do not commit the dir as it is |

```bash
python3 scripts/session_check.py results/raw/<campaign>... [--json <out>] [--markdown <out>]
#   exit 0 = every dir PASS, 1 = a HOLD or a FAIL, 2 = usage (not a dir, a malformed allow-list)
#   --history <csv>   prompt-token history (default: results/summary/device-runs.csv at git HEAD)
#   --ledger / --job-logs   default: <repo>/logs/dashboard-job/{ledger.tsv,*.log}
#   --user <name>     the account name to look for in paths (default: this account)
```

It reads only: the dirs, the git index and HEAD of the repo that holds them, the pin registries
as they were committed when the sitting ran (`git log` of `android/engine-pins.json` and
`environment.lock.json`), and the job's logs and ledger. No device, no network, nothing written
but `--json` / `--markdown`. 77 dirs take about 12 s on the Mac Studio.

## What it reads per dir

- **Kind.** `job anchor` / `job payload`: a `SESSION.json` with `schema`
  `dashboard-job-session.v1` and `job` `dashboard-v1` (what `write_session` stamps), or a
  `-dashboard-v1-` dir with no `SESSION.json` whose campaign a job log names (`--campaign <name>`;
  without job logs the name decides). `DDP`: a `ddp/` or `ddp-session/` subdir, `-ddp-` in the
  name, or records with `device.ddp`. `dev`: a name ending in `-dev`. `job (stopped)`: `-stopped-`
  in the name. Everything else is a `hand run`, including hand sittings that wrote a
  `SESSION.json` with another `job` text.
- **Records** — what `scripts/build_summary.py` reads: `app-path*/*.json` and
  `device-jsonl/*.json` at any depth and the dir's own `*.jsonl` (a Mac native-benchmark cell's
  `.jsonl` is one `YARDSTICK_NATIVE_OK` line by design, c32f4705, and is read through
  `app-path-native/`); quarantined captures (`*.attempt1`, `device-jsonl-flagged/`,
  `*.quarantine-*`) are not records here either.
- **Files the commit would carry** — tracked or untracked and not ignored (`git ls-files`); outside
  a git work tree every file counts.
- **The reply of each run** — `outputSample` (Apple); the stored `*.decoded.txt` (Android
  context-prompt launches); else read out of the run's engine log: `litert_lm_main` short-chat
  between its `input_prompt:` line and `BenchmarkInfo:`, `litert_lm_advanced_main` through
  `android/bench/parsers.litert_reply`, llama-cli after its prompt echo and backspace spinner up
  to `[ Prompt: … ]` (else `parsers.llama_cli_reply`), ONNX Runtime GenAI between
  `[OUTPUT BEGIN]` and `[OUTPUT END]`. Protocol cells (`native-benchmark-*`, benchmark mode)
  decode no text and have none.

## Rules

Every rule has a source: the commit whose message shows a person checking it, or the doc section
that sets it. A finding carries the rule id and a detail; one finding per cell or per file.

| id | verdict | source | reads | passes when |
|---|---|---|---|---|
| `not-admitted` | FAIL | 046c4dab (job doc §4, §5: a sitting admitted or refused on its anchor; "a refused sitting is never partially kept"); e3010721, 0efecb01 (the admission and its ratio stated in the commit); `render_dashboard.load_admission` | `SESSION.json` `admitted`, `verdict`, `reason` | `admitted` is not false. One case is re-read: a payload with verdict TIMEOUT and reason `anchor-short` whose dir holds ≥ 2 usable primary-anchor runs (the job re-judged it on a summary `bench matrix` never rebuilt, killed at the timeout) — the admission is unjudged and the dir gets `verdict` instead |
| `session-missing` | FAIL | 046c4dab (job doc §1 close: "`SESSION.json` in every campaign dir it created", §6); e998c56c ("each with `SESSION.json`") | `SESSION.json`; the job logs | a job dir has its `SESSION.json` (none = the sitting was killed before its close) |
| `stopped-sitting` | FAIL | e3010721 (the stopped 01:42 sitting's records "kept out of this commit (an uncommitted quarantine dir)") | the dir name | the name has no `-stopped-` |
| `logcat-unscrubbed` | FAIL | f231ad66 (`android/ddp/scrub.py` on every pulled logcat), 0186dcd5 / d6077c6b ("execution-level logcat.txt kept out, run logcats scrubbed") | the logcats of a DDP dir (or under `ddp/`, `ddp-session/`) | no `execution-*/logcat.txt` would be committed, and `scrub.scrub_text` would replace nothing in the others |
| `big-file` | FAIL | `.gitignore` "Models and weights — never commit" and `android/bin/` (ca5dfe6e); 73620406 (trace bundles, perf.data stay local); f3db1b23 (".perfetto-trace files stay on the measuring machine") | file names, ELF / Mach-O magic, ignore status | no weights (`.litertlm .gguf .pte .onnx .safetensors .tflite .task .mlpackage .mlmodelc .aimodel …`), trace (`.perfetto-trace`, `.trace`, `perf.data`) or engine binary (`.so .dylib .a .apk .aar`, executables) would be committed; none ever has been under `results/raw` |
| `secret` | FAIL | c32f4705 (an Instruments trace stores the traced process's environment, shell credentials included); the lane rule that an env dump carries `ANTHROPIC_API_KEY` | text of the files the commit would carry | no Anthropic / Hugging Face / GitHub / AWS / Google / Slack credential pattern and no private key |
| `pair-broken` | FAIL | job doc §1 (the anchor probe is its own campaign and admission reads it); e998c56c, 936c5ca3 ("each with `SESSION.json`") | payload `anchor_phase` | the anchor phase dir is on disk with an admitted `SESSION.json` |
| `verdict` | HOLD | 046c4dab (job doc §5, timeout: "look at the log"); 84364fc1 (verdict DEVICE: "re-run the missing cells by hand") | `SESSION.json` `verdict` | the verdict is not TIMEOUT or DEVICE |
| `partial` | HOLD | 65a36964, 69131de8, 178f0750 (people named the cells without records) | `cells_with_records`, `cells_expected` | every expected cell has records (as the job counted them at its close) |
| `runner-exit` | HOLD | `docs/OPERATIONS.md` Known limits ("read the job log's tail, not only the ledger, before calling a sitting clean"); 90c96a11 | `runner_exit` | 0 (124 is `verdict`) |
| `failures` | HOLD | job doc §6 (a person reads `FAILURES.txt`); 936c5ca3, 178f0750 | `FAILURES.txt` (dir and `app-path-android/`); the line's cell's record count | no line. Known exception (allow-list): the Mac llama.cpp teardown abort after the runs (c7b60c2b), when the cell has records |
| `flagged` | HOLD | job doc §5 table: LEVEL → "a targeted retake", DEGENERATE → "read the sample … never quote the rate"; b6ddcb2c (GATE_ERROR = a gate that crashed) | `FLAGGED.txt` | no LEVEL / DEGENERATE / GATE_ERROR line and no line outside the `GATE_FAIL` form. A HOT / SPREAD / DEAD / COLLAPSE retry is a note: §5 gives it no human step, the table renders it ⚠ |
| `text-fail` | HOLD | c6498ccd (job doc §5 "Decoded-text check": "read the stored text before the campaign is committed"; fairness-rules §12); edab6ed9 | `conditions.textCheck` | no run FAIL |
| `engine-stamp` | HOLD | CLAUDE.md (rows stamp the observed engine, which may differ from the registry); edab6ed9, 0efecb01, d6077c6b, e3010721 ("every LiteRT-LM record stamps v0.18.0") | `engineVersion`; `android_pins` (since d33ffa53, else the lock's Android tags) and `environment.lock.json` as committed at the sitting's first record | each arm's records carry one stamp, and it is the registry's pin (a whole version token of the stamp). Side builds (`llama.cpp-npu/-gpu`, `litert-lm-npu`) and arms without a registry entry are notes |
| `prompt-tokens` | HOLD | edab6ed9 ("Prefill Turn 1: 9 tokens; v0.16.0: 20 / 1339"), d6077c6b ("the short-chat prompt reaches the engine whole … 19 tokens Qwen3, 20 Gemma 4 … 1338 / 1106"), e3010721 (20); job doc §4 "Model bytes on the phone" (8 tokens) | `metrics.promptTokenCount`; the committed summary | every count equals the mode of the committed history for the same platform, build, arm, model and task (admitted campaigns, text-check FAIL rows and this sitting left out). No history at all: a note, not a HOLD |
| `prompt-newtag` | HOLD | edab6ed9 (the first v0.18.0 sitting read 9 where v0.16.0 read 20) | as above | with no history on this build, the count is within 10 % of some other build's mode. In the committed history the largest difference between builds for one cell is 5 % (Qwen3 4B short-chat 20 → 19, v0.16.0 → v0.18.0); a prompt that did not reach the engine reads 55 % low |
| `reply-empty` / `reply-loop` / `reply-off-task` | HOLD | e3010721 ("the replies read as answers to the prompt"), edab6ed9 ("answer the question"); fairness-rules §12 (`parsers.text_integrity`: empty, off the task's subject, repetition loop) and §4 (a loop is a failed run); 6dbaa099 (`cell_gate` DEGENERATE) | the reply of each run (above), for cells the runner's own text check did not judge | `text_integrity` raises no flag and `cell_gate.degenerate` is false. The task prompts' subject is on-device AI, so a reply naming none of its terms is off the prompt |
| `gen-budget` | HOLD | 8bd4cd71 (thought-channel tokens decoded past the 128 / 256 cap: the rate's window held them); b6ddcb2c (`litert_lm_main` v0.16.0 ignores `--max_output_tokens`) | `generatedTokenCount` vs `parameters.maxTokens` / `conditions.outputTokenBudget` | no run past its budget (where the record names one) |
| `invalid-decode` | HOLD | aaf64c5e ("invalid decode results at normal throughput"); ee240588 ("0 Invalid decode"); schema `vlInvalidDecodeLines` ("any > 0 voids the rate") | `conditions.invalidDecodeCount`, `metrics.vlInvalidDecodeLines`, `Invalid decode` lines of the run's log | none |
| `model-sha-source` | HOLD | job doc §4 "Model bytes on the phone (correction, 2026-10-15)"; f41b3661 (`push_verified` hashes the phone's copy); 0efecb01, d6077c6b ("modelShaSource device") | Android records after f41b3661: `provenance.modelShaSource` | `device` (the bytes on the phone were hashed) |
| `debug-build` | HOLD | fairness-rules §7 same-build-config; 5ad10ba8 (a Debug-build launch set aside) | `device.buildConfiguration` | not a Debug build |
| `raw-log-missing` | HOLD | ca5dfe6e, 0a6717bd (stored-report-rule: a number without a stored report is not a measurement) | `provenance.rawLog` beside the record, in the dir, or at its `results/raw/` path | every named log is there |
| `record-unreadable` | HOLD | c32f4705, 43fe4ffb (a record the summary cannot parse is never read: the Mac native line is lifted into `app-path-native/`); `build_summary.py` skips what it cannot parse | the record files | every one parses |
| `pair-incomplete` | HOLD | e998c56c, 936c5ca3, 422983c7 (the anchor and payload dirs of a sitting committed together) | `anchor_phase` both ways; git index | the other half is committed or in the same check |
| `reference-uncommitted` | HOLD | 0684f014 ("the anchor SESSION.json name the two skill-smoke campaigns as their admission reference, and the records existed on disk only"); 422983c7 | the primary anchor's `reference.campaign` | the reference is committed or in the same check |
| `user-name` | HOLD | d25a9985 / 8208edff / dde2149e / ceeaa362 (the account name → `USER` in `/Users/<name>`, `-Users-<name>-`, `_bazel_<name>` and `ls` owner columns); edab6ed9, af2c8b42 ("The user name in paths reads USER") | text of the files the commit would carry | none of those forms. Hygiene, not a secret: a HOLD to scrub, never a FAIL |
| `big-file-size` | HOLD | the largest file ever committed under `results/raw` is 4,961,673 bytes (`git ls-tree`, 2026-10-18); 114a32e8 ("The raw logits stay out of the repo") | file size | no other file over 5 MB |
| `not-job` | HOLD | 046c4dab (job doc §6: the commit is a person's step); 46235e36 (a hand retake beside the job's dirs, read through its own NOTES) — these rules are the job session's | the kind | the dir is a job campaign |

Notes, never a verdict: HOT / SPREAD / DEAD / COLLAPSE retries, `SKIPPED.txt` lines, an
admission on a non-nominal start, cpu-capped runs (past the 15 % line or counted — the
renderer's cpu-cap-rule already pools or drops each run), `firstEver` runs, cells with no prompt
history, arms with no registry entry, a committed dir with untracked files beside it.

## The allow-list

`ops/session-check/allow-list.tsv`: one excused finding per line, five tab-separated fields —
rule, dir glob, match (`*`, a substring of the detail, or `re:<regex>`), the commit whose message
gives the reason, and the reason. A line goes in only when that commit message states the reason;
a finding no commit explains stays HOLD or FAIL, and the round records it (ROUND1.md "訂正").
An excused finding is still printed, with its commit. A malformed line (not five fields, no hash,
a bad regex) is a usage error, exit 2.

Two kinds of lines: known exceptions that hold for any dir (the Mac llama.cpp teardown abort,
c7b60c2b; the Qwen3 0.6B LiteRT-LM bundle whose chat template predates 0.18 and leaves the user
turn empty on every v0.18.0 sitting, e3010721 / edab6ed9), and per-dir lines for committed
sittings whose commit message explained the finding.

## A person reads

The machine proxies above screen every reply; none reads it for meaning. The `--markdown` output
lists one reply per cell (the first non-empty one) under "A person reads one reply per cell", and
its table counts them per dir. A PASS never stands for that reading.

## Not covered

What the 212 commits show people doing that no rule here does yet — the per-run sampler review of
a CPU cap's mechanism, Mac quiet-window CPU samples, local (non-DDP) logcats, the bundle-id name in
iOS consoles — is listed with its reason in ROUND1.md "提案".
