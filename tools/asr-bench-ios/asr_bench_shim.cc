// See asr_bench_shim.h. The config assembly copies asr_runner.cc's
// LoadConfigFromJsonFile (unchanged semantics) and the run loop copies
// RunAsrRunner; there is no download path on the phone (files are staged).
#include "bench_ios/asr_bench_shim.h"

#include <chrono>  // NOLINT
#include <cstdlib>
#include <cstring>
#include <filesystem>  // NOLINT
#include <fstream>
#include <memory>
#include <sstream>
#include <string>
#include <utility>
#include <variant>
#include <vector>

#include "absl/log/absl_log.h"  // from @com_google_absl
#include "absl/status/status.h"  // from @com_google_absl
#include "absl/status/status_macros.h"  // from @com_google_absl
#include "absl/status/statusor.h"  // from @com_google_absl
#include "absl/strings/match.h"  // from @com_google_absl
#include "absl/strings/str_cat.h"  // from @com_google_absl
#include "absl/strings/string_view.h"  // from @com_google_absl
#include "absl/time/time.h"  // from @com_google_absl
#include "omni/asr/asr_engine.h"
#include "omni/asr/file_audio_source.h"
#include "omni/asr/model_metadata.h"
#include "omni/omni_session.h"

#ifndef ASR_BENCH_ENGINE_VERSION
#define ASR_BENCH_ENGINE_VERSION "unknown"
#endif

