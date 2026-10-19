// tools/asr-qnn/burst_driver.cc
//
// asr-qnn-v1's in-process driver (docs/asr-qnn-v1.md): sherpa-onnx v1.13.8 built with the Qualcomm NPU
// (QNN), one process, the recognizer built once, a warm-up utterance decoded once outside the timing,
// then the utterances of --list one by one, one JSONL row each, in the shape of asr-burst-v1 (litert-samples
// AsrBenchTest + BenchJson, edge-llm-bench docs/asr-burst-v1.md).
//
// v1.13.8's C, C++ and JNI APIs carry no QNN settings for a NeMo CTC model, so this driver uses the
// classes sherpa-onnx's own executables use (sherpa-onnx/csrc) and takes their flags: OfflineRecognizerConfig
// registers --provider, --tokens, --nemo-ctc.qnn-backend-lib, ... exactly as sherpa-onnx-offline does.
//
// Pacing (--pace):
//   none   the utterances back to back.
//   burst  before each utterance a wait of at least --pace-gap-ms after the previous one ended and until
//          every cpufreq policy's scaling_max_freq is back at its cpuinfo_max_freq (read every
//          --pace-poll-ms, at most --pace-max-wait-s; then it starts anyway and the wait is marked).
//          While it runs the ceilings are read every --cap-poll-ms; an utterance during which one fell
//          more than --cap-line-pct is run once more after they are back and --retake-settle-s, and past
//          the line again it stays out of RTF_burst (counted). AsrBenchTest's BurstPacer / BurstRule.
// Timing: processing_seconds = ReadWave -> CreateStream -> AcceptWaveform (features) -> DecodeStream
//   (normalization, the QNN graph, CTC greedy search) -> GetResult, the span AsrBenchTest's sherpa engine
//   times (readWave -> createStream -> acceptWaveform -> decode -> getResult).
// stderr: "[asr-qnn] begin <id> <attempt>" and "[asr-qnn] end <id> <attempt> ..." around every attempt, so
//   sherpa's own lines (an input longer than the model's window is truncated, with a line) are attributed.
//
// Build: tools/asr-qnn/build.sh (sherpa-onnx-offline's flags and link line).
// Host self-test of the pacing, the cap rule, the list and the JSON: clang++ -std=c++17 -DHOST_TEST.

#include <dirent.h>
#include <time.h>
#include <unistd.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <condition_variable>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <functional>
#include <mutex>
#include <optional>
#include <set>
#include <sstream>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#ifndef HOST_TEST
#include <sys/system_properties.h>

#include "sherpa-onnx/csrc/offline-recognizer.h"
#include "sherpa-onnx/csrc/parse-options.h"
#include "sherpa-onnx/csrc/version.h"
#include "sherpa-onnx/csrc/wave-reader.h"
#endif

namespace {

constexpr int64_t kNsPerMs = 1000000;
[[maybe_unused]] const char kHarness[] = "asr-qnn-v1";

using Ceilings = std::vector<std::optional<int64_t>>;  // kHz per cpufreq policy; nullopt = not read

int64_t CeilDiv(int64_t a, int64_t b) { return (a + b - 1) / b; }

double Round3(double v) { return std::round(v * 1000.0) / 1000.0; }

// ---- JSON (rows in the shape tools/omni-eval/score.py and asr-burst-v1 read)

std::string JStr(const std::string &s) {
  std::string o = "\"";
  for (unsigned char c : s) {
    switch (c) {
      case '"': o += "\\\""; break;
      case '\\': o += "\\\\"; break;
      case '\n': o += "\\n"; break;
      case '\r': o += "\\r"; break;
      case '\t': o += "\\t"; break;
      default:
        if (c < 0x20) {
          char b[8];
          snprintf(b, sizeof(b), "\\u%04x", c);
          o += b;
        } else {
          o += static_cast<char>(c);
        }
    }
  }
  return o + "\"";
}

std::string JNum(double v) {
  if (!std::isfinite(v)) return "null";
  char b[40];
  snprintf(b, sizeof(b), "%.12g", v);
  return b;
}

std::string JInt(int64_t v) { return std::to_string(v); }
std::string JBool(bool v) { return v ? "true" : "false"; }
std::string JOpt(const std::optional<int64_t> &v) { return v ? JInt(*v) : "null"; }
[[maybe_unused]] std::string JOpt(const std::optional<double> &v) { return v ? JNum(*v) : "null"; }
[[maybe_unused]] std::string JOptStr(const std::optional<std::string> &v) { return v ? JStr(*v) : "null"; }

[[maybe_unused]] std::string JArr(const std::vector<std::string> &encoded) {
  std::string o = "[";
  for (size_t i = 0; i < encoded.size(); ++i) o += (i ? "," : "") + encoded[i];
  return o + "]";
}

// One JSON object, keys in insertion order; Put takes an encoded value.
class JObj {
 public:
  JObj &Put(const std::string &key, const std::string &encoded) {
    if (!body_.empty()) body_ += ",";
    body_ += JStr(key) + ":" + encoded;
    return *this;
  }
  std::string Str() const { return "{" + body_ + "}"; }

