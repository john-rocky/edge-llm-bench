#if canImport(ExecuTorchLLM)
import Foundation
import ExecuTorch
import ExecuTorchLLM

/// PyTorch ExecuTorch adapter using the Apple `TextRunner` Swift binding.
///
/// Loads a `.pte` model exported with the executorch llama exporter
/// (XNNPACK or CoreML backend) plus a sentencepiece `tokenizer.model`.
/// Streams tokens via `TextRunner.generate(_:_:tokenCallback:)`.
///
/// Requires iOS 17+ and the `executorch_llm` SwiftPM product.
public actor ExecuTorchRuntime: LLMRuntime {
    public let kind: RuntimeKind = .executorch
    public let isAvailable: Bool = true
    public nonisolated let supportedModels: [ModelInfo] = ModelCatalog.executorch

    public private(set) var loadedModelId: String?

    private var runner: TextRunner?

    public init() {}

    public func loadModel(
        _ model: ModelInfo,
        progress: @Sendable @escaping (Double) -> Void
    ) async throws {
        guard supportedModels.contains(where: { $0.id == model.id }) else {
            throw LLMRuntimeError.modelNotInCatalog(model.id)
        }

        let snapshot = try await HFDownloader.snapshot(for: model, runtime: kind, progress: progress)
        let pteURL = snapshot.appendingPathComponent(model.primaryFile)
        let tokenizerURL = snapshot.appendingPathComponent("tokenizer.model")

        guard FileManager.default.fileExists(atPath: pteURL.path) else {
            throw LLMRuntimeError.loadFailed(".pte not found at \(pteURL.path)")
        }
        guard FileManager.default.fileExists(atPath: tokenizerURL.path) else {
            throw LLMRuntimeError.loadFailed("tokenizer.model not found in \(snapshot.path)")
        }

        let r = TextRunner(modelPath: pteURL.path, tokenizerPath: tokenizerURL.path, specialTokens: [])
        do {
            try r.load()
            self.runner = r
            self.loadedModelId = model.id
        } catch {
            throw LLMRuntimeError.loadFailed(error.localizedDescription)
        }
    }

    public func unloadModel() async {
        runner?.stop()
        runner = nil
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
        guard let runner else { throw LLMRuntimeError.modelNotLoaded }

        let config = Config { c in
            c.sequenceLength = 2048
            c.maximumNewTokens = parameters.maxTokens
            c.temperature = Double(parameters.temperature)
            c.isEchoEnabled = false
        }

        let prefillStart = CFAbsoluteTimeGetCurrent()
        var firstTokenAt: CFAbsoluteTime?
        var tokenCount = 0

        try await withCheckedThrowingContinuation { (cc: CheckedContinuation<Void, Error>) in
            do {
                try runner.generate(prompt, config) { piece in
                    if firstTokenAt == nil { firstTokenAt = CFAbsoluteTimeGetCurrent() }
                    continuation.yield(.chunk(piece))
                    tokenCount += 1
                }
                cc.resume()
            } catch {
                cc.resume(throwing: error)
            }
        }

        let end = CFAbsoluteTimeGetCurrent()
        let prefillTime = (firstTokenAt ?? end) - prefillStart
        let generateTime = max(end - (firstTokenAt ?? prefillStart), 0.001)

        continuation.yield(.info(GenerationInfo(
            promptTokenCount: 0,
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

/// Compile-time-disabled ExecuTorch runtime. Add the executorch SPM
/// products (`executorch`, `executorch_llm`, `backend_xnnpack`,
/// `kernels_llm`, `kernels_optimized`, `kernels_quantized`) from
/// https://github.com/pytorch/executorch.git branch swiftpm-* to enable.
public final class ExecuTorchRuntime: LLMRuntime, @unchecked Sendable {
    public let kind: RuntimeKind = .executorch
    public let isAvailable: Bool = false
    public nonisolated let supportedModels: [ModelInfo] = ModelCatalog.executorch
    public var loadedModelId: String? { nil }

    public init() {}

    public func loadModel(_ model: ModelInfo, progress: @Sendable @escaping (Double) -> Void) async throws {
        throw LLMRuntimeError.unsupported("ExecuTorch SPM products not added. See runtimes/executorch.md.")
    }

    public func unloadModel() async {}

    public func generate(prompt: String, parameters: GenerationParameters) -> AsyncThrowingStream<GenerationEvent, Error> {
        AsyncThrowingStream { c in
            c.finish(throwing: LLMRuntimeError.unsupported("ExecuTorch SPM products not added."))
        }
    }
}
#endif
