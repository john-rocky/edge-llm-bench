#if canImport(llama)
import Foundation
import llama
import HuggingFace
#if canImport(Jinja)
import Jinja  // swift-transformers' template engine (its Tokenizers target depends on it)
#endif

/// llama.cpp adapter.
///
/// Uses the vendored `llama.xcframework` from
/// https://github.com/ggml-org/llama.cpp/releases (downloaded by
/// `scripts/bootstrap.sh`). The Swift wrapper pattern follows
/// `examples/llama.swiftui/llama.cpp.swift/LibLlama.swift` upstream,
/// adapted to the runtime-agnostic `LLMRuntime` surface.
public actor LlamaCppRuntime: LLMRuntime {
    public let kind: RuntimeKind = .llamaCpp
    public let isAvailable: Bool = true
    public nonisolated let supportedModels: [ModelInfo] = ModelCatalog.llamaCpp

    public private(set) var loadedModelId: String?

    private var model: OpaquePointer?
    private var context: OpaquePointer?
    private var vocab: OpaquePointer?
    private var batch: llama_batch?

    /// The GGUF's own chat template, compiled at load so the timed window holds only the
    /// render: renders one user turn with the assistant turn opened. `nil` when the jinja
    /// path is unavailable for the loaded model (`jinjaUnavailable` says why).
    private var renderChatTemplate: ((String) throws -> String)?
    private var jinjaUnavailable: String?
    /// `enable_thinking` handed to that template (`ModelInfo.chatTemplateThinking`).
    private var templateThinking: Bool?
    /// How the last `generate` built its prompt, carried into its record.
    private var lastConditions: RunConditions?

    /// KV context size handed to `llama_init_from_model`. llama.cpp allocates its KV to
    /// `n_ctx` up front, so this is most of what a memory cell measures — it used to be
    /// hardcoded at 4096 while LiteRT-LM sized its KV from the task, which meant the
    /// cross-runtime memory column compared arms at different context budgets without
    /// saying so. `prepareContext` now sets it, so `--context-tokens` means the same thing
    /// for both. Default unchanged at 4096 for runs that don't pass it.
    private var contextBudget: Int32 = 4096

    private static let backendInit: Void = {
        llama_backend_init()
    }()

    /// `--llama-backend cpu|gpu` (the app's flag; default gpu = every layer on Metal, the arm every
    /// Apple llama.cpp row so far measured). cpu keeps every layer on the CPU (`n_gpu_layers = 0`), and
    /// the record's runtime id becomes `llama.cpp-cpu`, as `litert-lm-cpu` does for LiteRT-LM.
    public nonisolated(unsafe) static var launchBackend: ComputeBackend = .gpu
    public enum ComputeBackend: String, Sendable { case cpu, gpu }
    private let backend: ComputeBackend

    public var recordRuntimeLabel: String {
        backend == .cpu ? "\(kind.rawValue)-cpu" : kind.rawValue
    }

    public init() {
        _ = Self.backendInit
        backend = Self.launchBackend
    }

    public func prepareContext(maxContextTokens: Int) {
        contextBudget = Int32(max(256, maxContextTokens))
    }

    public var recordConditions: RunConditions? { lastConditions }

    public func loadModel(
        _ model: ModelInfo,
        progress: @Sendable @escaping (Double) -> Void
    ) async throws {
        guard supportedModels.contains(where: { $0.id == model.id }) else {
            throw LLMRuntimeError.modelNotInCatalog(model.id)
        }

        let snapshot = try await HFDownloader.snapshot(for: model, runtime: kind, progress: progress)
        let ggufPath = snapshot.appendingPathComponent(model.primaryFile).path
        guard FileManager.default.fileExists(atPath: ggufPath) else {
            throw LLMRuntimeError.loadFailed("GGUF file not found at \(ggufPath)")
        }

        await unloadModel()

        var modelParams = llama_model_default_params()
        #if targetEnvironment(simulator)
        modelParams.n_gpu_layers = 0
        #endif
        if backend == .cpu {
            modelParams.n_gpu_layers = 0
        }
        guard let m = llama_model_load_from_file(ggufPath, modelParams) else {
            throw LLMRuntimeError.loadFailed("llama_model_load_from_file returned NULL")
        }
        self.model = m
        self.vocab = llama_model_get_vocab(m)
        self.templateThinking = model.chatTemplateThinking
        compileChatTemplate()

        let nThreads = max(1, min(8, ProcessInfo.processInfo.processorCount - 2))
        var ctxParams = llama_context_default_params()
        ctxParams.n_ctx = UInt32(contextBudget)
        // n_batch defaults to 512. A prompt longer than that is submitted as one
        // `llama_batch` and comes back with logits that sample EOG immediately — the
        // 1K-token parity prompt generated zero tokens until this was raised.
        // Keep it within the context: llama.cpp clamps n_batch to n_ctx internally, and a
        // batch wider than the context is meaningless.
        ctxParams.n_batch = UInt32(min(2048, contextBudget))
        ctxParams.n_ubatch = 512
        ctxParams.n_threads = Int32(nThreads)
        ctxParams.n_threads_batch = Int32(nThreads)

        guard let c = llama_init_from_model(m, ctxParams) else {
            llama_model_free(m)
            self.model = nil
            throw LLMRuntimeError.loadFailed("llama_init_from_model returned NULL")
        }
        self.context = c

        self.batch = llama_batch_init(2048, 0, 1)

        self.loadedModelId = model.id
    }

    /// Build a sampler chain for one generation. `temperature == 0` means greedy, which is
    /// what every benchmark task asks for; the other adapters honour it, so this one must too.
    private func makeSampler(_ parameters: GenerationParameters) throws -> UnsafeMutablePointer<llama_sampler> {
        guard let chain = llama_sampler_chain_init(llama_sampler_chain_default_params()) else {
            throw LLMRuntimeError.generationFailed("llama_sampler_chain_init returned NULL")
        }
        if parameters.temperature <= 0 {
            llama_sampler_chain_add(chain, llama_sampler_init_greedy())
        } else {
            llama_sampler_chain_add(chain, llama_sampler_init_top_p(parameters.topP, 1))
            llama_sampler_chain_add(chain, llama_sampler_init_temp(parameters.temperature))
            llama_sampler_chain_add(chain, llama_sampler_init_dist(UInt32(parameters.seed ?? 1234)))
        }
        return chain
    }

    public func unloadModel() async {
        if var b = batch { llama_batch_free(b); _ = withUnsafeMutablePointer(to: &b) { _ in } }
        if let c = context { llama_free(c) }
        if let m = model { llama_model_free(m) }
        batch = nil
        context = nil
        model = nil
        vocab = nil
        renderChatTemplate = nil
        jinjaUnavailable = nil
        templateThinking = nil
        lastConditions = nil
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
        guard let context, let vocab, let model else {
            throw LLMRuntimeError.modelNotLoaded
        }

        // Every call re-submits the prompt at positions 0…n-1. Without clearing the KV
        // cache first, a second call in the same process collides with the first turn's
        // entries and `llama_decode` fails — which is what a multi-run task (`--runs 4`)
        // does. Matches the fresh-conversation-per-run behaviour of the other adapters.
        llama_memory_clear(llama_get_memory(context), true)

        // Build the sampler per call so the task's parameters are honoured. The chain used
        // to be fixed at temp 0.7 / top-p 0.9, which silently ignored a greedy task and made
        // llama.cpp the only sampled runtime in an otherwise greedy comparison.
        let sampler = try makeSampler(parameters)
        defer { llama_sampler_free(sampler) }

        // The prompt as the model's own chat template renders it, so llama.cpp sees the same
        // input as the other adapters (rule 1). parseSpecial so the template's <|turn> /
        // <|im_start|> tokenize as special tokens, not literal text; addBOS adds the vocab's
        // BOS once (the jinja render's own leading <bos> is dropped, the built-in set writes none).
        let built = buildPrompt(prompt)
        lastConditions = RunConditions(chatTemplate: built.path, thinking: built.thinking)
        let promptTokens = tokenize(text: built.text, addBOS: true, parseSpecial: built.path != "bare")

        var b = batch ?? llama_batch_init(Int32(max(promptTokens.count, 2048)), 0, 1)
        // Reset batch.
        b.n_tokens = 0

        // Submit prompt.
        for (i, tok) in promptTokens.enumerated() {
            llama_batch_add(&b, tok, Int32(i), [0], false)
        }
        b.logits[Int(b.n_tokens) - 1] = 1
        self.batch = b

        let prefillStart = CFAbsoluteTimeGetCurrent()
        guard llama_decode(context, b) == 0 else {
            throw LLMRuntimeError.generationFailed("llama_decode (prefill) failed")
        }
        let prefillEnd = CFAbsoluteTimeGetCurrent()

        var nCur = Int32(promptTokens.count)
        var generatedCount = 0
        var stopReason: GenerationInfo.StopReason = .length

        let decodeStart = CFAbsoluteTimeGetCurrent()
        while generatedCount < parameters.maxTokens {
            try Task.checkCancellation()

            let newToken = llama_sampler_sample(sampler, context, -1)
            if llama_vocab_is_eog(vocab, newToken) {
                stopReason = .stop
                break
            }

            let piece = tokenToPiece(token: newToken)
            if !piece.isEmpty {
                continuation.yield(.chunk(piece))
            }

            generatedCount += 1
            nCur += 1

            // Re-prepare batch for one new token.
            b.n_tokens = 0
            llama_batch_add(&b, newToken, nCur - 1, [0], true)
            self.batch = b
            guard llama_decode(context, b) == 0 else {
                stopReason = .error
                break
            }
        }
        let decodeEnd = CFAbsoluteTimeGetCurrent()

        continuation.yield(.info(GenerationInfo(
            promptTokenCount: promptTokens.count,
            generationTokenCount: generatedCount,
            promptTime: prefillEnd - prefillStart,
            generateTime: max(decodeEnd - decodeStart, 0.001),
            stopReason: stopReason
        )))
        continuation.finish()
    }

    // MARK: - Tokenization helpers (mirror upstream LibLlama.swift)

    private func tokenize(text: String, addBOS: Bool, parseSpecial: Bool = false) -> [llama_token] {
        guard let vocab else { return [] }
        let utf8Count = text.utf8.count
        let n = utf8Count + (addBOS ? 1 : 0) + 1
        let buf = UnsafeMutablePointer<llama_token>.allocate(capacity: n)
        defer { buf.deallocate() }
        let count = llama_tokenize(vocab, text, Int32(utf8Count), buf, Int32(n), addBOS, parseSpecial)
        guard count > 0 else { return [] }
        return (0 ..< Int(count)).map { buf[$0] }
    }

    /// Wrap the bare prompt in the model's own chat template (read from the GGUF metadata)
    /// so llama.cpp sees the same input as every other adapter — MLX / CoreML / Core AI /
    /// ANEMLL / LiteRT all apply their template via the tokenizer; llama.cpp must do it
    /// explicitly (fairness rule 1). In order: the GGUF's jinja template rendered (what
    /// llama.cpp's own tools apply by default and HF tokenizers render), llama.cpp's built-in
    /// template set, the bare prompt. Returns the text, the path taken (the record's
    /// `conditions.chatTemplate`) and what the template was told about thinking (`nil` when
    /// no template applied). A bare run is not a measurement — the Gemma 4 GGUFs' template is
    /// outside the built-in set, and their rows ran bare until 2026-10-19 — so it is marked.
    private func buildPrompt(_ userPrompt: String) -> (text: String, path: String, thinking: RunConditions.Thinking?) {
        let thinking: RunConditions.Thinking = templateThinking.map { .passed($0) } ?? .templateDefault
        if let render = renderChatTemplate {
            do {
                let start = CFAbsoluteTimeGetCurrent()
                let text = try render(userPrompt)
                let ms = (CFAbsoluteTimeGetCurrent() - start) * 1000
                print(String(format: "YARDSTICK_NOTE chat_template=jinja thinking=%@ render_ms=%.2f", thinking.label, ms))
                fflush(stdout)
                return (text, "jinja", thinking)
            } catch {
                jinjaUnavailable = "render: \(error)"
            }
        }
        print("YARDSTICK_WARN chat_template_jinja_unavailable=\(jinjaUnavailable ?? "?")")
        if let templated = applyBuiltinTemplate(userPrompt) {
            print("YARDSTICK_NOTE chat_template=builtin thinking=template-default")
            fflush(stdout)
            return (templated, "builtin", .templateDefault)
        }
        print("YARDSTICK_WARN chat_template=bare thinking=none (no chat template applied: not a measurement)")
        fflush(stdout)
        return (userPrompt, "bare", nil)
    }

    /// Compile the GGUF's `tokenizer.chat_template` into `renderChatTemplate`, the way
    /// transformers and llama.cpp's own jinja engine read a chat template (trim_blocks,
    /// lstrip_blocks), with the vocab's BOS / EOS text as `bos_token` / `eos_token` and
    /// `enable_thinking` only when the catalog sets it: HF's
    /// `apply_chat_template([{"role": "user", "content": prompt}], add_generation_prompt=True)`.
    /// A leading BOS the template writes is dropped when the vocab adds one at tokenize, as
    /// llama.cpp's common_chat apply does, so the prompt carries exactly one.
    private func compileChatTemplate() {
        renderChatTemplate = nil
        jinjaUnavailable = nil
        #if canImport(Jinja)
        guard let model, let vocab, let source = llama_model_chat_template(model, nil) else {
            jinjaUnavailable = "no chat template in the GGUF"
            return
        }
        let template: Template
        do {
            template = try Template(Self.withCommentWhitespaceControl(String(cString: source)),
                                    with: .init(lstripBlocks: true, trimBlocks: true))
        } catch {
            jinjaUnavailable = "parse: \(error)"
            return
        }
        let bos = tokenText(llama_vocab_bos(vocab))
        let eos = tokenText(llama_vocab_eos(vocab))
        let dropBOS = llama_vocab_get_add_bos(vocab) && !bos.isEmpty
        let thinking = templateThinking
        renderChatTemplate = { prompt in
            var context: [String: Jinja.Value] = [  // HuggingFace has a Value too
                "messages": .array([.object(["role": .string("user"), "content": .string(prompt)])]),
                "add_generation_prompt": .boolean(true),
                "bos_token": .string(bos),
                "eos_token": .string(eos),
            ]
            if let thinking { context["enable_thinking"] = .boolean(thinking) }
            var text = try template.render(context)
            if dropBOS, text.hasPrefix(bos) { text.removeFirst(bos.count) }
            return text
        }
        #else
        jinjaUnavailable = "no Jinja module in this build"
        #endif
    }

    /// jinja2's whitespace control on comments, which swift-jinja 2.4.2 does not apply (its
    /// lexer strips around `{%-` / `{{-` / `-%}` / `-}}` only): without it the Gemma 4 GGUF
    /// template's `{%- endif %}`, blank line, `{#- … -#}` leaves a "\n" after `<bos>` that the
    /// reference renders (Python jinja2, llama.cpp) do not have — one prompt token more. The
    /// same steps as swift-jinja's own `{%-` pass, a literal `{` kept apart from the delimiter.
    private static func withCommentWhitespaceControl(_ source: String) -> String {
        var s = source.replacing(#/-#\}\s*/#, with: "#}")
        s = s.replacing(#/\{\s+\{#-/#, with: "{ {#")
        s = s.replacing(#/([^\{])\s*\{#-/#) { "\($0.1){#" }
        return s.replacing(#/^\s*\{#-/#, with: "{#")
    }

    /// The fallback: `llama_chat_apply_template`, llama.cpp's built-in template set (no
    /// jinja; Qwen's chatml is in it, the Gemma 4 GGUFs' `<|turn>` template is not). Returns
    /// nil if the model has no template or it isn't in the set.
    private func applyBuiltinTemplate(_ userPrompt: String) -> String? {
        guard let model, let tmpl = llama_model_chat_template(model, nil) else { return nil }
        return "user".withCString { rolePtr in
            userPrompt.withCString { contentPtr -> String? in
                var msg = llama_chat_message(role: rolePtr, content: contentPtr)
                var buf = [CChar](repeating: 0, count: max(userPrompt.utf8.count * 2 + 256, 512))
                var n = llama_chat_apply_template(tmpl, &msg, 1, true, &buf, Int32(buf.count))
                if n > Int32(buf.count) {                // buffer too small — grow once
                    buf = [CChar](repeating: 0, count: Int(n))
                    n = llama_chat_apply_template(tmpl, &msg, 1, true, &buf, Int32(buf.count))
                }
                guard n > 0 else { return nil }
                let take = max(0, min(Int(n), buf.count))
                return String(cString: Array(buf[0..<take]) + [0])
            }
        }
    }

    /// A special token's text (`<bos>`) for the template's bos_token / eos_token, as llama.cpp's
    /// common_chat passes them; "" when the vocab reports none.
    private func tokenText(_ token: llama_token) -> String {
        token == LLAMA_TOKEN_NULL ? "" : tokenToPiece(token: token, special: true)
    }

    private func tokenToPiece(token: llama_token, special: Bool = false) -> String {
        guard let vocab else { return "" }
        var buffer = [CChar](repeating: 0, count: 64)
        let nWritten = buffer.withUnsafeMutableBufferPointer { ptr in
            llama_token_to_piece(vocab, token, ptr.baseAddress, Int32(ptr.count), 0, special)
        }
        guard nWritten > 0 else { return "" }
        var bytes = Array(buffer.prefix(Int(nWritten)))
        bytes.append(0) // null-terminate
        return bytes.withUnsafeBufferPointer { p -> String in
            String(cString: p.baseAddress!)
        }
    }
}

// MARK: - Tiny llama_batch convenience (mirrors upstream LibLlama.swift)

private func llama_batch_add(
    _ batch: inout llama_batch,
    _ id: llama_token,
    _ pos: llama_pos,
    _ seqIds: [llama_seq_id],
    _ logits: Bool
) {
    let n = Int(batch.n_tokens)
    batch.token[n] = id
    batch.pos[n] = pos
    batch.n_seq_id[n] = Int32(seqIds.count)
    for (i, sid) in seqIds.enumerated() {
        batch.seq_id[n]?[i] = sid
    }
    batch.logits[n] = logits ? 1 : 0
    batch.n_tokens = Int32(n + 1)
}
#else
import Foundation

/// Compile-time-disabled llama.cpp runtime. Add `llama.xcframework` to the
/// project (run `scripts/bootstrap.sh`) to enable the real implementation.
public final class LlamaCppRuntime: LLMRuntime, @unchecked Sendable {
    public let kind: RuntimeKind = .llamaCpp
    public let isAvailable: Bool = false
    public nonisolated let supportedModels: [ModelInfo] = ModelCatalog.llamaCpp
    public var loadedModelId: String? { nil }

    /// As in the real runtime, so the app's `--llama-backend` flag parses without llama.xcframework.
    public nonisolated(unsafe) static var launchBackend: ComputeBackend = .gpu
    public enum ComputeBackend: String, Sendable { case cpu, gpu }

    public init() {}

    public func loadModel(_ model: ModelInfo, progress: @Sendable @escaping (Double) -> Void) async throws {
        throw LLMRuntimeError.unsupported("llama.xcframework not added — run scripts/bootstrap.sh.")
    }

    public func unloadModel() async {}

    public func generate(prompt: String, parameters: GenerationParameters) -> AsyncThrowingStream<GenerationEvent, Error> {
        AsyncThrowingStream { c in
            c.finish(throwing: LLMRuntimeError.unsupported("llama.xcframework not added — run scripts/bootstrap.sh."))
        }
    }
}
#endif
