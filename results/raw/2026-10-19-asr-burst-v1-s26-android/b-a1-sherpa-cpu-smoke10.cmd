# b-a1-sherpa-cpu-smoke10 2026-10-19 16:03:43 JST label=cold
cool: ok after 530s
dexopt: app speed/cmdline, test speed/cmdline; screen:  mWakefulness=Awake 
16:12:34 attempt 1: adb -s RFGL80R6A6H shell am instrument -r -e engine sherpa -e model sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8 -e accelerator cpu -e manifest /data/user/0/com.google.ai.edge.examples.asr.burst/files/sets/test-clean/manifest-device.tsv -e every 16 -e limit 10 -e tag b-a1-sherpa-cpu-smoke10 -e load_label cold -e app_commit 5f23093fb483498948497a42a83bb46ef68ff2c4 -e dexopt_app speed/cmdline -e dexopt_test speed/cmdline -e pace burst -e warmup_id 1995-1836-0004 -e foreground front -e require_top_app false   com.google.ai.edge.examples.asr.burst.test/androidx.test.runner.AndroidJUnitRunner
