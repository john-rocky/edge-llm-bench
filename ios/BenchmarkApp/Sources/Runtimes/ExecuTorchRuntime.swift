import Foundation

/// What the ExecuTorch adapter needs to know about a catalog model beyond `ModelInfo`:
/// the tokenizer file beside the `.pte`, the KV allocation the export fixed, the chat
/// template the runner does not apply, and the prompt token counts the Swift binding does
/// not report. Compiled in both build flavors (no ExecuTorch import), keyed by the
/// `ModelCatalog.executorch` id; a catalog row without a spec refuses to load.
public struct ExecuTorchModelSpec: Sendable {
    public enum Template: String, Sendable {
        /// The prompt reaches the runner as given (the Llama 3.2 row, as it always ran).
        case none
        /// Qwen 3's chat template for one user turn with the assistant turn opened —
        /// what `apply_chat_template([{"role": "user", "content": prompt}],
        /// add_generation_prompt=True)` renders with the template's defaults: nothing is
        /// passed for thinking, so no empty think block is added and the model thinks
        /// (the host-rendered prompts of the Mac and Android arms, byte for byte).
        case qwen3ChatML = "qwen3-chatml"
    }

    /// Tokenizer file in the model directory (`TextRunner` picks the format from it).
    public let tokenizerFile: String
    /// The KV cache the export allocated (`get_max_context_len`); `Config.sequenceLength`.
    public let contextTokens: Int
    public let template: Template
    /// Prompt token counts by the sha256 of the rendered prompt: the Swift `TextRunner`
    /// reports no statistics, so the count of each task's rendered prompt comes from the
    /// host tokenizer — `scripts/executorch/make_prompts.py` `prompts.json`
    /// (`renderedSha256` -> `hostPromptTokens`), the same file the Mac and Android runners
    /// check their runner's own count against. A prompt not listed reports 0 tokens
    /// (no prefill rate), never an estimate.
    public let hostPromptTokens: [String: Int]
    /// Where `hostPromptTokens` came from (printed on the console note of every run).
    public let hostPromptTokenSource: String

    public func render(_ prompt: String) -> String {
        switch template {
        case .none:
            return prompt
        case .qwen3ChatML:
            return "<|im_start|>user\n" + prompt + "<|im_end|>\n<|im_start|>assistant\n"
        }
    }

    public static func of(_ modelId: String) -> ExecuTorchModelSpec? { table[modelId] }

    /// The Qwen3 0.6B / 1.7B / 4B tokenizers are one tokenizer: one table for the three.
    private static let qwen3 = ExecuTorchModelSpec(
        tokenizerFile: "tokenizer.json",
        contextTokens: 2048,
        template: .qwen3ChatML,
        hostPromptTokens: [
            // short-chat (prompts/text/short-chat.txt, 98 bytes rendered)
            "9d2fe60da55b75283dbd26cd6f8db55bf12e5c3c0c1f37670067623f6461074d": 19,
            // long-context-1024-gen256 (prompts/text/long-context-1024-gen256.txt, 5,269 bytes)
            "360771899cd15f27bcedd5911f5c7f6775ccc15a092e2d133ec29cd83c90baf2": 1338,
        ],
        hostPromptTokenSource: "host-tokenizer:make_prompts.py(Qwen3 tokenizer.json,transformers-5.0.0rc1)"
    )

    private static let table: [String: ExecuTorchModelSpec] = [
        "own-export/Qwen3-0.6B-ET1.5.1-xnnpack-8da4w-emb8-ctx2048": qwen3,
        "own-export/Qwen3-1.7B-ET1.5.1-xnnpack-8da4w-emb8-ctx2048": qwen3,
        "own-export/Qwen3-4B-ET1.5.1-xnnpack-8da4w-emb8-ctx2048": qwen3,
        "executorch-community/Llama-3.2-1B-Instruct-SpinQuant_INT4_EO8-ET": ExecuTorchModelSpec(
            tokenizerFile: "tokenizer.model",
            contextTokens: 2048,
            template: .none,
            hostPromptTokens: [:],
            hostPromptTokenSource: "none"
        ),
    ]
}

#if canImport(ExecuTorchLLM)
import CryptoKit
import ExecuTorch
import ExecuTorchLLM

