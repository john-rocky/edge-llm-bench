# Anchor launches (head = round 0, tail = round 99)

| when | arm | model | regime | decode tok/s | out tok | thermal start→end | file |
|---|---|---|---|---|---|---|---|
| head | mlx-swift | Qwen3-0.6B-4bit | cold | 229.0 | 128 | nominal→nominal | mlx-swift_mlx-community_Qwen3-0.6B-4bit_short-chat_2026-10-17T10-47-08Z.json |
| head | mlx-swift | Qwen3-0.6B-4bit | warm | 222.5 | 128 | nominal→nominal | mlx-swift_mlx-community_Qwen3-0.6B-4bit_short-chat_2026-10-17T10-47-09Z.json |
| head | mlx-swift | Qwen3-0.6B-4bit | warm | 222.8 | 128 | nominal→nominal | mlx-swift_mlx-community_Qwen3-0.6B-4bit_short-chat_2026-10-17T10-47-10Z.json |
| tail | mlx-swift | Qwen3-0.6B-4bit | cold | 225.2 | 128 | nominal→nominal | mlx-swift_mlx-community_Qwen3-0.6B-4bit_short-chat_2026-10-17T11-11-23Z.json |
| tail | mlx-swift | Qwen3-0.6B-4bit | warm | 221.2 | 128 | nominal→nominal | mlx-swift_mlx-community_Qwen3-0.6B-4bit_short-chat_2026-10-17T11-11-24Z.json |
| tail | mlx-swift | Qwen3-0.6B-4bit | warm | 221.7 | 128 | nominal→nominal | mlx-swift_mlx-community_Qwen3-0.6B-4bit_short-chat_2026-10-17T11-11-25Z.json |

Warm anchor median over the sitting: 222.1 tok/s (n=4; head 222.5, 222.8; tail 221.2, 221.7). Ratio to the reference 223.0: 0.996 (within the 5 % rule).
