# l4-litert-cpu-30s-S4-p2 2026-10-19 17:48:36 JST label=cold
cool: ok after 1s
dexopt:       arm64: [status=run-from-apk] [reason=unknown] [primary-abi]
17:48:37 attempt 1: adb -s RFGL80R6A6H shell am instrument -r -e model parakeet-tdt-0.6b-v3-30s -e accelerator cpu -e manifest /data/user/0/com.google.ai.edge.examples.asr/files/sets/test-clean/manifest-device.tsv -e every 4 -e limit 0 -e tag l4-litert-cpu-30s-S4-p2 -e load_label cold -e app_commit 289d4672fad088e416a0a91fcd0a842392abbf9b  -e start_after 260-123440-0005 com.google.ai.edge.examples.asr.test/androidx.test.runner.AndroidJUnitRunner