 private:
  std::string body_;
};

// ---- files

std::optional<std::string> ReadText(const std::string &path) {
  std::ifstream f(path);
  if (!f) return std::nullopt;
  std::stringstream ss;
  ss << f.rdbuf();
  std::string s = ss.str();
  while (!s.empty() && (s.back() == '\n' || s.back() == '\r' || s.back() == ' ')) s.pop_back();
  return s;
}

[[maybe_unused]] std::optional<int64_t> ReadLong(const std::string &path) {
  auto t = ReadText(path);
  if (!t || t->empty()) return std::nullopt;
  char *end = nullptr;
  long long v = strtoll(t->c_str(), &end, 10);
  if (end == t->c_str()) return std::nullopt;
  return static_cast<int64_t>(v);
}

// "Key:\tvalue" of /proc/self/status, the value trimmed.
std::optional<std::string> ProcStatus(const std::string &key) {
  std::ifstream f("/proc/self/status");
  std::string line;
  while (std::getline(f, line)) {
    if (line.compare(0, key.size() + 1, key + ":") == 0) {
      std::string v = line.substr(key.size() + 1);
      size_t a = v.find_first_not_of(" \t");
      return a == std::string::npos ? std::string() : v.substr(a);
    }
  }
  return std::nullopt;
}

[[maybe_unused]] std::optional<int64_t> ProcStatusKb(const std::string &key) {
  auto v = ProcStatus(key);
  if (!v) return std::nullopt;
  char *end = nullptr;
  long long kb = strtoll(v->c_str(), &end, 10);
  if (end == v->c_str()) return std::nullopt;
  return static_cast<int64_t>(kb);
}

// The cpuset line of /proc/self/cgroup ("…:cpuset:/top-app"), else every line joined with ';'.
std::optional<std::string> CpusetOf(const std::optional<std::string> &cgroup) {
  if (!cgroup) return std::nullopt;
  std::stringstream ss(*cgroup);
  std::string line, all;
  while (std::getline(ss, line)) {
    if (line.empty()) continue;
    if (line.find(":cpuset:") != std::string::npos) return line;
    all += (all.empty() ? "" : ";") + line;
  }
  return all;
}

// The CPUs of a list such as "0-5" or "0-3,6" (Cpus_allowed_list, related_cpus with spaces).
std::set<int> ParseCpuList(const std::optional<std::string> &spec) {
  std::set<int> out;
  if (!spec) return out;
  std::string s = *spec;
  for (char &c : s) {
    if (c == ',') c = ' ';
  }
  std::stringstream ss(s);
  std::string part;
  while (ss >> part) {
    size_t dash = part.find('-');
    int first = atoi(part.substr(0, dash).c_str());
    int last = dash == std::string::npos ? first : atoi(part.substr(dash + 1).c_str());
    for (int i = first; i <= last; ++i) out.insert(i);
  }
  return out;
}

// ---- the cap rule (AsrBenchTest's Burst.kt, same numbers)

// The largest (1 - min / hw) * 100 over the policies, one decimal; nullopt when no policy was read.
// [only] keeps the policies at those indices (the policies of the CPUs the process may run on).
std::optional<double> CapDropPct(const Ceilings &min_khz, const Ceilings &hw_khz, const std::set<int> *only = nullptr) {
  std::optional<double> best;
  for (size_t i = 0; i < min_khz.size(); ++i) {
    if (only && !only->count(static_cast<int>(i))) continue;
    if (!min_khz[i] || i >= hw_khz.size() || !hw_khz[i] || *hw_khz[i] <= 0) continue;
    double d = std::max(0.0, (1.0 - static_cast<double>(*min_khz[i]) / static_cast<double>(*hw_khz[i])) * 100.0);
    if (!best || d > *best) best = d;
  }
  if (best) best = std::round(*best * 10.0) / 10.0;
  return best;
}

struct Clock {
  std::function<int64_t()> now_ns;
  std::function<void(int64_t)> sleep_ms;
};

// One wait: from the end of the previous utterance to the moment this one may start.
struct Wait {
  double waited_ms = 0;
  bool timed_out = false;
  int polls = 0;
  Ceilings ceilings;
};

class Pacer {
 public:
  Pacer(Ceilings hw, std::function<Ceilings()> read, Clock clock, int64_t min_gap_ms = 500, int64_t poll_ms = 200,
        int64_t max_wait_ms = 120000)
      : hw_(std::move(hw)), read_(std::move(read)), clock_(std::move(clock)), min_gap_ms_(min_gap_ms),
        poll_ms_(poll_ms), max_wait_ms_(max_wait_ms) {}

  // True when every policy whose maximum and ceiling were both read sits at its maximum.
  bool AtMax(const Ceilings &c) const {
    for (size_t i = 0; i < hw_.size(); ++i) {
      if (!hw_[i] || i >= c.size() || !c[i]) continue;
      if (*c[i] < *hw_[i]) return false;
    }
    return true;
  }

  Wait Await(int64_t since_ns) const {
    const int64_t gap_end = since_ns + min_gap_ms_ * kNsPerMs;
    const int64_t deadline = since_ns + max_wait_ms_ * kNsPerMs;
    int64_t t = clock_.now_ns();
    if (t < gap_end) clock_.sleep_ms(CeilDiv(gap_end - t, kNsPerMs));
    Wait w;
    while (true) {
      Ceilings c = read_();
      w.polls++;
      t = clock_.now_ns();
      if (AtMax(c) || t >= deadline) {
        w.waited_ms = static_cast<double>(t - since_ns) / 1e6;
        w.timed_out = !AtMax(c);
        w.ceilings = c;
        return w;
      }
      clock_.sleep_ms(std::min(poll_ms_, CeilDiv(deadline - t, kNsPerMs)));
    }
  }

 private:
  Ceilings hw_;
  std::function<Ceilings()> read_;
  Clock clock_;
  int64_t min_gap_ms_, poll_ms_, max_wait_ms_;
};

// The lowest ceiling per policy over the reads taken while one attempt ran (read from two threads).
class CeilingMin {
 public:
  explicit CeilingMin(const Ceilings &hw) : hw_(hw), min_(hw.size()) {}
  void Add(const Ceilings &c) {
    std::lock_guard<std::mutex> lock(mu_);
    reads_++;
    for (size_t i = 0; i < min_.size() && i < c.size(); ++i) {
      if (!c[i]) continue;
      min_[i] = min_[i] ? std::min(*min_[i], *c[i]) : *c[i];
    }
  }
  int Reads() {
    std::lock_guard<std::mutex> lock(mu_);
    return reads_;
  }
  Ceilings Min() {
    std::lock_guard<std::mutex> lock(mu_);
    return min_;
  }

 private:
  Ceilings hw_;
  std::mutex mu_;
  Ceilings min_;
  int reads_ = 0;
};

template <typename T>
struct Attempt {
  T value;
  Wait wait;
  int64_t start_ns = 0, end_ns = 0;
  Ceilings min_khz;
  int reads = 0;
  std::optional<double> drop_pct;
};

template <typename T>
struct Outcome {
  std::vector<Attempt<T>> attempts;
  bool excluded = false;
  const Attempt<T> &Final() const { return attempts.back(); }
};

// One utterance under the burst rule: wait, run once, and when the ceiling fell past the line during the
// run, wait until it is back plus the settle time, then run once more. The last attempt's fall decides
// whether the utterance counts; retake_allowed says no for an attempt that failed (recorded, not repeated).
class Rule {
 public:
  Rule(const Pacer *pacer, Ceilings hw, std::function<Ceilings()> read, Clock clock, double line_pct = 15.0,
       int64_t settle_ms = 5000)
      : pacer_(pacer), hw_(std::move(hw)), read_(std::move(read)), clock_(std::move(clock)), line_pct_(line_pct),
        settle_ms_(settle_ms) {}

  bool Over(const std::optional<double> &d) const { return d && *d > line_pct_; }

  template <typename T>
  Outcome<T> Utterance(int64_t prev_end_ns, const std::function<bool(const T &)> &retake_allowed,
                       const std::function<T(CeilingMin &)> &run) const {
    Outcome<T> out;
    out.attempts.push_back(Try<T>(pacer_->Await(prev_end_ns), run));
    const Attempt<T> &first = out.attempts.front();
    if (!Over(first.drop_pct) || !retake_allowed(first.value)) {
      out.excluded = Over(first.drop_pct);
      return out;
    }
    const int64_t first_end = first.end_ns;
    Wait back = pacer_->Await(first_end);
    clock_.sleep_ms(settle_ms_);
    back.waited_ms = static_cast<double>(clock_.now_ns() - first_end) / 1e6;
    out.attempts.push_back(Try<T>(back, run));
    out.excluded = Over(out.attempts.back().drop_pct);
    return out;
  }

