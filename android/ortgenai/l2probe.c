// What bionic's sysconf() reports for the CPU caches on the device: the value
// ONNX Runtime 1.30.0's posix Env::GetL2CacheSize() returns on Android, which
// the GroupQueryAttention CPU flash path sizes its tiles from (round r2c,
// 2026-10-08). Dynamically linked on purpose: the device's libc.so answers.
//   clang --target=aarch64-linux-android28 -O2 -Wall -fPIE -pie -o l2probe l2probe.c
#include <errno.h>
#include <stdio.h>
#include <unistd.h>

static void q(const char* name, int id) {
  errno = 0;
  long v = sysconf(id);
  printf("%s %ld errno=%d\n", name, v, errno);
}

int main(void) {
  q("_SC_LEVEL1_DCACHE_SIZE", _SC_LEVEL1_DCACHE_SIZE);
  q("_SC_LEVEL2_CACHE_SIZE", _SC_LEVEL2_CACHE_SIZE);
  q("_SC_LEVEL3_CACHE_SIZE", _SC_LEVEL3_CACHE_SIZE);
  q("_SC_NPROCESSORS_ONLN", _SC_NPROCESSORS_ONLN);
  q("_SC_LEVEL1_DCACHE_LINESIZE", _SC_LEVEL1_DCACHE_LINESIZE);
  q("_SC_LEVEL1_ICACHE_LINESIZE", _SC_LEVEL1_ICACHE_LINESIZE);
  q("_SC_LEVEL2_CACHE_LINESIZE", _SC_LEVEL2_CACHE_LINESIZE);
  return 0;
}
