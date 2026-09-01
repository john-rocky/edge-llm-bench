// Yardstick — Apple Silicon AI benchmark CLI (Mac).
//
// Usage:
//   yardstick run --task short-chat \
//                 --runtime mlx-swift \
//                 --model mlx-community/gemma-4-e2b-it-4bit \
//                 [--output results/raw/<auto>.jsonl]
//
// One run produces one `BenchmarkResult`. Multiple invocations append to the
// output file as JSONL. Aggregation lives outside the CLI (`results/` +
// scripts), so this binary stays tiny.

import Foundation

// The CLI is built two ways:
//
//   1. `swift build` from the repo root — `main.swift` is in the
//      `YardstickCLI` SPM target, and the bench types live in the
//      sibling `YardstickKit` library target.
//   2. `xcodebuild -scheme yardstick` — `main.swift` is compiled
//      together with `Sources/{Benchmark,Models,Runtimes}/...` into a
//      single `yardstick` Mac tool target. In that build there is no
//      separate `YardstickKit` module.
//
// The conditional import keeps both paths happy.
#if canImport(YardstickKit)
    import YardstickKit
#endif

@main
struct YardstickApp {
    static func main() async {
        do {
            try await runMain()
        } catch {
            FileHandle.standardError.write(Data("error: \(error)\n".utf8))
            exit(1)
        }
    }

    static func runMain() async throws {
        let argv = Array(CommandLine.arguments.dropFirst())
        guard let subcommand = argv.first else {
            printUsage()
            exit(2)
        }

        switch subcommand {
        case "run":
            try await runCommand(Array(argv.dropFirst()))
        case "list":
            if argv.dropFirst().contains("--json") {
                listCatalogJSON()
            } else {
                listCatalog()
            }
        case "version":
            // The only reliable probe of build flavor: the SPM build compiles out
            // four runtimes (YARDSTICK_SPM) but `list` prints all of them statically.
            // Runners hard-fail on spm-lite (scripts/bench_matrix_mac.sh).
            print("yardstick flavor=\(buildFlavor) harness=\(BenchmarkRunner.harnessStamp)")
        case "--help", "-h", "help":
            printUsage()
        default:
            FileHandle.standardError.write(Data("unknown command: \(subcommand)\n".utf8))
            printUsage()
            exit(2)
        }
    }

    // MARK: - `yardstick run`

