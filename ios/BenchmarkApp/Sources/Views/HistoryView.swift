import SwiftUI
#if canImport(UIKit)
import UIKit
#endif

struct HistoryView: View {
    @EnvironmentObject private var session: AppSession
    @State private var exportURL: URL?
    @State private var showingExport = false

    var body: some View {
        List {
            if session.history.isEmpty {
                ContentUnavailableView(
                    "No runs yet",
                    systemImage: "tray",
                    description: Text("Tap Run on the Run tab to record your first benchmark.")
                )
            } else {
                ForEach(session.history) { result in
                    NavigationLink(destination: ResultDetailView(result: result)) {
                        VStack(alignment: .leading, spacing: 4) {
                            HStack {
                                Text(result.runtime).font(.headline)
                                Spacer()
                                Text(result.task).font(.caption).foregroundStyle(.secondary)
                            }
                            Text(result.model.displayName)
                                .font(.subheadline)
                            HStack {
                                Label(String(format: "%.1f tok/s", result.metrics.decodeTokensPerSecond), systemImage: "speedometer")
                                Label("\(result.metrics.firstTokenLatencyMS) ms", systemImage: "timer")
                                Label("\(Int(result.metrics.memoryPeakDuringDecodeMB)) MB", systemImage: "memorychip")
                            }
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        }
                    }
                }
            }
        }
        .navigationTitle("History")
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Menu {
                    Button {
                        if let url = try? exportAllJSONL() {
                            exportURL = url
                            showingExport = true
                        }
                    } label: {
                        Label("Export all (JSONL)", systemImage: "square.and.arrow.up.on.square")
                    }
                    .disabled(session.history.isEmpty)

                    Button(role: .destructive) {
                        Task {
                            try? await ResultStore.shared.clear()
                            await session.reloadHistory()
                        }
                    } label: {
                        Label("Clear all", systemImage: "trash")
                    }
                } label: {
                    Image(systemName: "ellipsis.circle")
                }
            }
        }
        .sheet(isPresented: $showingExport) {
            #if canImport(UIKit)
            if let url = exportURL {
                ShareSheet(items: [url])
            }
            #endif
        }
        .task {
            await session.reloadHistory()
        }
    }

    /// Writes every history row to a single newline-delimited JSON file
    /// in the temp directory and returns its URL. One file → one AirDrop
    /// tap → `cp` into `results/raw/` on the Mac.
    private func exportAllJSONL() throws -> URL {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        encoder.dateEncodingStrategy = .iso8601

        var lines: [String] = []
        lines.reserveCapacity(session.history.count)
        for result in session.history {
            let data = try encoder.encode(result)
            if let line = String(data: data, encoding: .utf8) {
                lines.append(line)
            }
        }

        let device = result_device_label()
        let stamp = ISO8601DateFormatter().string(from: Date())
            .replacingOccurrences(of: ":", with: "-")
        let filename = "yardstick-\(device)-export-\(stamp).jsonl"
        let url = FileManager.default.temporaryDirectory.appendingPathComponent(filename)
        try lines.joined(separator: "\n").write(to: url, atomically: true, encoding: .utf8)
        return url
    }

    /// Snake-case device label that matches the convention used in
    /// `scripts/render_results.py::DEVICE_DISPLAY`. The renderer reads
    /// the first dash-separated chunk of each JSONL filename as the
    /// device key.
    private func result_device_label() -> String {
        let model = session.history.first?.device.modelIdentifier ?? "device"
        return model
            .lowercased()
            .replacingOccurrences(of: ",", with: "-")
            .replacingOccurrences(of: "_", with: "-")
    }
}

