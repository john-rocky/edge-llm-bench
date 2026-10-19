# b-l4-litert-cpu-30s-S32 2026-10-19 16:30:13 JST label=cold
cool: ok after 41s
dexopt: app speed/cmdline, test speed/cmdline; screen:  mWakefulness=Awake 
16:30:54 attempt 1: adb -s RFGL80R6A6H shell am instrument -r -e engine litert -e model parakeet-tdt-0.6b-v3-30s -e accelerator cpu -e manifest /data/user/0/com.google.ai.edge.examples.asr.burst/files/sets/test-clean/manifest-device.tsv -e every 32 -e limit 0 -e tag b-l4-litert-cpu-30s-S32 -e load_label cold -e app_commit 5f23093fb483498948497a42a83bb46ef68ff2c4 -e dexopt_app speed/cmdline -e dexopt_test speed/cmdline -e pace burst -e warmup_id 1995-1836-0004 -e foreground front -e require_top_app true   com.google.ai.edge.examples.asr.burst.test/androidx.test.runner.AndroidJUnitRunner
# b-l4-litert-cpu-30s-S32.resume1 2026-10-20 00:36:01 JST label=warm
cool: ok after 326s
dexopt: app speed/cmdline, test speed/cmdline; screen:  mWakefulness=Awake 
00:41:27 attempt 1.resume1: adb -s RFGL80R6A6H shell am instrument -r -e engine litert -e model parakeet-tdt-0.6b-v3-30s -e accelerator cpu -e manifest /data/user/0/com.google.ai.edge.examples.asr.burst/files/sets/test-clean/manifest-device.tsv -e every 32 -e limit 0 -e tag b-l4-litert-cpu-30s-S32 -e load_label warm -e app_commit 5f23093fb483498948497a42a83bb46ef68ff2c4 -e dexopt_app speed/cmdline -e dexopt_test speed/cmdline -e pace burst -e warmup_id 1995-1836-0004 -e foreground front -e require_top_app true  -e start_after 8463-294828-0029 com.google.ai.edge.examples.asr.burst.test/androidx.test.runner.AndroidJUnitRunner