 private:
  template <typename T>
  Attempt<T> Try(const Wait &wait, const std::function<T(CeilingMin &)> &run) const {
    CeilingMin min(hw_);
    min.Add(read_());
    Attempt<T> a;
    a.wait = wait;
    a.start_ns = clock_.now_ns();
    a.value = run(min);
    a.end_ns = clock_.now_ns();
    min.Add(read_());
    a.min_khz = min.Min();
    a.reads = min.Reads();
    a.drop_pct = CapDropPct(a.min_khz, hw_);
    return a;
  }

  const Pacer *pacer_;
  Ceilings hw_;
  std::function<Ceilings()> read_;
  Clock clock_;
  double line_pct_;
  int64_t settle_ms_;
};

// ---- the list: "id<TAB>wav<TAB>seconds" per line; a relative wav is resolved against the list's directory

struct Row {
  std::string id, wav;
  double seconds = 0;
};

std::vector<Row> ParseList(const std::string &text, const std::string &base_dir, std::string *error) {
  std::vector<Row> rows;
  std::stringstream ss(text);
  std::string line;
  int n = 0;
  while (std::getline(ss, line)) {
    ++n;
    if (!line.empty() && line.back() == '\r') line.pop_back();
    if (line.empty()) continue;
    std::vector<std::string> cols;
    size_t a = 0, b;
    while ((b = line.find('\t', a)) != std::string::npos) {
      cols.push_back(line.substr(a, b - a));
      a = b + 1;
    }
    cols.push_back(line.substr(a));
    if (cols.size() != 3) {
      *error = "list line " + std::to_string(n) + ": expected 3 tab-separated columns, got " + std::to_string(cols.size());
      return {};
    }
    char *end = nullptr;
    double sec = strtod(cols[2].c_str(), &end);
    if (end == cols[2].c_str()) {
      *error = "list line " + std::to_string(n) + ": seconds '" + cols[2] + "' is not a number";
      return {};
    }
    std::string wav = cols[1];
    if (!base_dir.empty() && !wav.empty() && wav[0] != '/') wav = base_dir + "/" + wav;
    rows.push_back({cols[0], wav, sec});
  }
  return rows;
}

std::optional<double> Median(std::vector<double> v) {
  if (v.empty()) return std::nullopt;
  std::sort(v.begin(), v.end());
  size_t mid = v.size() / 2;
  return v.size() % 2 ? v[mid] : (v[mid - 1] + v[mid]) / 2.0;
}

// One transcription attempt: the text, the wall seconds from opening the WAV to the text, the stage times.
struct Transcribed {
  std::string text;
  double seconds = 0;
  std::vector<std::pair<std::string, double>> stage_ms;
  std::optional<int64_t> feature_frames;  // read after the timing
  std::optional<std::string> error;
};

[[maybe_unused]] std::string StageJson(const std::vector<std::pair<std::string, double>> &stages) {
  JObj o;
  for (const auto &s : stages) o.Put(s.first, JNum(Round3(s.second)));
  return o.Str();
}

// The utterance row of asr-burst-v1 (BenchJson.utterance): window fields empty (one whole-utterance call),
// then the extras in order.
std::string UtteranceRow(const Row &row, const Transcribed &t, const std::vector<std::pair<std::string, std::string>> &extra) {
  JObj o;
  o.Put("type", JStr("utterance"))
      .Put("id", JStr(row.id))
      .Put("text", JStr(t.text))
      .Put("audio_seconds", JNum(row.seconds))
      .Put("processing_seconds", JNum(Round3(t.seconds)))
      .Put("windows", "0")
      .Put("empty_windows", "0")
      .Put("tokens", "[]")
      .Put("mel_ms", "[]")
      .Put("encode_ms", "[]")
      .Put("decode_ms", "[]");
  if (t.error) o.Put("error", JStr(*t.error));
  for (const auto &kv : extra) o.Put(kv.first, kv.second);
  return o.Str();
}

std::string CeilingsJson(const std::vector<std::string> &names, const Ceilings &c) {
  JObj o;
  for (size_t i = 0; i < names.size(); ++i) o.Put(names[i], JOpt(i < c.size() ? c[i] : std::nullopt));
  return o.Str();
}

}  // namespace

#ifndef HOST_TEST

