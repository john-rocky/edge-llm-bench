# 2026-09-26 — LiteRT-LM main: a text user message renders as an empty user turn when the bundle's chat template expects `content` as a string (C API called directly, macOS, CPU)

## Question

On 2026-09-25 a LiteRT-LM C API built from the open-source tree at `main@1dadd00c` lost the
user's text on an iPhone 18 Pro and on a Mac (the model answered a question it never received),
while Google's released `v0.17.0` / `v0.17.1` framework delivered it through the same app
(`../2026-09-25-litertlm-oss-ios-build-1dadd00c-iphone18pro-ios/NOTES.md`). Is that a property of
building the C API from the open-source tree, or of the commits between the `v0.17.0` tag and
`1dadd00c`?

## Prior report

The mechanism found here was already reported from this side on 2026-09-20 as
[LiteRT-LM #3688](https://github.com/google-ai-edge/LiteRT-LM/issues/3688) (from a `litert-lm-nightly`
0.18.0.dev20260918 run of the same `qwen3_0_6b_mixed_int4.litertlm`): since `6c6b4582` the template
receives `content` as a list of parts. The maintainer's answer there (2026-09-20): in 0.18.0 there
is a chat template standard (`models/README.md` in LiteRT-LM), and the contents will always be a
list of objects with a type; the issue was closed on 2026-09-22. This page adds the bisect, the
head and CLI runs, the C-API-level probe and the survey below; it was not filed as a new issue.

## Instrument

`probes/capi/capi_render_probe.py` opens one `libCLiteRTLM_mac.dylib` through Python `ctypes`
(no Swift package, no app), creates a CPU engine from a `.litertlm` bundle
(`litert_lm_engine_settings_create(path, "cpu", NULL, NULL)`, max tokens 1280, 4 threads,
benchmark counters on), creates a conversation, renders the preface and one user message through
the bundle's chat template (`litert_lm_conversation_render_preface_to_string`,
`litert_lm_conversation_render_message_to_string`), sends the same message
(`litert_lm_conversation_send_message`, 48 output tokens) and reads the prompt token count from
`litert_lm_conversation_get_benchmark_info`. The message JSON is the shape the Swift package's
`Message.toJson` and the Kotlin package's `Message.toJson` produce for a text message:

```
{"role":"user","content":[{"type":"text","text":"Explain what on-device AI means in simple terms."}]}
```

`probes/capi/capi_render_shapes.py` renders five message shapes (single text part, plain string,
two text parts, assistant role, system role) without sending.

Machine: Mac Studio (M4 Max), macOS 27.0. Python 3.14.6. Each run's stdout and stderr are under
`probes/capi/` (`<dylib>.probe.*`, `<dylib>.shapes.*`, `<dylib>.dyn.*`); the commands as run are
in `probes/capi/runlog.log` (`### CMD:` lines).

### The four dylibs

| label | how it was made | `libCLiteRTLM_mac.dylib` |
|---|---|---|
| release v0.17.0 | `CLiteRTLM_mac.zip` from the `v0.17.0` Swift package (`Package.swift` binaryTarget URL, zip sha256 `83efd536…` = the checksum in `Package.swift`) | 144,666,096 B, sha256 `ece7f316…` (arm64 + x86_64; no dependency on `libGemmaModelConstraintProvider.dylib`) |
| OSS at tag `v0.17.0` (`e9fd8c53`) | `bazelisk build //swift:CLiteRTLM_mac` in a worktree at the tag, `.bazelrc` defaults (`-c opt`), Bazel 7.6.1, Xcode 27.0 RC; 196 s (`probes/bazel_mac_v0170.log`) | 60,139,184 B, sha256 `0dad343a…` |
| OSS at `1dadd00c` | same command at `1dadd00c`; 177 s (`probes/bazel_mac_1dadd00c.log`) | 61,161,824 B, sha256 `427c07eb…` |
| OSS at `66058c82` | same command at `66058c82`; 199 s (`probes/bazel_mac_66058c82.log`) | 61,303,216 B, sha256 `dbef791c…` |

The three OSS dylibs link `@rpath/libGemmaModelConstraintProvider.dylib`; the prebuilt from the
same commit's `prebuilt/macos_arm64/` was placed beside each dylib.

