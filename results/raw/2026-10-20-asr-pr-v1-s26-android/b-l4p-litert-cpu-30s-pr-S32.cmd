# b-l4p-litert-cpu-30s-pr-S32 2026-10-20 13:11:36 JST label=warm
cool: ok after 83s
dexopt: app speed/cmdline, test speed/cmdline; screen:  mWakefulness=Awake 
13:13:00 attempt 1: adb -s RFGL80R6A6H shell am instrument -r -e engine litert -e model parakeet-tdt-0.6b-v3-30s -e accelerator cpu -e manifest /data/user/0/com.google.ai.edge.examples.asr.prcheck/files/sets/test-clean/manifest-device.tsv -e every 32 -e limit 0 -e tag b-l4p-litert-cpu-30s-pr-S32 -e load_label warm -e app_commit 8b9f5590cf7e642e4f72a197096278a015130761 -e dexopt_app speed/cmdline -e dexopt_test speed/cmdline -e pace burst -e warmup_id 1995-1836-0004 -e foreground front -e require_top_app true  com.google.ai.edge.examples.asr.prcheck.test/androidx.test.runner.AndroidJUnitRunner
