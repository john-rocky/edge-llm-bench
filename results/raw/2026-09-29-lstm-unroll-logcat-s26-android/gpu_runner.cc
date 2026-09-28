// Adapted from GLiNER2.5 round4; provenance.json records the exact source.
// LiteRT 2.2.0 CompiledModel C API, six named float32 inputs, CPU or GPU only.
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#include <unistd.h>
#include <atomic>
#include <thread>
#include <mutex>
#include <condition_variable>

#include "litert/c/litert_compiled_model.h"
#include "litert/c/litert_environment.h"
#include "litert/c/litert_model.h"
#include "litert/c/litert_opaque_options.h"
#include "litert/c/litert_options.h"
#include "litert/c/litert_profiler.h"
#include "litert/c/litert_tensor_buffer.h"
#include "litert/c/litert_tensor_buffer_requirements.h"

namespace fs = std::filesystem;
using Clock = std::chrono::steady_clock;

std::string Quote(const std::string& input) {
  std::ostringstream out;
  out << '"';
  for (unsigned char c : input) {
    if (c == '"' || c == '\\') out << '\\' << c;
    else if (c == '\n') out << "\\n";
    else if (c == '\r') out << "\\r";
    else if (c == '\t') out << "\\t";
    else if (c < 32) out << "\\u" << std::hex << std::setw(4)
                         << std::setfill('0') << static_cast<int>(c) << std::dec;
    else out << c;
  }
  out << '"';
  return out.str();
}

template <class T>
std::string Number(T value) {
  std::ostringstream out;
  out << std::setprecision(12) << value;
  return out.str();
}

void Check(LiteRtStatus status, const char* operation) {
  if (status != kLiteRtStatusOk) {
    throw std::runtime_error(std::string(operation) + " status=" + Number(status));
  }
}
#define CHECK(call) Check((call), #call)

double Elapsed(Clock::time_point start) {
  return std::chrono::duration<double, std::milli>(Clock::now() - start).count();
}

void WriteText(const fs::path& path, const std::string& value) {
  std::ofstream file(path);
  file << value << '\n';
  if (!file) throw std::runtime_error("Cannot write " + path.string());
}

struct Record {
  std::vector<std::pair<std::string, std::string>> fields;
  void Put(const std::string& key, const std::string& json) {
    for (auto& item : fields) if (item.first == key) { item.second = json; return; }
    fields.push_back({key, json});
  }
  std::string Json() const {
    std::string out = "{";
    for (size_t i = 0; i < fields.size(); ++i) {
      if (i) out += ",";
      out += "\n  " + Quote(fields[i].first) + ": " + fields[i].second;
    }
    return out + "\n}";
  }
};

std::string JsonArray(const std::vector<std::string>& values) {
  std::string out = "[";
  for (size_t i = 0; i < values.size(); ++i) {
    if (i) out += ",";
    out += values[i];
  }
  return out + "]";
}

