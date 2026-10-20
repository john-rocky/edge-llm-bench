# e-l4p-litert-cpu-30s-pr-edge2 2026-10-20 13:00:31 JST label=cold
cool: ok after 652s
dexopt: app speed/cmdline, test speed/cmdline; screen:  mWakefulness=Awake 
13:11:24 attempt 1: adb -s RFGL80R6A6H shell am instrument -r -e engine litert -e model parakeet-tdt-0.6b-v3-30s -e accelerator cpu -e manifest /data/user/0/com.google.ai.edge.examples.asr.prcheck/files/sets/test-clean/manifest-edge.tsv -e every 1 -e limit 2 -e tag e-l4p-litert-cpu-30s-pr-edge2 -e load_label cold -e app_commit 8b9f5590cf7e642e4f72a197096278a015130761 -e dexopt_app speed/cmdline -e dexopt_test speed/cmdline -e pace none -e warmup_id 1995-1836-0004 -e foreground front -e require_top_app true  com.google.ai.edge.examples.asr.prcheck.test/androidx.test.runner.AndroidJUnitRunner
