# Prompt hash check — the Swift task against the generated prompt file

`stub.swift` declares the two types `LongContextTask.swift` needs (the `BenchmarkTask` protocol, `GenerationParameters`)
so the real task source compiles alone on the Mac; `main.swift` prints the byte count and SHA-256 of the
`long-context-2048-gen256-noref` and `long-context-2048-gen256` prompts the task builds. Run from the repository root:

```bash
cd results/raw/2026-10-17-catalog-x2-iphone18pro-ios/tools/prompt-hash-check
swiftc -O stub.swift main.swift ../../../../../ios/BenchmarkApp/Sources/Benchmark/Tasks/LongContextTask.swift -o /tmp/promptcheck && /tmp/promptcheck
shasum -a 256 ../../../../../prompts/text/long-context-2048-gen256-noref.txt ../../../../../prompts/text/long-context-2048-gen256.txt
```

2026-10-17 19:40 JST: noref 7822 bytes 3e3f17a3941f25300adc2097db767582bbae95ef6ba46fc498588e4d0317b392, the 2048 task
7730 bytes eaf098b375fc13634367d529e54f17e7dbcf98b0ef1969417c56677e1bbc86c1 — both equal to the files `scripts/gen_task_prompts.py` writes.
