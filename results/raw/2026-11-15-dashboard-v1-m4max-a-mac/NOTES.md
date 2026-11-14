# Core AI records set aside (2026-11-15)

The Core AI records of this sitting (`core-ai/qwen3-0.6b-4bit-gpu` and `core-ai/qwen3-1.7b-gpu` short-chat, 4 runs
each) are kept here as `core-ai_core-ai_qwen3-0_6b-4bit-gpu_short-chat.jsonl.quarantine-stamp` and
`core-ai_core-ai_qwen3-1_7b-gpu_short-chat.jsonl.quarantine-stamp` and are not records of the sitting.

- They stamp `engineVersion` `0.2.0-dirty+static-inputs-patch`. The yardstick that measured them
  (`.build/dd-mac/Build/Products/Release/yardstick`, built 2026-10-31 09:24) carries apple/coreai-models at
  bd3c539 (`1.0.0-10-gbd3c539`, the pin in `environment.lock.json`): the binary holds none of the 0.2.0 patch's
  `EngineOptions` field `perTokenInputProvider`, which the 0.2.0-based yardsticks of 2026-09-11 and 2026-09-18 hold,
  and the same binary stamped `1.0.0-10-gbd3c539` in the 2026-11-08 sittings.
- The yardstick reads the stamp at run time from `ios/BenchmarkApp/Vendored/engine-pins.json`
  (`EnginePins.swift`). That file was rewritten on 2026-11-09 04:40 while `ios/BenchmarkApp/Vendored/coreai-models`
  pointed at a 0.2.0 checkout with the patch. Since 2026-11-15 07:50 the link points at a bd3c539 checkout again and
  the file says `1.0.0-10-gbd3c539` (no other entry changed).
- The Core AI cells of this sitting are measured again at the next weekly Mac sitting.
