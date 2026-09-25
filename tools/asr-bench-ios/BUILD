# edge-llm-bench iPhone leg of the asr-rtf-* task family: a C shim around
# omni/asr (the asr_runner path) as a static library for an iOS app.
# Build (device):
#   bazelisk build --config=ios_arm64 //bench_ios:asr_bench_static
load("@build_bazel_rules_apple//apple:apple.bzl", "apple_static_library")

package(default_visibility = ["//visibility:public"])

cc_library(
    name = "asr_bench_shim",
    srcs = ["asr_bench_shim.cc"],
    hdrs = ["asr_bench_shim.h"],
    defines = ["ASR_BENCH_ENGINE_VERSION=\\\"main@66058c82\\\""],
    alwayslink = True,
    deps = [
        "@com_google_absl//absl/log:absl_log",
        "@com_google_absl//absl/status",
        "@com_google_absl//absl/status:status_macros",
        "@com_google_absl//absl/status:statusor",
        "@com_google_absl//absl/strings",
        "@com_google_absl//absl/time",
        "//omni:omni_session",
        "//omni/asr:asr_engine",
        "//omni/asr:file_audio_source",
        "//omni/asr:model_metadata",
        "//runtime/executor:default_static_gpu_accelerator",
    ],
)

apple_static_library(
    name = "asr_bench_static",
    minimum_os_version = "17.0",
    platform_type = "ios",
    deps = [":asr_bench_shim"],
)
