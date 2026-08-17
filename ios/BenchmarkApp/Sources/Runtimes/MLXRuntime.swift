import Foundation
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

    private static func translate(_ reason: GenerateStopReason) -> GenerationInfo.StopReason {
        switch reason {
        case .stop: return .stop
        case .length: return .length
        case .cancelled: return .cancelled
        @unknown default: return .stop
        }
    }
}