// Linux /proc reports kB in KiB (1024 bytes); no host-side memory estimate.
struct MemorySample { long long rss_kib = 0, hwm_kib = 0; };
MemorySample ReadMemory() {
  MemorySample out;
  std::ifstream input("/proc/self/status");
  std::string line;
  while (std::getline(input, line)) {
    std::istringstream row(line); std::string key, unit; long long value;
    if (row >> key >> value >> unit) {
      if (key == "VmRSS:") out.rss_kib = value;
      if (key == "VmHWM:") out.hwm_kib = value;
    }
  }
  return out;
}
void PutMemory(Record& report) {
  const auto sample = ReadMemory();
  report.Put("peak_rss_bytes", Number(sample.hwm_kib * 1024));
  report.Put("rss_bytes", Number(sample.rss_kib * 1024));
  report.Put("memory_source", Quote("/proc/self/status VmHWM and VmRSS; kB converted with 1024"));
}
struct MemoryMonitor {
  fs::path folder;
  std::mutex lock; std::condition_variable wake; bool stopped = false;
  std::thread thread;
  Clock::time_point started = Clock::now();
  void Sample() {
    Record record; PutMemory(record);
    record.Put("pid", Number(getpid()));
    record.Put("elapsed_ms", Number(Elapsed(started)));
    const auto temporary = folder / "memory.json.tmp";
    WriteText(temporary, record.Json());
    fs::rename(temporary, folder / "memory.json");
  }
  explicit MemoryMonitor(const fs::path& path) : folder(path) {
    Sample();
    thread = std::thread([this]() {
      std::unique_lock<std::mutex> guard(lock);
      while (!wake.wait_for(guard, std::chrono::seconds(1), [this]() { return stopped; })) {
        try { Sample(); } catch (...) {}
      }
    });
  }
  ~MemoryMonitor() {
    { std::lock_guard<std::mutex> guard(lock); stopped = true; }
    wake.notify_one(); thread.join();
    try { Sample(); } catch (...) {}
  }
};

struct Handles {
  LiteRtEnvironment env = nullptr;
  LiteRtModel model = nullptr;
  LiteRtOptions options = nullptr;
  LiteRtCompiledModel compiled = nullptr;
  std::vector<LiteRtTensorBuffer> inputs;
  LiteRtTensorBuffer output = nullptr;
  ~Handles() {
    for (auto input : inputs) if (input) LiteRtDestroyTensorBuffer(input);
    if (output) LiteRtDestroyTensorBuffer(output);
    if (compiled) LiteRtDestroyCompiledModel(compiled);
    if (options) LiteRtDestroyOptions(options);
    if (model) LiteRtDestroyModel(model);
    if (env) LiteRtDestroyEnvironment(env);
  }
};

void AddToml(LiteRtOptions options, const char* identifier, const std::string& toml) {
  // Exact payload identifiers/TOML keys are reused from the accepted GLiNER2.5
  // v2.2.0 runner. provenance.json pins that source and both runtime libraries.
  void* payload = std::malloc(toml.size() + 1);
  if (!payload) throw std::bad_alloc();
  std::memcpy(payload, toml.c_str(), toml.size() + 1);
  LiteRtOpaqueOptions opaque = nullptr;
  const auto status = LiteRtCreateOpaqueOptions(identifier, payload, std::free, &opaque);
  if (status != kLiteRtStatusOk) std::free(payload);
  Check(status, "LiteRtCreateOpaqueOptions");
  CHECK(LiteRtAddOpaqueOptions(options, opaque));
}

size_t FloatCount(const LiteRtRankedTensorType& type) {
  if (type.element_type != kLiteRtElementTypeFloat32)
    throw std::runtime_error("Expected float32 model I/O");
  size_t count = 1;
  for (unsigned i = 0; i < type.layout.rank; ++i) {
    if (type.layout.dimensions[i] <= 0) throw std::runtime_error("Expected fixed shape");
    count *= type.layout.dimensions[i];
  }
  return count;
}

std::string Shape(const LiteRtRankedTensorType& type) {
  std::vector<std::string> dims;
  for (unsigned i = 0; i < type.layout.rank; ++i)
    dims.push_back(Number(type.layout.dimensions[i]));
  return JsonArray(dims);
}

LiteRtTensorBuffer MakeBuffer(Handles& h, const LiteRtRankedTensorType& type, bool input, int index = 0) {
  LiteRtTensorBufferRequirements req = nullptr;
  if (input) CHECK(LiteRtGetCompiledModelInputBufferRequirements(h.compiled, 0, index, &req));
  else CHECK(LiteRtGetCompiledModelOutputBufferRequirements(h.compiled, 0, 0, &req));
  LiteRtTensorBuffer buffer = nullptr;
  CHECK(LiteRtCreateManagedTensorBufferFromRequirements(h.env, &type, req, &buffer));
  size_t packed = 0;
  CHECK(LiteRtGetTensorBufferPackedSize(buffer, &packed));
  if (packed != FloatCount(type) * sizeof(float)) {
    LiteRtDestroyTensorBuffer(buffer);
    throw std::runtime_error("Packed buffer size does not match model shape");
  }
  return buffer;
}

