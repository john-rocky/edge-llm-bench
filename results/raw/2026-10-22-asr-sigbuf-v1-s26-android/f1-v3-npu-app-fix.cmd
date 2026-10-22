# v3-npu-app-fix 2026-10-22 12:58:35 JST
dexopt: app verify/install, test verify/install; screen:  mWakefulness=Awake 
12:58:36 adb -s RFGL80R6A6H shell am instrument -r -e class com.google.ai.edge.examples.asr.SigbufBenchTest -e model parakeet-tdt-0.6b-v3 -e accelerator npu -e manifest /data/user/0/com.google.ai.edge.examples.asr.sigbufcheck.npu/files/sets/test-clean/manifest-device.tsv -e every 32 -e limit 3 -e max_tokens 630 -e pace none  -e foreground front -e tag v3-npu-app-fix com.google.ai.edge.examples.asr.sigbufcheck.npu.test/androidx.test.runner.AndroidJUnitRunner
