import Foundation
import CryptoKit
func sha(_ s: String) -> String { SHA256.hash(data: Data(s.utf8)).map { String(format: "%02x", $0) }.joined() }
let noref = LongContextTask(id: "long-context-2048-gen256-noref", targetTokens: 2048, maxTokens: 256,
                            forceLongOutput: true, blocks: 27, tail: LongContextTask.norefTail)
let ref = LongContextTask(id: "long-context-2048-gen256", targetTokens: 2048, maxTokens: 256,
                          forceLongOutput: true, blocks: 27)
print("noref", noref.prompt.utf8.count, sha(noref.prompt))
print("ref  ", ref.prompt.utf8.count, sha(ref.prompt))
