# MLX Swift / MLX Swift LM

Apple's MLX framework, with the Swift bindings via `mlx-swift` and the high-level LLM/VLM library `mlx-swift-lm`.

- Repository: <https://github.com/ml-explore/mlx-swift>
- LLM library: <https://github.com/ml-explore/mlx-swift-lm>
- License: MIT
- Backend: Apple GPU via Metal (Apple Silicon unified memory)

## Strengths

- First-class Swift API. `async`/`await`, `AsyncStream<Generation>`, `Sendable`-correct.
- Streaming + cancellation work cleanly.
- Tight Apple-platform fit: runs on Mac, iPad, iPhone, Vision Pro with the same code.
- Active model coverage in the Hub `mlx-community` namespace — Qwen, Llama, Gemma, Phi, SmolLM, DeepSeek, etc.
- Supports quantized KV cache (`kvBits: 4 / 8`) for long context on iPhone.

## Weaknesses

- ANE is not used — runs entirely on the GPU. So battery / thermal cost is higher than an ANE-tuned CoreML pipeline.
- Model conversion is a separate flow (Python `mlx-lm` does the conversion before models can be served).
- Package dependency tree is non-trivial: `mlx-swift`, `mlx-swift-lm`, `swift-huggingface`, `swift-transformers`. First build is slow.

## iOS integration notes

Required Swift Package dependencies for an iOS app:

| Package | Products needed |
|---------|-----------------|
| `mlx-swift-lm` | `MLXLLM`, `MLXLMCommon`, `MLXHuggingFace` |
| `swift-huggingface` | `HuggingFace` (provides `HubClient`) |
| `swift-transformers` | `Tokenizers` |

Minimum deployment target: **iOS 17** (per `mlx-swift-lm`'s `Package.swift`).

Imports:

```swift
import MLXLLM
import MLXLMCommon
import MLXHuggingFace
import HuggingFace
import Tokenizers
```

Loading a model from the Hub:

```swift
let container = try await loadModelContainer(
    from: #hubDownloader(),                  // macro: HubClient → Downloader
    using: #huggingFaceTokenizerLoader(),    // macro: AutoTokenizer → TokenizerLoader
    configuration: LLMRegistry.qwen3_0_6b_4bit
) { progress in
    // progress.fractionCompleted
}
```

Streaming generation:

```swift
await container.perform { context in
    let userInput = UserInput(prompt: "Hello")
    let lmInput = try await context.processor.prepare(input: userInput)
    let parameters = GenerateParameters(maxTokens: 256, temperature: 0.7)

    let stream = try MLXLMCommon.generate(
        input: lmInput, parameters: parameters, context: context
    )
    for await event in stream {
        switch event {
        case .chunk(let text): // append to UI
        case .info(let info):  // info.tokensPerSecond, info.promptTokensPerSecond
        case .toolCall:        break
        }
    }
}
```

## Models tested in this benchmark

- `mlx-community/Qwen3-0.6B-4bit` (default — small, fast, good quality)
- `mlx-community/Qwen3-1.7B-4bit`
- `mlx-community/SmolLM3-3B-4bit`
- `mlx-community/Llama-3.2-1B-Instruct-4bit`
- `mlx-community/gemma-3-1b-it-qat-4bit`
- `mlx-community/gemma-4-e2b-it-4bit`

The full registry is in `LLMRegistry` (`Libraries/MLXLLM/LLMModelFactory.swift` upstream).

## Known iOS gotchas

- The first generation after launch is significantly slower than subsequent ones because Metal compiles shaders on demand. Always report cold vs warm separately.
- Aggressive ARC pressure during decode if the caller does not drain the `AsyncStream` promptly — see [Evaluate.swift documentation](https://github.com/ml-explore/mlx-swift-lm/blob/main/Libraries/MLXLMCommon/Evaluate.swift) on `generateTask` for deterministic cleanup.
- Backgrounding the app while the GPU is running may pause generation; resuming is generally clean but worth testing per OS version.
