import Foundation
#if canImport(CoreAILanguageModels)
import CoreAILanguageModels
import Metal
#endif
#if canImport(CoreAI)
import CoreAI
#endif
#if canImport(Tokenizers)
import Tokenizers
#endif

/// Apple **Core AI** adapter — the Core ML successor announced at WWDC 2026
/// (iOS / macOS 27). Loads a `.aimodel` LLM bundle produced by the official
/// `coreai.llm.export` pipeline and runs it through the official
/// `coreai-models` Swift runtime (`CoreAILM`), faithful to Apple's intended
/// on-device usage.
///
/// We deliberately use the low-level `EngineFactory` / `InferenceEngine` path —
/// the same one Apple's own `llm-benchmark` CLI tool uses
/// (`swift/Sources/Tools/benchmark/BenchmarkMain.swift`) — rather than the
/// high-level `LanguageModelSession`: it yields a raw token stream, so we get
/// true per-token timing (TTFT, inter-token latency) instead of a single
/// aggregate.
///
/// **Two compute paths, two bundles.** On iPhone the compute unit is decided by
/// the *export shape*, not just a runtime flag: the static iOS export
/// (`--platform iOS`) is detected as a chunked-static model → the `static-shape`
/// **ANE** engine; the dynamic export → the `coreai-pipelined` **GPU** engine.
/// So `…-ane` and `…-gpu` are two separate AOT-compiled bundles, distinguished
/// in the result rows with no schema change.
///
/// **iOS needs AOT compilation.** An exported `.aimodel` ships MLIR IR which
/// iOS cannot JIT; it must be compiled with `xcrun coreai-build compile
/// --platform iOS` to a `.aimodelc`, then `metadata.json assets.main` points at
/// the device-arch compiled file. See `methodology/coreai-ios.md` /
/// `scripts/bench_coreai_iphone.sh`.
///
/// The compiled bundles are **side-loaded** under `Documents/CoreAIModels/<name>/`
/// (large; not published to HF).
///
/// **Stock path (`g4stock_*` folders).** Apple's own Gemma 4 export
/// (`models/gemma4/export.py` on apple/coreai-models main, unmodified) runs through
/// `loadStock` / `runGenerateStock`: the call sequence of Apple's `llm-runner`
/// (`LanguageModelBundle` → `EngineFactory.createEngine(bundle:)` → tokenizer → stop
/// tokens → default warmup → `engine.generate`), greedy like Apple's `llm-benchmark`.
/// It sets no COREAI_* variable, binds no side table and skips no warmup; the export
/// itself decides the engine (chunked-static → static-shape on the Neural Engine).
///
/// Requires iOS 27 / macOS 27 — the `coreai-models` Swift package floor. When
/// that package is not linked into the build (`canImport` false), this file
/// compiles to an unavailable stub so the rest of the app is unaffected.
public final class CoreAIRuntime: LLMRuntime, @unchecked Sendable {
    public let kind: RuntimeKind = .coreAI
    #if canImport(CoreAILanguageModels)
    public let isAvailable: Bool = true
    #else
    public let isAvailable: Bool = false
    #endif
    public let supportedModels: [ModelInfo] = ModelCatalog.coreAI

    nonisolated(unsafe) private var _loadedModelId: String?
    public var loadedModelId: String? { _loadedModelId }

    #if canImport(CoreAILanguageModels)
    nonisolated(unsafe) private var engine: (any InferenceEngine)?
    nonisolated(unsafe) private var tokenizer: (any Tokenizer)?
    nonisolated(unsafe) private var eosTokenIds: Set<Int32> = []
    // Stock path only. The stop set is kept split by origin so each run can say whether
    // its stop token was in Apple's runner set or only in the bundle metadata's list.
    nonisolated(unsafe) private var stockLoaded = false
    nonisolated(unsafe) private var appleStopIds: Set<Int32> = []
    nonisolated(unsafe) private var metadataStopIds: Set<Int32> = []
    nonisolated(unsafe) private var bundleMaxContext: Int?
    nonisolated(unsafe) private var generateCalls = 0
    // Stock path, for `nativeBenchmarkStock`: the vocabulary its synthetic prompt draws from and
    // what the load measured (the YARDSTICK_COREAI_PREPARE line's values).
    nonisolated(unsafe) private var bundleVocabSize: Int?
    nonisolated(unsafe) private var stockPrepare: CoreAINativeBenchmark.Prepare?
    #endif

    public init() {}

    /// Stock path: the bundle's `language.max_context_length`, i.e. the top rung of the
    /// static-shape ladder. Nothing outside the bundle sizes this engine's KV, so the record
    /// carries this value rather than the requested `--context-tokens`.
    public var recordedContextTokens: Int? {
        get async {
            #if canImport(CoreAILanguageModels)
            return stockLoaded ? bundleMaxContext : nil
            #else
            return nil
            #endif
        }
    }

    // MARK: - Model id → bundle + compute variant

