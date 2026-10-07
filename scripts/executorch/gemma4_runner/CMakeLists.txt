# Build ExecuTorch's Gemma 4 e2e runner (examples/models/gemma4: e2e_runner.cpp +
# runner/gemma4_runner.cpp, unchanged) against an installed llm-release build, with
# what its Buck targets (examples/models/gemma4/targets.bzl) link.
#
# The tree's own examples/models/gemma4/CMakeLists.txt (v1.5.1) compiles
# e2e_runner.cpp only: it has no runner/gemma4_runner.cpp, no stb and no
# extension_llm_runner / extension_threadpool, and stops at
# "'stb_image_resize.h' file not found". This file adds exactly those:
#   - runner/gemma4_runner.cpp                (targets.bzl :gemma4_runner)
#   - stb, pinned as examples/models/gemma3/CMakeLists.txt pins it, + stb_impl.c
#   - extension_llm_runner (load_tokenizer, Sampler), extension_threadpool
#     (ET_USE_THREADPOOL, as targets.bzl's preprocessor_flags)
# and otherwise links the same kernel and backend libraries as llama_main
# (examples/models/llama/CMakeLists.txt): optimized + quantized + custom ops +
# torchao ops, XNNPACK (+ KleidiAI).
#
#   cmake -S scripts/executorch/gemma4_runner -B <ET>/cmake-out/examples/models/gemma4-r3 \
#     -DCMAKE_BUILD_TYPE=Release -DEXECUTORCH_ROOT=<ET> -DET_CMAKE_OUT=<ET>/cmake-out
#   cmake --build <ET>/cmake-out/examples/models/gemma4-r3 --target gemma4_e2e_runner -j
#
# Android (arm64-v8a): android/scripts/build_executorch_llama_main.sh configures this file
# with the NDK toolchain against its stage-1 install (ET_CMAKE_OUT=<ET>/cmake-out-android);
# the if(ANDROID) blocks below apply what examples/models/llama/CMakeLists.txt applies to
# llama_main there.
cmake_minimum_required(VERSION 3.24)
project(gemma4_e2e_runner C CXX)

set(EXECUTORCH_ROOT "" CACHE PATH "ExecuTorch source tree (a directory named executorch)")
set(ET_CMAKE_OUT "" CACHE PATH "installed llm-release build of that tree (cmake-out)")
if(NOT EXISTS "${EXECUTORCH_ROOT}/examples/models/gemma4/e2e_runner.cpp")
  message(FATAL_ERROR "EXECUTORCH_ROOT=${EXECUTORCH_ROOT} has no examples/models/gemma4/e2e_runner.cpp")
endif()
include(${EXECUTORCH_ROOT}/tools/cmake/Utils.cmake)
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

set(gflags_DIR ${ET_CMAKE_OUT}/third-party/gflags)
find_package(gflags REQUIRED)
list(APPEND CMAKE_FIND_ROOT_PATH ${ET_CMAKE_OUT})
find_package(executorch CONFIG REQUIRED FIND_ROOT_PATH_BOTH)
executorch_target_link_options_shared_lib(executorch)

include(FetchContent)
FetchContent_Declare(
  stb
  GIT_REPOSITORY https://github.com/nothings/stb.git
  GIT_TAG f0569113c93ad095470c54bf34a17b36646bbbb5
)
FetchContent_MakeAvailable(stb)

set(_g4 ${EXECUTORCH_ROOT}/examples/models/gemma4)
add_executable(
  gemma4_e2e_runner ${_g4}/e2e_runner.cpp ${_g4}/runner/gemma4_runner.cpp
                    ${CMAKE_CURRENT_SOURCE_DIR}/stb_impl.c
)
target_include_directories(
  gemma4_e2e_runner PUBLIC ${EXECUTORCH_ROOT}/.. ${stb_SOURCE_DIR}
                           ${stb_SOURCE_DIR}/deprecated
)
target_compile_definitions(gemma4_e2e_runner PRIVATE ET_USE_THREADPOOL)
target_compile_options(gemma4_e2e_runner PRIVATE -Wno-deprecated-declarations)

set(link_libraries
    executorch
    gflags
    optimized_native_cpu_ops_lib
    optimized_kernels
    portable_kernels
    cpublas
    eigen_blas
    quantized_kernels
    quantized_ops_lib
    custom_ops
    torchao_ops_executorch
    extension_threadpool
    pthreadpool
    cpuinfo
    xnnpack_backend
    XNNPACK
    xnnpack-microkernels-prod
    kleidiai
    extension_module
    extension_data_loader
    extension_tensor
    extension_flat_tensor
    extension_llm_runner
    tokenizers::tokenizers
)
if(ANDROID)
  # The llama README's stage 1 builds no torchao kernels for Android (the llm preset turns
  # them on for Apple silicon only); llama_main links them only if(TARGET
  # torchao_ops_executorch), and neither runner's .pte calls one. cpuinfo logs through
  # liblog there.
  foreach(_lib torchao_ops_executorch kleidiai)
    if(NOT TARGET ${_lib})
      list(REMOVE_ITEM link_libraries ${_lib})
    endif()
  endforeach()
  list(APPEND link_libraries log)
endif()
foreach(_lib optimized_native_cpu_ops_lib quantized_ops_lib custom_ops
             torchao_ops_executorch xnnpack_backend
)
  if(TARGET ${_lib})
    executorch_target_link_options_shared_lib(${_lib})
  endif()
endforeach()
target_link_libraries(gemma4_e2e_runner PUBLIC ${link_libraries})
if(CMAKE_BUILD_TYPE STREQUAL "Release")
  target_link_options_gc_sections(gemma4_e2e_runner)
  if(ANDROID)
    target_link_options(gemma4_e2e_runner PRIVATE "LINKER:-s")
  endif()
endif()
