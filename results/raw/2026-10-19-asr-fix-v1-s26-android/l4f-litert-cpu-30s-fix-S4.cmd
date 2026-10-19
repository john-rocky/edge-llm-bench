# l4f-litert-cpu-30s-fix-S4 2026-10-19 18:35:31 JST label=warm
cool: ok after 162s
dexopt: app speed/cmdline, test speed/cmdline; screen:  mWakefulness=Awake 
18:38:14 attempt 1: adb -s RFGL80R6A6H shell am instrument -r -e engine litert -e model parakeet-tdt-0.6b-v3-30s -e accelerator cpu -e tdt_fix true -e manifest /data/user/0/com.google.ai.edge.examples.asr.burstfix/files/sets/test-clean/manifest-device.tsv -e every 4 -e limit 0 -e tag l4f-litert-cpu-30s-fix-S4 -e load_label warm -e app_commit 6885e1709d7b183df856dcaa4e11bd26b3b5dd19 -e dexopt_app speed/cmdline -e dexopt_test speed/cmdline -e pace none -e warmup_id 1995-1836-0004 -e foreground front -e require_top_app true  com.google.ai.edge.examples.asr.burstfix.test/androidx.test.runner.AndroidJUnitRunner
# l4f-litert-cpu-30s-fix-S4.resume1 2026-10-19 22:13:55 JST label=warm
cool: ok after 875s
dexopt: app speed/cmdline, test speed/cmdline; screen:  mWakefulness=Awake 
22:28:31 attempt 1.resume1: adb -s RFGL80R6A6H shell am instrument -r -e engine litert -e model parakeet-tdt-0.6b-v3-30s -e accelerator cpu -e tdt_fix true -e manifest /data/user/0/com.google.ai.edge.examples.asr.burstfix/files/sets/test-clean/manifest-device.tsv -e every 4 -e limit 0 -e tag l4f-litert-cpu-30s-fix-S4 -e load_label warm -e app_commit 6885e1709d7b183df856dcaa4e11bd26b3b5dd19 -e dexopt_app speed/cmdline -e dexopt_test speed/cmdline -e pace none -e warmup_id 1995-1836-0004 -e foreground front -e require_top_app true -e start_after 6829-68769-0014 com.google.ai.edge.examples.asr.burstfix.test/androidx.test.runner.AndroidJUnitRunner