namespace {

int64_t NowNs() {
  // CLOCK_BOOTTIME = SystemClock.elapsedRealtimeNanos, AsrBenchTest's clock.
  struct timespec ts;
  clock_gettime(CLOCK_BOOTTIME, &ts);
  return static_cast<int64_t>(ts.tv_sec) * 1000000000LL + ts.tv_nsec;
}

void SleepMs(int64_t ms) {
  if (ms > 0) std::this_thread::sleep_for(std::chrono::milliseconds(ms));
}

std::string IsoUtc() {
  time_t t = time(nullptr);
  struct tm g;
  gmtime_r(&t, &g);
  char b[32];
  strftime(b, sizeof(b), "%Y-%m-%dT%H:%M:%SZ", &g);
  return b;
}

std::string Prop(const char *name) {
  char v[PROP_VALUE_MAX] = {0};
  __system_property_get(name, v);
  return v;
}

std::vector<std::string> CpufreqPolicies() {
  std::vector<std::pair<int, std::string>> found;
  const char *dir = "/sys/devices/system/cpu/cpufreq";
  if (DIR *d = opendir(dir)) {
    while (struct dirent *e = readdir(d)) {
      std::string n = e->d_name;
      if (n.rfind("policy", 0) == 0) found.emplace_back(atoi(n.c_str() + 6), n);
    }
    closedir(d);
  }
  std::sort(found.begin(), found.end());
  std::vector<std::string> out;
  for (auto &p : found) out.push_back(std::string(dir) + "/" + p.second);
  return out;
}

std::string Basename(const std::string &p) {
  size_t s = p.rfind('/');
  return s == std::string::npos ? p : p.substr(s + 1);
}

std::string ProcessState() {
  auto cgroup = ReadText("/proc/self/cgroup");
  return JObj()
      .Put("cpus_allowed", JOptStr(ProcStatus("Cpus_allowed_list")))
      .Put("cpuset", JOptStr(CpusetOf(cgroup)))
      .Put("threads", JOptStr(ProcStatus("Threads")))
      .Put("vmhwm_kb", JOpt(ProcStatusKb("VmHWM")))
      .Put("vmrss_kb", JOpt(ProcStatusKb("VmRSS")))
      .Str();
}

// The distinct mapped .so paths that witness the NPU path: the QNN libraries, the FastRPC client, onnxruntime.
std::string MappedLibs() {
  std::ifstream f("/proc/self/maps");
  std::string line;
  std::vector<std::string> out;
  std::set<std::string> seen;
  while (std::getline(f, line)) {
    size_t s = line.find('/');
    if (s == std::string::npos) continue;
    std::string path = line.substr(s);
    if (path.size() < 3 || path.compare(path.size() - 3, 3, ".so") != 0) continue;
    std::string base = Basename(path);
    if (base.find("Qnn") == std::string::npos && base.find("rpc") == std::string::npos &&
        base.find("onnxruntime") == std::string::npos && base.find("sherpa") == std::string::npos) {
      continue;
    }
    if (seen.insert(path).second) out.push_back(JStr(path));
  }
  return JArr(out);
}

std::optional<int64_t> FileBytes(const std::string &path) {
  std::ifstream f(path, std::ios::binary | std::ios::ate);
  if (!f) return std::nullopt;
  return static_cast<int64_t>(f.tellg());
}

Transcribed TranscribeOnce(const sherpa_onnx::OfflineRecognizer &rec, const std::string &wav) {
  Transcribed out;
  const int64_t start = NowNs();
  int64_t t = start;
  auto stage = [&](const char *name) {
    int64_t n = NowNs();
    out.stage_ms.emplace_back(name, static_cast<double>(n - t) / 1e6);
    t = n;
  };
  int32_t sampling_rate = -1;
  bool ok = false;
  std::vector<float> samples = sherpa_onnx::ReadWave(wav, &sampling_rate, &ok);
  stage("read");
  if (!ok) {
    out.error = "ReadWave failed: " + wav;
    out.seconds = static_cast<double>(NowNs() - start) / 1e9;
    return out;
  }
  auto s = rec.CreateStream();
  stage("create_stream");
  s->AcceptWaveform(sampling_rate, samples.data(), static_cast<int32_t>(samples.size()));
  stage("accept_waveform");  // the features (fbank) are computed here
  rec.DecodeStream(s.get());
  stage("decode");  // NeMo normalization, the QNN graph (pad / truncate to the window), CTC greedy search
  out.text = s->GetResult().text;
  stage("get_result");
  out.seconds = static_cast<double>(NowNs() - start) / 1e9;
  // Outside the timing: the number of feature frames the model got before its pad / truncation.
  int32_t dim = s->FeatureDim();
  if (dim > 0) out.feature_frames = static_cast<int64_t>(s->GetFrames().size() / dim);
  return out;
}

// <tag>.ceil.log: every ceiling read of a burst run while an utterance ran (run), at its start and end
// (edge), and the waits' reads that were below the maximum (wait). AsrBenchTest's CeilingLog.
class CeilingLog {
 public:
  CeilingLog(const std::string &path, int64_t origin, const std::vector<std::string> &names, const Ceilings &hw)
      : f_(fopen(path.c_str(), "a")), origin_(origin), hw_(hw) {
    if (!f_) return;
    fprintf(f_, "# elapsed_ms\tid\tattempt\tphase");
    for (const auto &n : names) fprintf(f_, "\t%s_scaling_max_kHz", n.c_str());
    fprintf(f_, "\n# hw_kHz");
    for (const auto &h : hw) fprintf(f_, "\t%s", h ? std::to_string(*h).c_str() : "-");
    fprintf(f_, "\n");
  }
  ~CeilingLog() {
    if (f_) fclose(f_);
  }
  void SetContext(const std::string &c) {
    std::lock_guard<std::mutex> lock(mu_);
    context_ = c;
  }
  void Add(const char *phase, const Ceilings &c) {
    std::lock_guard<std::mutex> lock(mu_);
    if (!f_) return;
    if (strcmp(phase, "wait") == 0) {
      bool at_max = true;
      for (size_t i = 0; i < hw_.size(); ++i) {
        if (hw_[i] && i < c.size() && c[i] && *c[i] < *hw_[i]) at_max = false;
      }
      if (at_max) return;
    }
    fprintf(f_, "%lld\t%s\t%s", static_cast<long long>((NowNs() - origin_) / kNsPerMs), context_.c_str(), phase);
    for (const auto &v : c) fprintf(f_, "\t%s", v ? std::to_string(*v).c_str() : "-");
    fprintf(f_, "\n");
  }
  void Flush() {
    std::lock_guard<std::mutex> lock(mu_);
    if (f_) fflush(f_);
  }

 private:
  FILE *f_;
  int64_t origin_;
  Ceilings hw_;
  std::mutex mu_;
  std::string context_ = "-\t0";
};

// Runs block while a thread adds every policy's ceiling to min every every_ms.
template <typename T>
T PollCeilings(CeilingMin &min, int64_t every_ms, const std::function<Ceilings()> &read, CeilingLog *log,
               const std::function<T()> &block) {
  std::atomic<bool> stop(false);
  std::mutex mu;
  std::condition_variable cv;
  std::thread poller([&] {
    std::unique_lock<std::mutex> lock(mu);
    while (!cv.wait_for(lock, std::chrono::milliseconds(every_ms), [&] { return stop.load(); })) {
      Ceilings c = read();
      min.Add(c);
      if (log) log->Add("run", c);
    }
  });
  T value = block();
  {
    std::lock_guard<std::mutex> lock(mu);
    stop = true;
  }
  cv.notify_all();
  poller.join();
  return value;
}

}  // namespace

