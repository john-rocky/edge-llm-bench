# Build et_native_bench (et_native_bench.cpp beside this file): the forced-count benchmark
# (task native-benchmark-<P>x<D>) on the LLM runner components of an installed ExecuTorch
# llm-release build, for the Qwen 3 exports llama_main runs. It links what llama_main links
# (examples/models/llama/CMakeLists.txt, v1.5.1): optimized + quantized + custom ops (+ torchao
# ops where built), XNNPACK (+ KleidiAI), extension_threadpool (ET_USE_THREADPOOL, as llama_main's
# runner), extension_module / data_loader / tensor / flat_tensor and extension_llm_runner.
#
#   cmake -S scripts/executorch/native_bench -B <ET>/cmake-out/examples/models/et_native_bench \
#     -DCMAKE_BUILD_TYPE=Release -DEXECUTORCH_ROOT=<ET> -DET_CMAKE_OUT=<ET>/cmake-out
#   cmake --build <ET>/cmake-out/examples/models/et_native_bench --target et_native_bench -j
#
# Android (arm64-v8a): android/scripts/build_executorch_llama_main.sh (ET_RUNNERS=et_native_bench)
# configures this file with the NDK toolchain against its stage-1 install
# (ET_CMAKE_OUT=<ET>/cmake-out-android).
cmake_minimum_required(VERSION 3.24)
project(et_native_bench C CXX)

set(EXECUTORCH_ROOT "" CACHE PATH "ExecuTorch source tree (a directory named executorch)")
set(ET_CMAKE_OUT "" CACHE PATH "installed llm-release build of that tree (cmake-out)")
if(NOT EXISTS "${EXECUTORCH_ROOT}/extension/llm/runner/text_prefiller.h")
  message(FATAL_ERROR "EXECUTORCH_ROOT=${EXECUTORCH_ROOT} has no extension/llm/runner/text_prefiller.h")
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

add_executable(et_native_bench ${CMAKE_CURRENT_SOURCE_DIR}/et_native_bench.cpp)
target_include_directories(et_native_bench PUBLIC ${EXECUTORCH_ROOT}/..)
target_compile_definitions(et_native_bench PRIVATE ET_USE_THREADPOOL)
target_compile_options(et_native_bench PRIVATE -Wno-deprecated-declarations)

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
# llama_main links torchao ops and KleidiAI only where the install built them (the llama README's
# Android stage 1 builds no torchao kernels); cpuinfo logs through liblog on Android.
foreach(_lib torchao_ops_executorch kleidiai)
  if(NOT TARGET ${_lib})
    list(REMOVE_ITEM link_libraries ${_lib})
  endif()
endforeach()
if(ANDROID)
  list(APPEND link_libraries log)
endif()
foreach(_lib optimized_native_cpu_ops_lib quantized_ops_lib custom_ops
             torchao_ops_executorch xnnpack_backend
)
  if(TARGET ${_lib})
    executorch_target_link_options_shared_lib(${_lib})
  endif()
endforeach()
target_link_libraries(et_native_bench PUBLIC ${link_libraries})
if(CMAKE_BUILD_TYPE STREQUAL "Release")
  target_link_options_gc_sections(et_native_bench)
  if(ANDROID)
    target_link_options(et_native_bench PRIVATE "LINKER:-s")
  endif()
endif()
