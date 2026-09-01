// edge-llm-bench endurance driver — the Android counterpart of the Mac
// yardstick's `MediaPipeRuntime.enduranceChat` turn loop
// (methodology/endurance.md). This file is HARNESS code, not upstream code:
// it is compiled inside a pristine LiteRT-LM checkout at the pinned tag by
// android/scripts/build_litert_lm_endurance.sh (the same acquisition reality
// as litert_lm_main — upstream ships no Android binary), and both the binary
// sha256 and this source's sha256 are recorded in android/engine-pins.json.
//
// Why a separate binary exists at all: the stock CLIs cannot run the
// protocol. litert_lm_main sends exactly one message per process;
// litert_lm_advanced_main's --multi_turns reads stdin interactively and
// exits on the first engine error, so it can neither script a session nor
// roll the conversation over at the context budget. The protocol needs one
// engine process, one accumulating conversation, a native per-turn cap,
// per-turn engine counters, and rollover-instead-of-widening — the same
// Conversation-level surface the Mac Swift harness drives.
//
// Output contract (parsed by android/bench/endurance_cell.py):
//   ENDURANCE_LOAD {json}      once, after engine creation
//   ENDURANCE_TURN {json}      one line per turn, flushed AS THE TURN
//                              COMPLETES (crash-safety: a death at turn 37
//                              leaves turns 1..36 on the host's sidecar)
//   ENDURANCE_SESSION {json}   once, at session end
// Exit code 0 only for status=completed (failed-runs-stay: the host keeps
// the record and partial series either way).
//
// Per-turn memory is /proc/self/status VmRSS — the same basis run_cell.py's
// on-device sampler reads for every other Android cell, read here at the
// turn boundary so the series is exactly turn-aligned. phys_footprint has no
// Android equivalent and is never fabricated (methodology/android.md).

#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <memory>
#include <sstream>
#include <string>
#include <thread>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

#include "absl/base/log_severity.h"  // from @com_google_absl
#include "absl/flags/flag.h"  // from @com_google_absl
#include "absl/flags/parse.h"  // from @com_google_absl
#include "absl/log/absl_log.h"  // from @com_google_absl
#include "absl/log/globals.h"  // from @com_google_absl
#include "absl/status/status.h"  // from @com_google_absl
#include "absl/status/statusor.h"  // from @com_google_absl
#include "absl/strings/match.h"  // from @com_google_absl
#include "absl/synchronization/mutex.h"  // from @com_google_absl
#include "absl/time/clock.h"  // from @com_google_absl
#include "absl/time/time.h"  // from @com_google_absl
#include "nlohmann/json.hpp"  // from @nlohmann_json
#include "runtime/conversation/conversation.h"
#include "runtime/conversation/io_types.h"
#include "runtime/engine/engine.h"
#include "runtime/engine/engine_factory.h"
#include "runtime/engine/engine_settings.h"
#include "runtime/engine/io_types.h"
#include "runtime/executor/executor_settings_base.h"
#include "runtime/executor/llm_executor_settings.h"
#include "runtime/proto/sampler_params.pb.h"

ABSL_FLAG(std::string, backend, "gpu", "Executor backend (cpu, gpu).");
ABSL_FLAG(std::string, model_path, "", "Model path.");
ABSL_FLAG(std::string, prompts_file, "",
          "Turn script: one prompt per line (prompts/text/endurance-chat"
          ".turns.txt; the 12-prompt cycle is part of the task).");
ABSL_FLAG(int, minutes, 30, "Session wall-clock window from the start of turn 1.");
ABSL_FLAG(int, turn_cap, 256,
          "Per-turn output token cap (native maxOutputTokens). 256 is the "
          "protocol; anything else is a diagnostic run.");
ABSL_FLAG(int, context_tokens, 4096,
          "Conversation KV budget (engine maxNumTokens). Outgrowing it "
          "rolls the conversation over — recorded, never silently widened.");
ABSL_FLAG(int, stall_seconds, 180, "No stream event for this long => hang.");
ABSL_FLAG(int, turn_seconds, 600, "Absolute per-turn bound => hang.");

