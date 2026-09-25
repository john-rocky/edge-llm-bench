// Copyright 2026 The ODML Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

// Batch ASR evaluation through the unified `OmniEngine` API.
//
// Reads a manifest (one `<id>\t<path.wav>` per line, 16 kHz mono 16-bit PCM),
// transcribes every file through `OmniEngine::CreateSession` +
// `PushInputSource`, and writes one JSON line per utterance with the
// transcript and the wall time the session spent producing it. The transcript
// is exactly what `asr_runner` prints: every non-empty `confirmed_text` from
// `ProcessNext()` joined by a space, then the text returned by `Flush()`.

#include <sys/resource.h>

#include <chrono>  // NOLINT
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iostream>
#include <memory>
#include <sstream>
#include <string>
#include <utility>
#include <variant>
#include <vector>

#include "absl/flags/flag.h"  // from @com_google_absl
#include "absl/flags/parse.h"  // from @com_google_absl
#include "absl/log/absl_log.h"  // from @com_google_absl
#include "absl/status/status.h"  // from @com_google_absl
#include "absl/status/statusor.h"  // from @com_google_absl
#include "absl/strings/str_cat.h"  // from @com_google_absl
#include "absl/strings/str_split.h"  // from @com_google_absl
#include "absl/strings/string_view.h"  // from @com_google_absl
#include "omni/omni_engine.h"
#include "omni/omni_session.h"

ABSL_FLAG(std::string, model_name, "parakeet-tdt-0.6b-v3",
          "Model name as known to OmniEngine (omni/asr/model_metadata.json).");
ABSL_FLAG(std::string, cache_dir, "",
          "Directory holding <model_name>.tflite|.litertlm and "
          "<model_name>_tokenizer.json (OmniEngine does not download).");
ABSL_FLAG(std::string, backend, "cpu", "cpu, gpu or npu.");
ABSL_FLAG(int, num_threads, 4, "CPU threads.");
ABSL_FLAG(std::string, manifest, "",
          "Manifest: one '<id>\\t<wav path>' per line.");
ABSL_FLAG(std::string, output, "", "Output JSONL path ('-' = stdout).");
ABSL_FLAG(int, limit, 0, "Stop after this many utterances (0 = all).");
ABSL_FLAG(int, push_chunk_ms, 0,
          "If > 0, push the audio as AudioInput chunks of this many ms "
          "(the streaming shape); 0 pushes the whole file as one AudioInput.");
ABSL_FLAG(bool, reuse_session, false,
          "Create one session and Reset() it between utterances instead of "
          "creating a session per utterance.");
ABSL_FLAG(bool, stop_on_not_found, false,
          "Treat a NOT_FOUND from ProcessNext() (\"Deque has no output "
          "available\") as fatal, the way omni/asr/asr_runner.cc does. The "
          "default keeps calling ProcessNext(): a pass that produced no text "
          "is not the end of the stream.");

