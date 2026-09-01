import Foundation

/// One turn of an endurance session — the raw series element. Written as one
/// NDJSON line per turn *as the turn completes* (crash resilience: a session
/// that dies at turn 37 leaves turns 1–36 on disk as evidence).
public struct EnduranceTurnRecord: Codable, Sendable {
    public let turn: Int
    /// Index into `EnduranceChatTask.turnPrompts` (the script cycles).
    public let promptIndex: Int
    /// Seconds since the start of turn 1.
    public let startedAtSeconds: Double
    /// True when this turn began a fresh conversation because the previous one
    /// would not have fit the context budget (full re-prefill from empty KV).
    public let rollover: Bool
    /// Why the rollover happened: "budget" (harness arithmetic against the
    /// configured context) or "kv-wall: <engine error>" — the engine refused
    /// the turn because the remaining state entries are smaller than its
    /// smallest prefill signature (the bundle's real ceiling, which can be
    /// lower than the requested budget; observed 2026-09-01, gemma-4-E2B
    /// bundle capping at 2048 under a 4096 request). nil when no rollover.
    public let rolloverReason: String?
    public let ttftMS: Double?
    public let wallSeconds: Double
    public let chunkCount: Int
    /// Engine counters for THIS turn (LiteRT-LM benchmark info; the per-turn
    /// "last*" values are read immediately after each turn).
    public let prefillTokens: Int?
    public let prefillTokensPerSecond: Double?
    public let decodeTokens: Int?
    public let decodeTokensPerSecond: Double?
    /// Harness wall-clock decode rate over the same turn (first→last chunk),
    /// the engine-independent cross-check.
    public let decodeTokensPerSecondWallClock: Double?
    /// Conversation KV occupancy after the turn (`getTokenCount`).
    public let kvTokensAfterTurn: Int?
    /// memory.md basis: `phys_footprint` / `resident_size`, sampled right after
    /// the turn's stream closes.
    public let footprintAfterTurnMB: Double
    public let residentAfterTurnMB: Double
    public let thermalState: String
    /// stop | length | hang | error
    public let stopReason: String
    public let degenerate: Bool
    /// First 160 chars of the turn's visible output (thought channel included).
    public let outputHead: String

    public init(
        turn: Int, promptIndex: Int, startedAtSeconds: Double, rollover: Bool,
        rolloverReason: String?,
        ttftMS: Double?, wallSeconds: Double, chunkCount: Int,
        prefillTokens: Int?, prefillTokensPerSecond: Double?,
        decodeTokens: Int?, decodeTokensPerSecond: Double?,
        decodeTokensPerSecondWallClock: Double?,
        kvTokensAfterTurn: Int?, footprintAfterTurnMB: Double,
        residentAfterTurnMB: Double, thermalState: String, stopReason: String,
        degenerate: Bool, outputHead: String
    ) {
        self.turn = turn
        self.promptIndex = promptIndex
        self.startedAtSeconds = startedAtSeconds
        self.rollover = rollover
        self.rolloverReason = rolloverReason
        self.ttftMS = ttftMS
        self.wallSeconds = wallSeconds
        self.chunkCount = chunkCount
        self.prefillTokens = prefillTokens
        self.prefillTokensPerSecond = prefillTokensPerSecond
        self.decodeTokens = decodeTokens
        self.decodeTokensPerSecond = decodeTokensPerSecond
        self.decodeTokensPerSecondWallClock = decodeTokensPerSecondWallClock
        self.kvTokensAfterTurn = kvTokensAfterTurn
        self.footprintAfterTurnMB = footprintAfterTurnMB
        self.residentAfterTurnMB = residentAfterTurnMB
        self.thermalState = thermalState
        self.stopReason = stopReason
        self.degenerate = degenerate
        self.outputHead = outputHead
    }
}

/// Per-turn degeneracy heuristic — the litertlm-convert
/// `verify_quality.degenerate()` rules ported verbatim, so a turn flagged here
/// means the same thing a publish-gate flag means there: looping 5-grams,
/// vocabulary collapse, character collapse, or special-token spam.
public enum DegeneracyCheck {
    public static func isDegenerate(_ text: String) -> Bool {
        let words = text.split(whereSeparator: { $0.isWhitespace }).map(String.init)
        if words.count >= 10 {
            var grams: [String: Int] = [:]
            for i in 0...(words.count - 5) {
                grams[words[i..<i + 5].joined(separator: " "), default: 0] += 1
            }
            if let peak = grams.values.max(), peak >= 3 { return true }
            if Double(Set(words).count) / Double(words.count) < 0.30 { return true }
        }
        if text.count >= 40 && Set(text).count < 15 { return true }
        if text.components(separatedBy: "<|").count - 1 >= 5 { return true }
        if text.components(separatedBy: "<pad>").count - 1 >= 5 { return true }
        return false
    }
}

