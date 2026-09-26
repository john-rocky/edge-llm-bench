# 2026-09-25 — LiteRT-LM built from the OSS tree at main@1dadd00c for iOS, driven by the bench app on the iPhone 18 Pro: the accelerator loads, the prompt does not arrive

The question: can an OSS bazel build of the LiteRT-LM C API for iOS, with the same commit's
prebuilt Metal accelerator placed beside the app, give iPhone numbers for the composite exports
before a released xcframework carries the fused prefill kernel? (The released v0.17.x
framework registers its own accelerator first — see
`../2026-09-25-litertlm-swift-package-prebuilt-dylib-iphone18pro-ios/`.)

## What was built

- `bazelisk build //swift:CLiteRTLM` in a worktree at `1dadd00c` with the xcframework rule
  reduced to the ios-arm64 device slice (`swift/BUILD`, simulator slice dropped): 5,375
  actions, 2 min with a warm disk cache; `CLiteRTLM.xcframework.zip` 9,725,051 B sha256
  `7d7db593eadf7b22…`, `ios-arm64/CLiteRTLM.framework/CLiteRTLM` 27,971,336 B sha256
  `6b96cc03996859d2…` (the release framework is 60,466,448 B: it carries the Metal
  accelerator inside, this one does not — its strings have neither `flash_prefill_sdpa`
  nor `Created a Metal device`). It links `@rpath/libGemmaModelConstraintProvider.dylib`,
  so that prebuilt (21,054,392 B, LFS at 1dadd00c) travels in `Frameworks/` too.
- The Swift package at 1dadd00c (`git worktree`, `swift/Benchmark.swift` maxNumTokens patch
  applied) with its iOS `binaryTarget` pointed at that local xcframework; the bench app
  built from a project copy (`BenchmarkApp-1dadd00c.xcodeproj`, same recipe as the
  prebuilt-dylib check), signed with the memory entitlements; `Frameworks/` holds
  `libLiteRtMetalAccelerator.dylib` (1dadd00c, `2cbff000…`) and the constraint provider.
  The app `chdir`s to `Frameworks/` and `dlopen`s the dylib by path before creating the
  engine (`MediaPipeRuntime.swift`, `LiteRTPrebuiltAccelerator`); the records' engine pins
  were stamped `main@1dadd00c (OSS bazel //swift:CLiteRTLM …)` by hand in the bundle.
- The runner and app gained two switches used here: `--litert-backend cpu|gpu`
  (cells `backend=`) and `--litert-engine-counters off` (cells `engine-counters=off`), and a
  diagnostic `--litert-send-mode sync` that also sends each prompt through the
  non-streaming API and logs the reply on stderr.

## What happened (consoles under `probes/`, records under `records/`; nothing enters a summary)

1. **The accelerator registers dynamically**: every launch logs `Attempting to load GPU
   accelerator(libLiteRtGpuAccelerator.dylib)`, then `…(libLiteRtMetalAccelerator.dylib)`,
   then `Dynamically loaded GPU accelerator(libLiteRtMetalAccelerator.dylib) registered.`
   and `delegate_metal.mm … Created a Metal device.` — the route the released framework
   never reaches. The engine's own benchmark mode
   (`--litert-native-benchmark 1024x256`, synthetic tokens, no text) runs on it: 9-flag 0.6B
   file, prefill 1,731 tok/s, decode 126.7 tok/s (`probes/native-benchmark_…`). That number
   is not a measurement (no text was read) and is listed only to show the path executes.
2. **The prompt does not reach the model.** Through the app's normal path
   (`Conversation.sendMessageStream`) every run reports `promptTokenCount` 8–9 whatever
   the prompt (19 tokens for `short-chat`, 1,339 for `long-context-1024-gen256`, ~700 for
   `long-context-512`) and answers a question the app never sent — on the GPU the 9-flag
   file wrote about "how to create a website using HTML and CSS" for the long-context
   prompt, on the CPU the published `litert-community/Qwen3-0.6B` bundle wrote about "a
   specific type of plant … Celtis" and the 9-flag file wrote "the user is asking about a
   specific question, but I don't have the question … Let me read again: "ut". The
   diagnostic non-streaming send confirms the app hands over the right text (`sync_send
   start prompt_chars=48 head=Explain what on-device AI means in simple terms.`) and the
   engine still replies about the plant (`probes/diag-sync-send_…`). Disabling the
   engine's benchmark flag (`engine-counters=off`) changes nothing. The same app code on
   the released v0.17.x framework (the prebuilt-dylib check, same phone, the 9-flag export on the GPU)
   answers the prompt ("Okay, the user wants to understand on-device AI in simple terms…",
   `promptTokenCount` 19), so the loss is inside the OSS-built engine at this commit
   (message → prompt-template path), not in the app or the Swift package (whose
   `Conversation.swift` / `Message.swift` differ from v0.17.0 only in error strings).
