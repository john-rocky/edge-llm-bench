| runtime | model | task | cold (run1) | warm (med r2-4) | n | thermal |
|---|---|---|---|---|---|---|
| executorch-xnnpack | own-export/Qwen3-0.6B-ET1.5.1-xnnpack-8da4w-emb8-ctx2048 | long-context-1024-gen256 | 81.2 | 72.7 | 4 | nominal |
| executorch-xnnpack | own-export/Qwen3-0.6B-ET1.5.1-xnnpack-8da4w-emb8-ctx2048 | short-chat | 189.0 | 192.1 | 4 | nominal |
| executorch-xnnpack | own-export/Qwen3-1.7B-ET1.5.1-xnnpack-8da4w-emb8-ctx2048 | long-context-1024-gen256 | 43.9 | 38.0 | 4 | nominal |
| executorch-xnnpack | own-export/Qwen3-1.7B-ET1.5.1-xnnpack-8da4w-emb8-ctx2048 | short-chat | 63.0 | 69.4 | 4 | nominal |
| executorch-xnnpack | own-export/Qwen3-4B-ET1.5.1-xnnpack-8da4w-emb8-ctx2048 | long-context-1024-gen256 | 19.5 | 13.4 | 4 | fair,serious |
| executorch-xnnpack | own-export/Qwen3-4B-ET1.5.1-xnnpack-8da4w-emb8-ctx2048 | short-chat | 32.2 | 27.8 | 4 | nominal |
