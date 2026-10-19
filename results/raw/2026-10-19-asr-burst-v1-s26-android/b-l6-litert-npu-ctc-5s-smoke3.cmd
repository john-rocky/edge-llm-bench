# b-l6-litert-npu-ctc-5s-smoke3 2026-10-19 22:54:11 JST label=cold
cool: ok after 468s
dexopt: app speed/cmdline, test speed/cmdline; screen:  mWakefulness=Awake 
23:02:00 attempt 1: adb -s RFGL80R6A6H shell am instrument -r -e engine litert -e model parakeet-ctc-0.6b -e accelerator npu -e manifest /data/user/0/com.google.ai.edge.examples.asr.burst/files/sets/test-clean/manifest-device.tsv -e every 32 -e limit 3 -e tag b-l6-litert-npu-ctc-5s-smoke3 -e load_label cold -e app_commit 5f23093fb483498948497a42a83bb46ef68ff2c4 -e dexopt_app speed/cmdline -e dexopt_test speed/cmdline -e pace burst -e warmup_id 1995-1836-0004 -e foreground front -e require_top_app true   com.google.ai.edge.examples.asr.burst.test/androidx.test.runner.AndroidJUnitRunner