#if canImport(LiteRTLM)

/// Drives one endurance session end to end: samplers + model load around
/// `MediaPipeRuntime.enduranceChat`, then session-stat derivation into a
/// schema-v1 `BenchmarkResult`. The turn loop itself lives on the runtime
/// (it needs the conversation-level LiteRT-LM surface).
public enum EnduranceSession {

    public struct Output: Sendable {
        public let result: BenchmarkResult
        public let turns: [EnduranceTurnRecord]
    }

    /// Windows compared for the decay verdict (first N vs last N seconds of
    /// the session, medians of per-turn engine decode rates).
    public static let decayWindowSeconds: Double = 300

    public static func run(
        runtime: MediaPipeRuntime,
        model: ModelInfo,
        task: EnduranceChatTask,
        contextTokens: Int?,
        turnsSidecarName: String?,
        onTurn: @Sendable @escaping (EnduranceTurnRecord) -> Void
    ) async throws -> Output {
        var device = DeviceSnapshot.capture()
        let memorySampler = MemorySampler()
        let thermalSampler = ThermalSampler()
        let budget = contextTokens ?? EnduranceChatTask.defaultContextTokens

        let baselineMB = MemoryMonitor.footprintMB()
        await thermalSampler.start()

        await runtime.prepareContext(maxContextTokens: budget)
        let loadStart = CFAbsoluteTimeGetCurrent()
        try await runtime.loadModel(model) { _ in }
        let loadTime = CFAbsoluteTimeGetCurrent() - loadStart
        let memoryAfterLoad = MemoryMonitor.footprintMB()
        await memorySampler.start()

        // Collect turns locally *and* forward them to the caller (which
        // streams them to the NDJSON sidecar as they happen).
        let collector = TurnCollector()
        let outcome = try await runtime.enduranceChat(
            task: task, contextTokens: budget
        ) { record in
            collector.append(record)
            onTurn(record)
        }
        let turns = collector.snapshot()

        await memorySampler.stop()
        await thermalSampler.stop()
        let endBattery = DeviceSnapshot.currentBattery()
        device.batteryState = endBattery.state
        device.batteryLevel = endBattery.level

        // ---- session stat derivation (all within-session; never pooled) ----
        let elapsed = (turns.last.map { $0.startedAtSeconds + $0.wallSeconds }) ?? 0
        let engineRates = turns.compactMap { $0.decodeTokensPerSecond }.filter { $0 > 0 }
        let wallRates = turns.compactMap { $0.decodeTokensPerSecondWallClock }.filter { $0 > 0 }

        let firstWindow = turns.filter { $0.startedAtSeconds < decayWindowSeconds }
            .compactMap { $0.decodeTokensPerSecond }.filter { $0 > 0 }
        let lastWindow = turns.filter { $0.startedAtSeconds >= elapsed - decayWindowSeconds }
            .compactMap { $0.decodeTokensPerSecond }.filter { $0 > 0 }
        // Only meaningful when the windows are disjoint (session ran longer
        // than two windows) and both have samples.
        let windowsValid = elapsed > 2 * decayWindowSeconds
            && !firstWindow.isEmpty && !lastWindow.isEmpty
        let firstMed = windowsValid ? median(firstWindow) : nil
        let lastMed = windowsValid ? median(lastWindow) : nil
        let decayPct: Double? = (firstMed != nil && lastMed != nil && firstMed! > 0)
            ? (firstMed! - lastMed!) / firstMed! * 100 : nil

        let slopePerTurn = leastSquaresSlope(
            turns.map { (Double($0.turn), $0.footprintAfterTurnMB) })
        let slopePerMinute = leastSquaresSlope(
            turns.map { ($0.startedAtSeconds / 60.0, $0.footprintAfterTurnMB) })

        let degenerateTurns = turns.filter { $0.degenerate }
        let promptTokens = turns.compactMap { $0.prefillTokens }.reduce(0, +)
        let genTokens = turns.compactMap { $0.decodeTokens }.reduce(0, +)
        let prefillSeconds = turns.compactMap { t -> Double? in
            guard let n = t.prefillTokens, let r = t.prefillTokensPerSecond, r > 0
            else { return nil }
            return Double(n) / r
        }.reduce(0, +)

        let summary = EnduranceSummary(
            plannedMinutes: task.minutes,
            elapsedSeconds: elapsed,
            turnsCompleted: turns.count,
            conversationRollovers: turns.filter { $0.rollover }.count,
            turnOutputTokenCap: task.parameters.maxTokens,
            status: outcome.status,
            failureDetail: outcome.failureDetail,
            windowSeconds: decayWindowSeconds,
            decodeTokSFirstWindowMedian: firstMed,
            decodeTokSLastWindowMedian: lastMed,
            decodeDecayPercent: decayPct,
            memorySlopeMBPerTurn: slopePerTurn,
            memorySlopeMBPerMinute: slopePerMinute,
            footprintAfterFirstTurnMB: turns.first?.footprintAfterTurnMB,
            footprintAfterLastTurnMB: turns.last?.footprintAfterTurnMB,
            degenerateTurnCount: degenerateTurns.count,
            firstDegenerateTurn: degenerateTurns.first?.turn,
            turnsSidecar: turnsSidecarName
        )

        let metrics = Metrics(
            coldRun: true,  // one fresh process per session; there is no warm regime here
            loadTimeSeconds: loadTime,
            downloadTimeSeconds: nil,
            firstTokenLatencyMS: Int((turns.first?.ttftMS ?? 0).rounded()),
            promptTokensPerSecond: prefillSeconds > 0 ? Double(promptTokens) / prefillSeconds : 0,
            decodeTokensPerSecond: engineRates.isEmpty ? 0 : median(engineRates),
            promptTokensPerSecondWallClock: nil,
            decodeTokensPerSecondWallClock: wallRates.isEmpty ? nil : median(wallRates),
            promptTokenCount: promptTokens,
            generatedTokenCount: genTokens,
            streamedChunkCount: turns.map { $0.chunkCount }.reduce(0, +),
            totalGenerationTimeSeconds: elapsed,
            cancellationLatencyMS: nil,
            stopReason: outcome.status == "completed" ? "stop" : "error",
            memoryBaselineMB: baselineMB,
            memoryAfterLoadMB: memoryAfterLoad,
            memoryPeakDuringDecodeMB: await memorySampler.peakMB,
            memoryAfterGenerationMB: MemoryMonitor.footprintMB(),
            memoryPeakResidentMB: await memorySampler.peakResidentMB,
            memoryMedianMB: await memorySampler.medianMB,
            memoryMedianResidentMB: await memorySampler.medianResidentMB,
            memoryFinalResidentMB: await memorySampler.finalResidentMB,
            contextTokensConfigured: budget,
            harnessStamp: BenchmarkRunner.harnessStamp + "+endurance-r1",
            initialThermalState: ThermalMonitor.describe(await thermalSampler.initialState),
            peakThermalState: ThermalMonitor.describe(await thermalSampler.peakState),
            finalThermalState: ThermalMonitor.describe(await thermalSampler.finalState),
            decodeRateRollingWindow: [],  // the per-turn series lives in the sidecar
            interTokenLatencyP50MS: nil,
            interTokenLatencyP95MS: nil,
            interTokenLatencyP99MS: nil,
            energyJoules: nil,
            batteryDeltaPercent: 0,
            energyJoulesPerToken: nil
        )

        let result = BenchmarkResult(
            device: device,
            runtime: runtime.kind.rawValue,
            engineVersion: EnginePins.version(for: runtime.kind),
            engineArtifact: EnginePins.artifact(for: runtime.kind),
            model: model,
            modelRevision: HFDownloader.resolvedRevision(hfRepoId: model.hfRepoId),
            task: task.id,
            parameters: task.parameters,
            metrics: metrics,
            outputSample: String((turns.first?.outputHead ?? "").prefix(200)),
            endurance: summary
        )
        return Output(result: result, turns: turns)
    }

