speed ladder: n-a: bench backend lane, no conversion, no form to ship (supervisor 2026-10-15)

# D6 DDP backend — lane close (round 6, Opus 5.5, 2026-10-15)

Lane: `./bench matrix <cells> --ddp <device id>` (Route C, `android/ddp/`), rounds 1–5 on branch `ddp-backend`
(1d6c7ad, 6c0b894, 0ed15f0, 0f9e551, 94d4ff5, the supervisor's f2b64fa) and this round's commit, which carries
this file. Round notes: `ROUND6.md`. Nothing measured, no device, no DDP session, no code or docs change.

litert-data: not run — no gate JSON, no compat device-run rows; the measurements are bench records (results/raw/2026-10-15-ddp-{smoke,slice}-*) and the summary

## public 反映 (proposals; draft `r6/public-reflection-draft.md`, no other repo touched)

| target | what | when / who |
|---|---|---|
| own repo `skills/run-edge-llm-bench/SKILL.md` | a section "Lab phones without adb (Developer Device Platform)" between "The two ad-hoc cases" and "Symptoms": the two commands, one job = one unit = its own sitting, capped lab units, `conditions.engineCache`, the logcat scrub; the description and "Tested on" lines gain DDP | in the `ddp-backend` PR or right after it, on the user's GO (supervisor); the assets row's `skill` cell (hold) can point to it after its blind run |
| litert-samples `skills/benchmark-on-ddp/SKILL.md` (the DDP skill upstream) | four "Watch for" bullets: a session's jobs run at once on separate units, some lab units start with lowered CPU ceilings, job args are split at spaces, pulled logcats carry the lab network's identifiers; an optional fifth bullet pointing LiteRT-LM cells with a prompt file to `bench matrix --ddp` (the user decides: it names the user's own harness) | Draft PR through /litert-team after the push, on the user's GO |
| litert-samples `skills/on-device-verification/SKILL.md` (the launch's candidate) | none: its loop is CompiledModel parity of a converted `.tflite`; this lane checked nothing about parity or residency on DDP | — |
| hf-to-litertlm (tools, docs, AGENTS.md Route row, llms.txt) | none: not a conversion lane, no converter step or Route changed | — |
| `~/code/standup/knowledge/litert.md` | one line (written, staged; below) | done in this round |

## diff 一覧

Memory (`~/.claude/projects/-Users-USER-code-edge-llm-bench/memory/`, the main checkout's slug):
- new `ddp-job-is-its-own-unit.md` (2,031 B, project): a session's jobs start together on separate lab units = every job its own sitting, never pooled; the session report names only the device id; args split at spaces; `executionTimeout` 1 min to 3 h; CPU-cap state per unit (`cpucapWaitSeconds`).
- new `ddp-logcat-carries-lab-network-ids.md` (1,741 B, feedback): never stage a pulled logcat that `android/ddp/scrub.py` has not processed; the exclude pathspec; residue checks by the scrub's prefixes; unlike the user name, the lab's identifiers must not reach a public commit.
- edited `litertlm-xnnpack-cache-name-jitter.md` (1,377 → 1,979 B, folded, not appended): the name jitter, plus a later process rebuilding under a name an earlier one wrote, a GPU run skipping its program cache, the proof lines, `conditions.engineCache` on DDP records, the litert-cli `touch` (its comment, not measured); the evidence figures of the old body left to its pointer.
- `MEMORY.md`: + 2 lines (the two new files, after the DDP litertlm line), 1 line rewritten (the edited file's title and hook). The index is 10,753 B (10,406 B before this round, already over the 10 KB bar; 62 lines): trimming other entries is not this round's call.
- not written: candidate (d) "the quiet-window hook reads heredoc bodies" — `mac-quiet-window-leaks.md` already says "The hook reads whole commands (heredocs, paths …)".

Handoff `~/code/standup/handoffs/2026-10-15-D6-dashboard-ddp-backend.md` (staged, not committed):
- header and 状態 line: the new SHAs, r6, K's file list, LANE's new path;
- §0 事実: + 4 lines (the rewrite old → new per commit, the backup branch, difference % kept out of the public repo, the CI DDP selftest step that exits 1 without the pinned binaries), `K/LANE.md` references → LANE;
- §2: one cross-reference "(§4 r2)" → "(§6 訂正 r2)"; §5 untouched (byte-equal to the staged copy);
- §3 GO log: + the supervisor's 20:0x rewrite line; the remaining GOs with the new SHAs and the CI decision;
- §4 訂正: replaced by a pointer to §6 (its 19 lines are in §6 with their round tags);
- §6 知見: rewritten as 84 one-fact lines with round tag and evidence (訂正 33 / 罠と袋小路 38 / op と delegate の観察 13) from ROUND1–5, LANE §0 with its r4 corrections, and this round's CI finding;
- §7 残り: push / PR / release / CI with the new SHAs, the CI decision, assets knowledge done, the public-reflection proposals, lane close done.
- `grep -nE '6efe1b2|9ae798b|9179dbd|099d76b'` = 2 lines, both in §0 and both saying 旧.

LANE (`K/LANE.md`, untracked, the supervisor's lane record with text that is not for the public repo) moved to
`~/code/standup/handoffs/2026-10-15-D6-dashboard-ddp-backend-LANE.md` (sha256 equal before and after), staged there; not in the worktree any more.

Knowledge: `~/code/standup/knowledge/litert.md` + 1 line at the end ("2026-10-15 edge-llm-bench DDP backend (lane D6): `./bench matrix <cells> --ddp <device id> …` … → lane close `results/raw/2026-10-15-ddp-backend-dev/LANE_CLOSE.md`, handoff …, lane memory …"). Only that line is staged: the file also carries another session's unstaged line, which `git add` would have swept in, so the index got the index copy plus this line (`git hash-object -w` + `git update-index --cacheinfo`); the other line stays unstaged.

Assets row `edge-llm-bench-ddp-backend` (through `assets.py`, behind `quiet_wait.py`): knowledge todo → done (ref `~/code/standup/knowledge/litert.md`); repo stays hold, its note refreshed (the new SHAs, the rewrite done, the CI step); `render` rc 0; the three ledger files differ from their pre-run copies in this row only. Lint (`r6/assets-lint.log`):
`HOLD edge-llm-bench-ddp-backend [tool] 3/6 done — open: repo=hold(public after the push GO …), skill=hold(the runbook …), article=hold(user decides …)` (rc 3).

litert-compat: no commit (no `/litert-data`).

Deleted (`D6_deleted_paths.txt`): `dry-run/android-selftest.done` (28 B) and `dry-run/android-selftest.log` (68,171 B) — untracked; the same proof is committed as `r4/android-selftest.{done,log}`.

Kept, with the reason:
- `<campaign>/ddp-raw/` in the three campaign dirs (3 + 32 + 32 files, gitignored): the logcats' bytes before the scrub = the originals.
- the 17 execution-level `logcat.txt` in the three campaign dirs (untracked, scrubbed in place since r4): out of every commit since r2; the bucket holds the pulled bytes too.
- `r2/` … `r5/`, `fixtures/`, `dry-run/*.txt`, `DESIGN.md`, `ROUND1.md` … `ROUND5.md` (committed): the lane's evidence.
- the bucket `gs://litert-edge-portal-devicerun` objects (inputs and the three sessions' outputs): never deleted (LANE §1 D11).
- branch `backup/ddp-backend-2026-10-15-pre-rewrite` (the supervisor's, not pushed): untouched.
- this session's scratchpad: deleted at the end of the round.

Staged in `~/code/standup` by this round (not committed): `handoffs/2026-10-15-D6-dashboard-ddp-backend.md`, `handoffs/2026-10-15-D6-dashboard-ddp-backend-LANE.md`, `knowledge/litert.md` (this lane's line only), `tools/assets/assets.jsonl`, `state/assets.md`, `knowledge/assets-ledger.md`. Staged by other sessions and left as they were: `handoffs/2026-10-15-T1c-qwen3-4b-17b-gpu-exports.md`, `launch/2026-10-15-T1c-qwen3-4b-17b-opus-r{2,4,5}.md`, `state/google-litert.md`.

For the supervisor before the push: f2b64fa's CI step `python android/ddp/selftest.py` exits 1 on a GitHub runner as written (`android/bin/v0.18.0/` is gitignored and no workflow step puts it in place; `android/ddp/selftest.py` 1158–1162) — handoff §0 / §3 / §7.
