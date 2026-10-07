/*
 * stb implementations for ExecuTorch's Gemma 4 e2e runner (examples/models/gemma4).
 * Its Buck target links a prebuilt "stb"; the CMake build here compiles them:
 * e2e_runner.cpp calls stbi_load / stbi_image_free, image_utils.h calls
 * stbir_resize_uint8_generic (stb's deprecated/stb_image_resize.h).
 */
#define STB_IMAGE_IMPLEMENTATION
#include <stb_image.h>
#define STB_IMAGE_RESIZE_IMPLEMENTATION
#include <stb_image_resize.h>