    static func runCommand(_ argv: [String]) async throws {
        var taskID = "short-chat"
        var runtimeID = "mlx-swift"
        var modelID: String? = nil
        var outputPath: String? = nil
        var coldRun = true
        var runs = 1
        // The agreed protocol has a context length as an independent axis (2048 for Gemma-4).
        // Until 2026-07-28 this CLI had no way to express it, so every Mac cell ran at whatever
        // `prepareContext` derived from the prompt — which is deviation #2 of
        // methodology/agreed-protocol-gemma4.md, fixed on iOS months earlier and still open
        // here. A Mac number captured without this flag is not comparable with an iPhone one.
        var contextTokens: Int? = nil
        var nativeBenchmark: (prefill: Int, decode: Int)? = nil

        var i = 0
        while i < argv.count {
            let arg = argv[i]
            switch arg {
            case "--task":
                taskID = argv.value(after: &i)
            case "--runtime":
                runtimeID = argv.value(after: &i)
            case "--model", "--model-id":
                // `--model-id` is the spelling the iOS driver uses; accepting both keeps one
                // protocol expressible by one set of flags on both devices.
                modelID = argv.value(after: &i)
            case "--context-tokens":
                let raw = argv.value(after: &i)
                guard let n = Int(raw), n > 0 else {
                    FileHandle.standardError.write(Data("bad --context-tokens '\(raw)'\n".utf8))
                    exit(2)
                }
                contextTokens = n
            case "--litert-native-benchmark":
                // `<prefill>x<decode>`, e.g. 1024x256 — LiteRT-LM's own force-prefill entry
                // point, the method behind the HF model card numbers. No other runtime has it.
                let raw = argv.value(after: &i)
                let parts = raw.lowercased().split(separator: "x")
                guard parts.count == 2, let p = Int(parts[0]), let d = Int(parts[1]),
                      p > 0, d > 0 else {
                    FileHandle.standardError.write(Data(
                        "bad --litert-native-benchmark '\(raw)' — expected <prefill>x<decode>, e.g. 1024x256\n".utf8))
                    exit(2)
                }
                nativeBenchmark = (p, d)
            case "--output":
                outputPath = argv.value(after: &i)
            case "--warm":
                coldRun = false
                i += 1
            case "--runs":
                runs = max(1, Int(argv.value(after: &i)) ?? 1)
            default:
                FileHandle.standardError.write(Data("unknown flag: \(arg)\n".utf8))
                exit(2)
            }
        }

        let runtime = try makeRuntime(id: runtimeID)
        let task = try makeTask(id: taskID)
        let model = try resolveModel(idOrHF: modelID, runtime: runtime)

        // The vendor-benchmark row runs instead of the task, not alongside it: it forces a
        // prefill with no prompt, so there is no task to run. It is the only row that is
        // card-comparable, and the only one no other runtime can produce.
        if let native = nativeBenchmark {
            try await runNativeBenchmark(runtime: runtime, runtimeID: runtimeID, model: model,
                                         spec: native, contextTokens: contextTokens,
                                         outputPath: outputPath)
            return
        }

        // Endurance sessions run INSTEAD of the generic per-run loop: one
        // 30-minute-class multi-turn session per invocation, per-turn series to
        // a sidecar, one schema-v1 session record to the JSONL.
        if let enduranceTask = task as? EnduranceChatTask {
            try await runEndurance(
                runtime: runtime, runtimeID: runtimeID, model: model,
                task: enduranceTask, contextTokens: contextTokens,
                runs: runs, outputPath: outputPath)
            return
        }

        let runner = BenchmarkRunner()
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        encoder.dateEncodingStrategy = .iso8601

        // `--runs N` mirrors the iOS app's fairness-rules §2 warm protocol: one
        // process, the model stays loaded across runs — run 1 is cold (fresh
        // process, weights on disk), runs 2..N are warm; report the median of
        // runs 2..N as warm. Each run gets its own JSONL record (coldRun flags
        // the split), identical to what the iPhone campaign driver imports.
        for runIndex in 1...runs {
            let config = BenchmarkRunner.Configuration(
                runtime: runtime,
                model: model,
                task: task,
                coldRun: runs > 1 ? (runIndex == 1) : coldRun,
                contextTokens: contextTokens
            )

            FileHandle.standardError.write(Data(
                "yardstick: run \(runIndex)/\(runs) task=\(taskID) runtime=\(runtimeID) model=\(model.id)\n".utf8
            ))

            let result = try await runner.run(config)
            let json = try encoder.encode(result)

            // Always print the result to stdout.
            FileHandle.standardOutput.write(json)
            FileHandle.standardOutput.write(Data("\n".utf8))

            // Optionally append to a JSONL file.
            if let outputPath {
                try appendJSONL(result: result, path: outputPath)
                FileHandle.standardError.write(Data("yardstick: appended to \(outputPath)\n".utf8))
            }

            // Friendly one-line summary on stderr.
            let m = result.metrics
            FileHandle.standardError.write(Data(
                "yardstick: run=\(runIndex) cold=\(runIndex == 1 && (runs > 1 || coldRun) ? 1 : 0) TTFT=\(m.firstTokenLatencyMS)ms decode=\(String(format: "%.2f", m.decodeTokensPerSecond))tok/s peakMB=\(Int(m.memoryPeakDuringDecodeMB))\n".utf8
            ))
        }
    }

