import Foundation

/// Task C's long-form sibling: a scripted multi-turn chat sustained for a fixed
/// wall-clock window (default 30 min) in ONE engine process, on ONE conversation
/// whose KV accumulates turn over turn. Protocol: `methodology/endurance.md`;
/// turn script rationale: `prompts/endurance-chat.md`.
///
/// What it measures that no run-once task can: decode-rate decay over tens of
/// minutes, a per-turn memory series (leak-class detection — a footprint that
/// climbs linearly per turn is a leak, a step at rollover is KV), per-turn
/// degeneracy, and context-rollover behavior when the conversation outgrows its
/// KV budget.
///
/// LiteRT-LM only for now: the loop needs a conversation that persists across
/// turns, a per-call output cap, and per-turn engine counters
/// (`Conversation.getTokenCount` / `getBenchmarkInfo`) — surfaces the generic
/// `LLMRuntime.generate` deliberately does not have. Same precedent as
/// `--litert-native-benchmark`.
public struct EnduranceChatTask: BenchmarkTask {
    public let id: String
    public let title = "Endurance chat"
    public let summary = "Scripted multi-turn chat for a fixed window; per-turn decode/memory/thermal/degeneracy series."

    /// Wall-clock window measured from the start of turn 1.
    public let minutes: Int

    /// Fixed 12-prompt cycle. Deterministic order; mixed short factual turns,
    /// follow-ups that reference earlier turns (so accumulated KV is actually
    /// attended to), and periodic summarize-the-conversation turns that sweep
    /// the full context. Each prompt is small (≤ ~50 tokens) so per-turn
    /// prefill cost stays dominated by the *delta*, not the script.
    public static let turnPrompts: [String] = [
        "Let's talk about running language models on phones. In two or three sentences, what is the biggest engineering constraint?",
        "Which matters more for the experience you just described: prefill speed or decode speed? Answer briefly and say why.",
        "Give me a concrete example with a model around 2B parameters.",
        "Summarize our conversation so far in one short paragraph.",
        "Now switch topics: explain KV cache growth during a long chat, in a few sentences.",
        "How does quantization interact with the problem you just explained? Keep it brief.",
        "Earlier you named an engineering constraint. Does quantization help with that one too? A short answer is fine.",
        "Write a four-line rhyming poem about a phone getting warm while it thinks.",
        "In one sentence each, name three ways a chat app can shorten its context when the conversation gets long.",
        "Which of those three would you pick for a low-RAM device, and why? Two sentences.",
        "Summarize everything we have discussed in this whole conversation in one short paragraph.",
        "Ask me one good follow-up question about on-device AI, then answer it yourself in two sentences.",
    ]

    /// First prompt doubles as the `BenchmarkTask.prompt` so generic surfaces
    /// (catalog listing, context estimation) stay uniform.
    public var prompt: String { Self.turnPrompts[0] }

    /// Per-TURN output cap (`maxTokens`), enforced natively via LiteRT-LM's
    /// `maxOutputTokens` — same cap for every model and every engine version
    /// (same-budget). Sampling matches Task C: typical chat, not greedy.
    public let parameters: GenerationParameters

    /// Default context (KV) budget when the cell passes no `--context-tokens`.
    /// Rollover — not silent widening — is what happens when a conversation
    /// outgrows it.
    public static let defaultContextTokens = 4096

    /// `turnCap` other than 256 is a DIAGNOSTIC knob (CLI env
    /// `ENDURANCE_TURN_CAP`), not a protocol variant: the cap is part of the
    /// measurement contract, and a non-256 run must never land in a standing
    /// campaign. It exists because the 2026-09-01 baseline needed a
    /// cap-vs-coherence probe (does a thinking model recover when turns can
    /// finish their <think> block?) — the row stays self-describing through
    /// `parameters.maxTokens` / `endurance.turnOutputTokenCap`.
    public init(minutes: Int = 30, turnCap: Int = 256) {
        self.minutes = minutes
        self.id = "endurance-chat-\(minutes)m"
        self.parameters = GenerationParameters(maxTokens: turnCap, temperature: 0.7, topP: 0.9)
    }
}
