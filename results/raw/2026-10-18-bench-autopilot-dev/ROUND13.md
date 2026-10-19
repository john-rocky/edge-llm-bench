# ROUND13 — llama.cpp arm: render the GGUF's own chat template (jinja) — worker edge-llm-bench-wt-autopilot-tmpl-b1 [24da3a] (Opus 5.5), started 2026-10-19 10:17 JST

Supervisor: edge-llm-bench-55 [4f120b]. Worktree `~/code/edge-llm-bench-wt-autopilot-tmpl`, branch `llama-chat-template` (from be17d5a4).
REPO = the worktree, MAIN = `~/code/edge-llm-bench`, SIDE = `MAIN/.build/dd-ios-0180-18pro/src`, K = this dir. Scratchpad = this session's
(e1bf9561) scratchpad dir (`tools/`, `probe/`, `render/`, `logs/`).

**Result**: the Apple llama.cpp adapter now renders the GGUF's own chat template (Gemma 4 with `enable_thinking: false`, Qwen3 with the
template's default) and every llama.cpp record carries `conditions.chatTemplate` / `conditions.thinking`. Mac smoke: all five cells
`jinja`; Gemma 4 prompt 12 → 20 (short-chat) and 1098 → 1106 (1K) = LiteRT-LM's counts; Qwen3 unchanged (19 / 1338, `<think>` replies).
The E4B 1K "[Item 1] …" skeleton is gone; with the template and greedy decoding E4B now **declines the lorem task in 86 tokens** — the same
words llama.cpp's own llama-cli gives with `--temp 0` and the same template (LiteRT-LM's and MLX's E4B decline too). Mac yardstick
(`MAIN/.build/dd-mac-tmpl`) built, not switched; iPhone app built, and on the 18 Pro by 11:17 (the supervisor's install: its llama-b11721
sitting's llama.cpp records carry `conditions.chatTemplate` jinja).

## 下見
- 10:17:43 JST. REPO `llama-chat-template` at be17d5a4, clean. MAIN on main (its HEAD moves with the backlog posts).
- `LlamaCppRuntime.swift` sha256 `62091ebd…` = REPO = SIDE = MAIN. Every app source file (`ios/BenchmarkApp/Sources`,
  `apple/YardstickCLI/Sources`) REPO = SIDE (`cmp`, no file missing or extra); `project.yml` and `BenchmarkApp.xcodeproj/project.pbxproj`
  REPO = SIDE (pbxproj `d6307a43…`).
- Jinja: swift-jinja **2.4.2** (`7d0b8880`, 2026-07-21) in `MAIN/.build/dd-ios-0180-18pro/SourcePackages/checkouts/swift-jinja`, a dependency
  of swift-transformers 1.3.3 (`2fa33e1f`), whose `Tokenizers` renders chat templates with
  `Template(s, with: .init(lstripBlocks: true, trimBlocks: true)).render([String: Jinja.Value])`. `Jinja.swiftmodule` is built into the same
  products dir as `Tokenizers.swiftmodule` (Mac `dd-mac`, iPhone `dd-ios-0180-18pro`) = importable without a project change. `HuggingFace`
  exports its own `Value`: the adapter writes `Jinja.Value` (swift-transformers does the same).
- The bench's GGUFs (HF cache, refs/main; scratchpad `tools/gguf_meta.py` reads the metadata):

| file | snapshot | blob | `tokenizer.chat_template` sha256 | chars | BOS / EOS | add_bos |
|---|---|---|---|---|---|---|
| gemma-4-E4B-it-Q4_K_M.gguf | bfc15c38 | 85a896a0… | 241c50d8… | 18,808 | `<bos>` 2 / `<turn\|>` 106 | true |
| gemma-4-E2B-it-Q4_K_M.gguf | 0314792d | 740185b2… | 241c50d8… (same) | 18,808 | `<bos>` 2 / `<turn\|>` 106 | true |
| Qwen3-0.6B-Q4_K_M.gguf | 50968a44 | ac2d9771… | 5da44855… | 4,905 | none / `<\|im_end\|>` 151645 | false |
| Qwen3-1.7B-Q4_K_M.gguf | d7f544ee | b1399498… | 8428c815… | 4,761 | none / `<\|im_end\|>` 151645 | false |
| Qwen3-4B-Q4_K_M.gguf | 22c9fc8a | f6f85177… | 5da44855… (= 0.6B) | 4,905 | none / `<\|im_end\|>` 151645 | false |

- The Gemma 4 template's own default is thinking off (`{%- set enable_thinking = enable_thinking | default(false) -%}`); the Qwen3 template
  thinks unless `enable_thinking` is false (`{%- if enable_thinking is defined and enable_thinking is false %}` adds the empty think block).
- Prompt-token counts of the 10-19 rebuilt Mac sitting (`MAIN/results/raw/2026-10-19-dashboard-v1-m4max-0180-rebuilt-mac/`), short-chat / 1K:
  llama.cpp Gemma 4 E2B **12 / 1098**, E4B **12 / 1098** (both bare); LiteRT-LM Gemma 4 E2B / E4B 20 / 1106; MLX Gemma 4 OptiQ E2B / E4B
  21 / 1107; Qwen3 0.6B / 1.7B / 4B 19 / 1338 on every arm (llama.cpp, MLX, LiteRT-LM, Core AI, ExecuTorch, ONNX Runtime GenAI). REPO's
  committed summary: every Mac / iPhone llama.cpp Gemma 4 row reads 12 / 1098 / 1629 (2K ladder) = bare on every date; text_check
  `FAIL:reply-empty,reply-off-task` on the Mac E4B 1K rows only, `PASS:screen` on the Mac E2B and short-chat rows, none on the iPhone rows.
- Reference renders (scratchpad `tools/ref_render.py`: Python jinja2 3.1.6 the HF way, trim_blocks + lstrip_blocks + loopcontrols; one user
  turn, add_generation_prompt) counted with llama-tokenize b11721 on each GGUF's vocab (`tools/ref_count.sh`: the leading `<bos>` stripped,
  the vocab's BOS added, parse_special on; bare = the prompt file, parse_special off):

| model | task | bare | rendered, thinking false / not passed | rendered, thinking true |
|---|---|---|---|---|
| Gemma 4 E4B (= E2B template) | short-chat | 12 | 20 | 27 |
| Gemma 4 E4B (= E2B template) | long-context-1024-gen256 | 1098 | 1106 | 1113 |
| Qwen3 0.6B (= 4B template) | short-chat | 11 | 19 | — |
| Qwen3 0.6B (= 4B template) | long-context-1024-gen256 | 1330 | 1338 | — |
| Qwen3 1.7B | short-chat / 1K | 11 / 1330 | 19 / 1338 | — |

## 設計
- **描画の入力** (`LlamaCppRuntime.compileChatTemplate`, the HF / llama.cpp `apply_chat_template` of one user turn): `messages` =
  `[{"role": "user", "content": prompt}]`, `add_generation_prompt` = true, `bos_token` / `eos_token` = the vocab's BOS / EOS token text
  (`llama_token_to_piece(…, special: true)`, "" for LLAMA_TOKEN_NULL — what llama.cpp's common_chat passes), `enable_thinking` only when
  `ModelInfo.chatTemplateThinking` is set. Options trim_blocks + lstrip_blocks (= transformers, = llama.cpp's jinja engine).
- **compile at load, render in generate**: the template is parsed in `loadModel` (outside the timed window; the probe: 23–36 ms for the
  Gemma 4 template, ~5 ms for Qwen3); `generate` only renders (≤ 0.22 ms in the probe, 0.83 ms on the yardstick's first run, printed per
  run as `render_ms`), inside the TTFT window as the tokenization already was.
- **swift-jinja 2.4.2 gap**: its lexer applies `{%-` / `{{-` / `-%}` / `-}}` but not the comment forms `{#-` / `-#}`, so the Gemma 4
  template's `{%- endif %}`, blank line, `{#- Pre-scan … -#}` rendered one `\n` after `<bos>` (+1 token; the probe's first comparison: 87 vs
  86 chars). The adapter applies the comment whitespace control to the source before compiling (4 regex steps, swift-jinja's own `{%-`
  pass mirrored). With it the probe's renders = Python jinja2 byte for byte, 10 of 10 (E4B thinking false / not passed / true, Qwen3 0.6B /
  1.7B, both tasks; scratchpad `tools/swift_vs_ref.sh`, `probe/jinja-probe`).
- **BOS**: the Gemma 4 template writes `<bos>`; when the vocab adds BOS (`llama_vocab_get_add_bos`) the leading BOS text is dropped and the
  tokenizer adds it (add_special) = exactly one BOS, as llama.cpp's common_chat `apply` and its server tokenization do. The built-in set
  writes no BOS (unchanged: addBOS true).
- **fallback**: jinja → `llama_chat_apply_template` (built-in set) → bare. Console per run: `YARDSTICK_NOTE chat_template=jinja
  thinking=<v> render_ms=<ms>`; on a fallback `YARDSTICK_WARN chat_template_jinja_unavailable=<why>` and then `YARDSTICK_NOTE
  chat_template=builtin thinking=template-default` or `YARDSTICK_WARN chat_template=bare thinking=none (no chat template applied: not a
  measurement)`.
- **record**: `conditions.chatTemplate` (jinja / builtin / bare), `conditions.thinking` (true / false = passed; "template-default" = nothing
  passed; absent on bare). Wiring (supervisor GO 10:3x): `LLMRuntime.recordConditions` (default nil, as `recordedContextTokens`),
  `BenchmarkResult.conditions` (optional: nil = no key = every other arm's record unchanged), `BenchmarkRunner` one argument. The readers of
  `conditions` (build_summary, session_check, dashboard_post) read textCheck / protocolFlags / cpuMaxFreqMHz / backendRegistered /
  contextTokens only.
- **thinking, per family** (`ModelInfo.chatTemplateThinking`, nil = not passed): every Gemma 4 GGUF row `false` (E2B QAT, E2B, E4B, 12B),
  Qwen3 nil. Table in `methodology/fairness-rules.md` §1:

| family | LiteRT-LM | MLX | llama.cpp (Mac / iPhone) | others on the Mac | evidence |
|---|---|---|---|---|---|
| Gemma 4 E2B / E4B | off, nothing passed (MediaPipeRuntime has no thinking key) | off, nothing passed (`UserInput(prompt:)`; the repo template defaults to false) | off: `enable_thinking: false` | — | direct replies in the 10-19 records |
| Qwen3 0.6B / 1.7B / 4B | on | on | on: nothing passed ("template-default") | on (Core AI, ExecuTorch, ORT GenAI) | replies open with `<think>` (LiteRT-LM: the thought text) |

- **no project change**: `import Jinja` under `#if canImport(Jinja)`; the other three committed projects compile the same file and would
  stamp builtin / bare if their graph had no Jinja. No new source file = no xcodegen.

## build の行と UUID
- Mac (SIDE → `MAIN/.build/dd-mac-tmpl`; r9's line, SourcePackages an APFS clone of `dd-ios-0180-18pro/SourcePackages`, in a quiet hold):
  `xcodebuild -project BenchmarkApp.xcodeproj -scheme yardstick -configuration Release -destination "platform=macOS,arch=arm64"
  -derivedDataPath MAIN/.build/dd-mac-tmpl -onlyUsePackageVersionsFromResolvedFile -skipPackagePluginValidation -skipMacroValidation
  ARCHS=arm64 ONLY_ACTIVE_ARCH=YES build` — BUILD SUCCEEDED 10:39:00–10:40:34; incremental after the comment-only edit 11:08:36–11:09:10
  (nothing relinked). `yardstick` sha256 **5579ae3a…cad47d**; `libCLiteRTLM_mac.dylib` 9526db9e… (= v0.18.0) UUID 4C4C440A (dyld);
  `llama.framework` UUID **843E7D68** (= b11721 macOS slice, = r9); the jinja branch in the binary (`strings`: 0 hits for "no Jinja module in
  this build"). `yardstick version`: flavor=full harness=2026-07-30-agreed-protocol-r4.
- Pins: the build's stamp writes SIDE's `Vendored/engine-pins.json` (a regular file); MAIN's and SIDE's pins sha256 `f9f0c846…` before =
  after both builds. SIDE's pins: litert-lm v0.18.0, llama.cpp b11721, mlx-swift 60bd0d78, core-ai 1.0.0-10-gbd3c539, cactus 1ace6d78,
  onnxruntime-genai 0.17.0.
- iPhone (SIDE, r9's `ios_build_r9.sh` line: `xcodebuild build -project BenchmarkApp.xcodeproj -scheme BenchmarkApp -configuration Release
  -destination generic/platform=iOS -derivedDataPath MAIN/.build/dd-ios-0180-18pro -allowProvisioningUpdates
  -allowProvisioningDeviceRegistration -skipPackagePluginValidation -skipMacroValidation DEVELOPMENT_TEAM=MFN25KNUGJ
  PRODUCT_BUNDLE_IDENTIFIER=com.example.CoreMLLLMChat`) — BUILD SUCCEEDED 11:11:30–11:12:04. `BenchmarkApp.app` main binary sha256
  **f4246030…6192a4** (r9's 06:06 build: 554dffca…); `Frameworks/llama.framework/llama` UUID **6226C23F** (= before, = b11721 ios-arm64);
  `Frameworks/CLiteRTLM.framework/CLiteRTLM` UUID **8B273118** (= before); bundle pins llama.cpp b11721 / `llama-b11721-xcframework.zip`,
  litert-lm v0.18.0, core-ai 1.0.0-10-gbd3c539; bundle id / signing `com.example.CoreMLLLMChat` / team MFN25KNUGJ; the jinja string is in the
  binary, the compiled-out marker is not. The r9 app is kept beside it: `BenchmarkApp.app.r9-20261019-0606` (APFS clone).
- Warnings in the touched files: the two lines that were there before (LlamaCppRuntime.swift 130 `_ =` on a Void, 167 unused `model`).

## smoke の表
`MAIN/results/raw/2026-10-19-llama-template-probe-mac/` (not committed), 11:09:11–11:11:30, the main tree's Mac runner called directly
(`DD_MAC=MAIN/.build/dd-mac-tmpl`, `BENCH_ENGINE_PINS_FILE` = SIDE's pins), cells = the launch's four + Gemma 4 E4B short-chat, runs=1,
cooldown 30 s (a template check: the speeds are not used). Every record: `engineVersion` b11721, `device.buildConfiguration` Release, the
schema validates (scratchpad `tools/schema_check_r13.py`, jsonschema 4.26.0). Before = the 10-19 rebuilt sitting's record of the same cell.

| cell | chatTemplate / thinking | prompt tokens before → after | generated | reply, first 80 chars (after) | reply before |
|---|---|---|---|---|---|
| Qwen3 0.6B short-chat | jinja / "template-default" | 19 → 19 | 128 length | `<think>\nOkay, the user is asking for an explanation of on-device AI in simple te` | `<think>\nOkay, the user is asking for an exp…` |
| Qwen3 1.7B 1K | jinja / "template-default" | 1338 → 1338 | 256 length | `<think>\nOkay, the user wants me to list 25 distinct things that on-device AI can` | `<think>\nOkay, the user wants me to list 25 …` |
| Gemma 4 E2B 1K | jinja / false | 1098 → 1106 | 256 length | `The provided text is entirely placeholder "Lorem ipsum" text and contains no act` | `\n\n1. **On-Device Image Recognition for rea…` |
| Gemma 4 E4B short-chat | jinja / false | 12 → 20 | 128 length | `Imagine you have a smart assistant on your phone, like Siri or Google Assistant.` | `\n\n**Think of it like this:** Instead of se…` |
| Gemma 4 E4B 1K | jinja / false | 1098 → 1106 | **86 stop** | `I am sorry, but the passage you provided is placeholder "Lorem ipsum" text. It c` | `\n\n1. [Item 1]\n2. [Item 2]\n3. [Item 3]\n4…` |

- `FAILURES.txt` lists all five: the runner marks the exit code, and every launch ends in the known Metal teardown abort after its record
  (crash reports `yardstick-2026-10-19-110923.ips` / `-110950.ips`: `ggml_abort` ← `ggml_metal_rsets_free` ← `ggml_metal_device_free` ←
  the device `unique_ptr`'s destructor; r9 found the same on b11721).
- The runner keeps only the last 4 console lines of a launch, so the smoke stored no `YARDSTICK_NOTE`; one direct yardstick launch (E4B
  short-chat, runs=1, output in the scratchpad `ys/`, 11:15:25) printed `YARDSTICK_NOTE chat_template=jinja thinking=false render_ms=0.83`,
  record jinja / false / 20 tokens, the same reply.
- **llama-cli greedy cross-check** (11:13:57, quiet hold): llama-cli b11721, the E4B GGUF, the same 1K prompt, `-st -n 256 -c 2048 -b 2048
  -ub 512 --temp 0 --jinja --chat-template-kwargs '{"enable_thinking": false}'` → "I am sorry, but the passage you provided is placeholder
  "Lorem ipsum" text. It contains no meaningful information about the capabilities of on-device AI versus cloud models. Therefore, I cannot use
  it as context to answer your request. If you provide a passage …, I would be happy to generate a list of 25 distinct points for you." (412
  chars) — the harness's 200-char sample word for word. The launch's llama-cli read that answered with a list carried no `--temp` (the
  CLI's own sampling); the harness decodes greedily.
- MLX side check (scratchpad `tools/mlx_plus1_check.sh`): the MLX repo's `chat_template.jinja` (`mlx-community/gemma-4-e4b-it-qat-OptiQ-4bit`)
  rendered by swift-jinja without the comment pass = 21 / 1107 tokens (`<bos>\n<|turn>user…`), with it = 20 / 1106 = the MLX records' +1 is
  this gap.

## commit
- **aaae422a** (branch `llama-chat-template`, not pushed, not merged; author / committer rockyshikoku@gmail.com, no attribution lines),
  then a second commit with this hash and the round-close lint line: `ios/BenchmarkApp/Sources/Runtimes/LlamaCppRuntime.swift`,
  `…/Runtimes/LLMRuntime.swift`, `…/Models/BenchmarkResult.swift`, `…/Benchmark/BenchmarkRunner.swift`, `…/Models/ModelCatalog.swift`,
  `schema/result.v1.json`, `methodology/fairness-rules.md`, `docs/dashboard-cells-v1.md`, K `ROUND13.md`, K `SPEED_LADDER.md`. No
  project.yml / pbxproj change. SIDE carries the same five source files (cmp = REPO), outside the commit.
- Round-close lint (`~/code/standup/tools/opus/round_close_lint.sh`): `PASS round close: results/raw/2026-10-18-bench-autopilot-dev/ROUND13.md`.

## 監督が打つ物
1. **dd-mac の切り替え**: the job's Mac route → `MAIN/.build/dd-mac-tmpl` (yardstick sha256 `5579ae3a…`), pins file = SIDE's
   `Vendored/engine-pins.json` (unchanged, `f9f0c846…`). Same LiteRT-LM dylib (`9526db9e…`) and llama.framework (843E7D68) as the r9 build
   the job uses now; only the Swift code differs (the chat template; `conditions` on llama.cpp records).
2. **install** — done by the supervisor before 11:17 (the 18 Pro's llama-b11721 sitting's first llama.cpp record, 11:21:19, carries
   `conditions.chatTemplate` jinja); the line for the record: `xcrun devicectl device install app --device 00008160-000038CA02C00036
   ~/code/edge-llm-bench/.build/dd-ios-0180-18pro/Build/Products/Release-iphoneos/BenchmarkApp.app`; record 1 must then read
   `device.buildConfiguration` Release and, on a llama.cpp row, `conditions.chatTemplate` jinja (Gemma 4: thinking false). Backing out:
   `BenchmarkApp.app.r9-20261019-0606` beside it. r9's 0.6B file copy line (ROUND9 "iPhone app の build と install の 1 行") is unchanged.
3. **re-measure**: Mac `python3 scripts/dashboard_job.py m4max --cells matrices/dashboard-llama-b11721-mac.cells --suffix llama-b11721 --once`
   (the file's header line) after the switch; iPhone `matrices/dashboard-llama-b11721-ios.cells` after the install. Each holds the four Gemma 4
   rows (short-chat + 1K, E2B + E4B) and the six Qwen3 rows. Not in them: the Mac 2K ladder's llama.cpp Gemma 4 rows
   (`matrices/dashboard-longctx-v1.cells` l.83–, bare too: 1,629 prompt tokens). Expect the E4B 1K cell to end early (86 tokens: the
   decline), like the LiteRT-LM and MLX E4B 1K cells.

## 提案
1. **checker `template-bare`**: `scripts/session_check.py` holds a llama.cpp record whose `conditions.chatTemplate` is `bare` (the
   runtime's own mark), and, for records without `conditions` (before 2026-10-19), a Gemma 4 GGUF record whose prompt count is the bare one
   (12 short-chat / 1098 1K / 1629 2K on the Gemma 4 vocab), so the page stops showing those numbers before the re-measure (the 18 Pro's E4B
   1K, 30.71 in LANE.md 04:3x, is one).
2. **the E4B 1K decline**: with the template applied, greedy Gemma 4 E4B declines the lorem 1K task on every arm (llama.cpp, LiteRT-LM, MLX),
   so the cell's decode rate is taken over the decline (86 tokens here), not over 256; E2B answers after a note. The `-noref` tail
   (`LongContextTask.norefTail`) made both Gemma 4 bundles fill 256 tokens on the S26 (catalog X2): a protocol decision for every arm, as the
   LANE.md 10:13 note says.
3. **other GGUF templates**: the catalog's other llama.cpp files (Llama 3.2 1B, Qwen2.5 0.5B, Qwen3.5 0.8B / 2B / 9B, Qwen3 8B / 14B, LFM2.5,
   MiniCPM5, Gemma 4 12B, the Google E2B QAT) now take the jinja path too; their renders were not compared (no dashboard cells file has
   them). Before one enters a cells file: a render vs Python jinja2 and a llama-tokenize count (scratchpad `tools/swift_vs_ref.sh`,
   `tools/ref_count.sh`), and a thinking decision against its other arms.
4. **swift-jinja upstream**: comment whitespace control (`{#-` / `-#}`) is not applied by swift-jinja 2.4.2 (`Lexer.preprocess` handles `{%-`
   / `{{-` / `-%}` / `-}}` only). It reaches the MLX arm through swift-transformers: MLX's Gemma 4 prompts are one token longer than LiteRT-LM's
   (21 / 1107 vs 20 / 1106, reproduced above). An issue / PR to huggingface/swift-jinja fixes it at the source (outward text: the user's GO);
   changing the MLX arm's prompt in the harness is that arm's protocol decision, not made here.
5. **Android llama-cli thinking**: `android/bench/run_cell.py` runs `llama-cli … -st` with no thinking switch; b11721's llama-cli passes
   enable_thinking = true by default, and on the Mac its Gemma 4 E2B / E4B replies then open with "[Start thinking]". Read one Android Gemma 4
   llama.cpp reply; if it thinks, the Gemma 4 rows need `--chat-template-kwargs '{"enable_thinking": false}'` (`--reasoning-budget 0` wrote the
   analysis out as the answer) — an Android arm change and a re-measure.
6. **explicit dependency (optional)**: if the transitive `import Jinja` is unwanted, add swift-jinja to `project.yml` (huggingface/swift-jinja,
   from 2.0.0; product Jinja on both targets) and regenerate the four committed projects with xcodegen in one commit.

## 経過
- 10:17 ListAgents (this session = edge-llm-bench-wt-autopilot-tmpl-b1 [24da3a]); HEAD be17d5a4, tree clean.
- 10:18 下見: LANE.md 10:13 (MAIN working copy), ROUND9's build lines (r9 scratchpad `tools/mac_build_r9.sh` / `ios_build_r9.sh` /
  `mac_smoke_r9.sh`). Supervisor's addition: 4 MLX entries in `ModelCatalog.swift`.
- 10:2x hashes and cmp (REPO = SIDE = MAIN); swift-jinja 2.4.2 API; the five GGUF templates; E2B = E4B template, both bare (premise correction).
- 10:26 SendMessage: the record stamp needs 3 files outside the write list + the E2B correction.
- 10:3x supervisor: GO for the 3 files and the ModelInfo flag (same commit, REPO + SIDE); re-measure = every llama.cpp Gemma 4 cell.
- 10:3x Python jinja2 reference renders + llama-tokenize counts; swift-jinja probe: Gemma 4 +1 `\n` (comment whitespace control), fixed by a
  pre-pass → 10 of 10 byte-equal. Supervisor: the 4 MLX entries cancelled (none had been added).
- 10:3x code in REPO; the five files copied into SIDE after checking SIDE = REPO HEAD for each.
- 10:39:00–10:40:34 Mac build into `MAIN/.build/dd-mac-tmpl`: BUILD SUCCEEDED, the jinja branch in the binary.
- 10:42 the smoke's own guard refused: r14's Mac sitting (wt-autopilot-q06, `mlx-gemma4-file-mac.cells`) took the quiet window at 10:41:10,
  36 s after the build ended. One waiter (`quiet_wait.py`), all window work moved into one hold.
- 10:4x–11:08 schema, fairness-rules §1 (paragraph + table), dashboard-cells-v1 section; claims checked against records (MLX passes no
  context, `--reasoning-budget 0` ≠ thinking off, the 18 Pro E4B 1K skeleton, the 2K ladder rows). A comment fix in `tokenText` (an
  unverified Qwen3 BOS claim removed), SIDE = REPO again.
- 11:08:36–11:12:09 window (213 s): Mac rebuild (nothing relinked), smoke 11:09:11–11:11:30 (5 cells, all jinja), iPhone build
  11:11:30–11:12:04, MLX +1 check, schema check. MAIN's `results/summary` showed 2 changed files at 11:12:09 — the Pixel 8a post's rebuild
  (committed on MAIN 11:12:40–43), clean again at 11:13; not mine (the runner's `run` writes no summary), nothing reverted.
- 11:13:57 llama-cli greedy cross-check (E4B 1K = the harness's reply word for word); 11:15:25 one direct yardstick launch for the console
  line.
- 11:16:19 the 18 Pro's q06-dynamic sitting ended (ledger), and its `./bench matrix` rebuilt MAIN's disk summary with every untracked
  campaign dir, this round's smoke dir among them (5 rows; HEAD has none). Left as is: the 18 Pro's next sitting was running.
- 11:21:19 the 18 Pro's `2026-10-19-dashboard-v1-iphone18pro-llama-b11721-ios` sitting (started 11:17 by the supervisor): its first
  llama.cpp record (Qwen3 0.6B short-chat) reads `conditions {chatTemplate jinja, thinking template-default}`, 19 tokens, b11721, Release =
  this round's app is installed (read from the record file; no device touched).
- 11:2x SPEED_LADDER.md, this report, commit aaae422a, round close.

## 訂正
- E2B is not in llama.cpp's built-in template set: the unsloth E2B and E4B GGUFs carry the same template (sha256 `241c50d8…`), and both ran
  bare in the harness (prompt 12 / 1098 on both; REPO summary: every Mac / iPhone Gemma 4 llama.cpp row). E2B's 1K replies read as answers
  because the bare continuation happened to take that shape. Evidence: scratchpad `tmpl/e2b.jinja` = `tmpl/e4b.jinja`;
  `MAIN/results/raw/2026-10-19-dashboard-v1-m4max-0180-rebuilt-mac/llama_cpp_unsloth_gemma-4-E2B-it-GGUF_Q4_K_M_*.jsonl`.
- llama-cli's thinking-on is llama-cli's default (it passes `enable_thinking = true`), not the template's: the Gemma 4 GGUF template defaults
  to off (`enable_thinking | default(false)`; scratchpad `tmpl/e4b.jinja`).
- The launch's E4B "answers with a list" read was sampled (no `--temp` in its llama-cli line); greedy, the same tool and template decline the
  task (scratchpad `llamacli/e4b-1k-greedy-nothink.out.txt`) exactly as the harness does — the launch expected "「1. **…**」の形".
- The launch's write range lacked the record wiring (BenchmarkResult / LLMRuntime / BenchmarkRunner) the goal needs; the supervisor added it
  at 10:3x.
- The launch's E4B 1K text-fail scope: on the page only the Mac E4B 1K cell is text-fail; the iPhone rows carry no screen verdict (the 18 Pro
  E4B 1K replies are the same skeleton: `results/raw/2026-10-06-dashboard-longctx1024-v1-iphone18pro-c4-ios/device-jsonl/`).

## 罠と袋小路
- **swift-jinja 2.4.2 drops comment whitespace control** (`{#-` / `-#}`): a template with a comment after a blank line renders an extra
  `\n` (Gemma 4: one token after `<bos>`). Compare every new template's render with Python jinja2 before trusting it (scratchpad
  `tools/swift_vs_ref.sh`); the adapter's pre-pass is `LlamaCppRuntime.withCommentWhitespaceControl`.
- `HuggingFace` exports a `Value` too: `[String: Value]` in a file importing both is ambiguous — write `Jinja.Value` (found by grep before
  the build).
- llama-cli `--reasoning-budget 0` is not "thinking off" for Gemma 4: the replies write the analysis out as the answer. Use
  `--chat-template-kwargs '{"enable_thinking": false}'`. And a llama-cli read without `--temp 0` is sampled: not comparable with the
  greedy harness.
- The Mac runner keeps only the last 4 lines of a launch's console (`| tail -4`): a `YARDSTICK_NOTE` is not in the smoke's log; run the
  yardstick directly to see it.
- The PreToolUse hook blocks `python3 -c …` and `xcodebuild -version` while another lane holds the Mac window, and a heredoc that merely reads
  the lock path ("would clear or overwrite the lock") — write such scripts with the Write tool and run checks inside your own hold.
- One quiet hold for all window work: a nested `quiet_hold.py` inside a hold waits on its own parent's flock. The window went to another lane
  36 s after my first build; a second take cost 20 min of waiting.
- zsh does not split `set -- $p`; run such loops under bash.
- `echo "…\n…" >> file` under zsh writes a real newline (it broke one 経過 line); write notes with the Write / Edit tools.

## op と delegate の観察
- Not an op / delegate round: no conversion, no backend change. Measured: llama.cpp b11721 Metal on the Mac runs every smoke cell to its
  record; every launch then aborts at teardown (`ggml_metal_rsets_free` ← `ggml_metal_device_free` ← the device `unique_ptr` destructor;
  crash reports 110923 / 110950 / the direct launch 11:15:30, rc 134), unchanged from r9. Fallback counts, fp16 / fp32 deltas: none
  measured (なし).

## 使った環境
- Mac Studio M4 Max (Mac16,9), macOS 27.0 (26A428); Xcode 27.0 (27A266a, `Xcode-27.0.0-RC.app`), Swift 6.4; no phone touched (no adb /
  devicectl), no device hold.
- Packages (side tree's resolution): swift-jinja 2.4.2, swift-transformers 1.3.3, swift-collections 1.6.0 (probe copies in the scratchpad);
  llama.cpp b11721 xcframework (macOS UUID 843E7D68, ios-arm64 6226C23F); LiteRT-LM v0.18.0 (`libCLiteRTLM_mac.dylib` 9526db9e…).
- Python 3.14.6 + jinja2 3.1.6 (system, `-I`); jsonschema 4.26.0 from `~/.venvs/ortgenai-0.17.1`; llama-tokenize / llama-cli b11721 from the
  supervisor's scratchpad (`llamacli/llama-b11721`).
- Mac quiet holds: "r13-yardstick-tmpl-build" 10:39:00–10:40:34, "r13 llama-template" 11:08:36–11:12:09, "r13 llamacli-greedy"
  11:13:57–11:14:02, "r13 yardstick-console" 11:15:25–11:15:30.

## 残した file
- K `ROUND13.md` (this), K `SPEED_LADDER.md` (the smoke rows): committed.
- `MAIN/.build/dd-mac-tmpl/` (the Mac yardstick for the switch; keep until the job uses it or the change is backed out).
- `MAIN/.build/dd-ios-0180-18pro/Build/Products/Release-iphoneos/BenchmarkApp.app` (the app now on the 18 Pro) and `BenchmarkApp.app.r9-20261019-0606`
  (r9's app, an APFS clone: 消してよい once the new app is installed and checked).
- SIDE's five source files (= REPO's commit; SIDE is the 18 Pro's build tree, untracked).
- `MAIN/results/raw/2026-10-19-llama-template-probe-mac/` (the smoke: 5 records, FAILURES.txt = the exit aborts; not committed; every
  disk rebuild of MAIN's summary takes its 5 rows in, as it takes r9's smoke dirs: 消してよい after review).
- Scratchpad (消してよい): `tools/` (gguf_meta.py, extract_templates.sh, ref_render.py, ref_all.sh, ref_count.sh, swift_vs_ref.sh,
  mlx_plus1_check.sh, schema_check_r13.py, mac_build_r13.sh, window_r13.sh, ios_build_r13_inner.sh, llamacli_greedy_r13.sh,
  ys_console_r13.sh), `tmpl/` (the five templates), `render/` (ref / swift / mlx renders), `probe/` (jinja-probe package with clones of
  swift-jinja and swift-collections, the smoke cells, a typecheck file), `llamacli/`, `ys/`, `logs/`, `round13_static.md`, `round13_tail.md`.
