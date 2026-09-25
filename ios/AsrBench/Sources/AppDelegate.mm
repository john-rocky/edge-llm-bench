#import "AppDelegate.h"

#include <dlfcn.h>
#include <mach/mach.h>
#include <sys/utsname.h>
#include <unistd.h>

#include <atomic>
#include <chrono>  // NOLINT
#include <cstring>
#include <string>
#include <vector>

#include "asr_bench_shim.h"

// One transcription per process, driven by launch arguments (scripts/asr_rtf_iphone.py):
//   --asr-autorun --run-id <id> --model-name <omni/asr name> --model-file <file under
//   Documents/asr/models> --metadata <file under Documents/asr/bin> --backend cpu|gpu
//   --threads 4 --overlap 0.4 --merger timestamp --audio <file under Documents/asr/audio>
// Writes Documents/asr/results/<run-id>.json (+ .log = the engine's stderr, + .done) and
// prints ASRBENCH_RESULT_JSON <json> / ASRBENCH_DONE <status> on stdout for the console.

namespace {

using Clock = std::chrono::steady_clock;

NSString* DocumentsDir() {
  return NSSearchPathForDirectoriesInDomains(NSDocumentDirectory, NSUserDomainMask, YES).firstObject;
}

NSString* AsrPath(NSString* sub, NSString* name) {
  NSString* dir = [[DocumentsDir() stringByAppendingPathComponent:@"asr"] stringByAppendingPathComponent:sub];
  [[NSFileManager defaultManager] createDirectoryAtPath:dir withIntermediateDirectories:YES attributes:nil error:nil];
  return name ? [dir stringByAppendingPathComponent:name] : dir;
}

NSString* Arg(NSString* flag, NSString* def) {
  NSArray<NSString*>* a = NSProcessInfo.processInfo.arguments;
  NSUInteger i = [a indexOfObject:flag];
  return (i != NSNotFound && i + 1 < a.count) ? a[i + 1] : def;
}

bool LaunchedWithFlags() {
  return [NSProcessInfo.processInfo.arguments containsObject:@"--asr-autorun"];
}

// The engine logs to stderr (absl). Mirror it into the run's .log and echo it on stdout,
// which is what `devicectl ... --console` bridges.
void TeeStderrToFile(NSString* path) {
  int fds[2];
  if (pipe(fds) != 0) return;
  FILE* log = fopen(path.UTF8String, "w");
  dup2(fds[1], STDERR_FILENO);
  close(fds[1]);
  const int reader = fds[0];
  dispatch_async(dispatch_get_global_queue(QOS_CLASS_UTILITY, 0), ^{
    char buf[4096];
    ssize_t n;
    while ((n = read(reader, buf, sizeof(buf))) > 0) {
      write(STDOUT_FILENO, buf, n);
      if (log != nullptr) {
        fwrite(buf, 1, n, log);
        fflush(log);
      }
    }
  });
}

// The runtime finds the GPU accelerator by file name (libLiteRtMetalAccelerator.dylib) with no
// directory when no runtime library dir is set (LiteRT gpu_registry.cc). The dylib is embedded
// in the app's Frameworks folder: load it from its absolute path first, and make that folder
// the working directory so the name-only dlopen resolves there as well.
std::string PrepareGpuAccelerator() {
  NSString* frameworks = NSBundle.mainBundle.privateFrameworksPath;
  NSString* dylib = [frameworks stringByAppendingPathComponent:@"libLiteRtMetalAccelerator.dylib"];
  if (![[NSFileManager defaultManager] fileExistsAtPath:dylib]) return "absent";
  chdir(frameworks.UTF8String);
  void* handle = dlopen(dylib.UTF8String, RTLD_NOW | RTLD_GLOBAL);
  std::string status = handle != nullptr ? "loaded" : (dlerror() ?: "dlopen failed");
  fprintf(stderr, "INFO: GPU accelerator dylib %s: %s\n", dylib.UTF8String, status.c_str());
  return status;
}

NSString* ThermalName() {
  switch (NSProcessInfo.processInfo.thermalState) {
    case NSProcessInfoThermalStateNominal: return @"nominal";
    case NSProcessInfoThermalStateFair: return @"fair";
    case NSProcessInfoThermalStateSerious: return @"serious";
    case NSProcessInfoThermalStateCritical: return @"critical";
  }
  return @"unknown";
}

NSString* BatteryStateName() {
  switch (UIDevice.currentDevice.batteryState) {
    case UIDeviceBatteryStateUnplugged: return @"unplugged";
    case UIDeviceBatteryStateCharging: return @"charging";
    case UIDeviceBatteryStateFull: return @"full";
    default: return @"unknown";
  }
}

NSString* MachineName() {
  struct utsname u;
  uname(&u);
  return @(u.machine);
}

// Peak memory of this process, sampled every 100 ms: phys_footprint (what iOS's jetsam
// accounts) and resident_size, both in MB.
struct MemSampler {
  std::atomic<bool> stop{false};
  std::atomic<double> peakFootprintMB{0};
  std::atomic<double> peakResidentMB{0};
  void sample() {
    task_vm_info_data_t info;
    mach_msg_type_number_t count = TASK_VM_INFO_COUNT;
    if (task_info(mach_task_self(), TASK_VM_INFO, (task_info_t)&info, &count) == KERN_SUCCESS) {
      double fp = info.phys_footprint / 1048576.0, rs = info.resident_size / 1048576.0;
      if (fp > peakFootprintMB) peakFootprintMB = fp;
      if (rs > peakResidentMB) peakResidentMB = rs;
    }
  }
  void start() {
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_UTILITY, 0), ^{
      while (!stop) { sample(); usleep(100000); }
    });
  }
};

