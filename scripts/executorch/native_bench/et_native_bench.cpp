// et_native_bench: the forced-count benchmark (task native-benchmark-<P>x<D>) on ExecuTorch's own
// LLM runner components, for the Qwen 3 exports llama_main runs (docs/executorch-arm-v1.md,
// "Protocol row").
//
// llama_main cannot take token ids: TextLLMRunner::generate encodes a text prompt, and
// TextLLMRunner::prefill(std::vector<MultimodalInput>) encodes text inputs and skips token inputs
// (extension/llm/runner/text_llm_runner.cpp, v1.5.1). This file builds the components
// create_text_llm_runner builds for llama_main (extension/llm/runner/llm_runner_helper.cpp: Module,
// metadata, EOS ids, IOManager, Sampler, TextDecoderRunner, TextPrefiller, TextTokenGenerator,
// Stats), unchanged, and drives them as TextLLMRunner::generate does, with token ids in place of
// the encoded prompt:
//   - P token ids (SplitMix64 from --seed, below the .pte's get_vocab_size: the generator of
//     CoreAIRuntime.randomPrompt and MLXRuntime.nativeBenchmark, so a model with the same vocab
//     gets the same ids there) go into ONE TextPrefiller::prefill call. It runs one forward over
//     all P when the export has dynamic shape and P <= get_max_seq_len, else it chunks or steps;
//     the count line says which;
//   - the first token is sampled from the prefill logits (greedy), then
//     TextTokenGenerator::generate runs D - 1 forward steps with ignore_eos set, so only the
//     count ends the decode.
// The tokenizer is loaded only because the components take one (EOS ids, and each generated
// token decoded to text for the callback); nothing is encoded and no text is printed.
//
// stdout: "PyTorchObserver {json}" (stats.h print_report, as llama_main prints it; the windows are
// set where TextLLMRunner::generate sets them, so generated_tokens = the decode loop's D - 1 and
// the prefill window holds no tokenization, there being no text), then one line
// "ET_NATIVE_BENCH_OK ..." (or "ET_NATIVE_BENCH_COUNT_MISMATCH ...") with the counts the run made.
// stderr: the ET_LOG lines (thread pool, metadata, RSS), as llama_main's.
// Exit 0 when the counts are P and D, 3 when they are not (both lines printed first), 1 when the
// engine fails.

#include <cinttypes>
#include <cstdio>
#include <memory>
#include <string>
#include <unordered_set>
#include <vector>

#include <gflags/gflags.h>

#include <executorch/extension/llm/runner/constants.h>
#include <executorch/extension/llm/runner/io_manager/io_manager.h>
#include <executorch/extension/llm/runner/llm_runner_helper.h>
#include <executorch/extension/llm/runner/stats.h>
#include <executorch/extension/llm/runner/text_decoder_runner.h>
#include <executorch/extension/llm/runner/text_prefiller.h>
#include <executorch/extension/llm/runner/text_token_generator.h>
#include <executorch/extension/llm/runner/util.h>
#include <executorch/extension/llm/sampler/sampler.h>
#include <executorch/extension/memory_allocator/cpu_caching_malloc_allocator.h>
#include <executorch/extension/module/module.h>
#include <executorch/runtime/platform/runtime.h>

#if defined(ET_USE_THREADPOOL)
#include <executorch/extension/threadpool/cpuinfo_utils.h>
#include <executorch/extension/threadpool/threadpool.h>
#endif

DEFINE_string(model_path, "", "The .pte: a one-method (forward) Qwen 3 export of examples/models/llama.");
DEFINE_string(tokenizer_path, "", "The export's tokenizer (EOS ids and the token callback only).");
DEFINE_int32(prefill_tokens, 1024, "P: token ids in the one prefill call.");
DEFINE_int32(decode_tokens, 256, "D: tokens generated after the prompt, the first sampled from the prefill logits.");
DEFINE_uint64(seed, 0, "SplitMix64 seed of the token ids.");
DEFINE_int32(cpu_threads, -1, "As llama_main: -1 = cpuinfo's count of performant cores.");

namespace llm = ::executorch::extension::llm;
using ::executorch::extension::Module;
using ::executorch::runtime::Error;

