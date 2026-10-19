# b-l4-litert-cpu-30s-off-first20 2026-10-19 18:21:17 JST label=cold
cool: ok after 406s
dexopt: app speed/cmdline, test speed/cmdline; screen:  mWakefulness=Awake 
18:28:04 attempt 1: adb -s RFGL80R6A6H shell am instrument -r -e engine litert -e model parakeet-tdt-0.6b-v3-30s -e accelerator cpu -e tdt_fix false -e manifest /data/user/0/com.google.ai.edge.examples.asr.burstfix/files/sets/test-clean/manifest-device.tsv -e every 16 -e limit 20 -e tag b-l4-litert-cpu-30s-off-first20 -e load_label cold -e app_commit 6885e1709d7b183df856dcaa4e11bd26b3b5dd19 -e dexopt_app speed/cmdline -e dexopt_test speed/cmdline -e pace burst -e warmup_id 1995-1836-0004 -e foreground front -e require_top_app true  com.google.ai.edge.examples.asr.burstfix.test/androidx.test.runner.AndroidJUnitRunner