int main(int32_t argc, char *argv[]) {
  const char *kUsage = R"usage(
asr-qnn-v1 driver: sherpa-onnx's recognizer over a list of WAV files in one process, one JSONL row each.

  asr-qnn-burst-driver --provider=qnn --tokens=tokens.txt \
    --nemo-ctc.qnn-backend-lib=libQnnHtp.so --nemo-ctc.qnn-system-lib=libQnnSystem.so \
    --nemo-ctc.qnn-context-binary=model.bin --num-threads=4 \
    --list=S32.tsv --out=run.jsonl --ceil-log=run.ceil.log --tag=run --pace=burst \
    --warmup-id=1995-1836-0004 --warmup-wav=W.wav --warmup-seconds=33.91

The list: one "id<TAB>wav<TAB>seconds" line per utterance.
)usage";
  sherpa_onnx::ParseOptions po(kUsage);
  sherpa_onnx::OfflineRecognizerConfig config;
  config.Register(&po);
  std::string list_path, out_path, ceil_path, tag = "run", pace = "none", warmup_id, warmup_wav, load_label;
  std::string start_after, failed_id, failed_kind = "crash", model_name, run_info, quant_recipe;
  float warmup_seconds = 0, cap_line_pct = 15;
  int32_t pace_gap_ms = 500, pace_poll_ms = 200, pace_max_wait_s = 120, cap_poll_ms = 100, retake_settle_s = 5;
  po.Register("list", &list_path, "id<TAB>wav<TAB>seconds per line");
  po.Register("out", &out_path, "JSONL output (appended)");
  po.Register("ceil-log", &ceil_path, "burst: every ceiling read (appended)");
  po.Register("tag", &tag, "run name, copied to the header and footer");
  po.Register("model-name", &model_name, "model name for the header");
  po.Register("run-info", &run_info, "free text the host passes (commit, list sha256), copied to the header");
  po.Register("quant-recipe", &quant_recipe, "how the model was quantized (quant-per-arm-rule), copied to the header");
  po.Register("pace", &pace, "none or burst");
  po.Register("warmup-id", &warmup_id, "warm-up utterance id (decoded once after the load, outside the timing)");
  po.Register("warmup-wav", &warmup_wav, "its WAV");
  po.Register("warmup-seconds", &warmup_seconds, "its seconds");
  po.Register("load-label", &load_label, "cold or warm (the host knows the order of processes)");
  po.Register("start-after", &start_after, "resume after this id");
  po.Register("failed-id", &failed_id, "the utterance the previous process died on (written as an error row)");
  po.Register("failed-kind", &failed_kind, "crash or hang");
  po.Register("pace-gap-ms", &pace_gap_ms, "burst: minimum gap after the previous utterance");
  po.Register("pace-poll-ms", &pace_poll_ms, "burst: ceiling poll while waiting");
  po.Register("pace-max-wait-s", &pace_max_wait_s, "burst: longest wait");
  po.Register("cap-poll-ms", &cap_poll_ms, "burst: ceiling poll while an utterance runs");
  po.Register("cap-line-pct", &cap_line_pct, "burst: the line of the fall");
  po.Register("retake-settle-s", &retake_settle_s, "burst: the wait after the ceilings are back before a retake");
  po.Read(argc, argv);
  if (list_path.empty() || out_path.empty() || (pace != "none" && pace != "burst")) {
    po.PrintUsage();
    return 2;
  }
  fprintf(stderr, "%s\n", config.ToString().c_str());
  if (!config.Validate()) {
    fprintf(stderr, "Errors in config!\n");
    return 1;
  }

  auto list_text = ReadText(list_path);
  if (!list_text) {
    fprintf(stderr, "cannot read --list %s\n", list_path.c_str());
    return 1;
  }
  std::string err;
  size_t slash = list_path.rfind('/');
  std::vector<Row> selection = ParseList(*list_text, slash == std::string::npos ? "" : list_path.substr(0, slash), &err);
  if (!err.empty()) {
    fprintf(stderr, "%s\n", err.c_str());
    return 1;
  }
  std::vector<Row> todo = selection;
  if (!start_after.empty()) {
    auto it = std::find_if(selection.begin(), selection.end(), [&](const Row &r) { return r.id == start_after; });
    if (it == selection.end()) {
      fprintf(stderr, "start-after id %s is not in the list\n", start_after.c_str());
      return 1;
    }
    todo.assign(it + 1, selection.end());
  }
  FILE *jsonl = fopen(out_path.c_str(), "a");
  if (!jsonl) {
    fprintf(stderr, "cannot open --out %s\n", out_path.c_str());
    return 1;
  }
  auto emit = [&](const std::string &line) {
    fprintf(jsonl, "%s\n", line.c_str());
    fflush(jsonl);
  };

  const int64_t process_start = NowNs();
  const std::string state_start = ProcessState();
  if (!failed_id.empty()) {
    // The previous process of this run died on this utterance (watchdog or crash).
    auto it = std::find_if(selection.begin(), selection.end(), [&](const Row &r) { return r.id == failed_id; });
    if (it != selection.end()) {
      Transcribed t;
      t.error = failed_kind;
      emit(UtteranceRow(*it, t, {}));
    }
  }

  // The load: the QNN backend (dlopen libQnnHtp.so), the device, the context from the binary, the graph.
  const int64_t t_load = NowNs();
  sherpa_onnx::OfflineRecognizer recognizer(config);
  const double load_ms = static_cast<double>(NowNs() - t_load) / 1e6;
  fprintf(stderr, "[asr-qnn] loaded in %.3f ms\n", load_ms);
  const std::string state_after_load = ProcessState();
  const std::string libs_after_load = MappedLibs();

  std::vector<std::string> policies = CpufreqPolicies(), names;
  Ceilings hw;
  std::vector<std::string> policy_json;
  std::vector<std::set<int>> policy_cpus;
  for (const auto &p : policies) {
    names.push_back(Basename(p));
    hw.push_back(ReadLong(p + "/cpuinfo_max_freq"));
    auto cpus = ReadText(p + "/related_cpus");
    policy_cpus.push_back(ParseCpuList(cpus));
    policy_json.push_back(
        JObj().Put("name", JStr(names.back())).Put("cpus", JOptStr(cpus)).Put("hw_khz", JOpt(hw.back())).Str());
  }
  auto read_ceilings = [&policies]() {
    Ceilings c;
    for (const auto &p : policies) c.push_back(ReadLong(p + "/scaling_max_freq"));
    return c;
  };

  const auto &mc = config.model_config;
  const bool burst = pace == "burst";
  std::string burst_json = "null";
  if (burst) {
    burst_json = JObj()
                     .Put("min_gap_ms", JInt(pace_gap_ms))
                     .Put("ceiling_poll_ms", JInt(pace_poll_ms))
                     .Put("max_wait_s", JInt(pace_max_wait_s))
                     .Put("cap_poll_ms", JInt(cap_poll_ms))
                     .Put("cap_line_pct", JNum(cap_line_pct))
                     .Put("retake_settle_s", JInt(retake_settle_s))
                     .Put("cap_rule", JStr("max over every cpufreq policy of (1 - min scaling_max_freq / "
                                           "cpuinfo_max_freq) * 100, one decimal"))
                     .Str();
  }
  emit(JObj()
           .Put("type", JStr("header"))
           .Put("harness", JStr(kHarness))
           .Put("tag", JStr(tag))
           .Put("engine", JStr("sherpa-onnx"))
           .Put("model_name", JStr(model_name))
           .Put("backend", JStr(mc.provider))
           .Put("run_info", JStr(run_info))
           .Put("quant_recipe", JStr(quant_recipe))
           .Put("num_threads", JInt(mc.num_threads))
           .Put("sherpa_onnx_version", JStr(sherpa_onnx::GetVersionStr()))
           .Put("sherpa_onnx_git_sha1", JStr(sherpa_onnx::GetGitSha1()))
           .Put("sherpa_onnx_git_date", JStr(sherpa_onnx::GetGitDate()))
           .Put("onnxruntime_version", JStr(sherpa_onnx::GetOnnxruntimeVersionStr()))
           .Put("sherpa_config", JStr(config.ToString()))
           .Put("qnn_context_binary", JStr(mc.nemo_ctc.qnn_config.context_binary))
           .Put("qnn_context_binary_bytes", JOpt(FileBytes(mc.nemo_ctc.qnn_config.context_binary)))
           .Put("qnn_backend_lib", JStr(mc.nemo_ctc.qnn_config.backend_lib))
           .Put("qnn_system_lib", JStr(mc.nemo_ctc.qnn_config.system_lib))
           .Put("tokens", JStr(mc.tokens))
           .Put("load_seconds", JNum(load_ms / 1000.0))
           .Put("load_ms", JNum(load_ms))
           .Put("load_scope", JStr("OfflineRecognizer constructor: QNN backend (dlopen of the backend lib, backend and "
                                   "device create), the context from the binary (system lib), the graph and its "
                                   "tensors, tokens, the feature config"))
           .Put("load_label", JStr(load_label))
           .Put("list", JStr(list_path))
           .Put("start_after", JStr(start_after))
           .Put("utterances_selected", JInt(static_cast<int64_t>(selection.size())))
           .Put("utterances_todo", JInt(static_cast<int64_t>(todo.size())))
           .Put("pace", JStr(pace))
           .Put("burst", burst_json)
           .Put("warmup_id", JStr(warmup_id))
           // Where this shell-started process may run (AsrBenchTest's app runs as the top app): the CPUs and
           // the cpuset line of /proc/self/cgroup, then every cgroup line.
           .Put("cpus_allowed", JOptStr(ProcStatus("Cpus_allowed_list")))
           .Put("cpuset", JOptStr(CpusetOf(ReadText("/proc/self/cgroup"))))
           .Put("cgroup", JOptStr(ReadText("/proc/self/cgroup")))
           .Put("process_state", JObj().Put("start", state_start).Put("after_load", state_after_load).Str())
           .Put("libs_mapped_after_load", libs_after_load)
           .Put("cpu_policies", JArr(policy_json))
           .Put("pid", JInt(getpid()))
           .Put("started_utc", JStr(IsoUtc()))
           .Put("device", JObj()
                              .Put("model", JStr(Prop("ro.product.model")))
                              .Put("soc", JStr(Prop("ro.soc.model")))
                              .Put("android", JStr(Prop("ro.build.version.release")))
                              .Put("build", JStr(Prop("ro.build.display.id")))
                              .Put("security_patch", JStr(Prop("ro.build.version.security_patch")))
                              .Str())
           .Str());

  if (!warmup_wav.empty()) {
    // Outside the timing: the first utterance after the load pays one-time costs (first runs of the graph,
    // allocator growth); its text is kept here and not scored.
    fprintf(stderr, "[asr-qnn] begin %s warmup\n", warmup_id.c_str());
    Transcribed w = TranscribeOnce(recognizer, warmup_wav);
    fprintf(stderr, "[asr-qnn] end %s warmup %.3f\n", warmup_id.c_str(), w.seconds);
    emit(JObj()
             .Put("type", JStr("warmup"))
             .Put("warmup_id", JStr(warmup_id))
             .Put("text", JStr(w.text))
             .Put("audio_seconds", JNum(warmup_seconds))
             .Put("processing_seconds", JNum(Round3(w.seconds)))
             .Put("windows", "0")
             .Put("stage_ms", StageJson(w.stage_ms))
             .Put("feature_frames", JOpt(w.feature_frames))
             .Put("error", JOptStr(w.error))
             .Str());
  }

  int done = 0, failed = 0;
  double sum_audio = 0, sum_wall = 0;
  std::vector<double> utterance_rtf;
  auto add_total = [&](const Row &row, const Transcribed &t) {
    if (!t.error) {
      done++;
      sum_audio += row.seconds;
      sum_wall += t.seconds;
      utterance_rtf.push_back(t.seconds / row.seconds);
    } else {
      failed++;
    }
  };
  std::string burst_footer;
  const Clock clock{NowNs, SleepMs};

  if (!burst) {
    for (size_t i = 0; i < todo.size(); ++i) {
      const Row &row = todo[i];
      fprintf(stderr, "[asr-qnn] begin %s 1\n", row.id.c_str());
      Transcribed t = TranscribeOnce(recognizer, row.wav);
      fprintf(stderr, "[asr-qnn] end %s 1 %.3f\n", row.id.c_str(), t.seconds);
      emit(UtteranceRow(row, t, {{"stage_ms", StageJson(t.stage_ms)}, {"feature_frames", JOpt(t.feature_frames)}}));
      add_total(row, t);
      if ((i + 1) % 25 == 0 || i + 1 == todo.size()) {
        fprintf(stderr, "[asr-qnn] progress %zu/%zu rtf=%.6f\n", i + 1, todo.size(), sum_wall / sum_audio);
      }
    }
  } else {
    CeilingLog log(ceil_path.empty() ? out_path + ".ceil.log" : ceil_path, process_start, names, hw);
    Pacer pacer(hw, [&] { Ceilings c = read_ceilings(); log.Add("wait", c); return c; }, clock, pace_gap_ms,
                pace_poll_ms, static_cast<int64_t>(pace_max_wait_s) * 1000);
    Rule rule(&pacer, hw, [&] { Ceilings c = read_ceilings(); log.Add("edge", c); return c; }, clock, cap_line_pct,
              static_cast<int64_t>(retake_settle_s) * 1000);
    std::vector<std::pair<double, double>> counted;  // (audio seconds, processing seconds)
    std::vector<double> waits;
    int excluded = 0, retaken = 0, retake_text_differs = 0, wait_timeouts = 0;
    double retake_wait_sum = 0;
    int64_t prev_end = NowNs();
    for (size_t i = 0; i < todo.size(); ++i) {
      const Row &row = todo[i];
      auto cpus_at_start = ProcStatus("Cpus_allowed_list");
      auto cpuset_at_start = CpusetOf(ReadText("/proc/self/cgroup"));
      std::set<int> engine_idx;
      std::set<int> allowed = ParseCpuList(cpus_at_start);
      for (size_t k = 0; k < policy_cpus.size(); ++k) {
        for (int c : policy_cpus[k]) {
          if (allowed.count(c)) engine_idx.insert(static_cast<int>(k));
        }
      }
      int attempt_no = 0;
      Outcome<Transcribed> outcome = rule.Utterance<Transcribed>(
          prev_end, [](const Transcribed &t) { return !t.error; },
          [&](CeilingMin &min) {
            attempt_no++;
            log.SetContext(row.id + "\t" + std::to_string(attempt_no));
            fprintf(stderr, "[asr-qnn] begin %s %d\n", row.id.c_str(), attempt_no);
            Transcribed t = PollCeilings<Transcribed>(min, cap_poll_ms, read_ceilings, &log,
                                                      [&] { return TranscribeOnce(recognizer, row.wav); });
            fprintf(stderr, "[asr-qnn] end %s %d %.3f\n", row.id.c_str(), attempt_no, t.seconds);
            return t;
          });
      prev_end = outcome.Final().end_ns;
      const auto &first = outcome.attempts.front();
      const auto &last = outcome.Final();
      std::vector<std::pair<std::string, std::string>> extra = {
          {"attempts", JInt(static_cast<int64_t>(outcome.attempts.size()))},
          {"wait_s", JNum(Round3(first.wait.waited_ms / 1000.0))},
          {"wait_timed_out", JBool(first.wait.timed_out)},
          {"wait_polls", JInt(first.wait.polls)},
          {"cap_drop_pct", JOpt(last.drop_pct)},
          {"cap_drop_engine_cpus_pct", JOpt(CapDropPct(last.min_khz, hw, &engine_idx))},
          {"cap_min_khz", CeilingsJson(names, last.min_khz)},
          {"cap_reads", JInt(last.reads)},
          {"excluded", JBool(outcome.excluded)},
          {"cpus_allowed", JOptStr(cpus_at_start)},
          {"cpuset", JOptStr(cpuset_at_start)},
      };
      if (outcome.attempts.size() > 1) {
        extra.emplace_back("retake", JObj()
                                         .Put("first", JObj()
                                                           .Put("processing_seconds", JNum(Round3(first.value.seconds)))
                                                           .Put("cap_drop_pct", JOpt(first.drop_pct))
                                                           .Put("cap_min_khz", CeilingsJson(names, first.min_khz))
                                                           .Put("cap_reads", JInt(first.reads))
                                                           .Put("text", JStr(first.value.text))
                                                           .Put("error", JOptStr(first.value.error))
                                                           .Str())
                                         .Put("wait_s", JNum(Round3(last.wait.waited_ms / 1000.0)))
                                         .Put("wait_timed_out", JBool(last.wait.timed_out))
                                         .Put("text_same", JBool(first.value.text == last.value.text))
                                         .Str());
        retaken++;
        retake_wait_sum += last.wait.waited_ms / 1000.0;
        if (first.value.text != last.value.text) retake_text_differs++;
      }
      extra.emplace_back("stage_ms", StageJson(last.value.stage_ms));
      extra.emplace_back("feature_frames", JOpt(last.value.feature_frames));
      emit(UtteranceRow(row, last.value, extra));
      log.Flush();
      add_total(row, last.value);
      waits.push_back(first.wait.waited_ms / 1000.0);
      if (first.wait.timed_out) wait_timeouts++;
      if (outcome.excluded && !last.value.error) excluded++;
      if (!outcome.excluded && !last.value.error) counted.emplace_back(row.seconds, last.value.seconds);
      if ((i + 1) % 25 == 0 || i + 1 == todo.size()) {
        fprintf(stderr, "[asr-qnn] progress %zu/%zu excluded=%d retaken=%d\n", i + 1, todo.size(), excluded, retaken);
      }
    }
    double audio = 0, wall = 0;
    std::vector<double> rtfs;
    for (const auto &c : counted) {
      audio += c.first;
      wall += c.second;
      rtfs.push_back(c.second / c.first);
    }
    double wait_sum = 0;
    for (double w : waits) wait_sum += w;
    burst_footer = JObj()
                       .Put("utterances_counted", JInt(static_cast<int64_t>(counted.size())))
                       .Put("utterances_excluded", JInt(excluded))
                       .Put("utterances_retaken", JInt(retaken))
                       .Put("retake_text_differs", JInt(retake_text_differs))
                       .Put("counted_audio_seconds", JNum(audio))
                       .Put("counted_processing_seconds", JNum(wall))
                       .Put("rtf_burst", audio > 0 ? JNum(wall / audio) : "null")
                       .Put("median_utterance_rtf_burst", JOpt(Median(rtfs)))
                       .Put("wait_sum_s", JNum(wait_sum))
                       .Put("wait_median_s", JOpt(Median(waits)))
                       .Put("wait_max_s", waits.empty() ? "null" : JNum(*std::max_element(waits.begin(), waits.end())))
                       .Put("wait_timeouts", JInt(wait_timeouts))
                       .Put("retake_wait_sum_s", JNum(retake_wait_sum))
                       .Str();
  }

  const double elapsed = static_cast<double>(NowNs() - process_start) / 1e9;
  const std::string libs_end = MappedLibs();
  const std::string state_end = ProcessState();
  const double rtf = sum_audio > 0 ? sum_wall / sum_audio : NAN;
  auto vmhwm = ProcStatusKb("VmHWM");
  JObj footer;
  footer.Put("type", JStr("footer"))
      .Put("tag", JStr(tag))
      .Put("utterances_done", JInt(done))
      .Put("utterances_failed", JInt(failed))
      .Put("sum_audio_seconds", JNum(sum_audio))
      .Put("sum_processing_seconds", JNum(sum_wall))
      .Put("rtf", JNum(rtf))
      .Put("rtfx", JNum(1.0 / rtf))
      .Put("median_utterance_rtf", JOpt(Median(utterance_rtf)));
  if (!burst_footer.empty()) footer.Put("burst", burst_footer);
  footer.Put("vmhwm_kb", JOpt(vmhwm))
      .Put("peak_rss_bytes", vmhwm ? JInt(*vmhwm * 1024) : "null")
      .Put("memory_scope", JStr("this driver process (sherpa-onnx, onnxruntime, the QNN client libraries)"))
      .Put("process_state_end", state_end)
      .Put("libs_mapped_end", libs_end)
      .Put("elapsed_seconds", JNum(elapsed))
      .Put("finished_utc", JStr(IsoUtc()));
  emit(footer.Str());
  fclose(jsonl);
  fprintf(stderr, "[asr-qnn] done tag=%s done=%d failed=%d rtf=%.6f vmhwm_kb=%lld\n", tag.c_str(), done, failed, rtf,
          static_cast<long long>(vmhwm.value_or(-1)));
  return 0;
}