3. **On the GPU the reply is not language.** With the prompt lost, the CPU backend still
   produces fluent English (2 above); the Metal path through the 1dadd00c dylib produces
   token salad for every bundle tried — published mixed-int4 ("ToPropsToPropsToProps…"),
   9-flag ("etableToProps NTNovedenge…"), deterministic across launches, with or without
   the Metal top-k sampler dylib (whose ObjC classes duplicate the accelerator's: 35
   `objc … implemented in both` warnings when both are embedded). Whether this is the
   dylib on this GPU or the OSS GPU executor path was not separated (the 66058c82 dylib
   does not load into a 1dadd00c engine: `llm_litert_compiled_model_executor_factory.cc:206`).

4. **The same loss on the Mac, and at head.** The same OSS C API built for macOS
   (`bazelisk build //swift:CLiteRTLM_mac` at `1dadd00c` and again at `66058c82`, the
   dylib wrapped with `xcodebuild -create-xcframework` into the package, the Mac yardstick
   built against it, `--litert-backend cpu`, the published Qwen3-0.6B bundle) answers the
   `short-chat` prompt with the same "Celtis" plant paragraph and `promptTokenCount` 9
   (`probes/mac-control_oss-*`). So the loss is a property of the OSS-built C API through
   the Swift package at both commits, on both platforms — not the iOS dylib, not the phone.
   The C API sources (`c/conversation.cc`, `c/engine.cc`) differ from the `v0.17.0` tag
   only in error handling, and Google's `v0.17.x` frameworks built from that tag deliver
   the prompt. (Erratum 2026-09-26: the sentence that stood here — "the OSS CLI answered
   prompts correctly on 2026-09-18 at this commit" — was wrong; that CLI was built from the
   `v0.17.0` tag, see `../2026-09-18-qwen3-composite-prebuilt-1dadd00c-mac/PROVENANCE.md`.
   The cause was found the next day by calling the C API directly, see the Reading below; it is the mechanism of LiteRT-LM #3688, filed from this side on 2026-09-20.) An iOS xcframework at `66058c82` was also built
   (`bazel-bin/swift/CLiteRTLM.xcframework.zip` in `~/code/litert-lm-asr-ios-wt`) but not
   installed, since the prompt loss reproduces at that commit on the Mac.

5. **Where the text goes: the rendered user turn is empty.** Asking the OSS engine to render
   the same message through the bundle's prompt template
   (`Conversation.renderMessageIntoString`, the C API's
   `litert_lm_conversation_render_message_to_string`) returns
   `<|im_start|>user⏎<|im_end|>⏎<|im_start|>assistant⏎` for a message whose content is the
   48-character text — the template scaffolding with no content — and
   `renderPrefaceIntoString` returns an error (`probes/diag-render_…`, iPhone, CPU
   backend, published Qwen3-0.6B bundle). So the loss happens between the parsed message
   JSON (`{"role":"user","content":[{"type":"text","text":…}]}`, the same shape the CLI
   builds) and the template input inside the OSS-built engine.

## Reading

No valid iPhone number for the composite files came out of this route today: the prompt
is lost before prefill (so no chat-path rate stands) and the GPU path decodes garbage (so no
benchmark-mode rate can be trusted either). The prompt loss is not phone-specific (4). **Resolved 2026-09-26**
(`../2026-09-26-litertlm-main-conversation-empty-user-turn-mac/PROVENANCE.md`): building from the
open-source tree is not the cause — the same recipe at the `v0.17.0` tag delivers the prompt.
Since `main` commit `6c6b4582` (2026-09-10) the Conversation API hands the chat template the
message content as a parts array, and this bundle's stored Qwen3 template sets `content = ''`
when `content` is not a string; the refreshed `Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm`
(a template that iterates parts) renders and answers correctly on the same OSS build. The
maintainer's answer in [#3688](https://github.com/google-ai-edge/LiteRT-LM/issues/3688) (2026-09-20)
makes the parts list the contract, so the composite exports used here need a re-export with a
parts-aware template before this route can give a number. What the route did establish: the accelerator
registration mechanism works from an OSS build on the phone (as for the ASR instrument),
and the instrument pieces (project copy, package worktree, dylib embedding, backend and
counter switches) are in place for the day a build pair works. The two defects are LiteRT-LM
findings at `1dadd00c` on iOS; whether they exist at head or only in an OSS iOS build is
open. Both 12-flag exports were regenerated for the day a working framework exists:
`p1024_06b_12flags` (341,779,680 B, sha256 `f3499966…`, side-loaded) and `p1024_4b_12flags`
(2,270,748,784 B, sha256 `aa9fcedd…`, 21:38 JST after the Qwen3-4B checkpoint was
re-downloaded); sections identical to the 09-18 exports, file hashes differ (uuid /
timestamp).