    /// Map a catalog id to its AOT-compiled bundle folder + the engine variant.
    /// The ANE bundle is the static iOS export compiled `--preferred-compute
    /// neural-engine` (structure → `static-shape`); the GPU bundle is the
    /// dynamic export compiled `--preferred-compute gpu` (structure →
    /// `coreai-pipelined`). The forced variant matches the bundle's structure;
    /// passing `nil` would auto-resolve to the same engine.
    private static func bundleSpec(for id: String) -> (folder: String, variant: String?)? {
        switch id {
        case "core-ai/qwen3-0.6b-ane": return ("qwen3_0_6b_ane", "static-shape")
        // June-lineage bundles (0.4.0-era compiles) kept as separate cells so cold numbers
        // can be compared 1:1 against the June sessions (artifact-lineage control).
        case "core-ai/qwen3-0.6b-ane-june": return ("qwen3_0_6b_ane_june", "static-shape")
        case "core-ai/qwen3-1.7b-gpu-june": return ("qwen3_1_7b_gpu_june", "coreai-pipelined")
        case "core-ai/qwen3-0.6b-gpu": return ("qwen3_0_6b_gpu", "coreai-pipelined")
        // 27-era re-export of the 0.6B 4-bit dynamic recipe (the entry above decodes
        // garbage on the 0.2.0 engine — ModelCatalog note, 2026-09-08).
        case "core-ai/qwen3-0.6b-4bit-gpu": return ("qwen3_0_6b_4bit_gpu", "coreai-pipelined")
        case "core-ai/qwen3-1.7b-ane": return ("qwen3_1_7b_ane", "static-shape")
        case "core-ai/qwen3-1.7b-gpu": return ("qwen3_1_7b_gpu", "coreai-pipelined")
        case "core-ai/qwen3-4b-ane":   return ("qwen3_4b_ane", "static-shape")
        case "core-ai/qwen3-4b-gpu":   return ("qwen3_4b_gpu", "coreai-pipelined")
        case "core-ai/qwen3-8b-ane":   return ("qwen3_8b_ane", "static-shape")
        case "core-ai/qwen3-8b-gpu":   return ("qwen3_8b_gpu", "coreai-pipelined")
        case "core-ai/deepseek-r1-1.5b-ane": return ("deepseek_r1_1_5b_ane", "static-shape")
        case "core-ai/deepseek-r1-1.5b-gpu": return ("deepseek_r1_1_5b_gpu", "coreai-pipelined")
        case "core-ai/lfm2.5-1.2b-gpu":  return ("lfm25_1_2b_gpu", "coreai-pipelined")
        case "core-ai/minicpm5-1b-gpu":  return ("minicpm5_1b_gpu", "coreai-pipelined")
        case "core-ai/tinyswallow-1.5b-ane": return ("tinyswallow_1_5b_ane", "static-shape")
        case "core-ai/tinyswallow-1.5b-gpu": return ("tinyswallow_1_5b_gpu", "coreai-pipelined")
        case "core-ai/vibethinker-1.5b-ane": return ("vibethinker_1_5b_ane", "static-shape")
        case "core-ai/vibethinker-1.5b-gpu": return ("vibethinker_1_5b_gpu", "coreai-pipelined")
        // 2026-06-25 export pass — GPU for all 6, ANE for llama/olmo2/smollm3 (ministral/gemma3/phi ANE pending)
        case "core-ai/ministral-3b-gpu":  return ("ministral3_3b_gpu", "coreai-pipelined")
        case "core-ai/gemma3-1b-gpu":     return ("gemma3_1b_gpu", "coreai-pipelined")
        // Gemma 4 E4B (Per-Layer-Embeddings). The `_tbl` decode graph gathers the PLE in-graph
        // from a mmap'd static table — the bundle folder also carries `ple/embed_per_layer.i8`
        // + `.scale.f32`, wired as EngineOptions.staticInputBuffers (see loadModel / GemmaPLEBench).
        case "core-ai/gemma4-e4b-gpu":    return ("gemma4_e4b_gpu", "coreai-pipelined")
        // The 2026-07-14 "EngineFactory wall" was a MISDIAGNOSIS — root-caused 2026-07-18 on
        // this app: the engine loads and generates fine through EngineFactory; what fataled
        // was our own warmup(queryLength: 8) after createEngine (S=1-only graph → binary-layer
        // NDArrayDescriptor fatal that `try?` can't catch). Fixed by skipping warmup for
        // gemma4_* (see loadModel). Two further requirements, both data-side: the bundle's
        // tokenizer_config.json must carry a chat_template (gemma-4 ships it as a separate
        // chat_template.jinja that swift-transformers doesn't read → raw-encode → degenerate
        // "<turn|>" output), and COREAI_CHUNK_THRESHOLD=1 must be set early (BenchmarkApp.init).
        case "core-ai/gemma4-e2b-gpu":    return ("gemma4_e2b_gpu", "coreai-pipelined")
        case "core-ai/phi-4-mini-gpu":    return ("phi4_mini_gpu", "coreai-pipelined")
        case "core-ai/llama-3.2-3b-ane":  return ("llama32_3b_ane", "static-shape")
        case "core-ai/llama-3.2-3b-gpu":  return ("llama32_3b_gpu", "coreai-pipelined")
        case "core-ai/olmo2-1b-ane":      return ("olmo2_1b_ane", "static-shape")
        case "core-ai/olmo2-1b-gpu":      return ("olmo2_1b_gpu", "coreai-pipelined")
        case "core-ai/smollm3-3b-ane":    return ("smollm3_3b_ane", "static-shape")
        case "core-ai/smollm3-3b-gpu":    return ("smollm3_3b_gpu", "coreai-pipelined")
        // 2026-06-26 static-GPU experiment — static-shape structure (extend_* fns, palettized LUT, identical to the
        // *_ane bundle) AOT-compiled `--preferred-compute gpu` → 0 ANE regions. Same "static-shape" engine as the ANE
        // bundle (structure match); the bundle's 0-ANE placement runs it on GPU. Forms the 3-way with *_ane (static/ANE)
        // and *_gpu (dynamic/GPU): static-ANE vs static-GPU = pure engine; static-GPU vs dynamic-GPU = shape/cold.
        // static_gpu = GPU MPSGraph (0 ANE regions) export. ⚠ 2026-06-26: these bundles compile but DO NOT LOAD in any
        // engine variant (static-shape / coreai-pipelined / nil=auto all fail EngineFactory POSIX Code=2 "No such file"):
        // the GPU compile emits an `mpsExecutable.mpsgraphpackage` (original_model/specialized_model/resources.bin) that
        // lacks the per-bucket `binary_0.llir.bundle/.../extend_*` artifacts the static engine needs. Needs an export-side
        // re-compile (full GPU bucket specialization / gemma4-bucketed port) — deferred to a separate session. Entries
        // kept wired so that session only needs to drop in loadable bundles. (nil = let the factory auto-resolve.)
        case "core-ai/deepseek-r1-1.5b-static-gpu": return ("deepseek_r1_1_5b_static_gpu", nil)
        case "core-ai/tinyswallow-1.5b-static-gpu": return ("tinyswallow_1_5b_static_gpu", nil)
        case "core-ai/vibethinker-1.5b-static-gpu": return ("vibethinker_1_5b_static_gpu", nil)
        case "core-ai/qwen3-0.6b-static-gpu":       return ("qwen3_0_6b_static_gpu", nil)
        case "core-ai/qwen3-1.7b-static-gpu":       return ("qwen3_1_7b_static_gpu", nil)
        case "core-ai/qwen3-4b-static-gpu":         return ("qwen3_4b_static_gpu", nil)
        case "core-ai/qwen3-8b-static-gpu":         return ("qwen3_8b_static_gpu", nil)
        case "core-ai/olmo2-1b-static-gpu":         return ("olmo2_1b_static_gpu", nil)
        case "core-ai/smollm3-3b-static-gpu":       return ("smollm3_3b_static_gpu", nil)
        case "core-ai/llama-3.2-3b-static-gpu":     return ("llama32_3b_static_gpu", nil)
        // Apple's own Gemma 4 export (apple/coreai-models main, models/gemma4/export.py,
        // unmodified), run on the stock path. nil = the structure picks the engine, as in
        // llm-runner (its "default" variant resolves the same way, EngineFactory.swift 209–215).
        case "core-ai/gemma4-e2b-stock-ctx2048":      return ("g4stock_e2b_ctx2048", nil)
        case "core-ai/gemma4-e2b-stock-ctxdefault":   return ("g4stock_e2b_ctxdefault", nil)
        case "core-ai/gemma4-e4b-stock-ctx2048":      return ("g4stock_e4b_ctx2048", nil)
        case "core-ai/gemma4-e4b-stock-ctxdefault":   return ("g4stock_e4b_ctxdefault", nil)
        case "core-ai/gemma4-e2b-stock-ctx2048-fp16": return ("g4stock_e2b_ctx2048_fp16", nil)
        default:                       return nil
        }
    }

    /// Folder prefix of the stock-path bundles. Never `gemma4_`: that prefix selects the
    /// legacy single-step / PLE-table handling in `loadModel`.
    private static let stockFolderPrefix = "g4stock_"

    /// Legacy Gemma-4 PLE ids (bundle folder `gemma4_*`): their S=1 decode graphs need
    /// COREAI_CHUNK_THRESHOLD=1 before the engine's first framework touch, which
    /// BenchmarkApp.init (phone) and Yardstick.runCommand (Mac) set from this. Keyed on the
    /// folder, not the id text: the stock ids contain "gemma4" too and must not get it.
    static func needsEarlySingleStepPrefill(modelId: String) -> Bool {
        bundleSpec(for: modelId)?.folder.hasPrefix("gemma4_") == true
    }