    /// One endurance session (`methodology/endurance.md`): the multi-turn loop
    /// lives on `MediaPipeRuntime.enduranceChat`, the sampling/assembly in
    /// `EnduranceSession`. Per-turn records stream to `<output>.turns.ndjson`
    /// AS THEY COMPLETE (a crash leaves the series on disk); the session record
    /// appends to the JSONL like any other run. Exit 1 when the session did not
    /// complete — the record still stands (failed-runs-stay).
    static func runEndurance(
        runtime: any LLMRuntime, runtimeID: String, model: ModelInfo,
        task: EnduranceChatTask, contextTokens: Int?, runs: Int,
        outputPath: String?
    ) async throws {
        #if canImport(LiteRTLM)
        guard let litert = runtime as? MediaPipeRuntime else {
            throw CLIError.invalidArgument(
                "endurance-chat requires --runtime litert-lm (got '\(runtimeID)') — the loop needs a persistent conversation + per-turn engine counters")
        }
        if runs > 1 {
            FileHandle.standardError.write(Data(
                "yardstick: WARNING --runs \(runs) ignored for endurance — one session per invocation; sessions are never pooled\n".utf8))
        }

        let sidecarPath: String? = outputPath.map { p in
            p.hasSuffix(".jsonl")
                ? String(p.dropLast(".jsonl".count)) + ".turns.ndjson"
                : p + ".turns.ndjson"
        }
        let sidecar = try sidecarPath.map { try NDJSONWriter(path: $0) }
        let turnEncoder = JSONEncoder()
        turnEncoder.outputFormatting = [.sortedKeys]

        FileHandle.standardError.write(Data(
            "yardstick: endurance session task=\(task.id) model=\(model.id) context_tokens=\(contextTokens ?? EnduranceChatTask.defaultContextTokens) turn_cap=\(task.parameters.maxTokens)\n".utf8))

        let output = try await EnduranceSession.run(
            runtime: litert, model: model, task: task,
            contextTokens: contextTokens,
            turnsSidecarName: sidecarPath.map { URL(fileURLWithPath: $0).lastPathComponent }
        ) { record in
            if let data = try? turnEncoder.encode(record) {
                sidecar?.writeLine(data)
            }
            let decode = record.decodeTokensPerSecond.map { String(format: "%.1f", $0) } ?? "-"
            FileHandle.standardError.write(Data(
                "yardstick: turn=\(record.turn) t=\(Int(record.startedAtSeconds))s decode=\(decode)tok/s kv=\(record.kvTokensAfterTurn ?? -1) footprintMB=\(Int(record.footprintAfterTurnMB)) stop=\(record.stopReason)\(record.rollover ? " ROLLOVER" : "")\(record.degenerate ? " DEGENERATE" : "")\n".utf8))
        }
        sidecar?.close()

        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        encoder.dateEncodingStrategy = .iso8601
        let json = try encoder.encode(output.result)
        FileHandle.standardOutput.write(json)
        FileHandle.standardOutput.write(Data("\n".utf8))
        if let outputPath {
            try appendJSONL(result: output.result, path: outputPath)
            FileHandle.standardError.write(Data("yardstick: appended to \(outputPath)\n".utf8))
        }

        let e = output.result.endurance
        FileHandle.standardError.write(Data(
            "yardstick: endurance status=\(e?.status ?? "?") turns=\(e?.turnsCompleted ?? 0) rollovers=\(e?.conversationRollovers ?? 0) decode_median=\(String(format: "%.2f", output.result.metrics.decodeTokensPerSecond))tok/s decay=\(e?.decodeDecayPercent.map { String(format: "%.1f%%", $0) } ?? "n/a") mem_slope=\(e?.memorySlopeMBPerTurn.map { String(format: "%.2fMB/turn", $0) } ?? "n/a") degenerate_turns=\(e?.degenerateTurnCount ?? 0)\n".utf8))
        if let status = e?.status, status != "completed" {
            FileHandle.standardError.write(Data(
                "yardstick: endurance session did not complete (\(status)): \(e?.failureDetail ?? "?") — record kept\n".utf8))
            exit(1)
        }
        #else
        throw CLIError.invalidArgument(
            "endurance-chat unavailable: LiteRTLM is not linked into this build")
        #endif
    }