### The bundles

| bundle | identity | stored chat template |
|---|---|---|
| `litert-community/Qwen3-0.6B` `qwen3_0_6b_mixed_int4.litertlm` | rev `a3c5d805` (this file last changed in Hub commit `154c5de0`, 2026-09-19), 497,516,544 B, LFS sha256 `7900eb4e…` | the Qwen3 template as published with the Qwen3 checkpoints: `{%- if message.content is string %}{%- set content = message.content %}{%- else %}{%- set content = '' %}{%- endif %}` |
| `litert-community/Qwen3-0.6B` `Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm` | rev `a3c5d805` (refreshed 2026-09-21, "current litert-torch export"), 344,671,744 B, LFS sha256 `03e7da1e…` | a rewritten template with `{%- macro format_content(content) -%}` that accepts a string or a sequence of `{"type":"text"}` parts |
| `litert-community/Qwen3-1.7B` `Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm` | rev `73fbc3fe` (file added 2026-08-05), 977,184,032 B, LFS sha256 `2eeffef7…` | a modified Qwen3 template: it keeps the `message.content is string` guard, but its user-turn line is `'<|im_start|>' + message.role + '\n' + message.content + '<|im_end|>'` (the unguarded field) |

## Result — the same message JSON, `qwen3_0_6b_mixed_int4.litertlm`, CPU

| dylib | `render_message` | prompt tokens | reply (first words) |
|---|---|---|---|
| release v0.17.0 | `<|im_start|>user⏎Explain what on-device AI means in simple terms.<|im_end|>⏎<|im_start|>assistant⏎` | 20 | "Okay, so the user wants a simple explanation of on-device AI…" |
| OSS at tag v0.17.0 | same as the release | 20 | "Okay, so the user wants a simple explanation of on-device AI…" |
| OSS at `1dadd00c` | `<|im_start|>user⏎<|im_end|>⏎<|im_start|>assistant⏎` | 9 | "Okay, the user wants me to provide a response to the query "What are the main factors that influence the choice of a business plan?"…" |
| OSS at `66058c82` | `<|im_start|>user⏎<|im_end|>⏎<|im_start|>assistant⏎` | 9 | the same "business plan" reply |

`render_preface` fails on all four (`Failed to apply template: undefined value (in template:13)`),
so that is not part of this finding.

Message shapes (`capi_render_shapes.py`): at the tag, a plain-string `content` and a single text
part both render the text, two text parts render an empty turn; at `1dadd00c` every shape renders
an empty turn and the system-role message fails (`probes/capi/oss0170.shapes.stdout.txt`,
`probes/capi/oss1dadd.shapes.stdout.txt`).

Control with the refreshed bundle (`Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm`): the OSS dylib at
`1dadd00c` renders `<|im_start|>user⏎Explain what on-device AI means in simple terms.<|im_end|>⏎…`,
prompt tokens 19, and the reply's thinking (all 48 output tokens land in the `thought` channel) is about on-device AI (`probes/capi/oss1dadd.dyn.stdout.txt`);
the tag build gives the same, and so does `upstream/main` at `5e3bd637` (`probes/head/clean-dir/probe_Qwen3-0.6B_dynamic_wi4b32_afp32.stdout.txt`).

