# Diagnostics behind the 2026-09-01 upstream issues (not campaign rows)

Post-baseline probes — DIAGNOSTIC runs, off the standing protocol; never
pool them with campaign records.

- `granite_5m_cap1024.{jsonl,turns.ndjson}` — endurance-chat-5m with
  `ENDURANCE_TURN_CAP=1024` (protocol cap is 256). The refutation test for
  the first "capped-mid-think empties history" hypothesis: coherence does
  NOT return at cap 1024 (23/29 turns degenerate, same answer lag), which
  redirected the investigation to the history render itself.
- `granite_debug_render.txt` — `yardstick debug-render` transcript: the
  engine's own `renderMessageIntoString` output showing assistant-history
  turns keep the pre-opened `<think>` with no closure and drop the thought
  channel; a capped turn renders as an empty `<think>\n<|im_end|>` turn.
  The measured mechanism cited verbatim in LiteRT-LM issue #3445.

Issues these back: google-ai-edge/LiteRT-LM #3443 (Qwen3-0.6B turn-2 render
prefix mismatch), #3444 (kv-wall / no ceiling API), #3445 (think-prefix
history never closes `</think>`), #3446 (~1 MB retained per conversation
rollover).
