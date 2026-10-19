# l4-litert-cpu-30s-S4 2026-10-19 15:18:41 JST label=cold
cool: ok after 183s
dexopt:       arm64: [status=run-from-apk] [reason=unknown] [primary-abi]
15:21:45 attempt 1: adb -s RFGL80R6A6H shell am instrument -r -e model parakeet-tdt-0.6b-v3-30s -e accelerator cpu -e manifest /data/user/0/com.google.ai.edge.examples.asr/files/sets/test-clean/manifest-device.tsv -e every 4 -e limit 0 -e tag l4-litert-cpu-30s-S4 -e load_label cold -e app_commit 289d4672fad088e416a0a91fcd0a842392abbf9b   com.google.ai.edge.examples.asr.test/androidx.test.runner.AndroidJUnitRunner
16:00:19 attempt 2: adb -s RFGL80R6A6H shell am instrument -r -e model parakeet-tdt-0.6b-v3-30s -e accelerator cpu -e manifest /data/user/0/com.google.ai.edge.examples.asr/files/sets/test-clean/manifest-device.tsv -e every 4 -e limit 0 -e tag l4-litert-cpu-30s-S4 -e load_label cold -e app_commit 289d4672fad088e416a0a91fcd0a842392abbf9b  -e start_after 121-121726-0005 -e failed_id 121-121726-0005 -e failed_kind crash com.google.ai.edge.examples.asr.test/androidx.test.runner.AndroidJUnitRunner
16:00:15 planned stop at the hold limit; see events.tsv notes (attempt 2 was the driver's relaunch after the stop)