/// PyTorch ExecuTorch adapter using the Apple `TextRunner` Swift binding (the prebuilt
/// ExecuTorch SwiftPM package; `project-executorch.yml` links it).
///
/// Loads a `.pte` plus the tokenizer its `ExecuTorchModelSpec` names, renders the task
/// prompt with the model's chat template, and streams tokens via
/// `TextRunner.generate(_:_:tokenCallback:)`. The binding has no statistics, so the
/// times are this adapter's wall clock around the runner's own windows
/// (docs/executorch-arm-v1.md, "iPhone"):
/// - prompt time = the `generate` call to the first token callback. The runner tokenizes
///   inside it, then prefills and samples the first token: the same window as the Mac
///   `llama_main` prefill (`inference_start_ms` -> `first_token_ms`, tokenization included).
/// - generate time = the first token callback to `generate` returning: the decode loop.
/// - generation tokens = callbacks - 1 = the decode loop's tokens (`llama_main`
///   `generated_tokens`); the reply is one token longer, the one prefill sampled.
/// - prompt tokens = the spec's host count for this rendered prompt (0 when unlisted).
///
/// Every own export here is XNNPACK-delegated and this build links only that delegate, so
/// the record's runtime is the arm id `executorch-xnnpack`.
public actor ExecuTorchRuntime: LLMRuntime {
    public let kind: RuntimeKind = .executorch
    public let isAvailable: Bool = true
    public nonisolated let supportedModels: [ModelInfo] = ModelCatalog.executorch

    public private(set) var loadedModelId: String?
    public var recordRuntimeLabel: String { "executorch-xnnpack" }

    private var runner: TextRunner?
    private var spec: ExecuTorchModelSpec?
    private var requestedContextTokens: Int?

    public init() {}

    /// The KV cache is fixed at export; the request is only checked against it.
    public func prepareContext(maxContextTokens: Int) async {
        requestedContextTokens = maxContextTokens
    }

    public func loadModel(
        _ model: ModelInfo,
        progress: @Sendable @escaping (Double) -> Void
    ) async throws {
        guard supportedModels.contains(where: { $0.id == model.id }) else {
            throw LLMRuntimeError.modelNotInCatalog(model.id)
        }
        guard let spec = ExecuTorchModelSpec.of(model.id) else {
            throw LLMRuntimeError.loadFailed("no ExecuTorchModelSpec for \(model.id)")
        }

        // An own export is side-loaded (docs/executorch-arm-v1.md): there is no Hub repo
        // behind its id, so a missing file is reported here instead of a download attempt.
        let directory: URL
        if model.hfRepoId.hasPrefix("own-export/") {
            directory = HFDownloader.modelDirectory(runtime: kind, hfRepoId: model.hfRepoId)
            progress(1)
        } else {
            directory = try await HFDownloader.snapshot(for: model, runtime: kind, progress: progress)
        }
        let pteURL = directory.appendingPathComponent(model.primaryFile)
        let tokenizerURL = directory.appendingPathComponent(spec.tokenizerFile)
        guard FileManager.default.fileExists(atPath: pteURL.path) else {
            throw LLMRuntimeError.loadFailed(".pte not found at \(pteURL.path) (not side-loaded?)")
        }
        guard FileManager.default.fileExists(atPath: tokenizerURL.path) else {
            throw LLMRuntimeError.loadFailed("\(spec.tokenizerFile) not found in \(directory.path)")
        }
        if let requested = requestedContextTokens, requested != spec.contextTokens {
            print("YARDSTICK_WARN executorch context_tokens=\(requested) but the export allocates "
                  + "\(spec.contextTokens); the record states the request (cells: context-tokens=\(spec.contextTokens))")
            fflush(stdout)
        }

        let r = TextRunner(modelPath: pteURL.path, tokenizerPath: tokenizerURL.path, specialTokens: [])
        do {
            try r.load()
            self.runner = r
            self.spec = spec
            self.loadedModelId = model.id
        } catch {
            throw LLMRuntimeError.loadFailed(error.localizedDescription)
        }
    }

    public func unloadModel() async {
        runner?.stop()
        runner = nil
        spec = nil
        loadedModelId = nil
    }

    public nonisolated func generate(
        prompt: String,
        parameters: GenerationParameters
    ) -> AsyncThrowingStream<GenerationEvent, Error> {
        AsyncThrowingStream { continuation in
            let task = Task {
                do {
                    try await self.runGenerate(prompt: prompt, parameters: parameters, continuation: continuation)
                } catch {
                    continuation.finish(throwing: error)
                }
            }
            continuation.onTermination = { _ in
                task.cancel()
            }
        }
    }

    private func runGenerate(
        prompt: String,
        parameters: GenerationParameters,
        continuation: AsyncThrowingStream<GenerationEvent, Error>.Continuation
    ) async throws {
        guard let runner, let spec else { throw LLMRuntimeError.modelNotLoaded }

        let rendered = spec.render(prompt)
        let renderedSha256 = SHA256.hash(data: Data(rendered.utf8))
            .map { String(format: "%02x", $0) }.joined()
        let hostTokens = spec.hostPromptTokens[renderedSha256]
        // The console transcript is the record's provenance (the runner stores it beside
        // the records): which prompt ran and where its token count came from.
        print("YARDSTICK_NOTE executorch template=\(spec.template.rawValue) prompt_sha256=\(renderedSha256) "
              + "prompt_bytes=\(rendered.utf8.count) prompt_tokens=\(hostTokens.map(String.init) ?? "unlisted") "
              + "prompt_tokens_source=\(hostTokens == nil ? "none" : spec.hostPromptTokenSource) "
              + "sequence_length=\(spec.contextTokens)")
        fflush(stdout)

        // The runner keeps its KV position across generate calls (a chat): without the
        // reset, run 2 would continue run 1's conversation, and a 1K prompt would overflow
        // the 2,048-token cache on the second run.
        runner.reset()
        let config = Config { c in
            c.sequenceLength = spec.contextTokens
            c.maximumNewTokens = parameters.maxTokens
            c.temperature = Double(parameters.temperature)
            c.isEchoEnabled = false
            c.bosCount = 0
            c.eosCount = 0
        }

        let callStart = CFAbsoluteTimeGetCurrent()
        var firstCallbackAt: CFAbsoluteTime?
        var callbacks = 0

        try await withCheckedThrowingContinuation { (cc: CheckedContinuation<Void, Error>) in
            do {
                try runner.generate(rendered, config) { piece in
                    if firstCallbackAt == nil { firstCallbackAt = CFAbsoluteTimeGetCurrent() }
                    callbacks += 1
                    continuation.yield(.chunk(piece))
                }
                cc.resume()
            } catch {
                cc.resume(throwing: error)
            }
        }

        let end = CFAbsoluteTimeGetCurrent()
        continuation.yield(.info(GenerationInfo(
            promptTokenCount: hostTokens ?? 0,
            generationTokenCount: max(callbacks - 1, 0),
            promptTime: (firstCallbackAt ?? end) - callStart,
            generateTime: firstCallbackAt.map { end - $0 } ?? 0,
            // The reply reached the budget (the decode loop ran max_new_tokens - 1 steps).
            stopReason: callbacks >= parameters.maxTokens ? .length : .stop
        )))
        continuation.finish()
    }
}
#else

/// Compile-time-disabled ExecuTorch runtime: this build does not link the ExecuTorch
/// SwiftPM products (project.yml links Core AI instead; `project-executorch.yml` builds
/// the app with them — docs/executorch-arm-v1.md, "iPhone").
public final class ExecuTorchRuntime: LLMRuntime, @unchecked Sendable {
    public let kind: RuntimeKind = .executorch
    public let isAvailable: Bool = false
    public nonisolated let supportedModels: [ModelInfo] = ModelCatalog.executorch
    public var loadedModelId: String? { nil }

    public init() {}

    public func loadModel(_ model: ModelInfo, progress: @Sendable @escaping (Double) -> Void) async throws {
        throw LLMRuntimeError.unsupported("ExecuTorch SPM products not added. See docs/executorch-arm-v1.md.")
    }

    public func unloadModel() async {}

    public func generate(prompt: String, parameters: GenerationParameters) -> AsyncThrowingStream<GenerationEvent, Error> {
        AsyncThrowingStream { c in
            c.finish(throwing: LLMRuntimeError.unsupported("ExecuTorch SPM products not added."))
        }
    }
}
#endif