std::vector<std::string>* g_chunks = nullptr;
void OnText(const char* text, void*) {
  if (g_chunks) g_chunks->push_back(text);
}

}  // namespace

@implementation AppDelegate

- (BOOL)application:(UIApplication*)application
    didFinishLaunchingWithOptions:(NSDictionary*)launchOptions {
  application.idleTimerDisabled = YES;
  UIDevice.currentDevice.batteryMonitoringEnabled = YES;
  if (!LaunchedWithFlags()) {
    self.logText = @"ASR bench: launch with --asr-autorun (scripts/asr_rtf_iphone.py).";
    return YES;
  }
  const auto tLaunch = Clock::now();
  NSString* runId = Arg(@"--run-id", @"run");
  NSString* resultPath = AsrPath(@"results", [runId stringByAppendingString:@".json"]);
  NSString* donePath = AsrPath(@"results", [runId stringByAppendingString:@".done"]);
  [[NSFileManager defaultManager] removeItemAtPath:donePath error:nil];
  [[NSFileManager defaultManager] removeItemAtPath:resultPath error:nil];
  TeeStderrToFile(AsrPath(@"results", [runId stringByAppendingString:@".log"]));

  dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^{
    NSString* modelName = Arg(@"--model-name", @"");
    NSString* backend = Arg(@"--backend", @"cpu");
    NSString* modelPath = AsrPath(@"models", Arg(@"--model-file", @""));
    NSString* metadataPath = AsrPath(@"bin", Arg(@"--metadata", @"model_metadata.json"));
    NSString* audioPath = AsrPath(@"audio", Arg(@"--audio", @""));
    NSString* cacheDir = AsrPath(@"models", nil);
    NSString* merger = Arg(@"--merger", @"timestamp");
    int threads = Arg(@"--threads", @"4").intValue;
    float overlap = Arg(@"--overlap", @"0.4").floatValue;

    NSString* thermalBefore = ThermalName();
    float batteryBefore = UIDevice.currentDevice.batteryLevel;
    NSString* batteryState = BatteryStateName();
    std::string gpuDylib = "not requested";
    if ([backend isEqualToString:@"gpu"]) gpuDylib = PrepareGpuAccelerator();

    MemSampler mem;
    mem.start();
    std::vector<std::string> chunks;
    g_chunks = &chunks;
    AsrBenchRequest req;
    std::memset(&req, 0, sizeof(req));
    req.model_name = modelName.UTF8String;
    req.metadata_path = metadataPath.UTF8String;
    req.model_path = modelPath.UTF8String;
    req.cache_dir = cacheDir.UTF8String;
    req.backend = backend.UTF8String;
    req.num_threads = threads;
    req.overlap_ratio = overlap;
    req.text_merger_type = merger.UTF8String;
    req.audio_path = audioPath.UTF8String;
    AsrBenchResult res;
    const auto tRun = Clock::now();
    const int rc = asr_bench_run(&req, OnText, nullptr, &res);
    const auto tEnd = Clock::now();
    mem.stop = true;
    mem.sample();
    g_chunks = nullptr;
    fflush(stderr);

    auto secs = [](Clock::time_point a, Clock::time_point b) {
      return std::chrono::duration<double>(b - a).count();
    };
    NSMutableDictionary* out = [NSMutableDictionary dictionary];
    out[@"runId"] = runId;
    out[@"ok"] = @(rc == 0 && res.ok);
    out[@"exitCode"] = @(rc);
    out[@"engineVersion"] = @(asr_bench_engine_version());
    out[@"modelName"] = modelName;
    out[@"modelFile"] = Arg(@"--model-file", @"");
    out[@"backend"] = backend;
    out[@"numThreads"] = @(threads);
    out[@"overlapRatio"] = @(overlap);
    out[@"textMerger"] = merger;
    out[@"audioFile"] = Arg(@"--audio", @"");
    out[@"gpuAcceleratorDylib"] = @(gpuDylib.c_str());
    out[@"launchToRunSeconds"] = @(secs(tLaunch, tRun));
    out[@"engineCreateSeconds"] = @(res.t_create_engine_s);
    out[@"sessionCreateSeconds"] = @(res.t_create_session_s);
    // load = launch -> "Starting" (the Mac / Android loadTimeSeconds analogue).
    out[@"loadTimeSeconds"] = @(secs(tLaunch, tRun) + res.t_create_engine_s + res.t_create_session_s);
    out[@"asrProcessingSeconds"] = @(res.t_process_s);
    out[@"asrFirstTextLatencyMS"] = res.t_first_text_s >= 0 ? @(res.t_first_text_s * 1000.0) : [NSNull null];
    out[@"textChunks"] = @(res.text_chunks);
    out[@"totalWallSeconds"] = @(secs(tLaunch, tEnd));
    out[@"transcript"] = res.transcript ? @(res.transcript) : @"";
    out[@"error"] = res.error ? @(res.error) : [NSNull null];
    out[@"memoryPeakFootprintMB"] = @(mem.peakFootprintMB.load());
    out[@"memoryPeakResidentMB"] = @(mem.peakResidentMB.load());
    out[@"thermalInitial"] = thermalBefore;
    out[@"thermalFinal"] = ThermalName();
    out[@"batteryLevelInitial"] = @(batteryBefore);
    out[@"batteryLevelFinal"] = @(UIDevice.currentDevice.batteryLevel);
    out[@"batteryState"] = batteryState;
    out[@"device"] = @{
      @"modelIdentifier": MachineName(),
      @"systemName": UIDevice.currentDevice.systemName,
      @"systemVersion": UIDevice.currentDevice.systemVersion,
      @"processorCount": @(NSProcessInfo.processInfo.processorCount),
      @"physicalMemoryMB": @(NSProcessInfo.processInfo.physicalMemory / 1048576ULL),
      @"lowPowerMode": @(NSProcessInfo.processInfo.lowPowerModeEnabled),
    };
    NSData* json = [NSJSONSerialization dataWithJSONObject:out options:0 error:nil];
    NSString* jsonText = [[NSString alloc] initWithData:json encoding:NSUTF8StringEncoding];
    [json writeToFile:resultPath atomically:YES];
    printf("ASRBENCH_RESULT_JSON %s\n", jsonText.UTF8String);
    fflush(stdout);
    [[NSString stringWithFormat:@"%d\n", rc] writeToFile:donePath atomically:YES
                                                 encoding:NSUTF8StringEncoding error:nil];
    asr_bench_result_free(&res);
    printf("ASRBENCH_DONE %d\n", rc);
    fflush(stdout);
    dispatch_async(dispatch_get_main_queue(), ^{
      self.logText = jsonText;
      self.textView.text = jsonText;
    });
    // Give the console reader a moment to drain, then end the process so the driver returns.
    sleep(1);
    exit(rc);
  });
  return YES;
}

@end
