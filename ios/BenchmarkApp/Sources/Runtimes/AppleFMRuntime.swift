import Foundation
#if canImport(FoundationModels)
import FoundationModels
#endif

/// Apple Foundation Models adapter (`apple-fm`).
///
/// Wraps `FoundationModels.LanguageModelSession` (macOS 26 / iOS 26). Apple
/// FM doesn't expose a tokenizer, so prompt / generation token counts are
/// estimated as `utf8.count / 4` — read as a coarse proxy when comparing
/// against the other runtimes' real token counts.
///
/// Streaming yields cumulative content per partial. We diff against the
/// previously-emitted string and forward only the new substring as a
/// `.chunk`, so the per-chunk timestamps the runner stores in `tokenWindow`
/// reflect Apple FM's stream cadence rather than one fat final blob.
public actor AppleFMRuntime: LLMRuntime {
    public let kind: RuntimeKind = .appleFM
    public nonisolated let supportedModels: [ModelInfo] = ModelCatalog.appleFM

    public private(set) var loadedModelId: String?

    #if canImport(FoundationModels)
    // Stored as `Any?` so the property declaration doesn't itself require
    // macOS 26 availability; the read/write paths below all go through
    // `#available` gates and cast on demand.
    private var _session: Any?

    @available(macOS 26.0, iOS 26.0, *)
    private var session: LanguageModelSession? {
        get { _session as? LanguageModelSession }
        set { _session = newValue }
    }
    #endif

    public init() {}

    public nonisolated var isAvailable: Bool {
        #if canImport(FoundationModels)
        if #available(macOS 26.0, iOS 26.0, *) {
            switch SystemLanguageModel.default.availability {
            case .available: return true
            case .unavailable: return false
            }
        }
        return false
        #else
        return false
        #endif
    }

    public func loadModel(
        _ model: ModelInfo,
        progress: @Sendable @escaping (Double) -> Void
    ) async throws {
        #if canImport(FoundationModels)
        if #available(macOS 26.0, iOS 26.0, *) {
            switch SystemLanguageModel.default.availability {
            case .available:
                break
            case .unavailable(let reason):
                throw LLMRuntimeError.loadFailed("Apple FM unavailable: \(reason)")
            }
            progress(1.0)
            self.session = LanguageModelSession()
            self.loadedModelId = model.id
            return
        }
        #endif
        throw LLMRuntimeError.loadFailed(
            "Apple FoundationModels requires macOS 26 / iOS 26 and an Apple-Intelligence-eligible device."
        )
    }

    public func unloadModel() async {
        #if canImport(FoundationModels)
        if #available(macOS 26.0, iOS 26.0, *) {
            self.session = nil
        }
        #endif
        loadedModelId = nil
    }

    public nonisolated func generate(
        prompt: String,
        parameters: GenerationParameters
    ) -> AsyncThrowingStream<GenerationEvent, Error> {
        AsyncThrowingStream { continuation in
            let task = Task {
                #if canImport(FoundationModels)
                if #available(macOS 26.0, iOS 26.0, *) {
                    do {
                        guard let session = await self.session else {
                            throw LLMRuntimeError.modelNotLoaded
                        }

                        let options = GenerationOptions(
                            temperature: Double(parameters.temperature),
                            maximumResponseTokens: parameters.maxTokens
                        )

                        let promptStart = CFAbsoluteTimeGetCurrent()
                        let stream = session.streamResponse(
                            to: prompt,
                            options: options
                        )

                        var previousContent = ""
                        var promptTime: Double = 0
                        var firstChunkAt: CFAbsoluteTime?

                        for try await partial in stream {
                            try Task.checkCancellation()
                            // Apple FM yields a `Snapshot` (Response<String>.Snapshot)
                            // per partial. `.content` is the cumulative text so
                            // far; diff against the last emitted text and
                            // forward only the new substring as a chunk so the
                            // runner's per-chunk timestamps reflect Apple FM's
                            // actual stream cadence.
                            let current = partial.content
                            let delta: String
                            if current.hasPrefix(previousContent) {
                                delta = String(current.dropFirst(previousContent.count))
                            } else {
                                delta = current
                            }
                            previousContent = current

                            if firstChunkAt == nil {
                                let now = CFAbsoluteTimeGetCurrent()
                                firstChunkAt = now
                                promptTime = now - promptStart
                            }
                            if !delta.isEmpty {
                                continuation.yield(.chunk(delta))
                            }
                        }

                        let end = CFAbsoluteTimeGetCurrent()
                        let estGenTokens = max(1, previousContent.utf8.count / 4)
                        let estPromptTokens = max(1, prompt.utf8.count / 4)
                        let generateTime = end - (firstChunkAt ?? end)

                        continuation.yield(.info(GenerationInfo(
                            promptTokenCount: estPromptTokens,
                            generationTokenCount: estGenTokens,
                            promptTime: promptTime,
                            generateTime: max(generateTime, 0.001),
                            stopReason: .stop
                        )))
                        continuation.finish()
                        return
                    } catch is CancellationError {
                        continuation.yield(.info(GenerationInfo(
                            promptTokenCount: 0,
                            generationTokenCount: 0,
                            promptTime: 0,
                            generateTime: 0,
                            stopReason: .cancelled
                        )))
                        continuation.finish()
                        return
                    } catch {
                        continuation.finish(throwing: error)
                        return
                    }
                }
                #endif
                continuation.finish(throwing: LLMRuntimeError.loadFailed(
                    "Apple FoundationModels requires macOS 26 / iOS 26."
                ))
            }
            continuation.onTermination = { _ in
                task.cancel()
            }
        }
    }
}
