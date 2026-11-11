# Draft PR for google-ai-edge/litert-samples (not opened; push and `gh pr create --draft` are the supervisor's, after GO)

- Head: `john-rocky:skills-benchmark-on-ddp-lab-notes` (worktree `~/code/litert-samples-ddp-skill-wt`,
  commit edfe9307 on upstream/main 2166c0f9), base `main`.
- Title (= the commit subject):
  `skills/benchmark-on-ddp: add five Watch for notes on lab units, job arguments, pulled logcats and LiteRT-LM prompt runs`
- The body is the EN block below, as is. The JA block is for the user's check only and does not go into the PR.

## EN (the PR body)

```markdown
Adds five notes to the Watch for section of `skills/benchmark-on-ddp/SKILL.md`, after "DDP device names come from the matrix". Nothing else in the file changes (10 added lines). No measurement is added, so `Tested on` is unchanged.

Where each note comes from (Device Run sessions and code that are public; the session files are in [edge-llm-bench](https://github.com/john-rocky/edge-llm-bench)):

- **A session's jobs run at once, each on its own lab unit.** The 2026-10-15 sessions `session-d5585b53` (akita-35) and `session-9002dfea` (m1q-36) each started 8 jobs within 0.05 s on 8 units (8 `ro.serialno` values per id), and their session reports name only the device id: `results/raw/2026-10-15-ddp-slice-akita-35-android/` and `results/raw/2026-10-15-ddp-slice-m1q-36-android/`, `ddp/session-1.json` and each job's `provenance.txt`.
- **Some lab units start with lowered CPU clock ceilings.** In `session-9002dfea` all 24 runs on the 8 m1q-36 units started with policy0 at 3187 of 3629 MHz and policy6 at 3398 of 4742 MHz (`scaling_max_freq` / `cpuinfo_max_freq`); the 24 runs on the akita-35 units of `session-d5585b53` started at the hardware maximum. Each run's `run<i>.state` in the same directories.
- **Job arguments are split at spaces.** The 13 `args` of a job's request arrived on the unit as 18 (`argc: 18`): `results/raw/2026-10-15-ddp-smoke-akita-35-android/`, `ddp/request-1.json` and the job's `provenance.txt`.
- **Pulled logcats carry the lab network's identifiers.** The kinds the edge-llm-bench driver replaces after each pull are listed in `android/ddp/scrub.py`; the counts per campaign are in each campaign's `ddp/scrub.json`.
- **A LiteRT-LM run with a real prompt file.** On LiteRT-CLI main (59d612e), a bundle's DDP job runs fixed benchmark flags and pushes only the bundle and the binary directory (`litert_cli/commands/benchmark/ddp.py`, `_build_lm_benchmark_args` and `_lm_pushes`). edge-llm-bench's `bench matrix <cells> --ddp <id>` pushes a prompt file with its own LiteRT-LM build (`docs/ddp-integration.md`, "Route C as `bench matrix --ddp`").
```

## JA(確認用、PR には入れない)

`skills/benchmark-on-ddp/SKILL.md` の Watch for 節に、「DDP device names come from the matrix」の後へ 5 つの注意を足します。この file の他の行は変えていません(追加 10 行)。計測は足していないので `Tested on` はそのままです。

各注意の出所(公開されている Device Run の session と code。session の file は [edge-llm-bench](https://github.com/john-rocky/edge-llm-bench) にあります):

- **session の job は同時に、それぞれ別の lab 個体で走る。** 2026-10-15 の `session-d5585b53`(akita-35)と `session-9002dfea`(m1q-36)は、どちらも 8 job を 0.05 秒以内に 8 個体で始めました(id ごとに `ro.serialno` が 8 種類)。session report には device id しか出ません: `results/raw/2026-10-15-ddp-slice-akita-35-android/` と `results/raw/2026-10-15-ddp-slice-m1q-36-android/` の `ddp/session-1.json` と各 job の `provenance.txt`。
- **CPU の clock 上限が下がった状態で始まる lab 個体がある。** `session-9002dfea` では m1q-36 の 8 個体の 24 run すべてが policy0 3187 / 3629 MHz、policy6 3398 / 4742 MHz で始まりました(`scaling_max_freq` / `cpuinfo_max_freq`)。`session-d5585b53` の akita-35 の 24 run は hardware の上限で始まりました。同じ dir の各 run の `run<i>.state`。
- **job の引数は空白で割られる。** job の request の `args` 13 個が、個体の上では 18 個で届きました(`argc: 18`): `results/raw/2026-10-15-ddp-smoke-akita-35-android/` の `ddp/request-1.json` と job の `provenance.txt`。
- **pull した logcat には lab の network の識別子が入る。** edge-llm-bench の driver が pull の後に置き換える種類は `android/ddp/scrub.py` に、campaign ごとの件数は各 campaign の `ddp/scrub.json` にあります。
- **本物の prompt file を使う LiteRT-LM の run。** LiteRT-CLI の main(59d612e)では、bundle の DDP job は固定の benchmark flag で走り、push するのは bundle と binary の directory だけです(`litert_cli/commands/benchmark/ddp.py` の `_build_lm_benchmark_args` と `_lm_pushes`)。edge-llm-bench の `bench matrix <cells> --ddp <id>` は自前の LiteRT-LM build で prompt file を push します(`docs/ddp-integration.md` の「Route C as `bench matrix --ddp`」)。

## The five bullets as committed (edfe9307, `skills/benchmark-on-ddp/SKILL.md` lines 80-89)

Read back with `git -C ~/code/litert-samples-ddp-skill-wt show HEAD:skills/benchmark-on-ddp/SKILL.md`
(`K/ROUND3.md` 経過 has the per-bullet sources with file:line).
