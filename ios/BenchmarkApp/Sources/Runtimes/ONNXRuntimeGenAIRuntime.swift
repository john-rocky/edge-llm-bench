#if canImport(onnxruntime_genai)
import CryptoKit
import Foundation
import HuggingFace
import onnxruntime_genai

/// ONNX Runtime GenAI adapter — the release `onnxruntime-genai.xcframework` (0.17.0, a CPU
/// build: the CPU EP is the arm), driven through its C API (`ort_genai_c.h`, exposed as the
/// module `onnxruntime_genai` by the map `scripts/fetch_ortgenai_xcframework.sh` writes next
/// to the framework).
///
/// The arm's protocol on every platform (docs/ortgenai-arm-v1.md): the folder's
/// `chat_template.jinja` on one user turn, no system prompt (Qwen3 thinking on); greedy
/// (`do_sample` false) for the greedy tasks; `max_length` = the run's context budget
/// (`prepareContext`, the cells' `context-tokens=`), which GenAI allocates the KV cache for
/// when a generator is created; a new generator per generation; stop at EOS or the task
/// budget, no `min_length`.
///
/// Cut points (upstream `model_benchmark`, the Mac and Android drivers): `promptTime` = the
/// wall clock of `AppendTokenSequences` (prompt forward pass + logits). The first
/// `GenerateNextToken` is a greedy pick from those logits, no forward pass. `generateTime` =
/// the summed wall clock of `GenerateNextToken` calls 2..N, each one forward pass + a pick,
/// and `generationTokenCount` = the N − 1 tokens those calls produce, so the runner's
/// decode rate (count / time) is the arm's decode tok/s. The Mac and Android records count
/// all N picked tokens; this one counts the decode loop's, as the iPhone ExecuTorch adapter.
/// The runner's TTFT is its own wall clock (call start → first streamed text: template,
/// tokenizer, generator creation, prefill, first pick); the engine-side split of every
/// generation is printed as a `YARDSTICK_NOTE ortgenai_run` line.
///
/// Telemetry: the release links the 1DS SDK (on by default). GenAI reads
/// `ORT_DISABLE_TELEMETRY` when the first model is created (v0.17.0
/// `CreateModelWithTelemetry` → `GenAiTelemetry::Initialize`), and the variable keeps the
/// uploader, the events and the device id off for the process. It is set when this runtime
/// is created (app start) and again before every model load, and `OgaSetTelemetryEnabled(false)`
/// is called before the load too.
///
/// Threads: GenAI sets the intra-op thread count itself unless the folder's genai_config.json
/// names one: min(max(1, hardware_concurrency() / 2), 16) (v0.17.0 `src/models/model.cpp`
/// `CreateSessionOptionsFromConfig`), and the C API has no getter. Every load prints that rule's
/// value from `activeProcessorCount` and whether the folder sets `intra_op_num_threads`. A lever
/// run only (the dashboard arm runs the folder as published): `ORTGENAI_INTRA_OP_THREADS=<n>` in
/// the launch environment loads a copy of the folder whose genai_config.json sets
/// `model.decoder.session_options.intra_op_num_threads` = n (the fetched folder stays as it is).
public actor ONNXRuntimeGenAIRuntime: LLMRuntime {
    public let kind: RuntimeKind = .onnxRuntimeGenAI
    public let isAvailable: Bool = true
    public nonisolated let supportedModels: [ModelInfo] = ModelCatalog.onnxRuntimeGenAI

    /// The arm carries its backend on every platform (`onnxruntime-genai-cpu`).
    public var recordRuntimeLabel: String { "\(kind.rawValue)-cpu" }

    public private(set) var loadedModelId: String?

    private var model: OpaquePointer?
    private var tokenizer: OpaquePointer?
    private var eosTokenIds: Set<Int32> = []
    /// `max_length` of every generator. 2048 = the cells' `context-tokens`; `prepareContext`
    /// sets it before a load.
    private var maxLength = 2048

    public init() {
        Self.disableTelemetryEnvironment()
    }

    public func prepareContext(maxContextTokens: Int) {
        maxLength = maxContextTokens
    }

    public func loadModel(
        _ model: ModelInfo,
        progress: @Sendable @escaping (Double) -> Void
    ) async throws {
        guard supportedModels.contains(where: { $0.id == model.id }) else {
            throw LLMRuntimeError.modelNotInCatalog(model.id)
        }
        guard let revision = ModelCatalog.onnxRuntimeGenAIRevisions[model.id] else {
            throw LLMRuntimeError.loadFailed("no pinned HF revision for \(model.id)")
        }
        let fetched = try await Self.fetchFolder(model, revision: revision, progress: progress)
        let eos = try Self.eosTokenIds(folder: fetched)
        let folderThreads = try Self.configIntraOpThreads(folder: fetched)
        let threadsOverride = try Self.intraOpThreadsOverride()
        let folder = try threadsOverride.map { try Self.threadsCopy(of: fetched, model: model, intraOpThreads: $0) }
            ?? fetched

        await unloadModel()
        Self.disableTelemetryEnvironment()
        OgaSetTelemetryEnabled(false)

        let t0 = Self.now()
        var newModel: OpaquePointer?
        try Self.check(OgaCreateModel(folder.path, &newModel), "OgaCreateModel")
        guard let newModel else { throw LLMRuntimeError.loadFailed("OgaCreateModel returned no model") }
        var newTokenizer: OpaquePointer?
        do {
            try Self.check(OgaCreateTokenizer(newModel, &newTokenizer), "OgaCreateTokenizer")
        } catch {
            OgaDestroyModel(newModel)
            throw error
        }
        let loadSeconds = Self.now() - t0

        var deviceTypePtr: UnsafePointer<CChar>?
        let deviceTypeResult = OgaModelGetDeviceType(newModel, &deviceTypePtr)
        let deviceType = deviceTypeResult == nil ? (deviceTypePtr.map { String(cString: $0) } ?? "?") : "?"
        if let deviceTypePtr { OgaDestroyString(deviceTypePtr) }
        if let deviceTypeResult { OgaDestroyResult(deviceTypeResult) }
        guard deviceType == "CPU" else {
            OgaDestroyTokenizer(newTokenizer)
            OgaDestroyModel(newModel)
            throw LLMRuntimeError.loadFailed("expected the CPU device type, the model reports \(deviceType)")
        }

        self.model = newModel
        self.tokenizer = newTokenizer
        self.eosTokenIds = eos
        self.loadedModelId = model.id
        let telemetryEnv = getenv("ORT_DISABLE_TELEMETRY").map { String(cString: $0) } ?? "unset"
        let processors = ProcessInfo.processInfo.activeProcessorCount
        let threads = threadsOverride.map { "intra_op_num_threads=\($0)(ORTGENAI_INTRA_OP_THREADS,folder-copy)" }
            ?? folderThreads.map { "intra_op_num_threads=\($0)(folder)" } ?? "engine-default"
        Self.note(String(
            format: "YARDSTICK_NOTE ortgenai_load model=%@ revision=%@ folder=%@ device_type=%@ ort=%@ "
                + "load_s=%.3f eos=%@ max_length=%ld threads=%@ processors=%ld "
                + "engine_default_threads=%ld(min(max(1,processors/2),16)) folder_intra_op_num_threads=%@ "
                + "telemetry=ORT_DISABLE_TELEMETRY=%@,api-disabled",
            model.id, revision, (model.primaryFile as NSString).deletingLastPathComponent, deviceType,
            Self.loadedOrtVersion(), loadSeconds,
            eos.sorted().map(String.init).joined(separator: ","), maxLength, threads,
            processors, min(max(1, processors / 2), 16), folderThreads.map(String.init) ?? "none", telemetryEnv
        ))
        if threadsOverride != nil {
            Self.note("YARDSTICK_NOTE ortgenai_threads_copy " + folder.path)
        }
    }

    public func unloadModel() async {
        if let tokenizer { OgaDestroyTokenizer(tokenizer) }
        if let model { OgaDestroyModel(model) }
        tokenizer = nil
        model = nil
        eosTokenIds = []
        loadedModelId = nil
        // No OgaShutdown(): it tears down GenAI's ONNX Runtime environment, and the next load
        // in the process would initialize a fresh one.
    }

    public nonisolated func generate(
        prompt: String,
        parameters: GenerationParameters
    ) -> AsyncThrowingStream<GenerationEvent, Error> {
        AsyncThrowingStream { continuation in
            let task = Task {
                do {
                    try await self.runGenerate(prompt: prompt, parameters: parameters, continuation: continuation)
                } catch is CancellationError {
                    continuation.yield(.info(GenerationInfo(
                        promptTokenCount: 0, generationTokenCount: 0,
                        promptTime: 0, generateTime: 0, stopReason: .cancelled
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

    private func runGenerate(
        prompt: String,
        parameters: GenerationParameters,
        continuation: AsyncThrowingStream<GenerationEvent, Error>.Continuation
    ) throws {
        guard let model, let tokenizer else { throw LLMRuntimeError.modelNotLoaded }

        // The folder's chat template on one user turn (template_str nil = the tokenizer's own).
        let messagesData = try JSONSerialization.data(
            withJSONObject: [["role": "user", "content": prompt]], options: [.withoutEscapingSlashes])
        let messages = String(decoding: messagesData, as: UTF8.self)
        var templatedPtr: UnsafePointer<CChar>?
        try Self.check(OgaTokenizerApplyChatTemplate(tokenizer, nil, messages, nil, true, &templatedPtr),
                       "OgaTokenizerApplyChatTemplate")
        guard let templatedPtr else { throw OgaError(call: "OgaTokenizerApplyChatTemplate", message: "no output") }
        let templated = String(cString: templatedPtr)
        OgaDestroyString(templatedPtr)

        var sequences: OpaquePointer?
        try Self.check(OgaCreateSequences(&sequences), "OgaCreateSequences")
        defer { OgaDestroySequences(sequences) }
        try Self.check(OgaTokenizerEncode(tokenizer, templated, sequences), "OgaTokenizerEncode")
        let promptTokens = OgaSequencesGetSequenceCount(sequences, 0)

        var params: OpaquePointer?
        try Self.check(OgaCreateGeneratorParams(model, &params), "OgaCreateGeneratorParams")
        defer { OgaDestroyGeneratorParams(params) }
        try Self.check(OgaGeneratorParamsSetSearchNumber(params, "max_length", Double(maxLength)),
                       "OgaGeneratorParamsSetSearchNumber(max_length)")
        let sampler: String
        if parameters.temperature <= 0 {
            try Self.check(OgaGeneratorParamsSetSearchBool(params, "do_sample", false),
                           "OgaGeneratorParamsSetSearchBool(do_sample)")
            sampler = "greedy"
        } else {
            try Self.check(OgaGeneratorParamsSetSearchBool(params, "do_sample", true),
                           "OgaGeneratorParamsSetSearchBool(do_sample)")
            try Self.check(OgaGeneratorParamsSetSearchNumber(params, "temperature", Double(parameters.temperature)),
                           "OgaGeneratorParamsSetSearchNumber(temperature)")
            try Self.check(OgaGeneratorParamsSetSearchNumber(params, "top_p", Double(parameters.topP)),
                           "OgaGeneratorParamsSetSearchNumber(top_p)")
            sampler = String(format: "sampled(temperature=%.2f,top_p=%.2f)", parameters.temperature, parameters.topP)
        }

        // A new generator per generation: its KV cache (max_length) is allocated here.
        let generatorStart = Self.now()
        var generator: OpaquePointer?
        try Self.check(OgaCreateGenerator(model, params, &generator), "OgaCreateGenerator")
        defer { OgaDestroyGenerator(generator) }
        let generatorSeconds = Self.now() - generatorStart

        var stream: OpaquePointer?
        try Self.check(OgaCreateTokenizerStream(tokenizer, &stream), "OgaCreateTokenizerStream")
        defer { OgaDestroyTokenizerStream(stream) }

        let prefillStart = Self.now()
        try Self.check(OgaGenerator_AppendTokenSequences(generator, sequences), "OgaGenerator_AppendTokenSequences")
        let promptTime = Self.now() - prefillStart

        var steps: [Double] = []
        steps.reserveCapacity(parameters.maxTokens)
        var tokens: [Int32] = []
        tokens.reserveCapacity(parameters.maxTokens)
        var text = ""
        while !OgaGenerator_IsDone(generator) && tokens.count < parameters.maxTokens {
            try Task.checkCancellation()
            let stepStart = Self.now()
            try Self.check(OgaGenerator_GenerateNextToken(generator), "OgaGenerator_GenerateNextToken")
            steps.append(Self.now() - stepStart)
            var next: UnsafePointer<Int32>?
            var count = 0
            try Self.check(OgaGenerator_GetNextTokens(generator, &next, &count), "OgaGenerator_GetNextTokens")
            guard let next, count > 0 else { throw OgaError(call: "OgaGenerator_GetNextTokens", message: "no token") }
            let token = next[0]
            tokens.append(token)
            if eosTokenIds.contains(token) { continue }  // the loop ends on IsDone; EOS is not text
            var piece: UnsafePointer<CChar>?
            try Self.check(OgaTokenizerStreamDecode(stream, token, &piece), "OgaTokenizerStreamDecode")
            if let piece, piece.pointee != 0 {
                let chunk = String(cString: piece)
                text += chunk
                continuation.yield(.chunk(chunk))
            }
        }

        let hitEOS = tokens.last.map { eosTokenIds.contains($0) } ?? false
        // The Mac and Android drivers' words: stop = EOS, length = the budget, max_length = the
        // KV allocation filled (no third reason in the app's record: it reads `length` there).
        let stopWord = hitEOS ? "stop" : (tokens.count >= parameters.maxTokens ? "length" : "max_length")
        let firstStep = steps.first ?? 0
        let decodeTime = steps.dropFirst().reduce(0, +)
        let decodeTokens = max(tokens.count - 1, 0)
        let templatedSha = SHA256.hash(data: Data(templated.utf8)).map { String(format: "%02x", $0) }.joined()
        Self.note(String(
            format: "YARDSTICK_NOTE ortgenai_run prompt_tokens=%ld picked_tokens=%ld decode_tokens=%ld "
                + "generator_ms=%.3f prefill_ms=%.3f first_step_ms=%.3f decode_ms=%.3f "
                + "prefill_tok_s=%.2f decode_tok_s=%.2f engine_ttft_ms=%.3f stop=%@ max_length=%ld "
                + "sampler=%@ templated_sha256=%@",
            promptTokens, tokens.count, decodeTokens,
            generatorSeconds * 1000, promptTime * 1000, firstStep * 1000, decodeTime * 1000,
            promptTime > 0 ? Double(promptTokens) / promptTime : 0,
            decodeTime > 0 ? Double(decodeTokens) / decodeTime : 0,
            (promptTime + firstStep) * 1000, stopWord, maxLength, sampler, templatedSha
        ))
        if let textJSON = try? JSONSerialization.data(withJSONObject: [text], options: [.withoutEscapingSlashes]) {
            Self.note("YARDSTICK_NOTE ortgenai_text " + String(decoding: textJSON, as: UTF8.self))
        }

        continuation.yield(.info(GenerationInfo(
            promptTokenCount: promptTokens,
            generationTokenCount: decodeTokens,
            promptTime: promptTime,
            generateTime: decodeTime,
            stopReason: hitEOS ? .stop : .length
        )))
        continuation.finish()
    }

    // MARK: - Helpers

    /// Fetch the model's folder at the pinned commit into the hub cache (python layout,
    /// `Library/Caches/huggingface/hub`). A commit revision is served from the cache once its
    /// files are there (no network after the first fetch).
    private static func fetchFolder(
        _ model: ModelInfo, revision: String, progress: @Sendable @escaping (Double) -> Void
    ) async throws -> URL {
        guard let repo = HuggingFace.Repo.ID(rawValue: model.hfRepoId) else {
            throw LLMRuntimeError.downloadFailed("Invalid HF repo id: \(model.hfRepoId)")
        }
        let snapshot: URL
        do {
            snapshot = try await HubClient.default.downloadSnapshot(
                of: repo,
                revision: revision,
                matching: model.hfFilePatterns,
                progressHandler: { @MainActor p in
                    progress(p.fractionCompleted)
                }
            )
        } catch {
            throw LLMRuntimeError.downloadFailed(error.localizedDescription)
        }
        // BenchmarkRunner stamps the record's modelRevision from the cache's refs/main
        // (HFDownloader.resolvedRevision), and a download by commit writes no ref: point refs/main
        // at the commit the files came from, the way a sideload stage pins it.
        try? HubClient.default.cache?.updateRef(repo: repo, kind: .model, ref: "main", commit: revision)
        let folder = snapshot.appendingPathComponent(
            (model.primaryFile as NSString).deletingLastPathComponent, isDirectory: true)
        guard FileManager.default.fileExists(atPath: folder.appendingPathComponent("genai_config.json").path) else {
            throw LLMRuntimeError.loadFailed("no genai_config.json in \(folder.path)")
        }
        return folder
    }

    /// genai_config.json `model.eos_token_id` (an id or a list), as the Mac driver reads it.
    private static func eosTokenIds(folder: URL) throws -> Set<Int32> {
        let data = try Data(contentsOf: folder.appendingPathComponent("genai_config.json"))
        guard let root = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let config = root["model"] as? [String: Any] else {
            throw LLMRuntimeError.loadFailed("genai_config.json has no model section")
        }
        if let one = config["eos_token_id"] as? Int { return [Int32(one)] }
        if let many = config["eos_token_id"] as? [Int], !many.isEmpty { return Set(many.map { Int32($0) }) }
        throw LLMRuntimeError.loadFailed("genai_config.json has no model.eos_token_id")
    }

    /// genai_config.json `model.decoder.session_options.intra_op_num_threads` (nil: the folder does
    /// not set it, and GenAI picks the count).
    private static func configIntraOpThreads(folder: URL) throws -> Int? {
        let data = try Data(contentsOf: folder.appendingPathComponent("genai_config.json"))
        let root = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        let decoder = (root?["model"] as? [String: Any])?["decoder"] as? [String: Any]
        return (decoder?["session_options"] as? [String: Any])?["intra_op_num_threads"] as? Int
    }

    /// `ORTGENAI_INTRA_OP_THREADS` from the launch environment (a lever run); nil when unset.
    private static func intraOpThreadsOverride() throws -> Int? {
        guard let raw = ProcessInfo.processInfo.environment["ORTGENAI_INTRA_OP_THREADS"] else { return nil }
        guard let n = Int(raw), n > 0 else {
            throw LLMRuntimeError.loadFailed("ORTGENAI_INTRA_OP_THREADS must be a positive integer, got '\(raw)'")
        }
        return n
    }

    /// The fetched folder copied to `Library/Caches/ortgenai-threads/<repo>-intra<n>/`, rebuilt at every
    /// load: each file a copy of its real file (the hub cache's snapshot entries are links into its blob
    /// store; FileManager clones on APFS), genai_config.json written with
    /// `model.decoder.session_options.intra_op_num_threads` = n. The fetched folder is not written.
    private static func threadsCopy(of folder: URL, model: ModelInfo, intraOpThreads: Int) throws -> URL {
        let fm = FileManager.default
        let caches = try fm.url(for: .cachesDirectory, in: .userDomainMask, appropriateFor: nil, create: true)
        let copy = caches.appendingPathComponent("ortgenai-threads", isDirectory: true).appendingPathComponent(
            "\(model.hfRepoId.replacingOccurrences(of: "/", with: "_"))-intra\(intraOpThreads)", isDirectory: true)
        if fm.fileExists(atPath: copy.path) { try fm.removeItem(at: copy) }
        try fm.createDirectory(at: copy, withIntermediateDirectories: true)
        for name in try fm.contentsOfDirectory(atPath: folder.path) {
            let source = folder.appendingPathComponent(name).resolvingSymlinksInPath()
            let target = copy.appendingPathComponent(name)
            guard name == "genai_config.json" else {
                try fm.copyItem(at: source, to: target)
                continue
            }
            let data = try Data(contentsOf: source)
            guard var root = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                  var config = root["model"] as? [String: Any],
                  var decoder = config["decoder"] as? [String: Any] else {
                throw LLMRuntimeError.loadFailed("genai_config.json has no model.decoder section")
            }
            var session = decoder["session_options"] as? [String: Any] ?? [:]
            session["intra_op_num_threads"] = intraOpThreads
            decoder["session_options"] = session
            config["decoder"] = decoder
            root["model"] = config
            try JSONSerialization.data(withJSONObject: root, options: [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes])
                .write(to: target)
        }
        return copy
    }

    /// The ONNX Runtime the framework carries, from its OrtApiBase table (two C function
    /// pointers: GetApi, GetVersionString; ABI-stable), as the Android driver reads it.
    private static func loadedOrtVersion() -> String {
        typealias GetApiBase = @convention(c) () -> UnsafeRawPointer?
        typealias GetVersionString = @convention(c) () -> UnsafePointer<CChar>?
        guard let symbol = dlsym(UnsafeMutableRawPointer(bitPattern: -2), "OrtGetApiBase") else { return "-" }  // RTLD_DEFAULT
        guard let base = unsafeBitCast(symbol, to: GetApiBase.self)(),
              let versionFn = base.load(fromByteOffset: MemoryLayout<UnsafeRawPointer>.stride,
                                        as: UnsafeRawPointer?.self) else { return "-" }
        return unsafeBitCast(versionFn, to: GetVersionString.self)().map { String(cString: $0) } ?? "-"
    }

    private static func disableTelemetryEnvironment() {
        setenv("ORT_DISABLE_TELEMETRY", "1", 1)
    }

    private static func check(_ result: OpaquePointer?, _ call: String) throws {
        guard let result else { return }
        let message = OgaResultGetError(result).map { String(cString: $0) } ?? "unknown error"
        OgaDestroyResult(result)
        throw OgaError(call: call, message: message)
    }

    private static func now() -> Double {
        Double(DispatchTime.now().uptimeNanoseconds) / 1e9
    }

    private static func note(_ line: String) {
        print(line)
        fflush(stdout)
    }
}

/// A failed ONNX Runtime GenAI call, with the engine's own message.
struct OgaError: LocalizedError {
    let call: String
    let message: String
    var errorDescription: String? { "\(call): \(message)" }
}
#else
import Foundation

/// Compile-time-disabled ONNX Runtime GenAI runtime. Run
/// `scripts/fetch_ortgenai_xcframework.sh` (bootstrap.sh does) to vendor the release
/// XCFramework and its module map, then regenerate the project (xcodegen).
public final class ONNXRuntimeGenAIRuntime: LLMRuntime, @unchecked Sendable {
    public let kind: RuntimeKind = .onnxRuntimeGenAI
    public let isAvailable: Bool = false
    public nonisolated let supportedModels: [ModelInfo] = ModelCatalog.onnxRuntimeGenAI
    public var loadedModelId: String? { nil }

    public init() {}

    public func loadModel(_ model: ModelInfo, progress: @Sendable @escaping (Double) -> Void) async throws {
        throw LLMRuntimeError.unsupported("onnxruntime-genai.xcframework not vendored — run scripts/fetch_ortgenai_xcframework.sh.")
    }

    public func unloadModel() async {}

    public func generate(prompt: String, parameters: GenerationParameters) -> AsyncThrowingStream<GenerationEvent, Error> {
        AsyncThrowingStream { c in
            c.finish(throwing: LLMRuntimeError.unsupported("onnxruntime-genai.xcframework not vendored — run scripts/fetch_ortgenai_xcframework.sh."))
        }
    }
}
#endif
