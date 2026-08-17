import Foundation

/// Samples `ProcessInfo.thermalState` over a run and returns the worst (peak) value seen.
///
/// `thermalState` is the only thermal signal available to third-party apps on iOS.
/// It is a coarse signal but is the same one that would throttle a shipping app.
public actor ThermalSampler {
    private(set) var initialState: ProcessInfo.ThermalState
    private(set) var peakState: ProcessInfo.ThermalState
    private(set) var finalState: ProcessInfo.ThermalState
    private var task: Task<Void, Never>?

    public init() {
        let state = ProcessInfo.processInfo.thermalState
        self.initialState = state
        self.peakState = state
        self.finalState = state
    }

    public func start(intervalMS: Int = 1000) {
        stop()
        let state = ProcessInfo.processInfo.thermalState
        initialState = state
        peakState = state
        finalState = state

        task = Task { [weak self] in
            while !Task.isCancelled {
                let current = ProcessInfo.processInfo.thermalState
                await self?.bump(current)
                try? await Task.sleep(nanoseconds: UInt64(intervalMS) * 1_000_000)
            }
        }
    }

    public func stop() {
        task?.cancel()
        task = nil
        finalState = ProcessInfo.processInfo.thermalState
    }

    private func bump(_ state: ProcessInfo.ThermalState) {
        if state.severity > peakState.severity {
            peakState = state
        }
        finalState = state
    }
}

public enum ThermalMonitor {
    public static func describe(_ state: ProcessInfo.ThermalState) -> String {
        switch state {
        case .nominal: return "nominal"
        case .fair: return "fair"
        case .serious: return "serious"
        case .critical: return "critical"
        @unknown default: return "unknown"
        }
    }
}

private extension ProcessInfo.ThermalState {
    var severity: Int {
        switch self {
        case .nominal: return 0
        case .fair: return 1
        case .serious: return 2
        case .critical: return 3
        @unknown default: return 0
        }
    }
}
