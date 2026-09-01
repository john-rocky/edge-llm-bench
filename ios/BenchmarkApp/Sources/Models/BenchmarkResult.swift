import Foundation

public struct BenchmarkResult: Codable, Sendable, Identifiable {
    public let id: UUID
    /// schema/result.v1.json `schemaVersion`. Optional so pre-v1 JSON still decodes;
    /// every row this build writes carries 1 (verified missing from device rows on
    /// 2026-08-13 — fix 3 had landed engineVersion/engineArtifact without it).
    public let schemaVersion: Int?
    public let timestamp: Date
    public let device: DeviceSnapshot
    public let runtime: String
    /// The engine build that produced this row (schema v1 `engineVersion`): the vendored
    /// runtime's tag/commit as OBSERVED at build time by `scripts/stamp_engine_pins.sh`
    /// (via the `BenchEnginePins` Info.plist key — see `EnginePins`). `nil` on rows from
    /// builds that predate the stamp (pre-2026-08-05) or when the pin could not be read.
    /// Recorded because the v0.13.1→v0.15.0 re-measure had to reconstruct build identity
    /// from prose READMEs — engine identity must be data, not prose.
    public let engineVersion: String?
    /// Artifact identity when the engine is a prebuilt binary (schema v1 `engineArtifact`),
    /// e.g. "CLiteRTLM.xcframework.zip@v0.13.0 sha256:af23c77b…". Kept separate from
    /// `engineVersion` because the binary can lag the repo tag (the v0.13.1 LiteRT-LM
    /// checkout ships v0.13.0 engine zips).
    public let engineArtifact: String?
    public let model: ModelInfo
    /// The HF revision (commit hash) the model was actually resolved from, read out of the
    /// on-device hub cache's `refs/main` at run time. Recorded because it is the one fact
    /// that cannot be recovered later: the MLX E2B checkpoint question (2c3e507 vs 238767…,
    /// two uploads under one repo id with different key sets) was unanswerable from stored
    /// results precisely because nothing recorded it. `nil` for sideloaded bundles whose
    /// identity is the file itself (LiteRT .litertlm, GGUF, Cactus CQ, Core AI .aimodelc).
    public let modelRevision: String?
    public let task: String
    public let parameters: GenerationParameters
    public let metrics: Metrics
    public let outputSample: String
    /// Session-level derived stats for endurance tasks (schema v1 `endurance`,
    /// additive). `nil` on every other task. The full per-turn series lives in
    /// the raw sidecar this record's `endurance.turnsSidecar` names — derived
    /// stats travel with the record, raw series stay raw.
    public let endurance: EnduranceSummary?

    public init(
        id: UUID = UUID(),
        schemaVersion: Int? = 1,
        timestamp: Date = Date(),
        device: DeviceSnapshot,
        runtime: String,
        engineVersion: String? = nil,
        engineArtifact: String? = nil,
        model: ModelInfo,
        modelRevision: String? = nil,
        task: String,
        parameters: GenerationParameters,
        metrics: Metrics,
        outputSample: String,
        endurance: EnduranceSummary? = nil
    ) {
        self.id = id
        self.schemaVersion = schemaVersion
        self.timestamp = timestamp
        self.device = device
        self.runtime = runtime
        self.engineVersion = engineVersion
        self.engineArtifact = engineArtifact
        self.model = model
        self.modelRevision = modelRevision
        self.task = task
        self.parameters = parameters
        self.metrics = metrics
        self.outputSample = outputSample
        self.endurance = endurance
    }
}