#else  // HOST_TEST: the pacing, the cap rule, the list and the JSON against AsrBenchTest's BurstTest cases.

namespace {

int failures = 0;

#define EXPECT(cond)                                                     \
  do {                                                                   \
    if (!(cond)) {                                                       \
      fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);    \
      failures++;                                                        \
    }                                                                    \
  } while (0)

struct FakeClock {
  int64_t ns = 0;
  Clock AsClock() {
    return Clock{[this] { return ns; }, [this](int64_t ms) { ns += ms * kNsPerMs; }};
  }
  void AdvanceMs(int64_t ms) { ns += ms * kNsPerMs; }
};

// The Galaxy S26 (SM8850): policy0 = cpu 0-5, policy6 = cpu 6-7.
const Ceilings kHw = {3628800, 4742400};
const Ceilings kLow = {2496000, 2438400};

void TestPacer() {
  {  // waits the minimum gap when every ceiling is at its maximum
    FakeClock c;
    c.AdvanceMs(100);
    Wait w = Pacer(kHw, [] { return kHw; }, c.AsClock()).Await(0);
    EXPECT(w.waited_ms == 500.0 && w.polls == 1 && !w.timed_out);
  }
  {  // polls every 200 ms until every policy is back (policy6 capped until 1.3 s)
    FakeClock c;
    Pacer p(kHw, [&c] { return c.ns < 1300 * kNsPerMs ? Ceilings{kHw[0], kLow[1]} : kHw; }, c.AsClock());
    Wait w = p.Await(0);
    EXPECT(w.waited_ms == 1300.0 && w.polls == 5 && !w.timed_out && w.ceilings == kHw);
  }
  {  // starts anyway after 120 s and marks it
    FakeClock c;
    Wait w = Pacer(kHw, [] { return kLow; }, c.AsClock()).Await(0);
    EXPECT(w.waited_ms == 120000.0 && w.timed_out && w.polls == 599);
  }
  {  // ignores a policy it cannot read
    FakeClock c;
    EXPECT(Pacer(Ceilings{kHw[0], std::nullopt}, [] { return kHw; }, c.AsClock()).AtMax(Ceilings{kHw[0], 1}));
    EXPECT(Pacer(kHw, [] { return kHw; }, c.AsClock()).AtMax(Ceilings{std::nullopt, kHw[1]}));
    EXPECT(!Pacer(kHw, [] { return kHw; }, c.AsClock()).AtMax(Ceilings{kHw[0], *kHw[1] - 1}));
  }
}

