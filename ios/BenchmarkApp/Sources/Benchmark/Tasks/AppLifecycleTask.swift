import Foundation

/// Placeholder for the multi-step lifecycle task.
///
/// The lifecycle scenario (cancel mid-generation, background/foreground, repeat-N)
/// is driven by `BenchmarkRunner.runLifecycleScenario(...)` rather than a single prompt,
/// so this task surface only exists to keep the catalog uniform.
public struct AppLifecycleTask: BenchmarkTask {
    public let id = "app-lifecycle"
    public let title = "App lifecycle loop"
    public let summary = "Cancel, background/foreground, repeat. Stresses real app conditions."

    public let prompt = "Hello!"
    public let parameters = GenerationParameters(maxTokens: 256, temperature: 0.7, topP: 0.9)

    public init() {}
}