    /// LiteRT-LM's own `benchmark()` entry point — force-prefill `prefill` tokens with no
    /// prompt, then decode `decode`. This is the method behind the HF model card's numbers.
    ///
    /// `--context-tokens` is not optional in practice even though it is optional here: the
    /// vendor helper hardcodes `maxNumTokens` to `max(prefill, decode) + 32` — 1056 at
    /// 1024x256, not the 2048 the Gemma-4 protocol pins. Running without it produces a number
    /// that looks on-protocol and is not, so the omission is warned about rather than defaulted
    /// silently.
    static func runNativeBenchmark(
        runtime: any LLMRuntime, runtimeID: String, model: ModelInfo,
        spec: (prefill: Int, decode: Int), contextTokens: Int?, outputPath: String?
    ) async throws {
        #if canImport(LiteRTLM)
        guard let litert = runtime as? MediaPipeRuntime else {
            throw CLIError.invalidArgument(
                "--litert-native-benchmark requires --runtime litert-lm (got '\(runtimeID)') — no other runtime has this entry point")
        }
        let ctx = contextTokens ?? (max(spec.prefill, spec.decode) + 32)
        if contextTokens == nil {
            FileHandle.standardError.write(Data(
                "yardstick: WARNING native benchmark context_tokens=\(ctx) (litert stock default; the agreed Gemma-4 protocol is 2048 — pass --context-tokens)\n".utf8))
        }
        FileHandle.standardError.write(Data(
            "yardstick: native benchmark model=\(model.id) prefill=\(spec.prefill) decode=\(spec.decode) context_tokens=\(ctx)\n".utf8))

        let info = try await litert.nativeBenchmark(
            model, prefillTokens: spec.prefill, decodeTokens: spec.decode, maxNumTokens: ctx)

        // Emitted in the same shape the iPhone driver's console lines carry, so
        // scripts/import_native_benchmark.py can lift Mac and iPhone rows identically.
        let line = String(
            format: "YARDSTICK_NATIVE_OK prefill_tokens=%d prefill_tok_s=%.2f decode_tokens=%d decode_tok_s=%.2f ttft_ms=%.1f init_s=%.2f context_tokens=%d harness=%@",
            info.prefillTokenCount, info.prefillTokensPerSecond,
            info.decodeTokenCount, info.decodeTokensPerSecond,
            info.timeToFirstTokenSeconds * 1000, info.initTimeSeconds, ctx,
            BenchmarkRunner.harnessStamp)
        print(line)
        if let outputPath {
            let handle: FileHandle
            if !FileManager.default.fileExists(atPath: outputPath) {
                FileManager.default.createFile(atPath: outputPath, contents: nil)
            }
            handle = try FileHandle(forWritingTo: URL(fileURLWithPath: outputPath))
            try handle.seekToEnd()
            try handle.write(contentsOf: Data((line + "\n").utf8))
            try handle.close()
            FileHandle.standardError.write(Data("yardstick: appended to \(outputPath)\n".utf8))
        }
        #else
        throw CLIError.invalidArgument(
            "--litert-native-benchmark unavailable: LiteRTLM is not linked into this build")
        #endif
    }

    static var buildFlavor: String {
        #if YARDSTICK_SPM
        return "spm-lite"
        #else
        return "full"
        #endif
    }

    // MARK: - `yardstick list`

    /// Machine-readable catalog for cell-file preflight (scripts/validate_cells.py
    /// --catalog). Keys are RuntimeKind raw values, matching the cells grammar.
    static func listCatalogJSON() {
        var models: [String: [[String: String]]] = [:]
        for (kind, catalog) in [
            (RuntimeKind.mlxSwift, ModelCatalog.mlx),
            (RuntimeKind.coreMLLLM, ModelCatalog.coreML),
            (RuntimeKind.executorch, ModelCatalog.executorch),
            (RuntimeKind.llamaCpp, ModelCatalog.llamaCpp),
            (RuntimeKind.anemll, ModelCatalog.anemll),
            (RuntimeKind.appleFM, ModelCatalog.appleFM),
            (RuntimeKind.mediaPipe, ModelCatalog.liteRTLM),
            (RuntimeKind.coreAI, ModelCatalog.coreAI),
            (RuntimeKind.cactus, ModelCatalog.cactus),
        ] {
            models[kind.rawValue] = catalog.map {
                ["id": $0.id, "hfRepoId": $0.hfRepoId,
                 "quantization": $0.quantization, "displayName": $0.displayName]
            }
        }
        let payload: [String: Any] = [
            "flavor": buildFlavor,
            "harness": BenchmarkRunner.harnessStamp,
            "tasks": BenchmarkTaskCatalog.all.map { $0.id },
            "models": models,
        ]
        let data = try! JSONSerialization.data(
            withJSONObject: payload, options: [.prettyPrinted, .sortedKeys])
        FileHandle.standardOutput.write(data)
        FileHandle.standardOutput.write(Data("\n".utf8))
    }

