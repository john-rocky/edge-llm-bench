import SwiftUI

struct ResultSummaryView: View {
    let result: BenchmarkResult

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(result.task).font(.headline)
            HStack {
                Text("\(result.metrics.decodeTokensPerSecond, specifier: "%.1f") tok/s")
                Text("•")
                Text("TTFT \(result.metrics.firstTokenLatencyMS) ms")
                Text("•")
                Text("\(Int(result.metrics.memoryPeakDuringDecodeMB)) MB peak")
            }
            .font(.caption)
            .foregroundStyle(.secondary)
        }
    }
}

struct ResultDetailView: View {
    let result: BenchmarkResult
    @State private var showingExportSheet = false

    var body: some View {
        Form {
            Section("Identity") {
                row("Runtime", result.runtime)
                row("Model", result.model.displayName)
                row("Task", result.task)
                row("Cold run", result.metrics.coldRun ? "yes" : "no")
                row("Stop reason", result.metrics.stopReason)
            }

            Section("Performance") {
                if let load = result.metrics.loadTimeSeconds {
                    row("Model load", String(format: "%.2f s", load))
                }
                row("TTFT", "\(result.metrics.firstTokenLatencyMS) ms")
                row("Prefill tok/s", String(format: "%.1f", result.metrics.promptTokensPerSecond))
                row("Decode tok/s", String(format: "%.1f", result.metrics.decodeTokensPerSecond))
                row("Prompt tokens", "\(result.metrics.promptTokenCount)")
                row("Generated tokens", "\(result.metrics.generatedTokenCount)")
                row("Total time", String(format: "%.2f s", result.metrics.totalGenerationTimeSeconds))
            }

            Section("Memory (MB)") {
                row("Baseline", String(format: "%.0f", result.metrics.memoryBaselineMB))
                if let load = result.metrics.memoryAfterLoadMB {
                    row("After load", String(format: "%.0f", load))
                }
                row("Peak (decode)", String(format: "%.0f", result.metrics.memoryPeakDuringDecodeMB))
                row("After generation", String(format: "%.0f", result.metrics.memoryAfterGenerationMB))
            }

            Section("Thermal") {
                row("Initial", result.metrics.initialThermalState)
                row("Peak", result.metrics.peakThermalState)
                row("Final", result.metrics.finalThermalState)
            }

            Section("Energy") {
                if let j = result.metrics.energyJoules {
                    row("Total", String(format: "%.1f J", j))
                    row("Battery delta", String(format: "%.1f%%", result.metrics.batteryDeltaPercent))
                    if let jpt = result.metrics.energyJoulesPerToken {
                        row("Per token", String(format: "%.3f J", jpt))
                    }
                } else {
                    Text("Run too short for a 1% battery step. Try the sustained-generation task or a larger model.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            if !result.metrics.decodeRateRollingWindow.isEmpty {
                Section("Decode rate over time") {
                    DecodeRateChart(samples: result.metrics.decodeRateRollingWindow)
                        .frame(height: 140)
                }
            }

            Section("Device") {
                row("Model", result.device.modelIdentifier)
                row("OS", "\(result.device.systemName) \(result.device.systemVersion)")
                row("RAM", "\(result.device.physicalMemoryMB) MB")
                row("Build", result.device.buildConfiguration)
                row("Battery", "\(result.device.batteryState) (\(Int(result.device.batteryLevel * 100))%)")
                row("Low power mode", result.device.isLowPowerModeEnabled ? "on" : "off")
            }

            Section("Output sample") {
                Text(result.outputSample)
                    .font(.system(.callout, design: .monospaced))
            }
        }
        .navigationTitle(result.task)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button { showingExportSheet = true } label: {
                    Image(systemName: "square.and.arrow.up")
                }
            }
        }
        .sheet(isPresented: $showingExportSheet) {
            if let data = try? jsonData(for: result) {
                ShareSheet(items: [data])
            }
        }
    }

    private func row(_ label: String, _ value: String) -> some View {
        HStack {
            Text(label).foregroundStyle(.secondary)
            Spacer()
            Text(value).font(.system(.body, design: .monospaced))
        }
    }

    private func jsonData(for result: BenchmarkResult) throws -> Data {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        encoder.dateEncodingStrategy = .iso8601
        return try encoder.encode(result)
    }
}

struct DecodeRateChart: View {
    let samples: [Double]

    var body: some View {
        GeometryReader { geo in
            let maxRate = (samples.max() ?? 1).rounded(.up)
            let stepX = samples.count > 1 ? geo.size.width / CGFloat(samples.count - 1) : 0

            ZStack {
                Path { path in
                    for (index, value) in samples.enumerated() {
                        let x = CGFloat(index) * stepX
                        let y = geo.size.height - CGFloat(value / max(maxRate, 0.001)) * geo.size.height
                        if index == 0 {
                            path.move(to: CGPoint(x: x, y: y))
                        } else {
                            path.addLine(to: CGPoint(x: x, y: y))
                        }
                    }
                }
                .stroke(Color.accentColor, lineWidth: 2)

                VStack {
                    HStack {
                        Spacer()
                        Text(String(format: "%.0f tok/s", maxRate))
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                }
            }
        }
    }
}

#if canImport(UIKit)
import UIKit

struct ShareSheet: UIViewControllerRepresentable {
    let items: [Any]
    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }
    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}
#endif
