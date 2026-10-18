import Foundation
public protocol BenchmarkTask: Sendable {
    var id: String { get }
    var title: String { get }
    var summary: String { get }
    var prompt: String { get }
    var parameters: GenerationParameters { get }
}
public struct GenerationParameters: Sendable {
    public var maxTokens: Int; public var temperature: Float; public var topP: Float
    public init(maxTokens: Int, temperature: Float = 0.7, topP: Float = 0.9) {
        self.maxTokens = maxTokens; self.temperature = temperature; self.topP = topP
    }
}