namespace {

using Clock = std::chrono::steady_clock;

double Secs(Clock::time_point a, Clock::time_point b) {
  return std::chrono::duration<double>(b - a).count();
}

char* Dup(const std::string& s) {
  char* p = static_cast<char*>(std::malloc(s.size() + 1));
  std::memcpy(p, s.data(), s.size());
  p[s.size()] = '\0';
  return p;
}

absl::StatusOr<litert::omni::asr::AsrEngineConfig> LoadConfig(
    const AsrBenchRequest& req) {
  std::string json_content;
  std::string json_path = req.metadata_path ? req.metadata_path : "";
  if (!json_path.empty() && std::filesystem::exists(json_path)) {
    std::ifstream f{json_path};
    if (!f.is_open()) {
      return absl::NotFoundError(
          absl::StrCat("Could not open JSON config file: ", json_path));
    }
    std::stringstream buffer;
    buffer << f.rdbuf();
    json_content = buffer.str();
  }
  litert::omni::asr::AsrEngineConfig config;
  config.cache_dir = req.cache_dir ? req.cache_dir : "";
  config.num_threads = req.num_threads;
  config.overlap_ratio = req.overlap_ratio;
  if (req.model_path && *req.model_path) config.model_path = req.model_path;
  ABSL_RETURN_IF_ERROR(litert::omni::asr::PopulateConfigFromMetadataJson(
      req.model_name ? req.model_name : "", json_content, config));
  absl::string_view merger = req.text_merger_type ? req.text_merger_type : "";
  if (!merger.empty()) {
    config.text_merger_type =
        absl::EqualsIgnoreCase(merger, "levenshtein")
            ? litert::omni::asr::AsrEngineConfig::TextMergerType::kLevenshtein
            : litert::omni::asr::AsrEngineConfig::TextMergerType::kTimestamp;
  }
  absl::string_view backend = req.backend ? req.backend : "cpu";
  if (backend == "gpu") {
    config.backend = litert::omni::asr::AsrEngineConfig::Backend::kGpu;
  } else if (backend == "npu") {
    config.backend = litert::omni::asr::AsrEngineConfig::Backend::kNpu;
  } else {
    config.backend = litert::omni::asr::AsrEngineConfig::Backend::kCpu;
  }
  std::string model_ext =
      std::filesystem::path(config.model_url).extension().string();
  if (model_ext.empty()) model_ext = ".tflite";
  std::filesystem::path cache_path(config.cache_dir);
  std::string model_filename = absl::StrCat(req.model_name, model_ext);
  std::string tokenizer_filename =
      absl::StrCat(req.model_name, "_tokenizer.json");
  if (config.model_path.empty()) {
    config.model_path = (cache_path / model_filename).string();
  } else {
    config.model_url.clear();
  }
  if (config.tokenizer_path.empty()) {
    config.tokenizer_path = (cache_path / tokenizer_filename).string();
  }
  return config;
}

absl::Status Run(const AsrBenchRequest& req,
                 void (*text_cb)(const char*, void*), void* user_data,
                 AsrBenchResult* out) {
  if (!req.audio_path || !*req.audio_path) {
    return absl::InvalidArgumentError("audio_path is required.");
  }
  ABSL_ASSIGN_OR_RETURN(auto config, LoadConfig(req));
  absl::Duration interval = absl::Milliseconds(config.input_milliseconds);
  absl::Duration overlap = interval * req.overlap_ratio;

  const auto t0 = Clock::now();
  // No downloader: every file is staged on the phone (NotFound otherwise).
  ABSL_ASSIGN_OR_RETURN(auto engine, litert::omni::asr::AsrEngine::Create(
                                         std::move(config), nullptr));
  const auto t1 = Clock::now();
  out->t_create_engine_s = Secs(t0, t1);
  ABSL_ASSIGN_OR_RETURN(
      auto audio_source,
      litert::omni::asr::FileAudioSource::Create(
          req.audio_path, interval, overlap, engine->config().sample_rate_hz));
  ABSL_ASSIGN_OR_RETURN(auto session,
                        engine->CreateSession(std::move(audio_source)));
  const auto t2 = Clock::now();
  out->t_create_session_s = Secs(t1, t2);

  std::string transcript;
  auto emit = [&](const std::string& text) {
    if (text.empty()) return;
    if (!transcript.empty()) transcript += ' ';
    transcript += text;
    out->text_chunks += 1;
    if (out->t_first_text_s < 0) out->t_first_text_s = Secs(t2, Clock::now());
    if (text_cb) text_cb(text.c_str(), user_data);
  };

  ABSL_LOG(INFO) << "Starting speech recognition on " << req.audio_path
                 << "...";
  const auto t_start = Clock::now();
  while (true) {
    auto result = session->ProcessNext();
    if (!result.ok()) {
      if (absl::IsOutOfRange(result.status())) {
        auto flush_result = session->Flush();
        if (flush_result.ok()) {
          const auto* text_out =
              std::get_if<litert::omni::OmniSession::TextOutput>(
                  &*flush_result);
          if (text_out != nullptr) emit(text_out->confirmed_text);
        }
        break;
      }
      return result.status();
    }
    const auto* text_out =
        std::get_if<litert::omni::OmniSession::TextOutput>(&*result);
    if (text_out != nullptr) emit(text_out->confirmed_text);
  }
  const auto t_fin = Clock::now();
  ABSL_LOG(INFO) << "Finished speech recognition.";
  out->t_process_s = Secs(t_start, t_fin);
  out->transcript = Dup(transcript);
  out->ok = 1;
  return absl::OkStatus();
}

}  // namespace

extern "C" int asr_bench_run(const AsrBenchRequest* req,
                             void (*text_cb)(const char*, void*),
                             void* user_data, AsrBenchResult* out) {
  std::memset(out, 0, sizeof(*out));
  out->t_first_text_s = -1.0;
  absl::Status st = Run(*req, text_cb, user_data, out);
  if (!st.ok()) {
    out->ok = 0;
    out->error = Dup(st.ToString());
    ABSL_LOG(ERROR) << "asr_bench_run failed: " << st;
    return 1;
  }
  return 0;
}