void TestCapDrop() {
  Ceilings min = {3513600, 3974400};  // r2's L1 smoke: policy0 -3.2 %, policy6 -16.2 %
  std::set<int> only0 = {0};
  EXPECT(*CapDropPct(min, kHw) == 16.2);
  EXPECT(*CapDropPct(min, kHw, &only0) == 3.2);
  EXPECT(*CapDropPct(kHw, kHw) == 0.0);
  EXPECT(!CapDropPct(Ceilings{std::nullopt, std::nullopt}, kHw));
  EXPECT(*CapDropPct(Ceilings{std::nullopt, 3974400}, kHw) == 16.2);
  EXPECT(*CapDropPct(Ceilings{3398400}, Ceilings{4000000}) == 15.0);  // 15.04 % -> 15.0, not past the line
  EXPECT((ParseCpuList(std::string("0-5")) == std::set<int>{0, 1, 2, 3, 4, 5}));
  EXPECT((ParseCpuList(std::string("0-3,6")) == std::set<int>{0, 1, 2, 3, 6}));
  EXPECT((ParseCpuList(std::string("6 7")) == std::set<int>{6, 7}));
  EXPECT(ParseCpuList(std::string("")).empty() && ParseCpuList(std::nullopt).empty());
}

// A run that takes ms and reads the ceilings once while it runs.
std::function<std::string(CeilingMin &)> RunOf(FakeClock *c, int64_t ms, Ceilings during, std::string text = "text") {
  return [=](CeilingMin &min) {
    c->AdvanceMs(ms / 2);
    min.Add(during);
    c->AdvanceMs(ms - ms / 2);
    return text;
  };
}

