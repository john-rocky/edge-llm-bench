// edge-llm-bench ONNX Runtime GenAI driver — one prompt, one generation, with
// the timing cut points of upstream model_benchmark (onnxruntime-genai v0.17.0
// benchmark/c/main.cpp) but stopping the way every other arm stops: at EOS or
// at the task budget. This file is HARNESS code, not upstream code; it links
// the official release AAR's libonnxruntime-genai.so
// (android/ortgenai/build_android.sh).
//
// Why model_benchmark is not enough: its MakeGeneratorParams sets
// min_length = prompt + generation length, which masks EOS — a forced-length
// tool, kept for the native-benchmark rows only. The short-chat and 1K task
// cells need a run that ends at EOS or the budget, on the model's own chat
// template, with no min_length.
//
// Cut points (v0.17.0 src/generator/generators.cpp and
// src/decoding/standard_decoding_strategy.cpp):
//   AppendTokenSequences    runs the model over the whole prompt    -> prefill_ms
//   1st GenerateNextToken   samples from the prefill logits only    -> ttft_ms = prefill_ms + this
//   every later call        one forward pass for the previous token,
//                           then sampling                           -> decode_ms_total
// IsDone() sits inside each timed span, as in main.cpp. gen_tokens counts
// GenerateNextToken calls: the call that samples EOS is counted (its forward
// pass ran) although GenAI does not append EOS to the sequence, so
// decode_tps = (gen_tokens - 1) / decode_ms_total is a rate of forward passes.
//
// Output contract (one generation per process; stdout):
//   [PROMPT BEGIN]<text given to Encode>[PROMPT END]
//   ORTGENAI prompt_tokens= gen_tokens= prefill_ms= ttft_ms= decode_ms_total=
//            decode_tps= stop=eos|budget|max_length max_length= peak_rss_kb=
//            seq_tokens= last_token= load_ms= generator_ms= chat_template=
//            ort_version= threads=<N|default>
//   ORTGENAI_LIBS <path of every mapped libonnxruntime*.so / libmat.so>
//   [OUTPUT BEGIN]<decoded generated tokens>[OUTPUT END]
// Exit 0 after a completed generation, 1 on an engine error, 2 on a usage
// error (-g 0, an empty prompt, telemetry not disabled).
//
// Threads: without --threads the model loads through OgaCreateModel, so GenAI
// picks the decoder's intra-op thread count itself (v0.17.0
// src/models/model.cpp CreateSessionOptionsFromConfig:
// hardware_concurrency() / 2, at least 1, at most 16, unless genai_config sets
// one). --threads N is a diagnostic: OgaCreateConfig, an overlay of
// model.decoder.session_options.intra_op_num_threads = N, then
// OgaCreateModelFromConfig (the same config load and model build, plus the
// overlay); load_ms then also covers the config load and the overlay.
//
// Memory: peak_rss_kb is getrusage ru_maxrss (KiB on Linux), the number
// model_benchmark prints. With past_present_share_buffer (the onnx-community
// Qwen3 configs) GenAI allocates and zero-fills the KV cache for max_length at
// generator creation, so -ml sets the memory the run pays for.
//
// Telemetry: the official build ships the 1DS SDK (libmat.so) with telemetry
// ON by default. ORT_DISABLE_TELEMETRY=1 in the environment before GenAI
// initializes stops the uploader, events and device id for the process
// lifetime (src/ort_genai_c.h). This driver refuses to run without it and also
// calls OgaSetTelemetryEnabled(false).

#include <dlfcn.h>
#include <sys/resource.h>

#include <cerrno>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <fstream>
#include <iostream>
#include <iterator>
#include <memory>
#include <set>
#include <sstream>
#include <string>
#include <string_view>

#include "ort_genai.h"

