# b-l1-litert-cpu-5s-S32 2026-10-19 23:58:26 JST label=cold
cool: ok after 143s
dexopt: app speed/cmdline, test speed/cmdline; screen:  mWakefulness=Awake 
00:00:50 attempt 1: adb -s RFGL80R6A6H shell am instrument -r -e engine litert -e model parakeet-tdt-0.6b-v3 -e accelerator cpu -e manifest /data/user/0/com.google.ai.edge.examples.asr.burst/files/sets/test-clean/manifest-device.tsv -e every 32 -e limit 0 -e tag b-l1-litert-cpu-5s-S32 -e load_label cold -e app_commit 5f23093fb483498948497a42a83bb46ef68ff2c4 -e dexopt_app speed/cmdline -e dexopt_test speed/cmdline -e pace burst -e warmup_id 1995-1836-0004 -e foreground front -e require_top_app true   com.google.ai.edge.examples.asr.burst.test/androidx.test.runner.AndroidJUnitRunner