namespace {

using ::litert::omni::OmniEngine;
using ::litert::omni::OmniSession;
using ::litert::omni::PushInputSource;

struct Wav {
  int sample_rate_hz = 0;
  int num_channels = 0;
  std::vector<float> samples;
};

uint32_t ReadU32(const char* p) {
  uint32_t v;
  std::memcpy(&v, p, 4);
  return v;
}
uint16_t ReadU16(const char* p) {
  uint16_t v;
  std::memcpy(&v, p, 2);
  return v;
}

absl::StatusOr<Wav> ReadPcm16Wav(const std::string& path) {
  std::ifstream f(path, std::ios::binary);
  if (!f.is_open()) {
    return absl::NotFoundError(absl::StrCat("cannot open ", path));
  }
  std::string bytes((std::istreambuf_iterator<char>(f)),
                    std::istreambuf_iterator<char>());
  if (bytes.size() < 12 || bytes.compare(0, 4, "RIFF") != 0 ||
      bytes.compare(8, 4, "WAVE") != 0) {
    return absl::InvalidArgumentError(absl::StrCat("not a RIFF/WAVE: ", path));
  }
  Wav wav;
  int bits = 0;
  int format = 0;
  size_t pos = 12;
  bool have_fmt = false;
  while (pos + 8 <= bytes.size()) {
    const std::string id = bytes.substr(pos, 4);
    const uint32_t size = ReadU32(bytes.data() + pos + 4);
    const size_t body = pos + 8;
    if (id == "fmt ") {
      if (size < 16 || body + 16 > bytes.size()) {
        return absl::InvalidArgumentError("short fmt chunk");
      }
      format = ReadU16(bytes.data() + body);
      wav.num_channels = ReadU16(bytes.data() + body + 2);
      wav.sample_rate_hz = static_cast<int>(ReadU32(bytes.data() + body + 4));
      bits = ReadU16(bytes.data() + body + 14);
      have_fmt = true;
    } else if (id == "data") {
      if (!have_fmt) return absl::InvalidArgumentError("data before fmt");
      if (format != 1 || bits != 16) {
        return absl::InvalidArgumentError(absl::StrCat(
            "need PCM16, got format ", format, " bits ", bits, ": ", path));
      }
      const size_t n = std::min<size_t>(size, bytes.size() - body) / 2;
      wav.samples.resize(n);
      const char* p = bytes.data() + body;
      for (size_t i = 0; i < n; ++i) {
        int16_t s;
        std::memcpy(&s, p + 2 * i, 2);
        wav.samples[i] = static_cast<float>(s) / 32768.0f;
      }
      return wav;
    }
    pos = body + size + (size & 1);
  }
  return absl::InvalidArgumentError(absl::StrCat("no data chunk: ", path));
}

std::string JsonEscape(absl::string_view s) {
  std::string out;
  out.reserve(s.size() + 8);
  for (unsigned char c : s) {
    switch (c) {
      case '"': out += "\\\""; break;
      case '\\': out += "\\\\"; break;
      case '\n': out += "\\n"; break;
      case '\r': out += "\\r"; break;
      case '\t': out += "\\t"; break;
      default:
        if (c < 0x20) {
          char buf[8];
          std::snprintf(buf, sizeof(buf), "\\u%04x", c);
          out += buf;
        } else {
          out += static_cast<char>(c);
        }
    }
  }
  return out;
}

double Seconds(std::chrono::steady_clock::time_point a,
               std::chrono::steady_clock::time_point b) {
  return std::chrono::duration<double>(b - a).count();
}

struct Result {
  std::string text;
  int outputs = 0;  // non-empty confirmed_text chunks from ProcessNext
  int not_found = 0;  // ProcessNext passes that produced no text (NOT_FOUND)
  bool flush_empty = false;  // Flush() had nothing pending (NOT_FOUND)
  absl::Status status;
};

// Pushes one utterance and drains the session the way asr_runner does.
Result Transcribe(OmniSession& session, PushInputSource& source,
                  const Wav& wav, int push_chunk_ms) {
  Result r;
  r.status = source.PushInput(OmniSession::AudioInputMetadata{
      .sample_rate_hz = wav.sample_rate_hz,
      .num_channels = wav.num_channels});
  if (!r.status.ok()) return r;
  if (push_chunk_ms > 0) {
    const size_t step =
        static_cast<size_t>(wav.sample_rate_hz) * push_chunk_ms / 1000;
    for (size_t i = 0; i < wav.samples.size(); i += step) {
      const size_t end = std::min(wav.samples.size(), i + step);
      r.status = source.PushInput(OmniSession::AudioInput{
          .pcm_samples = std::vector<float>(wav.samples.begin() + i,
                                            wav.samples.begin() + end)});
      if (!r.status.ok()) return r;
    }
  } else {
    r.status = source.PushInput(
        OmniSession::AudioInput{.pcm_samples = wav.samples});
    if (!r.status.ok()) return r;
  }
  r.status = source.PushInput(OmniSession::EndOfInput{});
  if (!r.status.ok()) return r;

  while (true) {
    absl::StatusOr<OmniSession::Output> out = session.ProcessNext();
    if (!out.ok()) {
      if (absl::IsOutOfRange(out.status())) {
        absl::StatusOr<OmniSession::Output> flushed = session.Flush();
        if (flushed.ok()) {
          const auto* t = std::get_if<OmniSession::TextOutput>(&*flushed);
          if (t != nullptr && !t->confirmed_text.empty()) {
            if (!r.text.empty()) r.text += ' ';
            r.text += t->confirmed_text;
          }
        } else if (absl::IsNotFound(flushed.status())) {
          // Nothing was pending in the merger ("Deque has no output
          // available"); asr_runner ignores this too.
          r.flush_empty = true;
        } else {
          r.status = flushed.status();
        }
        return r;
      }
      if (absl::IsNotFound(out.status()) &&
          !absl::GetFlag(FLAGS_stop_on_not_found)) {
        // A scheduling pass with nothing to report; the stream continues.
        if (++r.not_found > 100000) {
          r.status = absl::DeadlineExceededError(
              "100000 consecutive NOT_FOUND passes without end of stream");
          return r;
        }
        continue;
      }
      r.status = out.status();
      return r;
    }
    const auto* t = std::get_if<OmniSession::TextOutput>(&*out);
    if (t != nullptr && !t->confirmed_text.empty()) {
      if (!r.text.empty()) r.text += ' ';
      r.text += t->confirmed_text;
      ++r.outputs;
    }
  }
}

absl::Status Run() {
  const std::string manifest_path = absl::GetFlag(FLAGS_manifest);
  if (manifest_path.empty()) {
    return absl::InvalidArgumentError("--manifest is required");
  }
  std::ifstream manifest(manifest_path);
  if (!manifest.is_open()) {
    return absl::NotFoundError(absl::StrCat("cannot open ", manifest_path));
  }
  std::vector<std::pair<std::string, std::string>> items;
  std::string line;
  while (std::getline(manifest, line)) {
    if (line.empty()) continue;
    std::vector<std::string> cols = absl::StrSplit(line, '\t');
    if (cols.size() < 2) {
      return absl::InvalidArgumentError(
          absl::StrCat("manifest line without a tab: ", line));
    }
    items.emplace_back(cols[0], cols[1]);
  }
  const int limit = absl::GetFlag(FLAGS_limit);
  if (limit > 0 && items.size() > static_cast<size_t>(limit)) {
    items.resize(limit);
  }

  std::ostream* out = &std::cout;
  std::ofstream out_file;
  const std::string output_path = absl::GetFlag(FLAGS_output);
  if (!output_path.empty() && output_path != "-") {
    out_file.open(output_path);
    if (!out_file.is_open()) {
      return absl::InternalError(absl::StrCat("cannot write ", output_path));
    }
    out = &out_file;
  }

  OmniEngine::Options options;
  const std::string backend = absl::GetFlag(FLAGS_backend);
  if (backend == "gpu") {
    options.backend = OmniEngine::Options::Backend::kGpu;
  } else if (backend == "npu") {
    options.backend = OmniEngine::Options::Backend::kNpu;
  } else if (backend == "cpu") {
    options.backend = OmniEngine::Options::Backend::kCpu;
  } else {
    return absl::InvalidArgumentError(absl::StrCat("bad --backend ", backend));
  }
  options.cache_dir = absl::GetFlag(FLAGS_cache_dir);
  options.num_threads = absl::GetFlag(FLAGS_num_threads);
  const std::string model_name = absl::GetFlag(FLAGS_model_name);
  const int push_chunk_ms = absl::GetFlag(FLAGS_push_chunk_ms);
  const bool reuse_session = absl::GetFlag(FLAGS_reuse_session);

  const auto t_load0 = std::chrono::steady_clock::now();
  absl::StatusOr<std::unique_ptr<OmniEngine>> engine =
      OmniEngine::Create(model_name, options);
  if (!engine.ok()) return engine.status();
  const auto t_load1 = std::chrono::steady_clock::now();
  const double load_seconds = Seconds(t_load0, t_load1);

  *out << "{\"type\":\"header\",\"model_name\":\"" << JsonEscape(model_name)
       << "\",\"backend\":\"" << backend
       << "\",\"num_threads\":" << options.num_threads
       << ",\"push_chunk_ms\":" << push_chunk_ms
       << ",\"reuse_session\":" << (reuse_session ? "true" : "false")
       << ",\"stop_on_not_found\":"
       << (absl::GetFlag(FLAGS_stop_on_not_found) ? "true" : "false")
       << ",\"utterances\":" << items.size()
       << ",\"load_seconds\":" << load_seconds << "}" << std::endl;

  std::unique_ptr<OmniSession> shared_session;
  PushInputSource* shared_source = nullptr;
  double total_audio = 0, total_processing = 0, total_create = 0;
  int failures = 0;
  int done = 0;
  for (const auto& [id, path] : items) {
    absl::StatusOr<Wav> wav = ReadPcm16Wav(path);
    if (!wav.ok()) return wav.status();
    const double audio_seconds =
        static_cast<double>(wav->samples.size()) / wav->sample_rate_hz;

    const auto t0 = std::chrono::steady_clock::now();
    OmniSession* session = nullptr;
    PushInputSource* source = nullptr;
    std::unique_ptr<OmniSession> own_session;
    if (reuse_session) {
      if (shared_session == nullptr) {
        auto input = std::make_unique<PushInputSource>();
        shared_source = input.get();
        absl::StatusOr<std::unique_ptr<OmniSession>> s =
            (*engine)->CreateSession(std::move(input));
        if (!s.ok()) return s.status();
        shared_session = *std::move(s);
      } else {
        shared_session->Reset();
      }
      session = shared_session.get();
      source = shared_source;
    } else {
      auto input = std::make_unique<PushInputSource>();
      source = input.get();
      absl::StatusOr<std::unique_ptr<OmniSession>> s =
          (*engine)->CreateSession(std::move(input));
      if (!s.ok()) return s.status();
      own_session = *std::move(s);
      session = own_session.get();
    }
    const auto t1 = std::chrono::steady_clock::now();
    Result r = Transcribe(*session, *source, *wav, push_chunk_ms);
    const auto t2 = std::chrono::steady_clock::now();
    own_session.reset();
    const auto t3 = std::chrono::steady_clock::now();

    const double create_seconds = Seconds(t0, t1);
    const double processing_seconds = Seconds(t1, t2);
    total_audio += audio_seconds;
    total_processing += processing_seconds;
    total_create += create_seconds;
    if (!r.status.ok()) ++failures;
    ++done;

    *out << "{\"id\":\"" << JsonEscape(id) << "\",\"text\":\""
         << JsonEscape(r.text) << "\",\"audio_seconds\":" << audio_seconds
         << ",\"processing_seconds\":" << processing_seconds
         << ",\"session_create_seconds\":" << create_seconds
         << ",\"session_destroy_seconds\":" << Seconds(t2, t3)
         << ",\"outputs\":" << r.outputs << ",\"not_found_passes\":"
         << r.not_found << ",\"flush_empty\":"
         << (r.flush_empty ? "true" : "false") << ",\"error\":\""
         << JsonEscape(r.status.ok() ? "" : r.status.ToString()) << "\"}"
         << std::endl;
    if (done % 100 == 0) {
      ABSL_LOG(INFO) << done << "/" << items.size() << " audio "
                     << total_audio << " s, processing " << total_processing
                     << " s, RTFx " << total_audio / total_processing;
    }
  }

  struct rusage usage;
  getrusage(RUSAGE_SELF, &usage);
  *out << "{\"type\":\"footer\",\"utterances\":" << done
       << ",\"failures\":" << failures << ",\"total_audio_seconds\":"
       << total_audio << ",\"total_processing_seconds\":" << total_processing
       << ",\"total_session_create_seconds\":" << total_create
       << ",\"rtfx_processing\":" << total_audio / total_processing
       << ",\"rtfx_processing_plus_create\":"
       << total_audio / (total_processing + total_create)
       << ",\"peak_rss_bytes\":" << usage.ru_maxrss << "}" << std::endl;
  return absl::OkStatus();
}

}  // namespace

int main(int argc, char* argv[]) {
  absl::ParseCommandLine(argc, argv);
  absl::Status status = Run();
  if (!status.ok()) {
    ABSL_LOG(ERROR) << "omni_eval_runner failed: " << status;
    return 1;
  }
  return 0;
}