namespace {

using Clock = std::chrono::steady_clock;

double Ms(Clock::duration d) {
  return std::chrono::duration<double, std::milli>(d).count();
}

struct Options {
  std::string model_dir;
  std::string prompt_file;
  long budget = -1;
  long max_length = -1;
  long threads = -1;  // -1 = GenAI's own choice (no overlay)
  bool chat_template = true;
};

[[noreturn]] void Usage(const char* argv0, const std::string& error) {
  std::cerr << "Error: " << error << "\n"
            << "Usage: " << argv0
            << " -i <model dir> --prompt_file <path> -g <budget> -ml <max_length> [--threads N]"
               " [--no-chat-template]\n";
  std::exit(2);
}

long ParsePositive(const char* argv0, std::string_view flag, const char* text) {
  char* end = nullptr;
  errno = 0;
  const long value = std::strtol(text, &end, 10);
  if (errno != 0 || end == text || *end != '\0' || value <= 0)
    Usage(argv0, std::string(flag) + " needs a positive integer, got '" + text + "'");
  return value;
}

Options ParseOptions(int argc, char** argv) {
  Options opts;
  for (int i = 1; i < argc; ++i) {
    const std::string_view arg = argv[i];
    auto value = [&]() -> const char* {
      if (i + 1 >= argc) Usage(argv[0], std::string(arg) + " needs a value");
      return argv[++i];
    };
    if (arg == "-i") {
      opts.model_dir = value();
    } else if (arg == "--prompt_file") {
      opts.prompt_file = value();
    } else if (arg == "-g") {
      opts.budget = ParsePositive(argv[0], arg, value());
    } else if (arg == "-ml") {
      opts.max_length = ParsePositive(argv[0], arg, value());
    } else if (arg == "--threads") {
      opts.threads = ParsePositive(argv[0], arg, value());
    } else if (arg == "--no-chat-template") {
      opts.chat_template = false;
    } else {
      Usage(argv[0], "unknown option " + std::string(arg));
    }
  }
  if (opts.model_dir.empty()) Usage(argv[0], "-i is required");
  if (opts.prompt_file.empty()) Usage(argv[0], "--prompt_file is required");
  if (opts.budget < 0) Usage(argv[0], "-g is required");
  if (opts.max_length < 0) Usage(argv[0], "-ml is required");
  return opts;
}

std::string ReadPrompt(const char* argv0, const std::string& path) {
  std::ifstream in{path, std::ios::binary};
  if (!in) Usage(argv0, "cannot read prompt file " + path);
  std::string text{std::istreambuf_iterator<char>{in}, std::istreambuf_iterator<char>{}};
  if (text.find_first_not_of(" \t\r\n") == std::string::npos)
    Usage(argv0, "prompt file is empty: " + path);
  return text;
}

// A JSON string literal; bytes >= 0x80 pass through (UTF-8 is valid JSON).
std::string JsonString(std::string_view text) {
  std::string out = "\"";
  for (const unsigned char c : text) {
    switch (c) {
      case '"': out += "\\\""; break;
      case '\\': out += "\\\\"; break;
      case '\n': out += "\\n"; break;
      case '\r': out += "\\r"; break;
      case '\t': out += "\\t"; break;
      case '\b': out += "\\b"; break;
      case '\f': out += "\\f"; break;
      default:
        if (c < 0x20) {
          char escaped[8];
          std::snprintf(escaped, sizeof escaped, "\\u%04x", c);
          out += escaped;
        } else {
          out += static_cast<char>(c);
        }
    }
  }
  return out + "\"";
}

// The ORT image GenAI actually loaded (GenAI dlopens libonnxruntime.so at its
// first call, ORT_LIB_PATH first): its version string, read through the
// OrtApiBase table (two function pointers, ABI-stable).
std::string LoadedOrtVersion() {
  struct ApiBase {
    const void* (*get_api)(uint32_t);
    const char* (*get_version_string)();
  };
  void* handle = dlopen("libonnxruntime.so", RTLD_NOW | RTLD_NOLOAD);
  if (handle == nullptr) return "-";
  auto get_api_base = reinterpret_cast<const ApiBase* (*)()>(dlsym(handle, "OrtGetApiBase"));
  const char* version = get_api_base != nullptr ? get_api_base()->get_version_string() : nullptr;
  std::string result = version != nullptr ? version : "-";
  dlclose(handle);  // drops only the reference RTLD_NOLOAD added
  return result;
}

// Which files the run really used: every mapped ORT / GenAI / 1DS library.
std::string MappedEngineLibraries() {
  std::ifstream maps{"/proc/self/maps"};
  std::set<std::string> paths;
  for (std::string line; std::getline(maps, line);) {
    const auto slash = line.find('/');
    if (slash == std::string::npos) continue;
    const std::string path = line.substr(slash);
    const std::string name = path.substr(path.rfind('/') + 1);
    if (name.rfind("libonnxruntime", 0) == 0 || name == "libmat.so") paths.insert(path);
  }
  std::string out;
  for (const auto& path : paths) out += (out.empty() ? "" : " ") + path;
  return out.empty() ? "-" : out;
}

int Run(const Options& opts, const std::string& prompt) {
  const auto load_start = Clock::now();
  std::unique_ptr<OgaModel> model;
  if (opts.threads > 0) {
    auto config = OgaConfig::Create(opts.model_dir.c_str());
    const std::string overlay = R"({"model":{"decoder":{"session_options":{"intra_op_num_threads":)" +
                                std::to_string(opts.threads) + "}}}}";
    config->Overlay(overlay.c_str());
    model = OgaModel::Create(*config);
  } else {
    model = OgaModel::Create(opts.model_dir.c_str());
  }
  const auto load_time = Clock::now() - load_start;
  auto tokenizer = OgaTokenizer::Create(*model);

  // No system message and no template override: the model folder's own
  // chat_template.jinja, as llama.cpp -st and LiteRT-LM apply theirs.
  std::string text = prompt;
  if (opts.chat_template) {
    const std::string messages = "[{\"role\":\"user\",\"content\":" + JsonString(prompt) + "}]";
    text = static_cast<const char*>(tokenizer->ApplyChatTemplate(nullptr, messages.c_str(), nullptr, true));
  }
  auto sequences = OgaSequences::Create();
  tokenizer->Encode(text.c_str(), *sequences);
  const size_t prompt_tokens = sequences->SequenceCount(0);
  std::cout << "[PROMPT BEGIN]" << text << "[PROMPT END]\n" << std::flush;

  auto params = OgaGeneratorParams::Create(*model);
  params->SetSearchOption("max_length", static_cast<double>(opts.max_length));
  params->SetSearchOptionBool("do_sample", false);
  const auto generator_start = Clock::now();
  auto generator = OgaGenerator::Create(*model, *params);
  const auto generator_time = Clock::now() - generator_start;

  const auto prefill_start = Clock::now();
  generator->AppendTokenSequences(*sequences);
  const auto prefill_end = Clock::now();
  generator->GenerateNextToken();
  bool done = generator->IsDone();
  const auto first_token_end = Clock::now();

  long gen_tokens = 1;
  Clock::duration decode_time{};
  while (!done && gen_tokens < opts.budget) {
    const auto step_start = Clock::now();
    generator->GenerateNextToken();
    done = generator->IsDone();
    decode_time += Clock::now() - step_start;
    ++gen_tokens;
  }

  const size_t seq_tokens = generator->GetSequenceCount(0);
  const auto next_tokens = generator->GetNextTokens();
  const long last_token = next_tokens.empty() ? -1 : next_tokens[0];
  const char* stop = !done ? "budget"
                     : seq_tokens >= static_cast<size_t>(opts.max_length) ? "max_length"
                                                                         : "eos";
  const int32_t* sequence = generator->GetSequenceData(0);
  const std::string output = static_cast<const char*>(
      tokenizer->Decode(sequence + prompt_tokens, seq_tokens - prompt_tokens));

  struct rusage usage {};
  getrusage(RUSAGE_SELF, &usage);

  const double prefill_ms = Ms(prefill_end - prefill_start);
  const double decode_ms = Ms(decode_time);
  std::ostringstream line;
  line.setf(std::ios::fixed);
  line.precision(3);
  line << "ORTGENAI prompt_tokens=" << prompt_tokens << " gen_tokens=" << gen_tokens
       << " prefill_ms=" << prefill_ms << " ttft_ms=" << Ms(first_token_end - prefill_start)
       << " decode_ms_total=" << decode_ms << " decode_tps=";
  if (gen_tokens > 1 && decode_ms > 0) {
    line << (gen_tokens - 1) / decode_ms * 1000.0;
  } else {
    line << "-";
  }
  line << " stop=" << stop << " max_length=" << opts.max_length << " peak_rss_kb=" << usage.ru_maxrss
       << " seq_tokens=" << seq_tokens << " last_token=" << last_token << " load_ms=" << Ms(load_time)
       << " generator_ms=" << Ms(generator_time) << " chat_template=" << (opts.chat_template ? "model" : "none")
       << " ort_version=" << LoadedOrtVersion()
       << " threads=" << (opts.threads > 0 ? std::to_string(opts.threads) : std::string{"default"});
  std::cout << line.str() << "\n"
            << "ORTGENAI_LIBS " << MappedEngineLibraries() << "\n"
            << "[OUTPUT BEGIN]" << output << "[OUTPUT END]\n"
            << std::flush;
  return 0;
}

}  // namespace

int main(int argc, char** argv) {
  // Every usage error exits before the first GenAI call: std::exit() past
  // that point would skip OgaShutdown().
  const Options opts = ParseOptions(argc, argv);
  const char* telemetry_off = std::getenv("ORT_DISABLE_TELEMETRY");
  if (telemetry_off == nullptr || std::string_view{telemetry_off} != "1")
    Usage(argv[0], "ORT_DISABLE_TELEMETRY=1 must be set before launch (no number is taken with telemetry on)");
  const std::string prompt = ReadPrompt(argv[0], opts.prompt_file);

  Oga::SetTelemetryEnabled(false);
  OgaHandle handle;  // OgaShutdown() after every GenAI object below is gone
  try {
    return Run(opts, prompt);
  } catch (const std::exception& e) {
    std::cerr << "Error: " << e.what() << "\n";
    return 1;
  }
}
