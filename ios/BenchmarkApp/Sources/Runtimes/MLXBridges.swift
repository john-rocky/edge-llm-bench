import Foundation
import MLXLMCommon
import HuggingFace
import Tokenizers

/// Bridges `HuggingFace.HubClient` to `MLXLMCommon.Downloader`.
///
/// Replaces the `#hubDownloader(...)` macro from MLXHuggingFace, which is
/// brittle against newer swift-transformers (the macro's expansion
/// references `Tokenizers.TokenizerError.missingChatTemplate` which was
/// removed upstream).
public struct HubDownloaderBridge: MLXLMCommon.Downloader {
    private let client: HuggingFace.HubClient

    public init(client: HuggingFace.HubClient) {
        self.client = client
    }

    public func download(
        id: String,
        revision: String?,
        matching patterns: [String],
        useLatest: Bool,
        progressHandler: @Sendable @escaping (Foundation.Progress) -> Void
    ) async throws -> URL {
        print("[HubBridge] download id=\(id) rev=\(revision ?? "main") patterns=\(patterns)")
        guard let repoID = HuggingFace.Repo.ID(rawValue: id) else {
            print("[HubBridge] invalid repo id")
            throw NSError(domain: "MLXBridges", code: -1,
                          userInfo: [NSLocalizedDescriptionKey: "Invalid HF repo id: \(id)"])
        }
        do {
            let url = try await client.downloadSnapshot(
                of: repoID,
                revision: revision ?? "main",
                matching: patterns,
                progressHandler: { @MainActor progress in
                    progressHandler(progress)
                }
            )
            print("[HubBridge] downloaded to \(url.path)")
            return url
        } catch {
            print("[HubBridge] download FAILED: \(error.localizedDescription)")
            throw error
        }
    }
}

/// Bridges `Tokenizers.AutoTokenizer` to `MLXLMCommon.TokenizerLoader`.
///
/// Replaces the `#huggingFaceTokenizerLoader()` macro for the same reason
/// as `HubDownloaderBridge`. Wraps the HF tokenizer in an MLXLMCommon
/// `Tokenizer` adapter that maps the small subset of methods MLX needs.
public struct HFTokenizerLoaderBridge: MLXLMCommon.TokenizerLoader {
    public init() {}

    public func load(from directory: URL) async throws -> any MLXLMCommon.Tokenizer {
        let upstream = try await AutoTokenizer.from(modelFolder: directory)
        return TokenizerBridge(upstream: upstream)
    }
}

private struct TokenizerBridge: MLXLMCommon.Tokenizer, @unchecked Sendable {
    private let upstream: any Tokenizers.Tokenizer

    init(upstream: any Tokenizers.Tokenizer) {
        self.upstream = upstream
    }

    func encode(text: String, addSpecialTokens: Bool) -> [Int] {
        upstream.encode(text: text, addSpecialTokens: addSpecialTokens)
    }

    func decode(tokenIds: [Int], skipSpecialTokens: Bool) -> String {
        upstream.decode(tokens: tokenIds, skipSpecialTokens: skipSpecialTokens)
    }

    func convertTokenToId(_ token: String) -> Int? {
        upstream.convertTokenToId(token)
    }

    func convertIdToToken(_ id: Int) -> String? {
        upstream.convertIdToToken(id)
    }

    var bosToken: String? { upstream.bosToken }
    var eosToken: String? { upstream.eosToken }
    var unknownToken: String? { upstream.unknownToken }

    func applyChatTemplate(
        messages: [[String: any Sendable]],
        tools: [[String: any Sendable]]?,
        additionalContext: [String: any Sendable]?
    ) throws -> [Int] {
        try upstream.applyChatTemplate(
            messages: messages, tools: tools, additionalContext: additionalContext
        )
    }
}
