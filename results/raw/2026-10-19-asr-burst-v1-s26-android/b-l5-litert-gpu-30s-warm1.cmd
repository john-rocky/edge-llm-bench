# b-l5-litert-gpu-30s-warm1 2026-10-19 23:56:12 JST label=warm
cool: ok after 41s
dexopt: app speed/cmdline, test speed/cmdline; screen:  mWakefulness=Awake 
23:56:54 attempt 1: adb -s RFGL80R6A6H shell am instrument -r -e engine litert -e model parakeet-tdt-0.6b-v3-30s -e accelerator gpu -e manifest /data/user/0/com.google.ai.edge.examples.asr.burst/files/sets/test-clean/manifest-device.tsv -e every 32 -e limit 1 -e tag b-l5-litert-gpu-30s-warm1 -e load_label warm -e app_commit 5f23093fb483498948497a42a83bb46ef68ff2c4 -e dexopt_app speed/cmdline -e dexopt_test speed/cmdline -e pace burst -e warmup_id 1995-1836-0004 -e foreground front -e require_top_app true   com.google.ai.edge.examples.asr.burst.test/androidx.test.runner.AndroidJUnitRunner