namespace {

absl::Status RunManifest(const AsrBenchRequest& req, const char* manifest_path,
                         int limit,
                         void (*utt_cb)(int, const char*, double, int, const char*,
                                        int, void*),
                         void* user_data, AsrBenchResult* out) {
  std::ifstream mf(manifest_path);
  if (!mf.is_open()) {
    return absl::NotFoundError(absl::StrCat("manifest not found: ", manifest_path));
  }
  std::vector<std::pair<std::string, std::string>> items;
  std::string line;
  while (std::getline(mf, line)) {
    if (line.empty()) continue;
    auto tab = line.find('\t');
    if (tab == std::string::npos) continue;
    items.emplace_back(line.substr(0, tab), line.substr(tab + 1));
    if (limit > 0 && static_cast<int>(items.size()) >= limit) break;
  }
  ABSL_ASSIGN_OR_RETURN(auto config, LoadConfig(req));
  absl::Duration interval = absl::Milliseconds(config.input_milliseconds);
  absl::Duration overlap = interval * req.overlap_ratio;
  const int sample_rate = config.sample_rate_hz;
  const auto t0 = Clock::now();
  ABSL_ASSIGN_OR_RETURN(auto engine, litert::omni::asr::AsrEngine::Create(
                                         std::move(config), nullptr));
  out->t_create_engine_s = Secs(t0, Clock::now());
  ABSL_LOG(INFO) << "Starting per-utterance sessions: " << items.size()
                 << " utterances from " << manifest_path;
  const auto t_all = Clock::now();
  int index = 0;
  for (const auto& [id, path] : items) {
    std::string transcript;
    int chunks = 0;
    int ok = 1;
    const auto ts = Clock::now();
    {
      auto source = litert::omni::asr::FileAudioSource::Create(path, interval,
                                                               overlap, sample_rate);
      if (!source.ok()) {
        ABSL_LOG(ERROR) << id << ": " << source.status();
        ok = 0;
      } else {
        auto session = engine->CreateSession(std::move(*source));
        if (!session.ok()) {
          ABSL_LOG(ERROR) << id << ": " << session.status();
          ok = 0;
        } else {
          while (true) {
            auto result = (*session)->ProcessNext();
            if (!result.ok()) {
              if (absl::IsOutOfRange(result.status())) {
                auto flushed = (*session)->Flush();
                if (flushed.ok()) {
                  const auto* t = std::get_if<litert::omni::OmniSession::TextOutput>(
                      &*flushed);
                  if (t && !t->confirmed_text.empty()) {
                    if (!transcript.empty()) transcript += ' ';
                    transcript += t->confirmed_text;
                    ++chunks;
                  }
                }
                break;
              }
              ABSL_LOG(ERROR) << id << ": " << result.status();
              ok = 0;
              break;
            }
            const auto* t =
                std::get_if<litert::omni::OmniSession::TextOutput>(&*result);
            if (t && !t->confirmed_text.empty()) {
              if (!transcript.empty()) transcript += ' ';
              transcript += t->confirmed_text;
              ++chunks;
            }
          }
        }
      }
    }  // the session and its audio source are destroyed here, before the callback
    const double proc = Secs(ts, Clock::now());
    if (utt_cb) utt_cb(index, id.c_str(), proc, chunks, transcript.c_str(), ok, user_data);
    out->text_chunks += chunks;
    if (!ok) out->ok = 0;
    ++index;
  }
  out->t_process_s = Secs(t_all, Clock::now());
  ABSL_LOG(INFO) << "Finished per-utterance sessions: " << index;
  return absl::OkStatus();
}

}  // namespace

extern "C" int asr_bench_run_manifest(const AsrBenchRequest* req,
                                      const char* manifest_path, int limit,
                                      void (*utt_cb)(int, const char*, double, int,
                                                     const char*, int, void*),
                                      void* user_data, AsrBenchResult* out) {
  std::memset(out, 0, sizeof(*out));
  out->t_first_text_s = -1.0;
  out->ok = 1;
  absl::Status st = RunManifest(*req, manifest_path, limit, utt_cb, user_data, out);
  if (!st.ok()) {
    out->ok = 0;
    out->error = Dup(st.ToString());
    ABSL_LOG(ERROR) << "asr_bench_run_manifest failed: " << st;
    return 1;
  }
  return out->ok ? 0 : 2;
}

extern "C" void asr_bench_result_free(AsrBenchResult* out) {
  if (!out) return;
  std::free(out->transcript);
  std::free(out->error);
  out->transcript = nullptr;
  out->error = nullptr;
}

extern "C" const char* asr_bench_engine_version(void) {
  return ASR_BENCH_ENGINE_VERSION;
}