namespace {

using ::litert::lm::Backend;
using ::litert::lm::Conversation;
using ::litert::lm::ConversationConfig;
using ::litert::lm::EngineSettings;
using ::litert::lm::Message;
using ::litert::lm::ModelAssets;
using ::litert::lm::OptionalArgs;
using ::nlohmann::json;
using ::nlohmann::ordered_json;

double NowSeconds() { return absl::ToUnixMicros(absl::Now()) / 1e6; }

// /proc/self/status VmRSS / VmHWM in MB (kB fields). -1 when unreadable.
double ProcStatusMB(const std::string& key) {
  std::ifstream f("/proc/self/status");
  std::string line;
  while (std::getline(f, line)) {
    if (line.rfind(key, 0) == 0) {
      std::istringstream is(line.substr(key.size() + 1));
      long kb = -1;
      is >> kb;
      return kb < 0 ? -1.0 : kb / 1024.0;
    }
  }
  return -1.0;
}

// litertlm-convert verify_quality.degenerate() rules, ported the same way
// EnduranceSession.swift ports them (looping 5-grams >=3, unique-word ratio
// < 0.30, character collapse, special-token spam). Byte-based where Swift is
// character-based — equivalent on the ASCII-dominated outputs this checks.
bool IsDegenerate(const std::string& text) {
  std::vector<std::string> words;
  std::istringstream is(text);
  std::string w;
  while (is >> w) words.push_back(w);
  if (words.size() >= 10) {
    std::unordered_map<std::string, int> grams;
    int peak = 0;
    for (size_t i = 0; i + 5 <= words.size(); ++i) {
      std::string g = words[i];
      for (size_t j = i + 1; j < i + 5; ++j) g += " " + words[j];
      peak = std::max(peak, ++grams[g]);
    }
    if (peak >= 3) return true;
    std::unordered_set<std::string> uniq(words.begin(), words.end());
    if (static_cast<double>(uniq.size()) / words.size() < 0.30) return true;
  }
  if (text.size() >= 40 &&
      std::unordered_set<char>(text.begin(), text.end()).size() < 15)
    return true;
  auto count = [&text](const std::string& needle) {
    int n = 0;
    for (size_t p = text.find(needle); p != std::string::npos;
         p = text.find(needle, p + needle.size()))
      ++n;
    return n;
  };
  if (count("<|") >= 5) return true;
  if (count("<pad>") >= 5) return true;
  return false;
}

// Streaming state shared between the SendMessageAsync callback, the watchdog
// thread, and the turn loop.
struct TurnStream {
  absl::Mutex mu;
  double last_event = 0;
  double first_chunk_at = -1;
  double last_chunk_at = -1;
  int chunk_count = 0;
  std::string collected;
  bool done = false;
  std::string error;
  std::string fired;  // watchdog reason; read by the turn loop after join()
};

// Extract this chunk's incremental text: plain content pieces plus any
// channel deltas (thinking models stream their thought channel; both count
// for degeneracy and the wall-clock chunk tally, matching the Mac loop).
std::string ChunkText(const Message& m) {
  std::string text;
  if (m.contains("content") && m["content"].is_array()) {
    for (const auto& c : m["content"]) {
      if (c.is_object() && c.contains("text") && c["text"].is_string())
        text += c["text"].get<std::string>();
    }
  }
  if (m.contains("channels") && m["channels"].is_object()) {
    for (const auto& [k, v] : m["channels"].items()) {
      if (v.is_string()) text += v.get<std::string>();
    }
  }
  return text;
}

void EmitLine(const std::string& tag, const ordered_json& obj) {
  std::cout << tag << " " << obj.dump() << std::endl;  // endl flushes
}

int MainHelper() {
  absl::SetMinLogLevel(absl::LogSeverityAtLeast::kError);
  absl::SetStderrThreshold(absl::LogSeverityAtLeast::kError);

  const std::string model_path = absl::GetFlag(FLAGS_model_path);
  const std::string prompts_file = absl::GetFlag(FLAGS_prompts_file);
  const int minutes = absl::GetFlag(FLAGS_minutes);
  const int cap = absl::GetFlag(FLAGS_turn_cap);
  const int context_tokens = absl::GetFlag(FLAGS_context_tokens);
  const double stall_s = absl::GetFlag(FLAGS_stall_seconds);
  const double turn_s = absl::GetFlag(FLAGS_turn_seconds);

  std::vector<std::string> prompts;
  {
    std::ifstream f(prompts_file);
    std::string line;
    while (std::getline(f, line))
      if (!line.empty()) prompts.push_back(line);
  }
  if (model_path.empty() || prompts.empty()) {
    std::cerr << "need --model_path and a non-empty --prompts_file\n";
    return 2;
  }

  // _Exit, not return: engine teardown can wedge for minutes (the known
  // litert teardown hang the runners gtimeout around); every line above was
  // flushed by std::endl, and all measurement data lives host-side.
  auto fail = [](const std::string& stage, const absl::Status& s) {
    EmitLine("ENDURANCE_SESSION",
             ordered_json{{"status", "crash"},
                          {"failureDetail", stage + ": " + s.ToString()}});
    std::_Exit(1);
    return 1;  // unreached
  };

  // ---- engine (one process, one model load; benchmark counters on) -------
  const double load_start = NowSeconds();
  auto assets = ModelAssets::Create(model_path);
  if (!assets.ok()) return fail("model-assets", assets.status());
  auto backend = litert::lm::GetBackendFromString(absl::GetFlag(FLAGS_backend));
  if (!backend.ok()) return fail("backend", backend.status());
  auto engine_settings = EngineSettings::CreateDefault(*std::move(assets), *backend);
  if (!engine_settings.ok()) return fail("engine-settings", engine_settings.status());
  engine_settings->GetMutableBenchmarkParams() = litert::lm::proto::BenchmarkParams();
  engine_settings->GetMutableMainExecutorSettings().SetMaxNumTokens(context_tokens);
  auto engine = litert::lm::EngineFactory::CreateDefault(*std::move(engine_settings));
  if (!engine.ok()) return fail("engine-create", engine.status());
  const double load_seconds = NowSeconds() - load_start;

  // Task C's chat sampling (temperature 0.7 / topP 0.9 / topK 40) — the
  // protocol's configuration, driver-set. The prompt-task CLI cells run
  // engine-default because litert_lm_main exposes no sampler flags; this
  // driver owns its SessionConfig, so the endurance lane does not inherit
  // that disclosed deviation.
  auto make_conversation = [&]() -> absl::StatusOr<std::unique_ptr<Conversation>> {
    auto session_config = litert::lm::SessionConfig::CreateDefault();
    auto& sp = session_config.GetMutableSamplerParams();
    sp.set_type(litert::lm::proto::SamplerParameters::TOP_P);
    sp.set_k(40);
    sp.set_p(0.9f);
    sp.set_temperature(0.7f);
    auto config = ConversationConfig::Builder()
                      .SetSessionConfig(session_config)
                      .Build(**engine);
    if (!config.ok()) return config.status();
    return Conversation::Create(**engine, *config);
  };

  auto conversation_or = make_conversation();
  if (!conversation_or.ok()) return fail("conversation-create", conversation_or.status());
  std::unique_ptr<Conversation> conversation = *std::move(conversation_or);

  EmitLine("ENDURANCE_LOAD",
           ordered_json{{"loadSeconds", load_seconds},
                        {"contextTokens", context_tokens},
                        {"turnCap", cap},
                        {"plannedMinutes", minutes},
                        {"residentAfterLoadMB", ProcStatusMB("VmRSS")}});

  const double duration = minutes * 60.0;
  const double session_start = NowSeconds();
  int turn_index = 0;
  int empty_streak = 0;
  std::string session_status = "completed";
  std::string failure_detail;

  while (NowSeconds() - session_start < duration) {
    ++turn_index;
    const int prompt_index = (turn_index - 1) % static_cast<int>(prompts.size());
    const std::string& prompt_text = prompts[prompt_index];

    // Rollover check: leave room for this prompt + the output cap (same
    // arithmetic as the Mac loop: chars/3 + 16 + cap + 32).
    bool rollover = false;
    std::string rollover_reason;
    auto kv_or = conversation->GetTokenCount();
    int kv_now = kv_or.ok() ? *kv_or : 0;
    const int reserve = static_cast<int>(prompt_text.size()) / 3 + 16 + cap + 32;
    if (kv_now + reserve > context_tokens) {
      auto fresh = make_conversation();
      if (!fresh.ok()) return fail("rollover-create", fresh.status());
      conversation = *std::move(fresh);
      rollover = true;
      rollover_reason = "budget";
    }

    double turn_start = NowSeconds();
    TurnStream stream;
    std::string turn_error;
    std::string watchdog_fired;
    int attempt = 0;

    while (true) {  // kv-wall retry loop (at most 2 attempts)
      ++attempt;
      turn_start = NowSeconds();
      {
        absl::MutexLock l(&stream.mu);
        stream.last_event = turn_start;
        stream.first_chunk_at = stream.last_chunk_at = -1;
        stream.chunk_count = 0;
        stream.collected.clear();
        stream.done = false;
        stream.error.clear();
        stream.fired.clear();
      }
      turn_error.clear();

      // Watchdog: no stream event for stall_s, or the turn exceeding
      // turn_s, cancels the conversation — surfaced as `hang`, never
      // retried. CancelProcess poisons the conversation (upstream note),
      // which is fine: a hang ends the session. Cancel happens OUTSIDE the
      // stream lock — the callback takes the same lock.
      std::thread watchdog([&]() {
        while (true) {
          absl::SleepFor(absl::Seconds(5));
          std::string reason;
          {
            absl::MutexLock l(&stream.mu);
            if (stream.done) return;
            const double now = NowSeconds();
            if (now - stream.last_event > stall_s) {
              reason = "stall>" + std::to_string(static_cast<int>(stall_s)) + "s";
            } else if (now - turn_start > turn_s) {
              reason = "turn>" + std::to_string(static_cast<int>(turn_s)) + "s";
            } else {
              continue;
            }
            stream.fired = reason;
          }
          conversation->CancelProcess();
          return;
        }
      });

      Message user_message = ordered_json{
          {"role", "user"},
          {"content", ordered_json::array({ordered_json{{"type", "text"},
                                                        {"text", prompt_text}}})}};
      OptionalArgs args;
      args.max_output_tokens = cap;
      absl::Status sent = conversation->SendMessageAsync(
          user_message,
          [&stream](absl::StatusOr<Message> message) {
            absl::MutexLock l(&stream.mu);
            stream.last_event = NowSeconds();
            if (!message.ok()) {
              stream.error = message.status().ToString();
              stream.done = true;
              return;
            }
            if (message->is_null()) {  // end of stream
              stream.done = true;
              return;
            }
            const std::string text = ChunkText(*message);
            if (text.empty()) return;
            const double now = NowSeconds();
            if (stream.first_chunk_at < 0) stream.first_chunk_at = now;
            stream.last_chunk_at = now;
            ++stream.chunk_count;
            if (stream.collected.size() < 4000) stream.collected += text;
          },
          std::move(args));
      if (sent.ok()) {
        // Backstop bound beyond the watchdog's turn cap; the callback's
        // done flag is the real completion signal. Then wait (bounded) for
        // the terminal callback in case WaitUntilDone returned before the
        // null/error message was delivered.
        (*engine)->WaitUntilDone(absl::Seconds(turn_s + 60)).IgnoreError();
        absl::MutexLock l(&stream.mu);
        stream.mu.AwaitWithTimeout(absl::Condition(&stream.done), absl::Seconds(10));
      } else {
        turn_error = sent.ToString();
      }
      {
        absl::MutexLock l(&stream.mu);
        stream.done = true;  // stop the watchdog
        if (turn_error.empty() && !stream.error.empty()) turn_error = stream.error;
      }
      watchdog.join();
      watchdog_fired = stream.fired;  // post-join read; no race
      if (!watchdog_fired.empty()) break;  // hang; never retried

      // KV-wall rollover: the engine refuses the turn outright when the
      // remaining state entries are smaller than its smallest prefill
      // signature — the bundle's REAL ceiling, which can sit below the
      // requested budget (gemma-4-E2B: 2048 under a 4096 request,
      // 2026-09-01 Mac baseline; upstream #3444). A chat app rolls over
      // here; so does the harness — once, on a fresh conversation.
      int chunks_now;
      {
        absl::MutexLock l(&stream.mu);
        chunks_now = stream.chunk_count;
      }
      if (!turn_error.empty() && chunks_now == 0 && attempt == 1 &&
          absl::StrContains(turn_error, "state entries")) {
        auto fresh = make_conversation();
        if (!fresh.ok()) return fail("kv-wall-rollover-create", fresh.status());
        conversation = *std::move(fresh);
        rollover = true;
        rollover_reason = "kv-wall@" + std::to_string(kv_now) + ": " +
                          turn_error.substr(0, 120);
        continue;
      }
      break;
    }

    double first_chunk_at, last_chunk_at, started;
    int chunk_count;
    std::string collected;
    {
      absl::MutexLock l(&stream.mu);
      first_chunk_at = stream.first_chunk_at;
      last_chunk_at = stream.last_chunk_at;
      chunk_count = stream.chunk_count;
      collected = stream.collected;
    }
    started = turn_start;
    const double turn_end = last_chunk_at > 0 ? last_chunk_at : NowSeconds();

    // The engine's last-turn counters describe the last COMPLETED turn; a
    // turn that died before streaming anything must not inherit the
    // previous turn's numbers (the Mac baseline's crashed turn 2 carried
    // turn 1's 256 tokens until this guard).
    ordered_json turn{{"turn", turn_index},
                      {"promptIndex", prompt_index},
                      {"startedAtSeconds", started - session_start},
                      {"rollover", rollover}};
    if (!rollover_reason.empty()) turn["rolloverReason"] = rollover_reason;
    long decode_tokens = -1;
    if (chunk_count > 0) {
      auto bench = conversation->GetBenchmarkInfo();
      if (bench.ok()) {
        const int p = static_cast<int>(bench->GetTotalPrefillTurns()) - 1;
        const int d = static_cast<int>(bench->GetTotalDecodeTurns()) - 1;
        if (p >= 0) {
          auto pt = bench->GetPrefillTurn(p);
          if (pt.ok()) {
            turn["prefillTokens"] = pt->num_tokens;
            turn["prefillTokensPerSecond"] = bench->GetPrefillTokensPerSec(p);
          }
        }
        if (d >= 0) {
          auto dt = bench->GetDecodeTurn(d);
          if (dt.ok()) {
            decode_tokens = static_cast<long>(dt->num_tokens);
            turn["decodeTokens"] = dt->num_tokens;
            turn["decodeTokensPerSecond"] = bench->GetDecodeTokensPerSec(d);
          }
        }
      }
    }
    if (first_chunk_at > 0) turn["ttftMS"] = (first_chunk_at - started) * 1000.0;
    turn["wallSeconds"] = turn_end - started;
    turn["chunkCount"] = chunk_count;
    if (chunk_count >= 2 && last_chunk_at > first_chunk_at)
      turn["decodeTokensPerSecondWallClock"] =
          (chunk_count - 1) / (last_chunk_at - first_chunk_at);
    auto kv_after = conversation->GetTokenCount();
    if (kv_after.ok()) turn["kvTokensAfterTurn"] = *kv_after;
    turn["residentAfterTurnMB"] = ProcStatusMB("VmRSS");

    std::string stop_reason;
    if (!watchdog_fired.empty()) stop_reason = "hang";
    else if (!turn_error.empty()) stop_reason = "error";
    else if ((decode_tokens >= 0 ? decode_tokens : chunk_count) >= cap)
      stop_reason = "length";
    else stop_reason = "stop";
    turn["stopReason"] = stop_reason;
    turn["degenerate"] = IsDegenerate(collected);
    turn["outputHead"] = collected.substr(0, 160);
    EmitLine("ENDURANCE_TURN", turn);

    if (!watchdog_fired.empty()) {
      session_status = "hang";
      failure_detail = watchdog_fired;
      break;
    }
    if (!turn_error.empty()) {
      session_status = "crash";
      failure_detail = turn_error;
      break;
    }
    empty_streak = chunk_count == 0 ? empty_streak + 1 : 0;
    if (empty_streak >= 3) {
      session_status = "empty-output";
      failure_detail = "3 consecutive turns streamed no text";
      break;
    }
  }

  ordered_json session{{"status", session_status},
                       {"turnsCompleted", turn_index},
                       {"elapsedSeconds", NowSeconds() - session_start},
                       {"loadSeconds", load_seconds},
                       {"plannedMinutes", minutes},
                       {"contextTokens", context_tokens},
                       {"turnCap", cap},
                       {"residentFinalMB", ProcStatusMB("VmRSS")},
                       {"residentPeakMB", ProcStatusMB("VmHWM")}};
  if (!failure_detail.empty()) session["failureDetail"] = failure_detail;
  EmitLine("ENDURANCE_SESSION", session);
  // _Exit skips engine destructors on purpose: teardown can wedge ~10 min
  // (the known litert teardown hang) and everything measured is already out.
  std::_Exit(session_status == "completed" ? 0 : 1);
}

}  // namespace

int main(int argc, char** argv) {
  absl::ParseCommandLine(argc, argv);
  return MainHelper();
}