    /// Resolve a side-loaded `.aimodel` bundle folder on device. We look in
    /// `Documents/CoreAIModels/<folder>/` first (push it there with
    /// `xcrun devicectl device copy to …` or Finder file sharing), then fall
    /// back to an embedded app-bundle resource.
    private static func resolveBundleURL(folder: String) -> URL? {
        let fm = FileManager.default
        // Mac CLI: the matrix runner points BENCH_COREAI_MODELS_DIR at the directory
        // holding the side-loaded bundles (the runner's default is
        // ~/.cache/edge-llm-bench/CoreAIModels, a local non-iCloud folder — the same
        // <dir>/<folder>/metadata.json layout the app uses in its Documents container;
        // ~/Documents is iCloud-synced and evicted files fail to open, EDEADLK, 2026-09-21).
        // Unset on the phone, so the app's lookup below is unchanged.
        if let dir = ProcessInfo.processInfo.environment["BENCH_COREAI_MODELS_DIR"], !dir.isEmpty {
            let u = URL(fileURLWithPath: dir, isDirectory: true)
                .appendingPathComponent(folder, isDirectory: true)
            if fm.fileExists(atPath: u.appendingPathComponent("metadata.json").path) { return u }
        }
        if let docs = fm.urls(for: .documentDirectory, in: .userDomainMask).first {
            let u = docs.appendingPathComponent("CoreAIModels/\(folder)", isDirectory: true)
            if fm.fileExists(atPath: u.appendingPathComponent("metadata.json").path) { return u }
        }
        if let res = Bundle.main.url(forResource: folder, withExtension: nil),
           fm.fileExists(atPath: res.appendingPathComponent("metadata.json").path) {
            return res
        }
        return nil
    }

    #if canImport(CoreAILanguageModels)
    /// True when the bundle side-loads PLE tables — i.e. it can only run on a patched engine.
    /// Cheap file check, so it compiles against the stock runtime too.
    private static func hasPLETables(bundleURL: URL) -> Bool {
        FileManager.default.fileExists(
            atPath: bundleURL.appendingPathComponent("ple/embed_per_layer.i8").path)
    }

    #if COREAI_STATIC_INPUTS
    /// Gemma-4 E-series (E2B/E4B) carry Per-Layer-Embeddings whose table is too large to live
    /// in the graph. The `_tbl` decode graph gathers it in-graph from two static inputs
    /// (`ple_table` = int8 rows, `ple_scale` = per-row f32), mmap'd no-copy and bound on every
    /// encode. We side-load them next to the bundle under `ple/`. Returns [:] for non-PLE models.
    /// Adapted from `~/code/coreai/ondevice/GemmaPLEBench` (the reference that benched E4B on device).
    ///
    /// Requires the patched engine: `StaticInputBuffer` / `EngineOptions.staticInputBuffers` are
    /// not part of Apple's released coreai-models.
    private static func staticPLEBuffers(bundleURL: URL) -> [String: StaticInputBuffer] {
        let pleDir = bundleURL.appendingPathComponent("ple", isDirectory: true)
        let files = ["ple_table": "embed_per_layer.i8", "ple_scale": "embed_per_layer.scale.f32"]
        let fm = FileManager.default
        guard fm.fileExists(atPath: pleDir.appendingPathComponent(files["ple_table"]!).path),
              let device = MTLCreateSystemDefaultDevice() else { return [:] }
        var out: [String: StaticInputBuffer] = [:]
        for (name, file) in files {
            guard let buf = Self.mapTableBuffer(url: pleDir.appendingPathComponent(file), device: device)
            else { return [:] }
            out[name] = StaticInputBuffer(buf)
        }
        return out
    }

    /// mmap a table file read-only and wrap it as a no-copy, page-aligned MTLBuffer. The engine
    /// binds it unchanged on every encode and never writes it; COW pages stay clean/evictable so
    /// the multi-GB table doesn't count as dirty-resident (this is what lets E4B fit on device).
    private static func mapTableBuffer(url: URL, device: any MTLDevice) -> (any MTLBuffer)? {
        let fd = open(url.path, O_RDONLY)
        guard fd >= 0 else { return nil }
        defer { close(fd) }
        let size = Int(lseek(fd, 0, SEEK_END))
        guard size > 0 else { return nil }
        let page = Int(getpagesize())
        let mapLen = (size + page - 1) / page * page
        guard let p = mmap(nil, mapLen, PROT_READ | PROT_WRITE, MAP_PRIVATE, fd, 0),
              p != MAP_FAILED else { return nil }
        return device.makeBuffer(bytesNoCopy: UnsafeMutableRawPointer(mutating: p),
                                 length: mapLen, options: .storageModeShared, deallocator: nil)
    }
    #endif  // COREAI_STATIC_INPUTS
    #endif  // canImport(CoreAILanguageModels)

    // MARK: - Load

