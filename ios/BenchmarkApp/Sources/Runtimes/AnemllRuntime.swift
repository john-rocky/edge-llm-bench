#if canImport(AnemllCore)
import Foundation
@preconcurrency import AnemllCore

/// ANEMLL adapter — runs LLMs on the Apple Neural Engine via the
/// multi-`.mlmodelc` bundle layout (embeddings + N FFN chunks + lm_head + meta.yaml).
///
/// Wraps `AnemllCore.InferenceManager.generateResponse(...)` from
/// https://github.com/Anemll/Anemll. Requires iOS 18+ and Swift 6.
@available(iOS 18.0, macOS 15.0, *)
public actor AnemllRuntime: LLMRuntime {
    public let kind: RuntimeKind = .anemll
    public let isAvailable: Bool = true
    public nonisolated let supportedModels: [ModelInfo] = ModelCatalog.anemll

    public private(set) var loadedModelId: String?

    private var loaded: LoadedModels?
    private var tokenizer: AnemllCore.Tokenizer?
    private var engine: InferenceManager?
    private var config: YAMLConfig?

    public init() {}

    public func loadModel(
        _ model: ModelInfo,
        progress: @Sendable @escaping (Double) -> Void
    ) async throws {
        guard supportedModels.contains(where: { $0.id == model.id }) else {
            throw LLMRuntimeError.modelNotInCatalog(model.id)
        }

        let snapshot = try await HFDownloader.snapshot(for: model, runtime: kind, progress: progress)
        let metaPath = snapshot.appendingPathComponent("meta.yaml").path
        guard FileManager.default.fileExists(atPath: metaPath) else {
            throw LLMRuntimeError.loadFailed("meta.yaml not found in \(snapshot.path)")
        }

        do {
            let cfg = try YAMLConfig.load(from: metaPath)
            self.config = cfg

            let tok = try await AnemllCore.Tokenizer(
                modelPath: snapshot.path,
                template: cfg.modelPrefix,
                debugLevel: 0
            )
            self.tokenizer = tok

            let loader = ModelLoader()
            let models = try await loader.loadModel(
                from: cfg,
                configuration: .init(computeUnits: .cpuAndNeuralEngine)
            )
            self.loaded = models

            self.engine = try InferenceManager(
                models: models,
                contextLength: cfg.contextLength,
                batchSize: cfg.batchSize,
                splitLMHead: cfg.splitLMHead,
                argmaxInModel: cfg.argmaxInModel,
                slidingWindow: cfg.slidingWindow,
                updateMaskPrefill: cfg.updateMaskPrefill,
                prefillDynamicSlice: cfg.prefillDynamicSlice,
                modelPrefix: cfg.modelPrefix,
                vocabSize: cfg.vocabSize,
                lmHeadChunkSizes: cfg.lmHeadChunkSizes
            )

            self.loadedModelId = model.id
        } catch {
            throw LLMRuntimeError.loadFailed(error.localizedDescription)
        }
    }

    public func unloadModel() async {
        engine?.unload()
        engine = nil
        loaded = nil
        tokenizer = nil
        config = nil
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
                Task { await self.engine?.AbortGeneration(Code: 1) }
                task.cancel()
            }
        }
    }

    private func runGenerate(
        prompt: String,
        parameters: GenerationParameters,
        continuation: AsyncThrowingStream<GenerationEvent, Error>.Continuation
    ) async throws {
        guard let engine, let tokenizer else { throw LLMRuntimeError.modelNotLoaded }

        let messages: [AnemllCore.Tokenizer.ChatMessage] = [.user(prompt)]
        let initialTokens = tokenizer.applyChatTemplate(input: messages, addGenerationPrompt: true)

        var firstTokenAt: CFAbsoluteTime?
        var tokenCount = 0
        let prefillStart = CFAbsoluteTimeGetCurrent()

        let (_, prefillTime, _) = try await engine.generateResponse(
            initialTokens: initialTokens,
            temperature: parameters.temperature,
            maxTokens: parameters.maxTokens,
            eosTokens: tokenizer.eosTokenIds,
            tokenizer: tokenizer,
            onToken: { tokenId in
                if firstTokenAt == nil { firstTokenAt = CFAbsoluteTimeGetCurrent() }
                let piece = tokenizer.decode(tokens: [tokenId], skipSpecialTokens: true)
                if !piece.isEmpty { continuation.yield(.chunk(piece)) }
                tokenCount += 1
            },
            onWindowShift: { }
        )

        let end = CFAbsoluteTimeGetCurrent()
        let _ = prefillStart // referenced for clarity
        let generateTime = max(end - (firstTokenAt ?? (prefillStart + prefillTime)), 0.001)

        continuation.yield(.info(GenerationInfo(
            promptTokenCount: initialTokens.count,
            generationTokenCount: tokenCount,
            promptTime: prefillTime,
            generateTime: generateTime,
            stopReason: tokenCount >= parameters.maxTokens ? .length : .stop
        )))
        continuation.finish()
    }
}
#else
import Foundation

/// Compile-time-disabled ANEMLL runtime. Add the AnemllCore SPM product
/// from https://github.com/Anemll/Anemll (subdirectory `anemll-swift-cli`)
/// to enable. See `runtimes/anemll.md`.
public final class AnemllRuntime: LLMRuntime, @unchecked Sendable {
    public let kind: RuntimeKind = .anemll
    public let isAvailable: Bool = false
    public nonisolated let supportedModels: [ModelInfo] = ModelCatalog.anemll
    public var loadedModelId: String? { nil }

    public init() {}

    public func loadModel(_ model: ModelInfo, progress: @Sendable @escaping (Double) -> Void) async throws {
        throw LLMRuntimeError.unsupported("AnemllCore SPM product not added. See runtimes/anemll.md.")
    }

    public func unloadModel() async {}

    public func generate(prompt: String, parameters: GenerationParameters) -> AsyncThrowingStream<GenerationEvent, Error> {
        AsyncThrowingStream { c in
            c.finish(throwing: LLMRuntimeError.unsupported("AnemllCore SPM product not added."))
        }
    }
}
#endif