Second template form, `Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm`: at `5e3bd637` both `render_message`
and `send_message` return NULL with `Failed to apply template: invalid operation: tried to use +
operator on unsupported types string and sequence (in template:32)`
(`probes/head/head.q17dyn.stdout.txt`); the tag build renders the text (19 prompt tokens, reply
about on-device AI, `probes/capi/oss0170.q17dyn.stdout.txt`). So a template that guards
`content is string` renders an empty turn, and one that concatenates `message.content` directly
fails (the first is the Qwen3 checkpoint's own template; the second keeps the guard but writes the unguarded field at the user turn).

The head runs were repeated from a directory holding only the built `CLiteRTLM_mac/`,
`litert_lm_main`, the constraint-provider dylib, the probe script and the bundles, with the
commands exactly as an issue reader would type them (`probes/head/clean-dir/`,
`probes/capi/runlog.log`).

## Where the text goes

`Conversation::RenderMessageIntoString` and `SendMessage` pass the message through
`ModelDataProcessor::MessageToTemplateInput` and then the bundle's Jinja template (minijinja).
At the `v0.17.0` tag, `Qwen3DataProcessor::MessageToTemplateInput`
(`runtime/conversation/model_data_processor/qwen3_data_processor.cc:45-56`) unwrapped a
single text part into a plain string before the template. Commit `6c6b4582`
(2026-09-10, "refactor: normalize message content to multimodal parts in model data processors")
removed that override and made the base implementation normalize every message's `content` to a
parts array `[{"type":"text","text":"…"}]` (`data_utils.cc` `NormalizeContent`). A template that
guards `message.content is string` and otherwise sets `content = ''` — the Qwen3 template stored
in `qwen3_0_6b_mixed_int4.litertlm` and in exports made with the checkpoint's own template —
now renders every user turn empty, with no error. A template that iterates content parts (the
refreshed `dynamic_wi4b32_afp32` file) renders it.

Bisect (`git bisect run` between `e9fd8c53` good and `1dadd00c` bad; each step builds
`//swift:CLiteRTLM_mac` and runs `capi_render_shapes.py`; `probes/bisect/`): the first bad commit is `6c6b4582` (9 steps, 23:28–23:37 JST; the parent `2518fba8` renders the text, `6c6b4582` renders the empty turn; `probes/bisect/bisect.log`, `probes/bisect/bisect_gitlog.txt`, per-step `probe_<commit>.stdout.txt`).

At `upstream/main` `5e3bd637` (2026-09-26; `bazelisk build //swift:CLiteRTLM_mac //runtime/engine:litert_lm_main`, `probes/head/`): the C API renders the same empty turn (prompt tokens 9, reply about "a language question"), every message shape renders empty as at `1dadd00c`, and the tree's own CLI reproduces it — `litert_lm_main --backend cpu --model_path qwen3_0_6b_mixed_int4.litertlm --input_prompt "Explain what on-device AI means in simple terms."` prints the prompt and then answers as "a tutor for a 13-year-old who has a learning disability" (`probes/head/cli_litert_lm_main.stdout.txt`; `litert_lm_main.cc` sends `{"role":"user","content":[{"type":"text","text":…}]}` through the same `Conversation`).

`release/v0.17.0` does not contain `6c6b4582`; the released `v0.17.x` frameworks and wheels are
unaffected.

## How many published bundles carry such a template

`probes/survey/survey.py` read the first 3 MB of every `.litertlm` file under the litert-community
org (209 files, 2026-09-26) and classified the stored template by its text
(`probes/survey/survey.md`): 81 iterate content parts (a `format_content` macro or an equivalent
loop), 26 carry the `message.content is string` guard of the two Qwen3 templates above (Qwen3
0.6B, 0.6B-int4, 1.7B, 4B, 4B-Instruct-2507, 4B-Thinking-2507, 8B, 14B; MiniCPM5-1B, MiniCPM5-2B;
1Bit-Bonsai-1.7B-PoC, Ternary-Bonsai-1.7B, Ternary-Bonsai-8B), 46 have a Jinja template with
neither idiom (not tested here) and 56 show no Jinja template in the first 3 MB. Only the three
bundles above were run.

## Reading

Building the C API from the open-source tree is not what lost the prompt: the same recipe at the
`v0.17.0` tag delivers it. The loss seen on the iPhone and the Mac on 2026-09-25 is a behavior
change on `main` since 2026-09-10 — the Conversation API hands the chat template a content
array, and bundles whose template only handles a string either silently render an empty user turn (the `content is string` guard) or fail the template (`+` on a string and a sequence).
Every binding that goes through `Conversation` with JSON messages (Swift, Kotlin, the C API, the
CLI) is on that route; the per-turn count reported by the engine
(9 prompt tokens for a 48-character message) is the visible symptom. For the benchmark's
open-source iOS build the consequence follows the maintainer's answer in #3688: the composite
exports have to be re-exported with a parts-aware template (the LiteRT-LM Qwen3 template at
`a8178d7d`, as the refreshed `dynamic_wi4b32_afp32` file was) before the route can give a number;
the Metal-path token salad noted on 2026-09-25 is a separate question.