    public func loadModel(
        _ model: ModelInfo,
        progress: @Sendable @escaping (Double) -> Void
    ) async throws {
        guard supportedModels.contains(where: { $0.id == model.id }) else {
            throw LLMRuntimeError.modelNotInCatalog(model.id)
        }
        #if canImport(CoreAILanguageModels)
        guard let spec = Self.bundleSpec(for: model.id) else {
            throw LLMRuntimeError.loadFailed("Unknown Core AI model id \(model.id).")
        }
        guard let bundleURL = Self.resolveBundleURL(folder: spec.folder) else {
            throw LLMRuntimeError.loadFailed(
                "Core AI bundle '\(spec.folder)' not found. Side-load the exported "
                + "folder into Documents/CoreAIModels/\(spec.folder)/ "
                + "(it must contain metadata.json, the .aimodel, and tokenizer/)."
            )
        }
        if spec.folder.hasPrefix(Self.stockFolderPrefix) {
            try await loadStock(model, bundleURL: bundleURL, progress: progress)
            return
        }

        var step = "start"
        do {
            progress(0.15)
            // Mirror Apple's llm-benchmark tool: build a ModelConfig from the
            // LanguageBundle and hand it to EngineFactory.
            step = "LanguageModelBundle(\(bundleURL.lastPathComponent))"
            let bundle = try LanguageModelBundle(at: bundleURL)
            step = "requireModelURL"
            let modelURL = try bundle.modelBundle.requireModelURL(for: ModelBundle.ComponentKey.main)
            step = "ModelConfig"
            let engineConfig = ModelConfig(
                name: bundle.name,
                tokenizer: bundle.tokenizer,
                vocabSize: bundle.vocabSize,
                maxContextLength: bundle.maxContextLength,
                serializedModel: [bundle.modelAssetPath],
                function: bundle.language.functionMap?.name(for: "main") ?? "main"
            )
            let configData = try JSONEncoder().encode(engineConfig)
            progress(0.35)

            // Per-Layer-Embedding models (Gemma-4 E-series) bind the PLE table as static inputs;
            // the in-graph gather needs S=1 prefill steps (COREAI_CHUNK_THRESHOLD=1), set before
            // engine creation. Empty for non-PLE models (no behaviour change).
            //
            // COREAI_STATIC_INPUTS gates this: EngineOptions.staticInputBuffers is NOT in Apple's
            // released coreai-models (absent from 0.1.0 and 0.2.0) — it is a local engine patch.
            // A stock clone therefore builds every arm except this path, and PLE models (Gemma-4
            // E2B/E4B) are unavailable rather than the whole app failing to compile. See
            // methodology/core-ai-arm-provenance.md.
            // S=1 decode-only graphs need single-step prefill set BEFORE engine
            // creation, in the stock path too: Gemma-4 E-series, and the LFM2.5
            // ShortConv-hybrid export (its graph is `..._decode_...`; the zoo
            // runner prefill-steps it token-by-token — card: "prompt tok/s ≈
            // decode tok/s"). Chunked prefill fatals in NDArrayDescriptor
            // ("dimension 1 of 8 is not a valid substitution for source shape 1",
            // reproduced 2026-08-26 in results/raw/2026-08-26-iphone-coreai-pairs).
            let isSingleStep = spec.folder.hasPrefix("gemma4_") || spec.folder == "lfm25_1_2b_gpu"
            if isSingleStep {
                setenv("COREAI_CHUNK_THRESHOLD", "1", 1)
            }
            #if COREAI_STATIC_INPUTS
            let pleBuffers = Self.staticPLEBuffers(bundleURL: bundleURL)
            if !pleBuffers.isEmpty {
                setenv("COREAI_CHUNK_THRESHOLD", "1", 1)
            }
            step = "EngineFactory(variant=\(spec.variant ?? "auto"), model=\(modelURL.lastPathComponent), ple=\(pleBuffers.count))"
            let options = EngineOptions(
                variant: spec.variant, kvCacheStrategy: .auto, staticInputBuffers: pleBuffers)
            #else
            if Self.hasPLETables(bundleURL: bundleURL) {
                throw LLMRuntimeError.unsupported(
                    "\(model.id) is a per-layer-embedding model and needs EngineOptions.staticInputBuffers, "
                    + "which Apple's released coreai-models does not expose. Build with "
                    + "COREAI_STATIC_INPUTS against a patched engine to measure this arm.")
            }
            step = "EngineFactory(variant=\(spec.variant ?? "auto"), model=\(modelURL.lastPathComponent), ple=stock)"
            let options = EngineOptions(variant: spec.variant, kvCacheStrategy: .auto)
            #endif
            let engine = try await EngineFactory.createEngine(
                config: configData,
                modelURL: modelURL,
                options: options
            )
            progress(0.7)

            step = "loadTokenizer"
            let tok = try await bundle.loadTokenizer()
            var eos: Set<Int32> = []
            if let e = tok.eosTokenId { eos.insert(Int32(e)) }

            // Trigger kernel compilation up front so it folds into load time.
            // NOT for Gemma-4 PLE bundles: their decode graphs are S=1-only, and
            // warmup(queryLength: 8) fatals inside the binary runtime
            // ("NDArrayDescriptor.swift:139 ... dimension 1 of 8 is not a valid substitution
            // for source shape 1") — a fatalError, so `try?` cannot catch it. This was the
            // whole "EngineFactory wall": the engine loads fine, the warmup kills it.
            // For S=1 graphs the first generate step is the warmup (GemmaPLEDeviceBench rule:
            // never call engine.warmup on these). Root-caused in the other checkout 2026-07-18;
            // reproduced here 2026-07-27 and ported.
            step = "warmup"
            if !isSingleStep {
                try? await engine.warmup(queryLength: 8, sampling: SamplingConfiguration(temperature: 0))
            }

            self.engine = engine
            self.tokenizer = tok
            self.eosTokenIds = eos
            self._loadedModelId = model.id
            progress(1)
        } catch let e as LLMRuntimeError {
            throw e
        } catch {
            throw LLMRuntimeError.loadFailed("[\(step)] \(error)")
        }
        #else
        throw LLMRuntimeError.unsupported("Core AI runtime not present in this build (requires the coreai-models Swift package, iOS/macOS 27).")
        #endif
    }

    public func unloadModel() async {
        #if canImport(CoreAILanguageModels)
        engine = nil
        tokenizer = nil
        eosTokenIds = []
        stockLoaded = false
        appleStopIds = []
        metadataStopIds = []
        bundleMaxContext = nil
        generateCalls = 0
        bundleVocabSize = nil
        stockPrepare = nil
        #endif
        _loadedModelId = nil
    }

    #if canImport(CoreAILanguageModels)
    // MARK: - Stock path (Apple's own Gemma 4 export)