void TestRule() {
  auto always = [](const std::string &) { return true; };
  {  // keeps an attempt at the line (exactly -15.0 %)
    FakeClock c;
    Ceilings hw4 = {4000000};
    Pacer p(hw4, [&] { return hw4; }, c.AsClock());
    Rule r(&p, hw4, [&] { return hw4; }, c.AsClock());
    auto o = r.Utterance<std::string>(0, always, RunOf(&c, 800, Ceilings{3400000}));
    EXPECT(o.attempts.size() == 1 && *o.Final().drop_pct == 15.0 && !o.excluded);
    EXPECT(o.Final().reads == 3 && o.Final().wait.waited_ms == 500.0);
  }
  {  // retakes once after the ceiling is back and five seconds more
    FakeClock c;
    int64_t first_end = INT64_MAX;
    auto read = [&] { return c.ns > first_end && c.ns < first_end + 2000 * kNsPerMs ? kLow : kHw; };
    Pacer p(kHw, read, c.AsClock());
    Rule r(&p, kHw, read, c.AsClock());
    int calls = 0;
    auto o = r.Utterance<std::string>(0, always, [&](CeilingMin &min) {
      calls++;
      if (calls == 1) {
        c.AdvanceMs(500);
        min.Add(Ceilings{kHw[0], 3793920});  // policy6 -20 %
        c.AdvanceMs(500);
        first_end = c.ns;
        return std::string("first");
      }
      return RunOf(&c, 1000, kHw, "second")(min);
    });
    EXPECT(o.attempts.size() == 2 && o.attempts[0].value == "first" && *o.attempts[0].drop_pct == 20.0);
    EXPECT(o.Final().value == "second" && *o.Final().drop_pct == 0.0 && !o.excluded);
    // Back at 2.1 s after the first attempt (polls at 0.5, 0.7, ..., 2.1 s), then 5 s more.
    EXPECT(o.Final().wait.waited_ms == 7100.0);
    EXPECT(o.Final().start_ns == o.attempts[0].end_ns + 7100 * kNsPerMs);
  }
  {  // excludes an utterance whose retake is past the line too
    FakeClock c;
    Pacer p(kHw, [] { return kHw; }, c.AsClock());
    Rule r(&p, kHw, [] { return kHw; }, c.AsClock());
    auto o = r.Utterance<std::string>(0, always, RunOf(&c, 1000, kLow));
    EXPECT(o.attempts.size() == 2 && *o.Final().drop_pct == 48.6 && o.excluded);
  }
  {  // does not retake a failed attempt
    FakeClock c;
    Pacer p(kHw, [] { return kHw; }, c.AsClock());
    Rule r(&p, kHw, [] { return kHw; }, c.AsClock());
    auto o = r.Utterance<std::string>(0, [](const std::string &v) { return v != "error"; }, [](CeilingMin &min) {
      min.Add(kLow);
      return std::string("error");
    });
    EXPECT(o.attempts.size() == 1 && o.excluded);
  }
}

void TestListAndJson() {
  std::string err;
  auto rows = ParseList("a\tx/a.wav\t1.5\nb\t/abs/b.wav\t2\n\n", "/d", &err);
  EXPECT(err.empty() && rows.size() == 2 && rows[0].wav == "/d/x/a.wav" && rows[1].wav == "/abs/b.wav");
  EXPECT(rows[0].seconds == 1.5);
  ParseList("a\tb\n", "", &err);
  EXPECT(err.find("expected 3") != std::string::npos);
  EXPECT(JStr("he said \"hi\"\\\n\x01") == "\"he said \\\"hi\\\"\\\\\\n\\u0001\"");
  EXPECT(JStr("na\xc3\xafve") == "\"na\xc3\xafve\"");  // UTF-8 passes through
  EXPECT(JNum(0.61234) == "0.61234" && JNum(Round3(0.61234)) == "0.612" && JNum(NAN) == "null");
  EXPECT(JNum(1233.7449999999997) == "1233.745");
  Row row{"1089-134686-0000", "/w.wav", 10.435};
  Transcribed t;
  t.text = "he hoped";
  t.seconds = 0.61234;
  std::string line = UtteranceRow(row, t, {{"wait_s", JNum(0.5)}, {"excluded", JBool(false)}});
  EXPECT(line ==
         "{\"type\":\"utterance\",\"id\":\"1089-134686-0000\",\"text\":\"he hoped\",\"audio_seconds\":10.435,"
         "\"processing_seconds\":0.612,\"windows\":0,\"empty_windows\":0,\"tokens\":[],\"mel_ms\":[],"
         "\"encode_ms\":[],\"decode_ms\":[],\"wait_s\":0.5,\"excluded\":false}");
  t.error = "crash";
  EXPECT(UtteranceRow(row, t, {}).find("\"error\":\"crash\"") != std::string::npos);
  EXPECT(CeilingsJson({"policy0", "policy6"}, Ceilings{3513600, std::nullopt}) == "{\"policy0\":3513600,\"policy6\":null}");
  EXPECT(*Median({3, 1, 2}) == 2 && *Median({4, 1, 2, 3}) == 2.5 && !Median({}));
  EXPECT(CpusetOf(std::string("0::/\n4:cpuset:/top-app\n")) == std::string("4:cpuset:/top-app"));
  EXPECT(CpusetOf(std::string("0::/uid_2000\n")) == std::string("0::/uid_2000"));
}

}  // namespace

int main() {
  TestPacer();
  TestCapDrop();
  TestRule();
  TestListAndJson();
  if (failures) {
    fprintf(stderr, "host self-test: %d FAILED\n", failures);
    return 1;
  }
  fprintf(stderr, "host self-test: PASS (pacer, cap rule, retake, list, JSON)\n");
  return 0;
}

#endif  // HOST_TEST
