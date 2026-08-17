# llama.cpp

The reference C++ implementation of GGUF inference, with a Metal backend on Apple platforms.

- Repository: <https://github.com/ggml-org/llama.cpp>
- License: MIT
- Backend: Metal (or CPU NEON) on iOS

## Strengths

- Broadest model coverage of any local LLM runtime — anything that has been GGUF-converted.
- Mature quantization story (Q4_K_M, Q5_K_M, IQ4_XS, etc.) with well-understood quality/speed tradeoffs.
- Tiny binary footprint after stripping unused features.
- Battle-tested across desktop, mobile, web.

## Weaknesses

- C++ API. Requires a Swift wrapper (we use `llama.cpp.swift` via SwiftPM, or hand-roll one).
- No native streaming primitive — caller manages a token-eval loop.
- Cancellation requires manual flag checking.
- Build-time configuration matters (`LLAMA_METAL`, `GGML_NATIVE`, etc.); a misconfigured build is silently slower.

## iOS integration notes (planned, not yet implemented)

Two practical paths:

1. **SwiftPM via the unofficial `LLama.cpp.swift` package** — fastest to get running, but the wrapper's API surface and update cadence is owned by the wrapper author.
2. **Vendor `llama.cpp` as a git submodule and build with a small Swift bridge** — more control, more maintenance.

We will use option (1) for v0.1 and may switch to (2) once the GGUF model selection lands.

## Models targeted

- `Qwen2.5-0.5B-Instruct.Q4_K_M.gguf`
- `Llama-3.2-1B-Instruct.Q4_K_M.gguf`
- `gemma-3-1b-it.Q4_K_M.gguf`

GGUF conversions live under each model's HF page or in the `bartowski` and `unsloth` namespaces.

## Status

Stub adapter only. Wired up via `LLMRuntime` protocol so the rest of the app can call it; returns `unsupported` until the bridge is integrated.