    /// Apple's own export, loaded the way Apple's `llm-runner` loads it. Line numbers are
    /// those of apple/coreai-models d30b086 (the commit this arm links: the next one, #327,
    /// makes `createEngine(bundle:)` reject the PLE `.safetensors` asset as "not a valid Core
    /// AI model") `swift/Sources/Tools/llm-runner/LLMRunnerMain.swift` unless another file
    /// is named.
    private func loadStock(
        _ model: ModelInfo,
        bundleURL: URL,
        progress: @Sendable @escaping (Double) -> Void
    ) async throws {
        var step = "LanguageModelBundle(\(bundleURL.lastPathComponent))"
        do {
            progress(0.15)
            // 411: parse metadata.json. The asset check of 412 (verifyAssetsExisting) runs
            // inside createEngine(bundle:) (EngineFactory.swift 90); not called twice here.
            let bundle = try LanguageModelBundle(at: bundleURL)
            #if canImport(CoreAI)
            // Record only: what the framework's own model check (`AIModelAsset.isValid`, the
            // check #327 applies to every asset) says about each asset on this OS.
            for key in bundle.modelBundle.componentKeys {
                guard let url = bundle.modelBundle.modelURL(for: key) else { continue }
                print("YARDSTICK_COREAI_ASSETCHECK key=\(key) file=\(url.lastPathComponent) isValid=\(AIModelAsset.isValid(at: url) ? 1 : 0)")
            }
            fflush(stdout)
            #endif
            // 419 + 439: the main asset, and whether Core AI already holds its specialization
            // (a cache lookup; it never specializes).
            step = "isCached"
            let mainURL = try bundle.modelBundle.requireModelURL(for: ModelBundle.ComponentKey.main)
            let cached = PreparedModel.isCached(at: mainURL)

            // 457–467 with no CLI overrides: chunking from metadata.json (nil keeps the
            // engine default), tensor data from the bundle's assets (the PLE sidecar),
            // variant and KV strategy at their defaults (auto).
            let options = EngineOptions(
                prefillChunkSize: bundle.language.prefillChunkSize,
                prefillChunkThreshold: bundle.language.prefillChunkThreshold,
                tensorData: bundle.tensorData
            )

            // 476–477: the bundle-aware factory. A first-ever load specializes inside this
            // call, so it is timed and phys_footprint is sampled across it (the runner loads
            // the tokenizer concurrently, 472; here it follows, outside the timed span).
            step = "EngineFactory.createEngine(bundle:)"
            let sampler = MemorySampler()
            await sampler.start(intervalMS: 20)
            // Progress while the call runs: a first-ever load specializes for a minute or more,
            // and a phone killed the app inside it (E4B, 2026-10-06) with nothing on the console
            // after ASSETCHECK. A line at t=0 and every 5 s until the call returns keeps the
            // memory and thermal state before such a kill on record; it stays outside the timed span.
            let tickStart = CFAbsoluteTimeGetCurrent()
            await Self.prepareTick(0, sampler: sampler)
            let ticker = Task {
                while true {
                    do { try await Task.sleep(nanoseconds: 5_000_000_000) } catch { return }
                    await Self.prepareTick(CFAbsoluteTimeGetCurrent() - tickStart, sampler: sampler)
                }
            }
            let prepareStart = CFAbsoluteTimeGetCurrent()
            let engine: any InferenceEngine
            do {
                engine = try await EngineFactory.createEngine(bundle: bundle, options: options)
            } catch {
                ticker.cancel()
                await ticker.value
                await sampler.stop()
                throw error
            }
            let prepareSeconds = CFAbsoluteTimeGetCurrent() - prepareStart
            ticker.cancel()
            await ticker.value
            await sampler.stop()
            let prepareFootprintPeakMB = await sampler.peakMB
            progress(0.7)

            // 472 / 480: the bundle's tokenizer (embedded; HF fallback otherwise).
            step = "loadTokenizer"
            let tok = try await bundle.loadTokenizer()
            // Stop set A, the runner's: tokenizer eos (1110) + additionalStopTokenIds read
            // from the bundle's tokenizer dir (487–498, 1111).
            var apple: Set<Int32> = []
            if let e = tok.eosTokenId { apple.insert(Int32(e)) }
            if let dir = bundle.tokenizerPath {
                apple.formUnion(LanguageConfig.additionalStopTokenIds(from: dir, tokenizer: tok))
            }
            // Stop set B: metadata.json `language.eos_token_ids`, the generation_config eos
            // list models/gemma4/export.py 179–181 writes; no runner code reads it. The
            // harness stops on A ∪ B, like every other arm stops at its model's turn end.
            let metadata = Self.metadataEosTokenIds(bundle.rawMetadata)

            // 505 + 508–513 → 1270–1282: the runner's default warmup (queryLength 0) with the
            // sampling the runs use — greedy, llm-benchmark's SamplingConfiguration(temperature: 0)
            // (BenchmarkMain.swift 118).
            step = "warmup"
            let sampling = SamplingConfiguration(temperature: 0)
            try engine.validateSamplingStrategy(sampling)
            let warmupStart = CFAbsoluteTimeGetCurrent()
            try await engine.warmup(queryLength: 0, sampling: sampling)
            let warmupSeconds = CFAbsoluteTimeGetCurrent() - warmupStart

            print(String(
                format: "YARDSTICK_COREAI_PREPARE model=%@ cached=%d seconds=%.3f footprint_peak_mb=%.0f warmup_seconds=%.3f engine=%@ max_context=%d",
                model.id, cached ? 1 : 0, prepareSeconds, prepareFootprintPeakMB, warmupSeconds,
                String(describing: type(of: engine)), bundle.maxContextLength))
            print("YARDSTICK_COREAI_STOP apple=\(Self.idList(apple)) metadata=\(Self.idList(metadata))")
            fflush(stdout)

            self.engine = engine
            self.tokenizer = tok
            self.appleStopIds = apple
            self.metadataStopIds = metadata
            self.eosTokenIds = apple.union(metadata)
            self.bundleMaxContext = bundle.maxContextLength
            self.bundleVocabSize = bundle.vocabSize
            self.stockPrepare = CoreAINativeBenchmark.Prepare(
                cached: cached, seconds: prepareSeconds, footprintPeakMB: prepareFootprintPeakMB,
                engineWarmupSeconds: warmupSeconds)
            self.generateCalls = 0
            self.stockLoaded = true
            self._loadedModelId = model.id
            progress(1)
        } catch let e as LLMRuntimeError {
            throw e
        } catch {
            throw LLMRuntimeError.loadFailed("[\(step)] \(error)")
        }
    }

    /// One generation on the stock path: Apple's chat-template helper (531–532), then
    /// llm-benchmark's reset + greedy generate (BenchmarkMain.swift 178–184), stopping on the
    /// A ∪ B stop set or the task's token budget.
    private func runGenerateStock(
        engine: any InferenceEngine,
        tokenizer: any Tokenizer,
        prompt: String,
        parameters: GenerationParameters,
        continuation: AsyncThrowingStream<GenerationEvent, Error>.Continuation
    ) async throws {
        generateCalls += 1
        let call = generateCalls
        // Throws when the tokenizer has no chat template — never a silent raw encode.
        let promptIds = try PromptUtils.maybeApplyTokenizerChatTemplate(.prompt(prompt), tokenizer: tokenizer)
        let inputIds = promptIds.map { Int32($0) }

        try await engine.reset()
        let sampling = SamplingConfiguration(temperature: 0)
        let options = InferenceOptions(maxTokens: parameters.maxTokens, includeLogits: false)

        let prefillStart = CFAbsoluteTimeGetCurrent()
        let stream = try await engine.generate(
            with: inputIds,
            samplingConfiguration: sampling,
            inferenceOptions: options
        )
        // Arrival time of every token the engine yields (the stop token included), and the
        // time this loop spends on each one. The engine is pulled, so that time sits between
        // its steps; it is reported so a gap to llm-benchmark can be attributed.
        var arrivals: [CFAbsoluteTime] = []
        arrivals.reserveCapacity(parameters.maxTokens)
        var harnessSeconds = 0.0
        var stopToken: Int32?
        var detokenizer = IncrementalDetokenizer(tokenizer: tokenizer)
        var emitted = ""
        var chunks = 0
        for try await out in stream {
            let arrived = CFAbsoluteTimeGetCurrent()
            arrivals.append(arrived)
            try Task.checkCancellation()
            let tid = out.tokenId
            if eosTokenIds.contains(tid) {
                stopToken = tid
                stream.setStopReason(.eos)
                break
            }
            let delta = detokenizer.append(Int(tid))
            if !delta.isEmpty {
                emitted += delta
                chunks += 1
                continuation.yield(.chunk(delta))
            }
            harnessSeconds += CFAbsoluteTimeGetCurrent() - arrived
        }
        let end = CFAbsoluteTimeGetCurrent()

        let stopReason: GenerationInfo.StopReason
        switch stream.stopReason {
        case .eos?, .stopSequence?: stopReason = .stop
        case .maxTokens?: stopReason = .length
        case .cancelled?: stopReason = .cancelled
        case .error?: stopReason = .error
        case nil: stopReason = arrivals.count >= parameters.maxTokens ? .length : .stop
        }

        // Inter-token gaps as seen here: max (with the token that closed it and that token's
        // decode position — a static-shape rung change shows up as one long step), median,
        // and the harness's share. text_match compares the streamed text with one full decode.
        var gaps: [Double] = []
        if arrivals.count >= 2 {
            gaps.reserveCapacity(arrivals.count - 1)
            for i in 1..<arrivals.count { gaps.append((arrivals[i] - arrivals[i - 1]) * 1000) }
        }
        let textMatch = tokenizer.decode(tokens: detokenizer.ids) == emitted
        let stopOrigin: String
        if let s = stopToken {
            stopOrigin = appleStopIds.contains(s) ? "apple" : (metadataStopIds.contains(s) ? "metadata-only" : "?")
        } else {
            stopOrigin = "none"
        }
        if let maxIndex = gaps.indices.max(by: { gaps[$0] < gaps[$1] }) {
            let sorted = gaps.sorted()
            let rank = max(1, Int((0.5 * Double(sorted.count)).rounded(.up)))
            let p50 = sorted[min(rank - 1, sorted.count - 1)]
            let atToken = maxIndex + 2   // 1-based: gap k closes on token k + 2
            print(String(
                format: "YARDSTICK_COREAI_ITL run=%d max_ms=%.2f at_token=%d p50_ms=%.2f at_position=%d prompt_tokens=%d tokens=%d chunks=%d harness_ms=%.2f stop=%@ stop_token=%@ stop_origin=%@ text_match=%d",
                call, gaps[maxIndex], atToken, p50, inputIds.count + atToken - 2, inputIds.count,
                arrivals.count, chunks, harnessSeconds * 1000, stopReason.rawValue,
                stopToken.map { String($0) } ?? "-", stopOrigin, textMatch ? 1 : 0))
        } else {
            print("YARDSTICK_COREAI_ITL run=\(call) tokens=\(arrivals.count) prompt_tokens=\(inputIds.count) stop=\(stopReason.rawValue) stop_origin=\(stopOrigin)")
        }
        // The whole reply, once (the record keeps 200 characters): the text check reads the
        // output of this prompt length end to end, where a loop would show.
        if let json = try? JSONEncoder().encode(emitted), let quoted = String(data: json, encoding: .utf8) {
            print("YARDSTICK_COREAI_TEXT run=\(call) chars=\(emitted.count) text=\(quoted)")
        }
        fflush(stdout)

        let firstTokenAt = arrivals.first
        let promptTime = (firstTokenAt ?? end) - prefillStart
        let generateTime = max(end - (firstTokenAt ?? prefillStart), 0.001)
        continuation.yield(.info(GenerationInfo(
            promptTokenCount: inputIds.count,
            generationTokenCount: arrivals.count,
            promptTime: promptTime,
            generateTime: generateTime,
            stopReason: stopReason
        )))
        continuation.finish()
    }