std::vector<float> ReadFloats(const fs::path& path, size_t count) {
  if (fs::file_size(path) != count * sizeof(float))
    throw std::runtime_error("Fixture bytes do not match model input: " + path.string());
  std::vector<float> values(count);
  std::ifstream in(path, std::ios::binary);
  in.read(reinterpret_cast<char*>(values.data()), values.size() * sizeof(float));
  if (!in) throw std::runtime_error("Cannot read input " + path.string());
  for (float x : values) if (!std::isfinite(x))
    throw std::runtime_error("Input contains a nonfinite value");
  return values;
}

double Invoke(Handles& h, const std::vector<std::vector<float>>& inputs, std::vector<float>& output) {
  // End-to-end per-fixture latency includes input upload and synchronized readback.
  const auto started = Clock::now();
  void* bytes = nullptr;
  for (size_t i = 0; i < inputs.size(); ++i) {
    CHECK(LiteRtLockTensorBuffer(h.inputs[i], &bytes, kLiteRtTensorBufferLockModeWrite));
    std::memcpy(bytes, inputs[i].data(), inputs[i].size() * sizeof(float));
    CHECK(LiteRtUnlockTensorBuffer(h.inputs[i]));
  }
  CHECK(LiteRtRunCompiledModel(h.compiled, 0, h.inputs.size(), h.inputs.data(), 1, &h.output));
  CHECK(LiteRtLockTensorBuffer(h.output, &bytes, kLiteRtTensorBufferLockModeRead));
  std::memcpy(output.data(), bytes, output.size() * sizeof(float));
  CHECK(LiteRtUnlockTensorBuffer(h.output));
  return Elapsed(started);
}


std::vector<std::string> kInputNames;

struct Fixture {
  std::string id;
  std::vector<std::string> files;
};

bool SafeName(const std::string& value) {
  if (value.empty() || value == "." || value == "..") return false;
  for (unsigned char c : value)
    if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
          (c >= '0' && c <= '9') || c == '_' || c == '-' || c == '.')) return false;
  return true;
}

std::vector<std::string> SplitTabs(const std::string& line) {
  std::vector<std::string> fields;
  std::istringstream stream(line);
  std::string field;
  while (std::getline(stream, field, '\t')) fields.push_back(field);
  return fields;
}

std::vector<Fixture> ReadManifest(const fs::path& path) {
  std::ifstream file(path);
  if (!file) throw std::runtime_error("Cannot read fixture manifest " + path.string());
  std::string line;
  if (!std::getline(file, line) || line != "litert_fixture_pack_v1")
    throw std::runtime_error("Invalid fixture manifest format");
  if (!std::getline(file, line)) throw std::runtime_error("Missing input manifest header");
  auto header = SplitTabs(line);
  if (header.size() < 2 || header.front() != "id") throw std::runtime_error("Invalid manifest input header");
  kInputNames.assign(header.begin() + 1, header.end());
  std::set<std::string> unique_inputs;
  for (const auto& name : kInputNames)
    if (!SafeName(name) || !unique_inputs.insert(name).second) throw std::runtime_error("Invalid or duplicate input name");
  std::set<std::string> ids;
  std::vector<Fixture> rows;
  while (std::getline(file, line)) {
    auto fields = SplitTabs(line);
    if (fields.size() != kInputNames.size() + 1) throw std::runtime_error("Invalid manifest row");
    for (const auto& field : fields)
      if (!SafeName(field)) throw std::runtime_error("Unsafe manifest field");
    if (!ids.insert(fields.front()).second) throw std::runtime_error("Duplicate fixture id");
    rows.push_back({fields.front(), std::vector<std::string>(fields.begin() + 1, fields.end())});
  }
  if (rows.empty()) throw std::runtime_error("Empty fixture manifest");
  return rows;
}