/// Derived session stats for an endurance run (see `EnduranceChatTask` /
/// `methodology/endurance.md`). Every value here is computable from the turn
/// sidecar; they are duplicated onto the record so a session's verdicts —
/// decay, memory slope, degeneracy count, completion status — survive as data
/// even when only the summary layer is consulted.
public struct EnduranceSummary: Codable, Sendable {
    /// The task's wall-clock window as planned (`endurance-chat-<N>m`).
    public let plannedMinutes: Int
    /// Wall-clock actually covered, start of turn 1 → end of last turn.
    public let elapsedSeconds: Double
    /// Turns that finished (streamed to a natural end or the output cap).
    public let turnsCompleted: Int
    /// Conversations created *after* the first one because the next turn would
    /// not have fit the context budget. A rollover turn re-prefills from empty.
    public let conversationRollovers: Int
    /// Per-turn output cap actually enforced (native `maxOutputTokens`).
    public let turnOutputTokenCap: Int
    /// `completed` | `crash` (a turn threw) | `hang` (turn watchdog fired) |
    /// `empty-output` (three consecutive turns streamed no text — a collapse
    /// finding, cut short instead of spinning out the window). Failed sessions
    /// keep their record and their partial series (failed-runs-stay).
    public let status: String
    /// For non-completed sessions: the watchdog reason or the thrown error's
    /// description — the crash record must say why (stored-report-rule).
    public let failureDetail: String?
    /// Median engine decode tok/s over turns starting in the first
    /// `windowSeconds` of the session, and over turns starting in the last
    /// `windowSeconds`. The decay verdict compares like-for-like windows
    /// *within one session* — never across sessions (session-drift rule).
    public let windowSeconds: Double
    public let decodeTokSFirstWindowMedian: Double?
    public let decodeTokSLastWindowMedian: Double?
    /// (first − last) / first × 100; positive = the session got slower.
    public let decodeDecayPercent: Double?
    /// Least-squares slope of after-turn `phys_footprint` (memory.md basis)
    /// against turn index / minutes. A persistent positive slope that survives
    /// rollovers is the leak-class signal this task exists to catch.
    public let memorySlopeMBPerTurn: Double?
    public let memorySlopeMBPerMinute: Double?
    public let footprintAfterFirstTurnMB: Double?
    public let footprintAfterLastTurnMB: Double?
    /// Turns whose (thought + text) output tripped the degeneracy heuristic
    /// (looping n-grams / vocabulary collapse / special-token spam — the
    /// litertlm-convert `verify_quality.degenerate()` rules).
    public let degenerateTurnCount: Int
    public let firstDegenerateTurn: Int?
    /// Basename of the per-turn NDJSON sidecar next to this record
    /// (stored-report-rule: the series is the report).
    public let turnsSidecar: String?

    public init(
        plannedMinutes: Int, elapsedSeconds: Double, turnsCompleted: Int,
        conversationRollovers: Int, turnOutputTokenCap: Int, status: String,
        failureDetail: String?,
        windowSeconds: Double,
        decodeTokSFirstWindowMedian: Double?, decodeTokSLastWindowMedian: Double?,
        decodeDecayPercent: Double?,
        memorySlopeMBPerTurn: Double?, memorySlopeMBPerMinute: Double?,
        footprintAfterFirstTurnMB: Double?, footprintAfterLastTurnMB: Double?,
        degenerateTurnCount: Int, firstDegenerateTurn: Int?, turnsSidecar: String?
    ) {
        self.plannedMinutes = plannedMinutes
        self.elapsedSeconds = elapsedSeconds
        self.turnsCompleted = turnsCompleted
        self.conversationRollovers = conversationRollovers
        self.turnOutputTokenCap = turnOutputTokenCap
        self.status = status
        self.failureDetail = failureDetail
        self.windowSeconds = windowSeconds
        self.decodeTokSFirstWindowMedian = decodeTokSFirstWindowMedian
        self.decodeTokSLastWindowMedian = decodeTokSLastWindowMedian
        self.decodeDecayPercent = decodeDecayPercent
        self.memorySlopeMBPerTurn = memorySlopeMBPerTurn
        self.memorySlopeMBPerMinute = memorySlopeMBPerMinute
        self.footprintAfterFirstTurnMB = footprintAfterFirstTurnMB
        self.footprintAfterLastTurnMB = footprintAfterLastTurnMB
        self.degenerateTurnCount = degenerateTurnCount
        self.firstDegenerateTurn = firstDegenerateTurn
        self.turnsSidecar = turnsSidecar
    }
}

public struct GenerationParameters: Codable, Sendable, Hashable {
    public var maxTokens: Int
    public var temperature: Float
    public var topP: Float
    public var seed: UInt64?

    public init(maxTokens: Int, temperature: Float = 0.7, topP: Float = 0.9, seed: UInt64? = nil) {
        self.maxTokens = maxTokens
        self.temperature = temperature
        self.topP = topP
        self.seed = seed
    }

    public static let greedy = GenerationParameters(maxTokens: 128, temperature: 0.0, topP: 1.0)
    public static let chat = GenerationParameters(maxTokens: 512, temperature: 0.7, topP: 0.9)
}

public struct Metrics: Codable, Sendable {
    public let coldRun: Bool
    public let loadTimeSeconds: Double?
    public let downloadTimeSeconds: Double?