    /// One YARDSTICK_COREAI_PREPARE_TICK line (loadStock, while `createEngine(bundle:)` runs):
    /// seconds since the first tick, phys_footprint and resident size now, the 20 ms sampler's
    /// peak so far, and the thermal state.
    private static func prepareTick(_ t: Double, sampler: MemorySampler) async {
        let peakMB = await sampler.peakMB
        print(String(
            format: "YARDSTICK_COREAI_PREPARE_TICK t=%.1f footprint_mb=%.0f resident_mb=%.0f peak_mb=%.0f thermal=%@",
            t, MemoryMonitor.footprintMB(), MemoryMonitor.residentMB(), peakMB,
            ThermalMonitor.describe(ProcessInfo.processInfo.thermalState)))
        fflush(stdout)
    }

    /// `language.eos_token_ids` from metadata.json; empty when absent.
    private static func metadataEosTokenIds(_ raw: Data) -> Set<Int32> {
        guard let root = try? JSONSerialization.jsonObject(with: raw) as? [String: Any],
              let language = root["language"] as? [String: Any],
              let ids = language["eos_token_ids"] as? [Any]
        else { return [] }
        return Set(ids.compactMap { ($0 as? Int).map(Int32.init) })
    }

    private static func idList(_ ids: Set<Int32>) -> String {
        "[" + ids.sorted().map(String.init).joined(separator: ",") + "]"
    }

    /// BenchmarkMain.swift `runTrial` (171–205), line for line.
    private static func benchmarkTrial(
        engine: any InferenceEngine,
        prompt: [Int32],
        sampling: SamplingConfiguration,
        generationTokens: Int
    ) async throws -> (promptTime: Double, count: Int, genTime: Double, promptTps: Double, genTps: Double) {
        // 176–178: a brief pause for the engine to finish prior async work, then a full reset.
        try? await Task.sleep(for: .milliseconds(50))
        try await engine.reset()

        // 180–184
        let options = InferenceOptions(maxTokens: generationTokens, includeLogits: false)
        let start = SuspendingClock.now
        let stream = try await engine.generate(
            with: prompt, samplingConfiguration: sampling, inferenceOptions: options
        )

        // 186–197: every token the stream yields counts; nothing looks for a stop token.
        var promptTime: Double = 0
        var genStart = SuspendingClock.now
        var count = 0
        for try await _ in stream {
            if promptTime == 0 {
                let now = SuspendingClock.now
                promptTime = seconds(now - start)
                genStart = now
            }
            count += 1
        }

        // 199–202
        let genTime = seconds(SuspendingClock.now - genStart)
        let promptTps = promptTime > 0 ? Double(prompt.count) / promptTime : 0
        let decodeCount = max(0, count - 1)
        let genTps = genTime > 0 ? Double(decodeCount) / genTime : 0
        return (promptTime, count, genTime, promptTps, genTps)
    }

    /// One `benchmarkTrial` with memory and thermal sampled across it the way BenchmarkRunner
    /// samples a task run (MemorySampler 100 ms, ThermalSampler 1 s); llm-benchmark itself
    /// samples neither. `seconds` is the whole trial (pause, reset, generate), the span
    /// llm-benchmark times its warmup over.
    private static func sampledTrial(
        index: Int,
        engine: any InferenceEngine,
        prompt: [Int32],
        sampling: SamplingConfiguration,
        generationTokens: Int
    ) async throws -> (trial: CoreAINativeBenchmark.Trial, seconds: Double) {
        let memory = MemorySampler()
        let thermal = ThermalSampler()
        await thermal.start()
        await memory.start()
        let start = SuspendingClock.now
        let r = try await benchmarkTrial(
            engine: engine, prompt: prompt, sampling: sampling, generationTokens: generationTokens)
        let trialSeconds = seconds(SuspendingClock.now - start)
        await memory.stop()
        await thermal.stop()
        let peakMB = await memory.peakMB
        let medianMB = await memory.medianMB
        let medianResidentMB = await memory.medianResidentMB
        let samples = await memory.sampleCount
        let thermalInitial = await thermal.initialState
        let thermalPeak = await thermal.peakState
        let thermalFinal = await thermal.finalState
        let trial = CoreAINativeBenchmark.Trial(
            index: index, promptTokens: prompt.count, promptSeconds: r.promptTime,
            promptTokensPerSecond: r.promptTps, tokens: r.count, decodeSeconds: r.genTime,
            decodeTokensPerSecond: r.genTps, peakMB: peakMB, medianMB: medianMB,
            medianResidentMB: medianResidentMB, samples: samples,
            thermalInitial: ThermalMonitor.describe(thermalInitial),
            thermalPeak: ThermalMonitor.describe(thermalPeak),
            thermalFinal: ThermalMonitor.describe(thermalFinal))
        return (trial, trialSeconds)
    }

