import Foundation

/// Persists `BenchmarkResult` objects as JSON files under
/// `Documents/results/` so they survive app restarts and can be exported.
public actor ResultStore {
    public static let shared = ResultStore()

    private let directory: URL
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder

    private init() {
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
        directory = docs.appendingPathComponent("results", isDirectory: true)
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)

        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        encoder.dateEncodingStrategy = .iso8601
        self.encoder = encoder

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        self.decoder = decoder
    }

    public func save(_ result: BenchmarkResult) throws -> URL {
        let url = directory.appendingPathComponent("\(filename(for: result)).json")
        let data = try encoder.encode(result)
        try data.write(to: url, options: [.atomic])
        return url
    }

    public func load() throws -> [BenchmarkResult] {
        let urls = (try? FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil)) ?? []
        return urls
            .filter { $0.pathExtension == "json" }
            .compactMap { url in
                (try? Data(contentsOf: url)).flatMap { try? decoder.decode(BenchmarkResult.self, from: $0) }
            }
            .sorted { $0.timestamp > $1.timestamp }
    }

    public func clear() throws {
        let urls = (try? FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil)) ?? []
        for url in urls where url.pathExtension == "json" {
            try? FileManager.default.removeItem(at: url)
        }
    }

    private func filename(for result: BenchmarkResult) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withDashSeparatorInDate]
        let stamp = formatter.string(from: result.timestamp)
            .replacingOccurrences(of: ":", with: "-")
        return "\(result.runtime)_\(result.model.id.replacingOccurrences(of: "/", with: "_"))_\(result.task)_\(stamp)"
    }
}