int main(int argc, char** argv) {
  if (argc != 10) {
    std::cerr << "Usage: gpu_runner MODEL INPUT_DIR OUTPUT_DIR {cpu|fp32|default|single} REPS WARMUPS LIB_DIR MANIFEST_TSV TIME_LIMIT_SECONDS\n";
    return 2;
  }
  const fs::path output_dir = argv[3];
  const std::string precision = argv[4];
  const bool cpu = precision == "cpu";
  const bool single = precision == "single";
  Record report;
  report.Put("status", Quote("RUNNING"));
  report.Put("runtime", Quote("LiteRT 2.2.0 native CompiledModel C API"));
  report.Put("runner_build", Quote("synthetic-lstm-compile-v1"));
  report.Put("pid", Number(getpid()));
  report.Put("model", Quote(argv[1]));
  report.Put("precision", Quote(precision));
  report.Put("hardware_accelerators", Quote(cpu ? "CPU only (bitmask 1)" : "GPU only (bitmask 2)"));
  report.Put("timing_scope", Quote("all input lock/write/unlock + CompiledModel run + output lock/read/unlock; no file I/O"));
  std::string stage = "arguments";
  const auto run_started = Clock::now();
  try {
    fs::create_directories(output_dir);
    MemoryMonitor memory(output_dir);
    const int reps = std::stoi(argv[5]), warmups = std::stoi(argv[6]);
    if ((precision == "default" || single) ? (reps != 1 || warmups != 0) : (reps != 5 || warmups != 2))
      throw std::runtime_error("Gates require 5 reps/2 warmups; default single requires 1 rep/0 warmups");
    const int time_limit = std::stoi(argv[9]);
    if (time_limit < 1 || time_limit > 3600) throw std::runtime_error("Invalid execution time limit");
    alarm(static_cast<unsigned>(time_limit));
    report.Put("hard_time_limit_seconds", Number(time_limit));
    const auto fixtures = ReadManifest(argv[8]);
    report.Put("manifest", Quote(argv[8]));
    report.Put("fixture_count", Number(fixtures.size()));
    if (!cpu && precision != "fp32" && precision != "default" && !single) throw std::runtime_error("Unknown precision");
    report.Put("repetitions_per_fixture", Number(reps));
    report.Put("warmups_per_fixture", Number(warmups));
    Handles h;
    LiteRtEnvOption env_option{};
    env_option.tag = kLiteRtEnvOptionTagRuntimeLibraryDir;
    env_option.value.type = kLiteRtAnyTypeString;
    env_option.value.str_value = argv[7];
    stage = "environment";
    CHECK(LiteRtCreateEnvironment(1, &env_option, &h.env));
    stage = "model_load";
    CHECK(LiteRtCreateModelFromFile(h.env, argv[1], &h.model));
    LiteRtSignature signature = nullptr;
    LiteRtParamIndex signature_count = 0, inputs = 0, outputs = 0;
    CHECK(LiteRtGetNumModelSignatures(h.model, &signature_count));
    if (signature_count != 1) throw std::runtime_error("Expected one signature");
    CHECK(LiteRtGetModelSignature(h.model, 0, &signature));
    CHECK(LiteRtGetNumSignatureInputs(signature, &inputs));
    CHECK(LiteRtGetNumSignatureOutputs(signature, &outputs));
    if (inputs != kInputNames.size() || outputs != 1) throw std::runtime_error("Expected exactly the manifest inputs and one output");
    std::vector<LiteRtRankedTensorType> input_types(inputs);
    std::vector<std::string> input_names, input_report;
    for (size_t i = 0; i < inputs; ++i) {
      LiteRtTensor tensor = nullptr;
      CHECK(LiteRtGetSignatureInputTensorByIndex(signature, i, &tensor));
      CHECK(LiteRtGetRankedTensorType(tensor, &input_types[i]));
      const char* signature_name = nullptr;
      CHECK(LiteRtGetSignatureInputName(signature, i, &signature_name));
      FloatCount(input_types[i]);  // Require fixed float32 input tensors.
      const std::string sig_name = signature_name;
      const std::string name = sig_name;
      if (std::find(kInputNames.begin(), kInputNames.end(), name) == kInputNames.end() ||
          std::find(input_names.begin(), input_names.end(), name) != input_names.end())
        throw std::runtime_error("Unknown or duplicate input signature name: " + name);
      input_names.push_back(name);
      Record entry;
      entry.Put("logical_name", Quote(name));
      entry.Put("signature_name", Quote(signature_name));
      entry.Put("shape", Shape(input_types[i]));
      input_report.push_back(entry.Json());
    }
    report.Put("inputs_in_runtime_order", JsonArray(input_report));
    LiteRtTensor output_tensor = nullptr;
    LiteRtRankedTensorType output_type{};
    CHECK(LiteRtGetSignatureOutputTensorByIndex(signature, 0, &output_tensor));
    CHECK(LiteRtGetRankedTensorType(output_tensor, &output_type));
    const size_t output_count = FloatCount(output_type);
    if (output_type.layout.rank != 4 || output_type.layout.dimensions[0] != 1 ||
        output_type.layout.dimensions[1] != 1 || output_count < 1)
      throw std::runtime_error("Expected a sole packed rank-4 output [1,1,...,...]");
    report.Put("output_shape", Shape(output_type));
    CHECK(LiteRtCreateOptions(&h.options));
    CHECK(LiteRtSetOptionsHardwareAccelerators(h.options, cpu ? kLiteRtHwAcceleratorCpu : kLiteRtHwAcceleratorGpu));
    AddToml(h.options, "runtime_options_string", "enable_profiling = false\nerror_reporter_mode = 1\n");
    if (precision == "fp32" || single) {
      const std::string gpu_toml = "precision = 2\n";
      report.Put("gpu_options_toml", Quote(gpu_toml));
      AddToml(h.options, "gpu_options", gpu_toml);
    }
    if (precision == "default") report.Put("gpu_options_toml", Quote("omitted: runtime DEFAULT precision"));
    stage = cpu ? "cpu_compile" : "gpu_compile";
    report.Put("stage", Quote(stage));
    PutMemory(report);
    WriteText(output_dir / "run.json", report.Json());
    const auto compile_start = Clock::now();
    alarm(static_cast<unsigned>(std::min(900, time_limit)));
    report.Put("compile_timeout_seconds", Number(std::min(900, time_limit)));
    WriteText(output_dir / "run.json", report.Json());
    const auto compile_status = LiteRtCreateCompiledModel(h.env, h.model, h.options, &h.compiled);
    report.Put("compile_ms", Number(Elapsed(compile_start)));
    report.Put("compile_status", Number(compile_status));
    PutMemory(report);
    const auto compiled_memory = ReadMemory();
    report.Put("compile_peak_rss_bytes", Number(compiled_memory.hwm_kib * 1024));
    report.Put("post_compile_loaded_rss_bytes", Number(compiled_memory.rss_kib * 1024));
    Check(compile_status, "LiteRtCreateCompiledModel");
    const int remaining = time_limit - static_cast<int>(Elapsed(run_started) / 1000);
    if (remaining <= 0) throw std::runtime_error("Native total deadline reached");
    alarm(static_cast<unsigned>(remaining));
    bool fully_accelerated = false;
    CHECK(LiteRtCompiledModelIsFullyAccelerated(h.compiled, &fully_accelerated));
    report.Put("is_fully_accelerated", fully_accelerated ? "true" : "false");
    if (!cpu && !fully_accelerated) throw std::runtime_error("GPU gate rejects partial acceleration");
    report.Put("cpu_fallback_allowed", "false");
    stage = "allocate_buffers";
    for (size_t i = 0; i < inputs; ++i) h.inputs.push_back(MakeBuffer(h, input_types[i], true, i));
    h.output = MakeBuffer(h, output_type, false);
    std::vector<std::string> cases;
    for (const auto& fixture : fixtures) {
      const std::string& id = fixture.id;
      stage = "fixture:" + id;
      std::vector<std::vector<float>> input_values;
      for (size_t i = 0; i < inputs; ++i)
        input_values.push_back(ReadFloats(fs::path(argv[2]) / fixture.files.at(static_cast<size_t>(std::find(kInputNames.begin(), kInputNames.end(), input_names[i]) - kInputNames.begin())), FloatCount(input_types[i])));
      std::vector<float> output(output_count);
      bool all_warmups_finite = true, all_repetitions_finite = true;
      for (int w = 0; w < warmups; ++w) {
        stage = "fixture:" + id + ":warmup:" + Number(w);
        Invoke(h, input_values, output);
        for (float value : output)
          if (!std::isfinite(value)) { all_warmups_finite = false;
            if (precision != "default") throw std::runtime_error("Nonfinite warmup readback"); }
      }
      std::vector<double> times;
      for (int r = 0; r < reps; ++r) {
        stage = "fixture:" + id + ":timed:" + Number(r);
        times.push_back(Invoke(h, input_values, output));
        for (float value : output)
          if (!std::isfinite(value)) { all_repetitions_finite = false;
            if (precision != "default") throw std::runtime_error("Nonfinite timed readback"); }
      }
      std::ofstream dump(output_dir / (id + ".f32"), std::ios::binary);
      dump.write(reinterpret_cast<const char*>(output.data()), output.size() * sizeof(float));
      if (!dump) throw std::runtime_error("Cannot save packed output");
      std::vector<std::string> raw_times;
      for (double value : times) raw_times.push_back(Number(value));
      std::sort(times.begin(), times.end());
      Record row;
      row.Put("id", Quote(id));
      row.Put("output_file", Quote(id + ".f32"));
      row.Put("all_warmups_finite", all_warmups_finite ? "true" : "false");
      row.Put("all_repetitions_finite", all_repetitions_finite ? "true" : "false");
      row.Put("latency_ms", JsonArray(raw_times));
      row.Put("median_ms", Number((times[(times.size()-1)/2] + times[times.size()/2]) / 2));
      row.Put("min_ms", Number(times.front()));
      row.Put("max_ms", Number(times.back()));
      cases.push_back(row.Json());
      report.Put("fixtures", JsonArray(cases));
      WriteText(output_dir / "run.json", report.Json());
    }
    PutMemory(report);
    report.Put("steady_loaded_rss_bytes", Number(ReadMemory().rss_kib * 1024));
    report.Put("steady_rss_scope", Quote("After final readback, before destroying input/output buffers, CompiledModel, Model, Options or Environment"));
    report.Put("monitor_final_rss_scope", Quote("memory.json destructor sample is after resource teardown; it is not loaded steady RSS"));
    report.Put("status", Quote("EXECUTION_COMPLETE_PARITY_PENDING"));
    report.Put("stage", Quote("complete"));
    WriteText(output_dir / "run.json", report.Json());
    std::cout << report.Json() << std::endl;
    return 0;
  } catch (const std::exception& error) {
    report.Put("status", Quote("FAIL"));
    report.Put("stage", Quote(stage));
    report.Put("error", Quote(error.what()));
    PutMemory(report);
    try { WriteText(output_dir / "run.json", report.Json()); } catch (...) {}
    std::cerr << report.Json() << std::endl;
    return 1;
  }
}