    /// BenchmarkMain.swift `randomPrompt` (209–223): SplitMix64 token ids below `vocabSize`.
    private static func randomPrompt(vocabSize: Int, count: Int, seed: UInt64) -> [Int32] {
        var state = seed &+ 0x9E37_79B9_7F4A_7C15
        var out = [Int32]()
        out.reserveCapacity(count)
        let v = UInt64(vocabSize)
        for _ in 0..<count {
            state = state &+ 0x9E37_79B9_7F4A_7C15
            var z = state
            z = (z ^ (z >> 30)) &* 0xBF58_476D_1CE4_E5B9
            z = (z ^ (z >> 27)) &* 0x94D0_49BB_1331_11EB
            z = z ^ (z >> 31)
            out.append(Int32(z % v))
        }
        return out
    }

    /// `Duration.inSeconds` (CoreAIShared, package access, so not visible here), same formula.
    private static func seconds(_ d: Duration) -> Double {
        let (secs, attoseconds) = d.components
        return Double(secs) + Double(attoseconds) / 1e18
    }
    #endif  // canImport(CoreAILanguageModels)

    // MARK: - Native benchmark (stock path)

    /// `--coreai-native-benchmark <P>x<D>`: Apple's `llm-benchmark` measurement on the stock
    /// path. The load is `loadStock`, unchanged (llm-runner's sequence and its console lines);
    /// the rest copies BenchmarkMain.swift at d30b086, whose line numbers are cited: a seeded
    /// random prompt of `prefill` token ids, greedy, one whole warmup trial, then `trials` timed
    /// trials of `decode` tokens with no stop check. `onTrial` gets each trial as it ends: the
    /// warmup first, as trial 0 (cold: the first generate on this engine after the load), then
    /// the timed trials 1...`trials` (warm). Only the timed ones enter the result's mean.
    public func nativeBenchmarkStock(
        _ model: ModelInfo,
        prefill: Int,
        decode: Int,
        trials: Int,
        onTrial: @Sendable (CoreAINativeBenchmark.Setup, CoreAINativeBenchmark.Trial) -> Void
    ) async throws -> CoreAINativeBenchmark.Result {
        #if canImport(CoreAILanguageModels)
        guard prefill > 0, decode > 0, trials > 0 else {
            throw LLMRuntimeError.unsupported(
                "native benchmark needs prefill, decode and trials >= 1 (got \(prefill)x\(decode), \(trials) trials)")
        }
        guard Self.bundleSpec(for: model.id)?.folder.hasPrefix(Self.stockFolderPrefix) == true else {
            throw LLMRuntimeError.unsupported(
                "--coreai-native-benchmark measures Apple's own export on the stock path only "
                + "(bundle folder \(Self.stockFolderPrefix)*); \(model.id) is not a stock id")
        }
        if _loadedModelId != model.id {
            try await loadModel(model) { _ in }
        }
        guard stockLoaded, let engine, let vocabSize = bundleVocabSize, let prepare = stockPrepare,
              let contextTokens = bundleMaxContext
        else { throw LLMRuntimeError.modelNotLoaded }

        // 117–118: the synthetic prompt (llm-benchmark's default seed) and greedy sampling.
        let seed: UInt64 = 0
        let prompt = Self.randomPrompt(vocabSize: vocabSize, count: prefill, seed: seed)
        let sampling = SamplingConfiguration(temperature: 0)
        // A fingerprint of the prompt, so the ids can be compared with the tool's generator.
        let head = prompt.prefix(8).map(String.init).joined(separator: ",")
        let sum = prompt.reduce(Int64(0)) { $0 + Int64($1) }
        print("YARDSTICK_COREAI_NATIVE_PROMPT seed=\(seed) vocab=\(vocabSize) tokens=\(prompt.count) head=\(head) sum=\(sum)")
        fflush(stdout)

        // 120–126: the warmup is one whole trial, timed and not reported as a trial (it stays out
        // of the mean). It is also the cold trial, the first generate on this engine after the
        // load, so it is sampled like a timed trial and printed as trial 0.
        let (warmup, warmupSeconds) = try await Self.sampledTrial(
            index: 0, engine: engine, prompt: prompt, sampling: sampling, generationTokens: decode)
        print(String(
            format: "YARDSTICK_COREAI_NATIVE_WARMUP seconds=%.3f tokens=%d prefill_tok_s=%.3f decode_tok_s=%.3f",
            warmupSeconds, warmup.tokens, warmup.promptTokensPerSecond, warmup.decodeTokensPerSecond))
        fflush(stdout)

        let setup = CoreAINativeBenchmark.Setup(
            modelId: model.id, prefill: prefill, decode: decode, trials: trials, seed: seed,
            contextTokens: contextTokens, prepare: prepare, warmupTrialSeconds: warmupSeconds)
        onTrial(setup, warmup)

        // 132–139: the timed trials, each sampled across (`sampledTrial`).
        var results: [CoreAINativeBenchmark.Trial] = []
        for i in 1...trials {
            let (trial, _) = try await Self.sampledTrial(
                index: i, engine: engine, prompt: prompt, sampling: sampling, generationTokens: decode)
            results.append(trial)
            onTrial(setup, trial)
        }
        return CoreAINativeBenchmark.Result(setup: setup, warmup: warmup, trials: results)
        #else
        throw LLMRuntimeError.unsupported("Core AI runtime not present in this build (requires the coreai-models Swift package, iOS/macOS 27).")
        #endif
    }

    // MARK: - Generate

    public func generate(
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
            continuation.onTermination = { _ in task.cancel() }
        }
    }

    private func runGenerate(
        prompt: String,
        parameters: GenerationParameters,
        continuation: AsyncThrowingStream<GenerationEvent, Error>.Continuation
    ) async throws {
        #if canImport(CoreAILanguageModels)
        guard let engine, let tokenizer else { throw LLMRuntimeError.modelNotLoaded }
        if stockLoaded {
            try await runGenerateStock(
                engine: engine, tokenizer: tokenizer, prompt: prompt,
                parameters: parameters, continuation: continuation)
            return
        }

        // Tokenize with the model's chat template (greedy, deterministic — the
        // same sampling Apple's benchmark tool uses: temperature 0).
        let messages: [[String: String]] = [["role": "user", "content": prompt]]
        let promptIds: [Int] = (try? tokenizer.applyChatTemplate(messages: messages))
            ?? tokenizer.encode(text: prompt)
        let inputIds = promptIds.map { Int32($0) }

        try await engine.reset()
        let sampling = SamplingConfiguration(temperature: 0)
        let options = InferenceOptions(maxTokens: parameters.maxTokens, includeLogits: false)

        let prefillStart = CFAbsoluteTimeGetCurrent()
        var firstTokenAt: CFAbsoluteTime?
        var genCount = 0
        var accumIds: [Int] = []
        var emitted = ""

        // `await`: generate() became async in coreai-models 0.2.0. Harmless against an older
        // sync engine (Swift only warns that no async work occurs), so the patched-engine build
        // still compiles.
        let stream = try await engine.generate(
            with: inputIds,
            samplingConfiguration: sampling,
            inferenceOptions: options
        )
        for try await out in stream {
            try Task.checkCancellation()
            if firstTokenAt == nil { firstTokenAt = CFAbsoluteTimeGetCurrent() }
            let tid = out.tokenId
            genCount += 1
            if eosTokenIds.contains(tid) { break }
            accumIds.append(Int(tid))
            // Incremental decode → emit only the new text so the runner gets
            // real per-token timing for inter-token-latency percentiles.
            // Diff by COMMON PREFIX, never by slicing `current` with an index
            // taken from `emitted`: a String.Index is only valid for the string
            // it came from, so `current[emitted.endIndex...]` is undefined and
            // can crash or corrupt on byte-level tokenizers where a multi-byte
            // character straddles two tokens (a partial "�" that resolves on the
            // next token). dropFirst(sharedCount) is index-safe for any tokenizer.
            let current = tokenizer.decode(tokens: accumIds)
            if current != emitted {
                let shared = current.commonPrefix(with: emitted).count
                if current.count > shared {
                    let delta = String(current.dropFirst(shared))
                    continuation.yield(.chunk(delta))
                }
                emitted = current
            }
        }

        let end = CFAbsoluteTimeGetCurrent()
        let promptTime = (firstTokenAt ?? end) - prefillStart
        let generateTime = max(end - (firstTokenAt ?? prefillStart), 0.001)
        continuation.yield(.info(GenerationInfo(
            promptTokenCount: inputIds.count,
            generationTokenCount: genCount,
            promptTime: promptTime,
            generateTime: generateTime,
            stopReason: genCount >= parameters.maxTokens ? .length : .stop
        )))
        continuation.finish()
        #else
        throw LLMRuntimeError.unsupported("Core AI runtime not present in this build.")
        #endif
    }
}

