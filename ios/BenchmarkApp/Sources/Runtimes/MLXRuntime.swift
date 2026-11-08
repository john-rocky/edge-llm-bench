import Foundation
import MLX
import MLXLLM
import MLXLMCommon
import HuggingFace
import Tokenizers

/// MLX Swift LM adapter.
///
/// Loads a model from the Hugging Face Hub via `HubClient.default`, runs streaming
/// generation through the `MLXLMCommon.generate(input:parameters:context:)` AsyncStream,
/// and translates events into the runtime-agnostic `GenerationEvent` surface.
public actor MLXRuntime: LLMRuntime {
    public let kind: RuntimeKind = .mlxSwift
    public let isAvailable: Bool = true
    public nonisolated let supportedModels: [ModelInfo] = ModelCatalog.mlx

    public private(set) var loadedModelId: String?
    private var container: ModelContainer?

    public init() {}

    public func loadModel(
        _ model: ModelInfo,
        progress: @Sendable @escaping (Double) -> Void
    ) async throws {
        let configuration = ModelConfiguration(id: model.id)
        print("[MLX] load starting: \(model.id)")
        let t0 = CFAbsoluteTimeGetCurrent()
        do {
            let container = try await loadModelContainer(
                from: HubDownloaderBridge(client: HubClient.default),
                using: HFTokenizerLoaderBridge(),
                configuration: configuration,
                progressHandler: { p in
                    let pct = Int(p.fractionCompleted * 100)
                    print(String(format: "[MLX] download progress: %d%% (%lld/%lld bytes)",
                                  pct, p.completedUnitCount, p.totalUnitCount))
                    progress(p.fractionCompleted)
                }
            )
            self.container = container
            self.loadedModelId = model.id
            let dt = CFAbsoluteTimeGetCurrent() - t0
            print(String(format: "[MLX] load complete in %.2fs", dt))
        } catch {
            print("[MLX] load FAILED: \(error.localizedDescription)")
            throw LLMRuntimeError.loadFailed(error.localizedDescription)
        }
    }

    public func unloadModel() async {
        container = nil
        loadedModelId = nil
    }

    public nonisolated func generate(
        prompt: String,
        parameters: GenerationParameters
    ) -> AsyncThrowingStream<GenerationEvent, Error> {
        AsyncThrowingStream { continuation in
            let task = Task {
                do {
                    guard let container = await self.container else {
                        throw LLMRuntimeError.modelNotLoaded
                    }

                    let mlxParameters = GenerateParameters(
                        maxTokens: parameters.maxTokens,
                        temperature: parameters.temperature,
                        topP: parameters.topP
                    )

                    let lmInput = try await container.prepare(input: UserInput(prompt: prompt))
                    let stream = try await container.generate(
                        input: lmInput,
                        parameters: mlxParameters
                    )

                    for await event in stream {
                        try Task.checkCancellation()
                        switch event {
                        case .chunk(let text):
                            continuation.yield(.chunk(text))
                        case .info(let info):
                            continuation.yield(.info(GenerationInfo(
                                promptTokenCount: info.promptTokenCount,
                                generationTokenCount: info.generationTokenCount,
                                promptTime: info.promptTime,
                                generateTime: info.generateTime,
                                stopReason: Self.translate(info.stopReason)
                            )))
                        case .toolCall:
                            break
                        }
                    }

                    continuation.finish()
                } catch is CancellationError {
                    continuation.yield(.info(GenerationInfo(
                        promptTokenCount: 0,
                        generationTokenCount: 0,
                        promptTime: 0,
                        generateTime: 0,
                        stopReason: .cancelled
                    )))
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }

            continuation.onTermination = { _ in
                task.cancel()
            }
        }
    }

    /// The counts and clocks of one `nativeBenchmark` call.
    public struct NativeBenchmarkResult: Sendable {
        /// token ids handed to the one prefill (the LMInput's length)
        public let prefillTokenCount: Int
        /// tokens the iterator returned (the first is the pick from the prefill logits)
        public let decodeTokenCount: Int
        /// TokenIterator.promptPrefillTime (prepare) + the wait for the first token: mlx-swift-lm's promptTime
        public let prefillSeconds: Double
        /// first token -> last token: mlx-swift-lm's generateTime
        public let decodeSeconds: Double
        /// the prefill window passed to prepare (prompt chunks above it)
        public let prefillStepSize: Int
        /// forward passes over the prompt in prepare: ceil(P / prefillStepSize)
        public let prefillChunks: Int
        /// the first ids, for the record (the rest follow from the seed)
        public let firstTokenIds: [Int]
        public let seed: UInt64
        /// the ids are drawn below it (config.json vocab_size)
        public let vocabSize: Int
        /// mlx-swift-lm's definitions, the ones the app's MLX records use (BenchmarkRunner)
        public var prefillTokensPerSecond: Double { Double(prefillTokenCount) / prefillSeconds }
        public var decodeTokensPerSecond: Double { Double(decodeTokenCount) / decodeSeconds }
    }

    /// `native-benchmark-<P>x<D>` on the MLX Swift engine, after mlx-lm's own benchmark
    /// (mlx_lm/benchmark.py: random token ids below the config's vocab_size, EOS cleared,
    /// `max_tokens` = D, prefill step 2048): P token ids below the model's vocab_size (its
    /// config.json, as mlx-lm reads it), drawn by SplitMix64 from seed 0 as Apple's llm-benchmark
    /// and the Core AI port here do (CoreAIRuntime.randomPrompt; no text, no tokenizer, no chat
    /// template), go to one `TokenIterator`, whose `prepare` is the one prefill (one forward pass for P up to 2048), and
    /// the iterator runs to `maxTokens` = D: `TokenIterator.next()` stops only there; the EOS check
    /// lives in `generate(...)`, which this path does not call, so the model's output cannot end
    /// the decode. Greedy (temperature 0), as mlx-lm's default sampler. The timing cut points are
    /// mlx-swift-lm's own (`runSynchronousGenerationLoop`): prefill = prepare + the wait for the
    /// first token, decode = the first token to the last, and the rates the app's MLX records use.
    public func nativeBenchmark(prefillTokens: Int, decodeTokens: Int, seed: UInt64 = 0) async throws
        -> NativeBenchmarkResult
    {
        guard let container else { throw LLMRuntimeError.modelNotLoaded }
        let vocab = try Self.vocabSize(at: try await container.modelDirectory)
        var state = seed &+ 0x9E37_79B9_7F4A_7C15
        let ids: [Int32] = (0..<prefillTokens).map { _ in
            // SplitMix64 (CoreAIRuntime.randomPrompt): one fixed sequence per seed on every device
            state &+= 0x9E37_79B9_7F4A_7C15
            var z = state
            z = (z ^ (z >> 30)) &* 0xBF58_476D_1CE4_E5B9
            z = (z ^ (z >> 27)) &* 0x94D0_49BB_1331_11EB
            return Int32((z ^ (z >> 31)) % UInt64(vocab))
        }
        let step = max(2048, prefillTokens)
        struct Clocks: Sendable { let count: Int; let prefillSeconds: Double; let decodeSeconds: Double }
        let clocks = try await container.perform { context in
            let input = LMInput(tokens: MLXArray(ids))
            let parameters = GenerateParameters(maxTokens: decodeTokens, temperature: 0, prefillStepSize: step)
            var iterator = try TokenIterator(input: input, model: context.model, parameters: parameters)
            var start = Date.timeIntervalSinceReferenceDate
            var promptWait: TimeInterval = 0
            var count = 0
            while let _ = iterator.next() {
                if count == 0 {
                    let now = Date.timeIntervalSinceReferenceDate
                    promptWait = now - start
                    start = now
                }
                count += 1
            }
            let decodeSeconds = Date.timeIntervalSinceReferenceDate - start
            // TokenIterator keeps one step in flight (asyncEval); finish it before returning
            Stream().synchronize()
            return Clocks(count: count, prefillSeconds: iterator.promptPrefillTime + promptWait,
                          decodeSeconds: decodeSeconds)
        }
        return NativeBenchmarkResult(
            prefillTokenCount: ids.count, decodeTokenCount: clocks.count,
            prefillSeconds: clocks.prefillSeconds, decodeSeconds: clocks.decodeSeconds,
            prefillStepSize: step, prefillChunks: (ids.count + step - 1) / step,
            firstTokenIds: ids.prefix(8).map { Int($0) }, seed: seed, vocabSize: vocab)
    }

    /// config.json's vocab_size, or text_config.vocab_size (mlx_lm/benchmark.py reads the same two).
    static func vocabSize(at directory: URL) throws -> Int {
        let data = try Data(contentsOf: directory.appendingPathComponent("config.json"))
        let config = try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
        if let v = config["vocab_size"] as? Int, v > 0 { return v }
        if let text = config["text_config"] as? [String: Any], let v = text["vocab_size"] as? Int, v > 0 {
            return v
        }
        throw LLMRuntimeError.loadFailed("no vocab_size in \(directory.path)/config.json")
    }

    private static func translate(_ reason: GenerateStopReason) -> GenerationInfo.StopReason {
        switch reason {
        case .stop: return .stop
        case .length: return .length
        case .cancelled: return .cancelled
        @unknown default: return .stop
        }
    }
}