    static func listCatalog() {
        print("Available runtimes (Mac CLI):")
        print("  mlx-swift    — MLX Swift LM (default, MLX GPU)")
        print("  coreml-llm   — CoreML via swift-transformers / CoreMLLLM (ANE / GPU)")
        print("  executorch   — PyTorch ExecuTorch (XNNPACK / CoreML delegate)")
        print("  llama-cpp    — llama.cpp via vendored xcframework (CPU + Metal)")
        print("  anemll       — ANEMLL via vendored anemll-swift-cli (ANE)")
        print("  apple-fm     — Apple Foundation Models (macOS 26+, Apple-Intelligence-eligible Macs)")
        print("  litert-lm    — LiteRT-LM (google-ai-edge/LiteRT-LM, Metal GPU)")
        print("")
        print("Available tasks:")
        print("  short-chat   — 128-token reply, measures TTFT + decode tok/s")
        print("  long-context — 2K-token prefill + short reply, measures prefill")
        print("  cactus-parity— 1K-token prefill + 100-token reply, matches `cactus benchmark`")
        print("  sustained    — 512-token generation, watches thermal drift")
        print("  endurance-chat-30m — scripted multi-turn chat, 30 min; per-turn decode/memory/degeneracy series (litert-lm only)")
        print("  lifecycle    — short generation x N, mimics chat session reuse")
        print("")
        print("Available models per runtime — pass `--model <id-or-hf-repo>`.")
        for (label, models) in [
            ("mlx-swift", ModelCatalog.mlx),
            ("coreml-llm", ModelCatalog.coreML),
            ("executorch", ModelCatalog.executorch),
            ("llama-cpp", ModelCatalog.llamaCpp),
            ("anemll", ModelCatalog.anemll),
            ("apple-fm", ModelCatalog.appleFM),
            ("litert-lm", ModelCatalog.liteRTLM),
        ] {
            guard !models.isEmpty else { continue }
            print("\n  [\(label)]")
            for m in models {
                let size = m.onDiskSizeMB.map { "\($0) MB" } ?? "?"
                print("    \(m.id) — \(m.displayName) (\(m.quantization), ~\(size))")
            }
        }
    }

    // MARK: - Helpers

    static func makeRuntime(id: String) throws -> any LLMRuntime {
        switch id {
        case "mlx-swift", "mlx":
            return MLXRuntime()
        // These adapters pull vendored SDKs not yet wired into the SwiftPM macOS
        // build (CoreMLLLM / executorch / llama.xcframework / AnemllCore); the
        // xcodebuild target still ships them. YARDSTICK_SPM is defined only for the
        // SwiftPM CLI, where their sources are excluded from YardstickKit.
        #if !YARDSTICK_SPM
        case "coreml-llm", "coreml":
            return CoreMLRuntime()
        case "executorch", "et":
            return ExecuTorchRuntime()
        case "llama-cpp", "llama.cpp", "llamacpp":
            return LlamaCppRuntime()
        case "anemll":
            return AnemllRuntime()
        #endif
        case "apple-fm", "apple", "fm", "foundation-models":
            return AppleFMRuntime()
        case "litert-lm", "mediapipe":
            return MediaPipeRuntime()
        default:
            throw CLIError.invalidArgument(
                "unknown runtime '\(id)' — supported on Mac: mlx-swift, coreml-llm, executorch, llama-cpp, anemll, apple-fm, litert-lm"
            )
        }
    }