/// `--coreai-native-benchmark`: the values `CoreAIRuntime.nativeBenchmarkStock` measures and the
/// console lines the iOS app and the Mac CLI print from them. Plain values, so this compiles
/// without the coreai-models package too.
public enum CoreAINativeBenchmark {
    /// What `loadStock` measured (the YARDSTICK_COREAI_PREPARE line's values).
    public struct Prepare: Sendable {
        public let cached: Bool
        public let seconds: Double
        public let footprintPeakMB: Double
        public let engineWarmupSeconds: Double
    }

    /// The same for every trial of one invocation.
    public struct Setup: Sendable {
        public let modelId: String
        public let prefill: Int
        public let decode: Int
        public let trials: Int
        public let seed: UInt64
        /// The bundle's `language.max_context_length`; nothing passed in sizes this engine.
        public let contextTokens: Int
        public let prepare: Prepare
        public let warmupTrialSeconds: Double
    }

    /// One trial: llm-benchmark's two rates with the times they come from, and the memory and
    /// thermal samples taken across it. Index 0 is the warmup trial, 1...N the timed ones.
    public struct Trial: Sendable {
        /// 0 = the warmup trial (the first generate on this engine after the load, `cold`),
        /// 1...N = the timed trials that follow it in the same process.
        public let index: Int
        public let promptTokens: Int
        public let promptSeconds: Double
        public let promptTokensPerSecond: Double
        public let tokens: Int
        public let decodeSeconds: Double
        public let decodeTokensPerSecond: Double
        public let peakMB: Double
        public let medianMB: Double
        public let medianResidentMB: Double
        public let samples: Int
        public let thermalInitial: String
        public let thermalPeak: String
        public let thermalFinal: String
        public var cold: Bool { index == 0 }
    }

    public struct Result: Sendable {
        public let setup: Setup
        /// The warmup trial (index 0). Not one of `trials`, so not in the summary's mean.
        public let warmup: Trial
        public let trials: [Trial]
    }

    /// One YARDSTICK_NATIVE_OK line per trial (the warmup's as trial=0 cold=1), in the LiteRT-LM
    /// row's field names (scripts/import_native_benchmark.py lifts both kinds), plus the fields
    /// only this arm has. init_s is the Prepare time (`createEngine`), ttft_ms the prompt time
    /// llm-benchmark divides by.
    public static func line(_ s: Setup, _ t: Trial, harness: String) -> String {
        String(
            format: "YARDSTICK_NATIVE_OK runtime=core-ai trial=%d cold=%d trials=%d prefill_tokens=%d prefill_tok_s=%.3f decode_tokens=%d decode_tok_s=%.3f ttft_ms=%.3f decode_s=%.6f init_s=%.3f prepare_cached=%d prepare_peak_mb=%.0f engine_warmup_s=%.3f warmup_trial_s=%.3f context_tokens=%d peak_mb=%.0f median_mb=%.0f median_resident_mb=%.0f samples=%d thermal_initial=%@ thermal_peak=%@ thermal_final=%@ seed=%llu harness=%@",
            t.index, t.cold ? 1 : 0, s.trials, t.promptTokens, t.promptTokensPerSecond, t.tokens, t.decodeTokensPerSecond,
            t.promptSeconds * 1000, t.decodeSeconds, s.prepare.seconds, s.prepare.cached ? 1 : 0,
            s.prepare.footprintPeakMB, s.prepare.engineWarmupSeconds, s.warmupTrialSeconds,
            s.contextTokens, t.peakMB, t.medianMB, t.medianResidentMB, t.samples,
            t.thermalInitial, t.thermalPeak, t.thermalFinal, s.seed, harness)
    }

    /// llm-benchmark's own summary (BenchmarkMain.swift 141–150): Prepare, Warmup and the mean
    /// of the trials. Medians are taken from the per-trial lines, not from this line.
    public static func summaryLine(_ r: Result) -> String {
        let n = Double(max(r.trials.count, 1))
        let avgPrompt = r.trials.map(\.promptTokensPerSecond).reduce(0, +) / n
        let avgGen = r.trials.map(\.decodeTokensPerSecond).reduce(0, +) / n
        return String(
            format: "YARDSTICK_COREAI_NATIVE_SUMMARY model=%@ prefill=%d decode=%d trials=%d prepare_s=%.3f prepare_cached=%d warmup_trial_s=%.3f prompt_tok_s_mean=%.3f decode_tok_s_mean=%.3f",
            r.setup.modelId, r.setup.prefill, r.setup.decode, r.trials.count, r.setup.prepare.seconds,
            r.setup.prepare.cached ? 1 : 0, r.setup.warmupTrialSeconds, avgPrompt, avgGen)
    }
}

#if canImport(CoreAILanguageModels)
/// Streams text from a growing token list without re-decoding the whole list on every token:
/// two short decodes from a moving prefix offset (the scheme of HF text-generation-inference's
/// `decode_token`), so the per-token cost stays flat over a long output. A step whose text ends
/// in U+FFFD (a character split across tokens) emits nothing; the next token completes it.
/// Compared per Unicode scalar, so a combining mark never re-emits the character it joins.
/// The caller checks the streamed text against one full decode (`text_match`).
struct IncrementalDetokenizer {
    private static let replacement: Unicode.Scalar = "\u{FFFD}"
    let tokenizer: any Tokenizer
    private(set) var ids: [Int] = []
    private var prefixOffset = 0
    private var readOffset = 0

    init(tokenizer: any Tokenizer) {
        self.tokenizer = tokenizer
    }

    mutating func append(_ id: Int) -> String {
        ids.append(id)
        let prefix = tokenizer.decode(tokens: Array(ids[prefixOffset..<readOffset])).unicodeScalars
        let window = tokenizer.decode(tokens: Array(ids[prefixOffset...])).unicodeScalars
        guard window.count > prefix.count, window.last != Self.replacement else { return "" }
        prefixOffset = readOffset
        readOffset = ids.count
        return String(String.UnicodeScalarView(window.dropFirst(prefix.count)))
    }
}
#endif