    // MARK: - helpers

    static func median(_ xs: [Double]) -> Double {
        guard !xs.isEmpty else { return 0 }
        let s = xs.sorted()
        let mid = s.count / 2
        return s.count % 2 == 1 ? s[mid] : (s[mid - 1] + s[mid]) / 2
    }

    /// Ordinary least-squares slope of y over x; nil when under 3 points or
    /// x has no variance.
    static func leastSquaresSlope(_ points: [(Double, Double)]) -> Double? {
        guard points.count >= 3 else { return nil }
        let n = Double(points.count)
        let sx = points.map { $0.0 }.reduce(0, +)
        let sy = points.map { $0.1 }.reduce(0, +)
        let sxx = points.map { $0.0 * $0.0 }.reduce(0, +)
        let sxy = points.map { $0.0 * $0.1 }.reduce(0, +)
        let denom = n * sxx - sx * sx
        guard abs(denom) > 1e-9 else { return nil }
        return (n * sxy - sx * sy) / denom
    }

    /// Thread-safe turn accumulator (the onTurn callback is @Sendable).
    final class TurnCollector: @unchecked Sendable {
        private let lock = NSLock()
        private var records: [EnduranceTurnRecord] = []
        func append(_ r: EnduranceTurnRecord) {
            lock.lock(); records.append(r); lock.unlock()
        }
        func snapshot() -> [EnduranceTurnRecord] {
            lock.lock(); defer { lock.unlock() }
            return records
        }
    }
}

#endif