    public let firstTokenLatencyMS: Int
    public let promptTokensPerSecond: Double
    public let decodeTokensPerSecond: Double
    /// End-to-end wall-clock rates measured by the harness itself, for every
    /// runtime, on the same basis: prompt = call start -> first chunk,
    /// decode = first chunk -> end of stream. `decodeTokensPerSecond` above
    /// prefers the engine's own counters where a runtime exposes them
    /// (LiteRT-LM, MLX), which excludes host-side detokenize/stream cost;
    /// these two fields are the like-for-like column across all arms.
    public let promptTokensPerSecondWallClock: Double?
    public let decodeTokensPerSecondWallClock: Double?
    public let promptTokenCount: Int
    public let generatedTokenCount: Int
    /// Number of `.chunk` (decoded-text) events actually streamed during the
    /// run. Distinct from `generatedTokenCount` (which prefers the runtime's
    /// `.info` decode-token count): when a run reports tokens but streams *no*
    /// text (`streamedChunkCount == 0` while `generatedTokenCount > 0`) the
    /// model produced only non-decodable / special tokens — i.e. a degenerate
    /// collapse, not a capture bug. Persisting it makes an empty `outputSample`
    /// self-diagnosing. Optional so pre-2026-06 JSONL still decodes.
    public let streamedChunkCount: Int?
    public let totalGenerationTimeSeconds: Double
    public let cancellationLatencyMS: Int?
    public let stopReason: String

    // Memory is `phys_footprint` (jetsam-charged) — see MemoryMonitor. Runs
    // captured before 2026-06 used resident_size (RSS); the two are not
    // byte-identical (phys_footprint runs higher; RSS omits compressed pages).
    public let memoryBaselineMB: Double
    public let memoryAfterLoadMB: Double?
    public let memoryPeakDuringDecodeMB: Double
    public let memoryAfterGenerationMB: Double
    /// Peak `resident_size` over the same window as `memoryPeakDuringDecodeMB`.
    /// Mapped-but-resident pages (mmap'd weights) land here and not in the
    /// footprint, so the gap between the two is the mapped share.
    public let memoryPeakResidentMB: Double?
    /// Median of the sampled footprints / resident sizes over the same window, plus the
    /// settled resident size at the end. Peak resident is page-cache noise (66-281%
    /// run-to-run, measured 2026-07-26); rank on the medians.
    public let memoryMedianMB: Double?
    public let memoryMedianResidentMB: Double?
    public let memoryFinalResidentMB: Double?
    /// The context (KV) budget this run was actually given, i.e. the value handed to
    /// `LLMRuntime.prepareContext`. Either the runner's prompt+output estimate or the
    /// `--context-tokens` override. Recorded because it is not derivable from anything
    /// else in the row, and a memory cell means nothing without it: the LiteRT card's
    /// 1,450 MB is at 2048, our pre-2026-07-27 cells sat at ~660-1,849.
    public let contextTokensConfigured: Int?
    /// Which measurement contract produced this cell. Bump it whenever the semantics of
    /// a recorded field change, so an inherited number can be told apart from a fresh one
    /// — the 92 MB deep-context cell rode five revisions because nothing on it said which
    /// harness it came from.
    public let harnessStamp: String?

    public let initialThermalState: String
    public let peakThermalState: String
    public let finalThermalState: String

    public let decodeRateRollingWindow: [Double]

    /// Inter-token latency distribution in milliseconds, derived from the
    /// gap between consecutive `.chunk` events. `nil` when fewer than two
    /// tokens were emitted. The p95 / p99 numbers surface the worst-case
    /// glitch that a chat UI will perceive as a stall, even when the
    /// average decode tok/s looks smooth.
    public let interTokenLatencyP50MS: Double?
    public let interTokenLatencyP95MS: Double?
    public let interTokenLatencyP99MS: Double?

    /// Estimated joules used during the run, derived from battery-level delta.
    /// `nil` when the run was too short for a 1% battery step to register.
    public let energyJoules: Double?
    /// Battery percentage drop observed during the run (e.g. 1.5 means -1.5%).
    public let batteryDeltaPercent: Float
    /// Joules per generated token, when both `energyJoules` and a token
    /// count are available.
    public let energyJoulesPerToken: Double?
    /// Average whole-system power over the measured window (joules / seconds).
    /// On iOS this is battery-delta-derived; on Mac it is injected post-hoc by
    /// `scripts/measure_energy.py` from `powermetrics`.
    public let averagePackagePowerW: Double?
    /// Length of the window the energy figure covers, in seconds.
    public let energyMeasurementWindowSeconds: Double?
    /// Where the energy number came from: `battery-tick-window` (iOS, measured
    /// between 5%-step battery-level transitions — the only basis valid for
    /// J/tok on iOS 27's coarse gauge), `battery-1pct` (legacy pre-r4 rows,
    /// start/end delta) or `powermetrics` (Mac). `nil` when no energy was
    /// measured (including when no tick window completed — never fabricated).
    public let energySource: String?
    /// Number of complete 5% battery steps inside the tick window (≥1; J is
    /// exactly ticks × 5% × pack capacity).
    public let energyTickCount: Int?
    /// Streamed chunks counted inside the tick window — the denominator of
    /// `energyJoulesPerToken` on the tick basis.
    public let energyWindowTokenCount: Int?
    /// Level-transition timestamps, seconds relative to generation start —
    /// the raw evidence a tick-window cell is audited from.
    public let batteryTickTimestamps: [Double]?

