import Foundation

public protocol BenchmarkTask: Sendable {
    /// Stable id used for filenames and the result table.
    var id: String { get }

    /// Human-friendly title shown in the UI.
    var title: String { get }

    /// One-sentence description of what this task measures.
    var summary: String { get }

    /// The prompt to feed into the runtime.
    var prompt: String { get }

    /// Generation parameters specific to this task.
    var parameters: GenerationParameters { get }

    /// When non-nil, the runner repeats generation until this many seconds of
    /// active decode have elapsed, instead of running the prompt once. Used by
    /// the energy task so a measurable battery delta builds up (a single short
    /// reply is far below the iOS battery API's 1% step). `nil` = run once.
    var sustainSeconds: TimeInterval? { get }

    /// The version of the prompt text when it changed under the same id, written into every
    /// record as `conditions.promptVersion` (= `prompts/text/versions.tsv`). `nil` = the text
    /// the id was born with: the record carries no key.
    var promptVersion: String? { get }
}

public extension BenchmarkTask {
    var sustainSeconds: TimeInterval? { nil }
    var promptVersion: String? { nil }
}

public enum BenchmarkTaskCatalog {
    public static let all: [any BenchmarkTask] = [
        ShortChatTask(),
        LongContextTask(id: "long-context-512", targetTokens: 512),     // context-length sweep within the 4096 ctx ceiling
        LongContextTask(id: "long-context-1024", targetTokens: 1024, maxTokens: 256),  // p=1024/g=256, one-sentence tail (the 7/18 deep-context cells)
        // Same p=1024 prefill, but the tail forces the model to fill the 256-token budget.
        // This is the only cross-arm instrument for the deep-context column: LiteRT-LM's
        // native benchmark() forces prefill without a prompt, and no other runtime has an
        // equivalent entry point, so the four remaining arms can only be measured here.
        // Since 2026-10-19 the tail is the -noref sentence below (the blocks are filler, the
        // list comes from the model's own knowledge): with the model's own chat template,
        // Gemma 4 on llama.cpp and MLX declined the "passage above" tail as placeholder text.
        // Same id, blocks and budget; the records carry the version, and the summary's
        // prompt_version marks the series break (docs/dashboard-cells-v1.md "1K task tail").
        LongContextTask(id: "long-context-1024-gen256", targetTokens: 1024, maxTokens: 256,
                        forceLongOutput: true, tail: LongContextTask.norefTail,
                        promptVersion: "noref-2026-10-19"),
        // p≈2048 / g=256 — the dashboard's long-context column (2026-09-18): the same
        // forced-output prompt, twice the depth. 27 filler blocks put the measured prompt
        // just under 2,048 Qwen3 tokens (≈1,980 with the chat template) so it still fits
        // the llama.cpp adapter's 2,048-token prefill batch; Gemma-4's tokenizer reads the
        // same text ≈17% shorter. The record's promptTokenCount is the ground truth, as
        // for every sweep id.
        LongContextTask(id: "long-context-2048-gen256", targetTokens: 2048, maxTokens: 256,
                        forceLongOutput: true, blocks: 27),
        // The same 27 blocks with a tail that calls them filler and asks the list from the
        // model's own knowledge (`LongContextTask.norefTail` = scripts/gen_task_prompts.py
        // NOREF_TAIL; the Android drivers' task since 2026-10-12, catalog X2). Same budget;
        // the tail is part of the task id, so its records never pool with the task above.
        // Its text is unchanged since that day: the version names it (records before
        // 2026-10-19 carry no version and the same text).
        LongContextTask(id: "long-context-2048-gen256-noref", targetTokens: 2048, maxTokens: 256,
                        forceLongOutput: true, blocks: 27, tail: LongContextTask.norefTail,
                        promptVersion: "noref-2026-10-12"),
        LongContextTask(),                                              // ~2K
        LongContextTask(id: "long-context-3k", targetTokens: 3072),     // near the 4096 ctx ceiling (room for 128 decode)
        LongContextTask(id: "long-context-8k", targetTokens: 8192),
        LongContextTask(id: "long-context-32k", targetTokens: 32768),
        CactusParityTask(),
        SustainedGenerationTask(),
        EnergyTask(),
        QualityTask(),
        AppLifecycleTask(),
        EnduranceChatTask(),                    // 30 min, the standing protocol
        EnduranceChatTask(minutes: 2),          // smoke variant for harness checks
    ]

    public static func task(for id: String) -> (any BenchmarkTask)? {
        if let t = all.first(where: { $0.id == id }) { return t }
        // Any endurance duration is a valid task id (endurance-chat-<N>m) —
        // the catalog lists the canonical two, the pattern admits the rest.
        if id.hasPrefix("endurance-chat-"), id.hasSuffix("m"),
           let n = Int(id.dropFirst("endurance-chat-".count).dropLast()), n > 0 {
            return EnduranceChatTask(minutes: n)
        }
        return nil
    }
}
