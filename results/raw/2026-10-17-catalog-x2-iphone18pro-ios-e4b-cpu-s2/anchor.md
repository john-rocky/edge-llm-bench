# Anchor launches (head = round 0, tail = round 99)

| when | arm | model | regime | decode tok/s | out tok | thermal start→end | file |
|---|---|---|---|---|---|---|---|
| head | mlx-swift | Qwen3-0.6B-4bit | cold | 225.7 | 128 | nominal→nominal | mlx-swift_mlx-community_Qwen3-0.6B-4bit_short-chat_2026-10-17T15-08-15Z.json |
| head | mlx-swift | Qwen3-0.6B-4bit | warm | 222.4 | 128 | nominal→nominal | mlx-swift_mlx-community_Qwen3-0.6B-4bit_short-chat_2026-10-17T15-08-16Z.json |
| head | mlx-swift | Qwen3-0.6B-4bit | warm | 221.5 | 128 | nominal→nominal | mlx-swift_mlx-community_Qwen3-0.6B-4bit_short-chat_2026-10-17T15-08-17Z.json |

Warm anchor median over the sitting: 222.0 tok/s (n=2; head 222.4, 221.5; tail —). Ratio to the reference 223.0: 0.995 (within the 5 % rule).
