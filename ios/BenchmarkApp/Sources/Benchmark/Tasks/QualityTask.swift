import Foundation

/// Quality-parity sanity check. A fixed set of short, unambiguously-checkable questions,
/// greedy (temp 0). This is NOT a full perplexity / MMLU eval — it's a guardrail that catches
/// quantization-induced quality *collapse* (wrong answers, degenerate looping/repetition), so the
/// decode-tok/s comparison across runtimes (each with its own native 4-bit quant) is made at
/// roughly equal output quality rather than speed-at-any-quality. The full output is persisted
/// (BenchmarkRunner keeps it for `id == "quality"`) and scored post-hoc by
/// `scripts/quality_check.py` (correctness out of 8 + a repetition/degeneracy flag).
public struct QualityTask: BenchmarkTask {
    public let id = "quality"
    public let title = "Quality parity"
    public let summary = "8 fixed checkable questions, greedy. Scored for correctness + degeneracy across runtimes."
    public let parameters = GenerationParameters(maxTokens: 256, temperature: 0.0, topP: 1.0)

    public init() {}

    public var prompt: String {
        """
        Answer each question on its own line, as briefly as possible — just the answer, no explanation.
        1. What is 17 + 25?
        2. What is the capital of Japan?
        3. What is the opposite of "hot"?
        4. How many days are in a week?
        5. How do you say "thank you" in French?
        6. What is 8 times 7?
        7. Which is larger: 0.9 or 0.11?
        8. Complete the rhyme: "Roses are red, violets are ___"
        """
    }
}
