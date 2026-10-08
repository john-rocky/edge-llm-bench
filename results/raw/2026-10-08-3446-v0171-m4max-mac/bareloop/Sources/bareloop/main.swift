// One engine (GPU, maxNumTokens 2048), then:
//   loop A: create a Conversation and drop it, no generation (default 50 cycles)
//   loop B: create, one streamed turn ("Reply with one word."), drop (default 30 cycles)
// After every cycle: phys_footprint (TASK_VM_INFO, MB) as `cycle,kind,footprintMB` on stdout.
// Same footprint arithmetic as the yardstick's MemoryMonitor.footprintMB().
import Darwin
import Foundation
import LiteRTLM

func footprintMB() -> Double {
  var info = task_vm_info_data_t()
  var count = mach_msg_type_number_t(
    MemoryLayout<task_vm_info_data_t>.size / MemoryLayout<integer_t>.size)
  let result = withUnsafeMutablePointer(to: &info) { ptr -> kern_return_t in
    ptr.withMemoryRebound(to: integer_t.self, capacity: Int(count)) { rebound in
      task_info(mach_task_self_, task_flavor_t(TASK_VM_INFO), rebound, &count)
    }
  }
  guard result == KERN_SUCCESS else { return 0 }
  return Double(info.phys_footprint) / (1024 * 1024)
}

func emit(_ cycle: Int, _ kind: String) {
  print("\(cycle),\(kind),\(String(format: "%.3f", footprintMB()))")
  fflush(stdout)
}

func note(_ s: String) {
  FileHandle.standardError.write(Data("bareloop: \(s)\n".utf8))
}

let args = CommandLine.arguments
guard args.count >= 2 else {
  note("usage: bareloop <model.litertlm> [bareCycles=50] [genCycles=30]")
  exit(2)
}
let modelPath = args[1]
let bareCycles = args.count > 2 ? (Int(args[2]) ?? 50) : 50
let genCycles = args.count > 3 ? (Int(args[3]) ?? 30) : 30

print("cycle,kind,footprintMB")
emit(0, "start")
let config = try EngineConfig(
  modelPath: modelPath, backend: .gpu, maxNumTokens: 2048, cacheDir: NSTemporaryDirectory())
let engine = Engine(engineConfig: config)
try await engine.initialize()
emit(0, "engine")
// Same sampler as the yardstick endurance loop (topK 40, topP 0.9, temperature 0.7).
let sampler = try SamplerConfig(topK: 40, topP: 0.9, temperature: 0.7)

// Loop A: the Conversation goes out of scope at the end of each `do`, so its deinit
// (litert_lm_conversation_delete) runs before the sample.
for i in 1...bareCycles {
  do {
    let conversation = try await engine.createConversation(
      with: ConversationConfig(samplerConfig: sampler))
    withExtendedLifetime(conversation) {}
  }
  emit(i, "bare")
}
try await Task.sleep(nanoseconds: 5_000_000_000)
emit(bareCycles, "bare-settle5s")

// Loop B: one streamed turn per conversation, capped at 256 output tokens like the yardstick.
var lastReply = ""
var tokensTotal = 0
for i in 1...genCycles {
  do {
    let conversation = try await engine.createConversation(
      with: ConversationConfig(samplerConfig: sampler))
    var text = ""
    for try await chunk in conversation.sendMessageStream(
      Message("Reply with one word."), maxOutputTokens: 256)
    {
      text += chunk.toString
    }
    tokensTotal += text.count
    lastReply = text
  }
  emit(i, "gen")
}
try await Task.sleep(nanoseconds: 5_000_000_000)
emit(genCycles, "gen-settle5s")
note("last reply: \(lastReply.prefix(80).replacingOccurrences(of: "\n", with: " ")) (chars over loop B: \(tokensTotal))")
