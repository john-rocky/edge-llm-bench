// C shim around LiteRT-LM omni/asr for the edge-llm-bench iPhone leg of the
// asr-rtf-* task family. Mirrors omni/asr/asr_runner.cc (AsrEngine +
// FileAudioSource, the engine's default streaming protocol) so the phone rows
// are the same instrument as the Mac and Android rows, minus the process
// launch: the app calls this once per run in a fresh process.
#ifndef EDGE_LLM_BENCH_IOS_ASR_BENCH_SHIM_H_
#define EDGE_LLM_BENCH_IOS_ASR_BENCH_SHIM_H_

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct AsrBenchRequest {
  const char* model_name;        // omni/asr model_metadata.json key
  const char* metadata_path;     // model_metadata.json (empty = embedded)
  const char* model_path;        // the artifact (.tflite / .litertlm)
  const char* cache_dir;         // holds <model_name>_tokenizer.json
  const char* backend;           // "cpu" | "gpu"
  int num_threads;               // 4
  float overlap_ratio;           // 0.4
  const char* text_merger_type;  // "timestamp" | "levenshtein"
  const char* audio_path;        // the stream WAV
} AsrBenchRequest;

typedef struct AsrBenchResult {
  int ok;                          // 1 = ProcessNext loop reached OutOfRange and Flush ran
  double t_create_engine_s;        // AsrEngine::Create wall (model load + compile)
  double t_create_session_s;       // CreateSession wall
  double t_process_s;              // "Starting" -> "Finished" wall (the chunk loop incl. flush)
  double t_first_text_s;           // "Starting" -> first non-empty confirmed text (-1 = none)
  int text_chunks;                 // non-empty confirmed_text outputs from ProcessNext
  char* transcript;                // malloc'd, caller frees; confirmed texts joined by " "
  char* error;                     // malloc'd status string when ok == 0 (NULL otherwise)
} AsrBenchResult;

// Runs one transcription. Logs "Starting speech recognition" / "Finished speech
// recognition" through absl like asr_runner does. `text_cb` (optional) receives
// each confirmed text as it is produced.
int asr_bench_run(const AsrBenchRequest* req,
                  void (*text_cb)(const char* text, void* user_data),
                  void* user_data, AsrBenchResult* out);

void asr_bench_result_free(AsrBenchResult* out);

// The LiteRT-LM commit this library was built from (set at build time).
const char* asr_bench_engine_version(void);

#ifdef __cplusplus
}
#endif

#endif  // EDGE_LLM_BENCH_IOS_ASR_BENCH_SHIM_H_
