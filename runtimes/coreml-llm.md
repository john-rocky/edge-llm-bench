# CoreML-LLM

ANE-first CoreML pipelines for autoregressive LLMs, via the `john-rocky/CoreML-LLM` Swift package.

- Repository: <https://github.com/john-rocky/CoreML-LLM>
- License: see upstream
- Backend: Apple Neural Engine (CPU fallback per op)
- Layout: chunked `.mlmodelc` bundle (embeddings + N transformer chunks + lm_head + prefill chunks + tokenizer files)

## Strengths

- Lowest battery / thermal cost per token on Apple Silicon when the model is well-mapped to the ANE.
- Bundled `.mlmodelc` runs directly from the app bundle — no download UX needed.
- App Store distribution is straightforward.
- Plays well with iOS background-mode constraints (the ANE is its own coprocessor).

## Weaknesses

- Model conversion is the hardest part of any runtime: prefill / decode are typically two separate `.mlpackage`s (prefill flexible-shape, decode 1-token), and quality regressions during conversion are common.
- ANE-friendly architectures are a subset (no MoE today, GQA/MQA support is fiddly, custom attention kernels often fall to CPU).
- Limited public model zoo — most "ANE LLM" demos use bespoke conversions.

## iOS integration

Wired through the `CoreMLLLM` SwiftPM product. The adapter calls `CoreMLLLM.load(model: .gemma4e2b)` (or `.gemma4e4b`, etc.), which downloads the chunked bundle to `Documents/Models/<folderName>/`, ANE-compiles it (slow on first run, ~1–2 min), and returns an inference engine. Streaming is via `llm.stream(prompt, maxTokens:) -> AsyncStream<String>`.

```swift
import CoreMLLLM

let llm = try await CoreMLLLM.load(model: .gemma4e2b) { _ in /* status */ }
for await piece in try await llm.stream("Hello", maxTokens: 256) {
    print(piece, terminator: "")
}
```

Min platform: iOS 18 / Swift 6.

## Models in our catalog

| id | Model | Size | Source |
|---|---|---:|---|
| `coreml-llm/gemma4-e2b` | Gemma 4 E2B (multimodal) | 5.4 GB | `mlboydaisuke/gemma-4-E2B-coreml` |
| `coreml-llm/gemma4-e4b` | Gemma 4 E4B (text) | 5.5 GB | `mlboydaisuke/gemma-4-E4B-coreml` |
| `coreml-llm/qwen3.5-0.8b` | Qwen 3.5 0.8B | 1.2 GB | `mlboydaisuke/qwen3.5-0.8B-CoreML` |
| `coreml-llm/qwen3.5-2b` | Qwen 3.5 2B | 2.8 GB | `mlboydaisuke/qwen3.5-2B-CoreML` |
| `coreml-llm/lfm2.5-350m` | LFM 2.5 350M | 810 MB | `mlboydaisuke/lfm2.5-350m-coreml` |
| `coreml-llm/qwen2.5-0.5b` | Qwen 2.5 0.5B | 309 MB | GitHub release |

## Why this loader rather than swift-transformers' `LanguageModel`

`huggingface/swift-transformers` exposes a `LanguageModel.loadCompiled(url:)` API, but it expects a single stateful `.mlpackage` (`input_ids` + `logits` + KV-state). Gemma 4 is not published in that layout. `CoreMLLLM` handles the chunked layout (embedding sidecar + N decode chunks + prefill chunks) that `mlboydaisuke/*-coreml` ships with, and it is the only Swift library today that can load Gemma 4 from CoreML on iPhone.

## Status

Wired and building. iPhone benchmark runs once the user supplies signing.