    static func makeTask(id: String) throws -> any BenchmarkTask {
        switch id {
        case "short-chat":
            return ShortChatTask()
        case "long-context":
            return LongContextTask()
        case "sustained":
            return SustainedGenerationTask()
        case "lifecycle":
            return AppLifecycleTask()
        default:
            // Resolve any other registered task by id (e.g. long-context-8k /
            // long-context-32k sweep variants, energy) from the shared catalog.
            if let t = BenchmarkTaskCatalog.task(for: id) { return t }
            throw CLIError.invalidArgument(
                "unknown task '\(id)' — see `yardstick list`"
            )
        }
    }

    static func resolveModel(idOrHF: String?, runtime: any LLMRuntime) throws -> ModelInfo {
        let supported = runtime.supportedModels
        guard !supported.isEmpty else {
            throw CLIError.invalidArgument(
                "runtime \(runtime.kind.displayName) has no supportedModels listed"
            )
        }
        guard let idOrHF else {
            return supported[0]
        }
        if let match = supported.first(where: { $0.id == idOrHF || $0.hfRepoId == idOrHF }) {
            return match
        }
        // Fall back: synthesize a ModelInfo for any HF repo id. The runtime
        // will fail loadModel if the repo doesn't fit its expected layout.
        return ModelInfo(
            id: idOrHF,
            displayName: idOrHF,
            quantization: "?",
            hfRepoId: idOrHF
        )
    }

    static func appendJSONL(result: BenchmarkResult, path: String) throws {
        let url = URL(fileURLWithPath: path)
        try FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let line = try encoder.encode(result) + Data("\n".utf8)

        if FileManager.default.fileExists(atPath: url.path) {
            let handle = try FileHandle(forWritingTo: url)
            try handle.seekToEnd()
            try handle.write(contentsOf: line)
            try handle.close()
        } else {
            try line.write(to: url)
        }
    }

    static func printUsage() {
        print(
            """
            Yardstick — Apple Silicon AI benchmark CLI

            Usage:
              yardstick run --task <id> --runtime <id> --model <id|hf-repo> [--output <path>] [--warm] [--runs N]
              yardstick list
              yardstick help

            Examples:
              yardstick run --task short-chat \\
                            --runtime mlx-swift \\
                            --model mlx-community/gemma-4-e2b-it-4bit

              yardstick run --task sustained \\
                            --runtime mlx-swift \\
                            --output results/raw/m4max-mlx-sustained.jsonl

            See `yardstick list` for the catalog of available tasks and models.
            """
        )
    }
}

/// Append-only NDJSON writer for the endurance turn sidecar. Locked because the
/// onTurn callback is @Sendable; each line is flushed immediately so a crashed
/// session leaves every completed turn on disk.
final class NDJSONWriter: @unchecked Sendable {
    private let handle: FileHandle
    private let lock = NSLock()

    init(path: String) throws {
        let fm = FileManager.default
        let url = URL(fileURLWithPath: path)
        try fm.createDirectory(
            at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        // A leftover sidecar from a quarantined/retried cell is audit trail,
        // not something to truncate: rotate it aside the way the runner
        // rotates the .jsonl (first free .attemptN suffix).
        if let attrs = try? fm.attributesOfItem(atPath: path),
           (attrs[.size] as? Int ?? 0) > 0 {
            var n = 1
            while fm.fileExists(atPath: "\(path).attempt\(n)") { n += 1 }
            try? fm.moveItem(atPath: path, toPath: "\(path).attempt\(n)")
        }
        fm.createFile(atPath: path, contents: nil)
        handle = try FileHandle(forWritingTo: url)
        try handle.seekToEnd()
    }

    func writeLine(_ data: Data) {
        lock.lock()
        defer { lock.unlock() }
        try? handle.write(contentsOf: data + Data("\n".utf8))
    }

    func close() {
        lock.lock()
        defer { lock.unlock() }
        try? handle.close()
    }
}

enum CLIError: Error, CustomStringConvertible {
    case invalidArgument(String)

    var description: String {
        switch self {
        case .invalidArgument(let msg):
            return msg
        }
    }
}

private extension Array where Element == String {
    func value(after index: inout Int) -> String {
        guard index + 1 < count else {
            FileHandle.standardError.write(Data(
                "flag \(self[index]) requires a value\n".utf8
            ))
            exit(2)
        }
        defer { index += 2 }
        return self[index + 1]
    }
}
