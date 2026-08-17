# Task D — App-lifecycle loop

This task simulates real usage. It is the task most likely to expose runtimes that look fast on a single benchmark but cannot survive shipping.

## Steps

1. **Load model** — measure cold load time
2. **Short Q1** — `Hello!` (5 tokens out)
3. **Short Q2 with history** — `What did I just say?` (forces the runtime to either use the existing KV cache or re-prefill)
4. **Cancel mid-generation** — start a 256-token generation and cancel after 50 tokens; measure cancellation latency
5. **New generation after cancel** — confirm the runtime is in a clean state
6. **Background the app** for 10 s
7. **Foreground** and immediately start a new generation — measure recovery
8. **Repeat (2)–(5)** five more times — measure memory drift and tail-latency drift

## What this measures

- Cancellation success and latency
- Background → foreground recovery (does the model still work? does it have to reload?)
- Memory drift across N sessions
- Stability — any crash, hang, or watchdog termination is a failure

## Why this matters

Most published "tokens/sec" numbers come from a single generation in a tight loop. Apps that ship to the App Store get cancelled, backgrounded, foregrounded, and asked to handle dozens of generations per session. A runtime that drops 20% of its decode rate by the 10th generation is not shippable.
