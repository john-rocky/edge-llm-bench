import Foundation

public struct ShortChatTask: BenchmarkTask {
    public let id = "short-chat"
    public let title = "Short chat"
    public let summary = "128-token assistant response. Measures TTFT and steady-state decode."

    public let prompt = "Explain what on-device AI means in simple terms."

    public let parameters = GenerationParameters(maxTokens: 128, temperature: 0.0, topP: 1.0)

    public init() {}
}