    public init(
        coldRun: Bool,
        loadTimeSeconds: Double?,
        downloadTimeSeconds: Double?,
        firstTokenLatencyMS: Int,
        promptTokensPerSecond: Double,
        decodeTokensPerSecond: Double,
        promptTokensPerSecondWallClock: Double? = nil,
        decodeTokensPerSecondWallClock: Double? = nil,
        promptTokenCount: Int,
        generatedTokenCount: Int,
        streamedChunkCount: Int? = nil,
        totalGenerationTimeSeconds: Double,
        cancellationLatencyMS: Int?,
        stopReason: String,
        memoryBaselineMB: Double,
        memoryAfterLoadMB: Double?,
        memoryPeakDuringDecodeMB: Double,
        memoryAfterGenerationMB: Double,
        memoryPeakResidentMB: Double? = nil,
        memoryMedianMB: Double? = nil,
        memoryMedianResidentMB: Double? = nil,
        memoryFinalResidentMB: Double? = nil,
        contextTokensConfigured: Int? = nil,
        harnessStamp: String? = nil,
        initialThermalState: String,
        peakThermalState: String,
        finalThermalState: String,
        decodeRateRollingWindow: [Double],
        interTokenLatencyP50MS: Double?,
        interTokenLatencyP95MS: Double?,
        interTokenLatencyP99MS: Double?,
        energyJoules: Double?,
        batteryDeltaPercent: Float,
        energyJoulesPerToken: Double?,
        averagePackagePowerW: Double? = nil,
        energyMeasurementWindowSeconds: Double? = nil,
        energySource: String? = nil,
        energyTickCount: Int? = nil,
        energyWindowTokenCount: Int? = nil,
        batteryTickTimestamps: [Double]? = nil
    ) {
        self.coldRun = coldRun
        self.loadTimeSeconds = loadTimeSeconds
        self.downloadTimeSeconds = downloadTimeSeconds
        self.firstTokenLatencyMS = firstTokenLatencyMS
        self.promptTokensPerSecond = promptTokensPerSecond
        self.decodeTokensPerSecond = decodeTokensPerSecond
        self.promptTokensPerSecondWallClock = promptTokensPerSecondWallClock
        self.decodeTokensPerSecondWallClock = decodeTokensPerSecondWallClock
        self.promptTokenCount = promptTokenCount
        self.generatedTokenCount = generatedTokenCount
        self.streamedChunkCount = streamedChunkCount
        self.totalGenerationTimeSeconds = totalGenerationTimeSeconds
        self.cancellationLatencyMS = cancellationLatencyMS
        self.stopReason = stopReason
        self.memoryBaselineMB = memoryBaselineMB
        self.memoryAfterLoadMB = memoryAfterLoadMB
        self.memoryPeakDuringDecodeMB = memoryPeakDuringDecodeMB
        self.memoryAfterGenerationMB = memoryAfterGenerationMB
        self.memoryPeakResidentMB = memoryPeakResidentMB
        self.memoryMedianMB = memoryMedianMB
        self.memoryMedianResidentMB = memoryMedianResidentMB
        self.memoryFinalResidentMB = memoryFinalResidentMB
        self.contextTokensConfigured = contextTokensConfigured
        self.harnessStamp = harnessStamp
        self.initialThermalState = initialThermalState
        self.peakThermalState = peakThermalState
        self.finalThermalState = finalThermalState
        self.decodeRateRollingWindow = decodeRateRollingWindow
        self.interTokenLatencyP50MS = interTokenLatencyP50MS
        self.interTokenLatencyP95MS = interTokenLatencyP95MS
        self.interTokenLatencyP99MS = interTokenLatencyP99MS
        self.energyJoules = energyJoules
        self.batteryDeltaPercent = batteryDeltaPercent
        self.energyJoulesPerToken = energyJoulesPerToken
        self.averagePackagePowerW = averagePackagePowerW
        self.energyMeasurementWindowSeconds = energyMeasurementWindowSeconds
        self.energySource = energySource
        self.energyTickCount = energyTickCount
        self.energyWindowTokenCount = energyWindowTokenCount
        self.batteryTickTimestamps = batteryTickTimestamps
    }
}