namespace {

// CoreAIRuntime.randomPrompt / MLXRuntime.nativeBenchmark, step for step.
std::vector<uint64_t> splitmix_ids(int n, uint64_t seed, uint64_t vocab) {
  std::vector<uint64_t> ids(n);
  uint64_t state = seed + 0x9E3779B97F4A7C15ULL;
  for (int i = 0; i < n; ++i) {
    state += 0x9E3779B97F4A7C15ULL;
    uint64_t z = state;
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    ids[i] = (z ^ (z >> 31)) % vocab;
  }
  return ids;
}

double rss_mib() {
  return llm::get_rss_bytes() / 1024.0 / 1024.0;
}

} // namespace

int main(int argc, char** argv) {
  gflags::ParseCommandLineFlags(&argc, &argv, true);
  ::executorch::runtime::runtime_init();
  const int P = FLAGS_prefill_tokens;
  const int D = FLAGS_decode_tokens;
  if (FLAGS_model_path.empty() || FLAGS_tokenizer_path.empty() || P < 1 || D < 1) {
    ET_LOG(Error, "et_native_bench needs --model_path, --tokenizer_path, --prefill_tokens >= 1, --decode_tokens >= 1");
    return 1;
  }

#if defined(ET_USE_THREADPOOL)
  // llama_main's thread setup (examples/models/llama/main.cpp)
  const uint32_t threads = FLAGS_cpu_threads == -1
      ? ::executorch::extension::cpuinfo::get_num_performant_cores()
      : static_cast<uint32_t>(FLAGS_cpu_threads);
  ET_LOG(Info, "Resetting threadpool with num threads = %d", threads);
  if (threads > 0) {
    ::executorch::extension::threadpool::get_threadpool()->_unsafe_reset_threadpool(threads);
  }
#endif

  std::unique_ptr<::tokenizers::Tokenizer> tokenizer = llm::load_tokenizer(FLAGS_tokenizer_path);
  if (!tokenizer || !tokenizer->is_loaded()) {
    ET_LOG(Error, "tokenizer %s did not load", FLAGS_tokenizer_path.c_str());
    return 1;
  }

  // create_text_llm_runner's components, built as it builds them
  auto module = std::make_unique<Module>(
      FLAGS_model_path,
      Module::LoadMode::MmapUseMlockIgnoreErrors,
      nullptr, // event tracer
      nullptr, // memory allocator
      std::make_unique<::executorch::extension::CPUCachingAllocator>(10 * 1024 * 1024));
  auto metadata_result = llm::get_llm_metadata(tokenizer.get(), module.get());
  if (metadata_result.error() != Error::Ok) {
    ET_LOG(Error, "reading the .pte metadata failed");
    return 1;
  }
  const auto metadata = metadata_result.get();
  auto method_names = module->method_names();
  if (!method_names.ok() || method_names.get().count(llm::kForwardMethod) == 0) {
    ET_LOG(Error, "the .pte has no '%s' method (a prefill/decode two-method export is outside this harness)",
           llm::kForwardMethod);
    return 1;
  }
  auto eos_ids = std::make_unique<std::unordered_set<uint64_t>>(
      llm::get_eos_ids(tokenizer.get(), module.get()));
  auto io_manager = std::make_unique<llm::IOManager>(*module);
  const int64_t vocab = metadata.at(llm::kVocabSize);
  const bool use_kv_cache = metadata.at(llm::kUseKVCache);
  const bool dynamic_shape = metadata.at(llm::kEnableDynamicShape);
  const int64_t max_seq_len = metadata.at(llm::kMaxSeqLen);
  const int64_t max_context_len = metadata.at(llm::kMaxContextLen);
  auto stats = std::make_unique<llm::Stats>();
  auto decoder = std::make_unique<llm::TextDecoderRunner>(
      module.get(), io_manager.get(), llm::kForwardMethod,
      std::make_unique<llm::Sampler>(static_cast<int32_t>(vocab), 0.0f), stats.get());
  auto prefiller = std::make_unique<llm::TextPrefiller>(
      decoder.get(), use_kv_cache, dynamic_shape, max_seq_len);
  auto generator = std::make_unique<llm::TextTokenGenerator>(
      tokenizer.get(), decoder.get(), use_kv_cache, std::move(eos_ids), stats.get());
  if (static_cast<int64_t>(P) + D > max_context_len) {
    ET_LOG(Error, "P + D = %d > get_max_context_len %" PRId64, P + D, max_context_len);
    return 1;
  }

  // TextLLMRunner::load, timed where TextLLMRunner::generate times it
  stats->model_load_start_ms = llm::time_in_ms();
  if (prefiller->load() != Error::Ok || io_manager->load() != Error::Ok ||
      generator->load() != Error::Ok) {
    ET_LOG(Error, "loading the forward method failed");
    return 1;
  }
  stats->model_load_end_ms = llm::time_in_ms();
  ET_LOG(Info, "RSS after loading model: %f MiB (0 if unsupported)", rss_mib());

  std::vector<uint64_t> ids = splitmix_ids(P, FLAGS_seed, static_cast<uint64_t>(vocab));
  stats->inference_start_ms = llm::time_in_ms();
  stats->model_execution_start_ms = 0;
  stats->model_execution_end_ms = 0;
  int64_t pos = 0;
  auto prefill_result = prefiller->prefill(ids, pos); // advances pos by P
  if (!prefill_result.ok()) {
    ET_LOG(Error, "prefill failed: error %d", static_cast<int>(prefill_result.error()));
    return 1;
  }
  const uint64_t first_token = prefill_result.get();
  stats->first_token_ms = llm::time_in_ms();
  stats->prompt_eval_end_ms = llm::time_in_ms();
  ET_LOG(Info, "RSS after prompt prefill: %f MiB (0 if unsupported)", rss_mib());
  const int64_t pos_after_prefill = pos;

  std::vector<uint64_t> tokens = ids;
  tokens.push_back(first_token);
  generator->set_ignore_eos(true);
  int64_t callbacks = 0;
  auto generate_result = generator->generate(
      tokens, pos, D - 1, 0.0f, [&callbacks](const std::string&) { ++callbacks; });
  if (!generate_result.ok()) {
    ET_LOG(Error, "decode failed: error %d", static_cast<int>(generate_result.error()));
    return 1;
  }
  const int64_t steps = generate_result.get();
  stats->inference_end_ms = llm::time_in_ms();
  ET_LOG(Info, "RSS after finishing text generation: %f MiB (0 if unsupported)", rss_mib());
  stats->num_prompt_tokens = P;
  stats->num_generated_tokens = steps;
  llm::print_report(*stats);

  const int64_t chunks = P > max_seq_len ? (P + max_seq_len - 1) / max_seq_len : 1;
  const int64_t forwards = (dynamic_shape || !use_kv_cache) ? chunks : P;
  const int64_t generated = 1 + steps; // the prefill-sampled token + the decode loop's
  const bool counts_ok = pos_after_prefill == P && steps == D - 1 && generated == D;
  std::string head;
  for (size_t i = 0; i < ids.size() && i < 8; ++i) {
    head += (i ? "," : "") + std::to_string(ids[i]);
  }
  printf(
      "ET_NATIVE_BENCH_%s requested_prefill=%d requested_decode=%d prefill_tokens=%" PRId64
      " prefill_calls=1 prefill_chunks=%" PRId64 " prefill_forwards=%" PRId64
      " sampled_from_prefill=1 decode_forward_steps=%" PRId64 " generated_tokens=%" PRId64
      " token_callbacks=%" PRId64 " ignore_eos=1 sampler=greedy seed=%" PRIu64 " vocab=%" PRId64
      " ids_head=%s max_seq_len=%" PRId64 " max_context_len=%" PRId64
      " enable_dynamic_shape=%d use_kv_cache=%d\n",
      counts_ok ? "OK" : "COUNT_MISMATCH", P, D, pos_after_prefill, chunks, forwards, steps,
      generated, callbacks, static_cast<uint64_t>(FLAGS_seed), vocab, head.c_str(), max_seq_len,
      max_context_len, dynamic_shape ? 1 : 0, use_kv_cache ? 1 : 0);
  fflush(stdout);
  return counts_ok ? 0 : 3;
}
