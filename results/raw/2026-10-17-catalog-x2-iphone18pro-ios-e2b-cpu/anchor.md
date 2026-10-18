# Anchor launches (head = round 0, tail = round 99)

| when | arm | model | regime | decode tok/s | out tok | thermal start→end | file |
|---|---|---|---|---|---|---|---|
| head | mlx-swift | Qwen3-0.6B-4bit | cold | 220.9 | 128 | fair→fair | mlx-swift_mlx-community_Qwen3-0.6B-4bit_short-chat_2026-10-17T11-52-55Z.json |
| head | mlx-swift | Qwen3-0.6B-4bit | warm | 219.9 | 128 | fair→fair | mlx-swift_mlx-community_Qwen3-0.6B-4bit_short-chat_2026-10-17T11-52-56Z.json |
| tail | mlx-swift | Qwen3-0.6B-4bit | cold | 222.5 | 128 | fair→fair | mlx-swift_mlx-community_Qwen3-0.6B-4bit_short-chat_2026-10-17T12-35-28Z.json |
| tail | mlx-swift | Qwen3-0.6B-4bit | warm | 220.7 | 128 | fair→fair | mlx-swift_mlx-community_Qwen3-0.6B-4bit_short-chat_2026-10-17T12-35-29Z.json |
| tail | mlx-swift | Qwen3-0.6B-4bit | warm | 220.8 | 128 | fair→fair | mlx-swift_mlx-community_Qwen3-0.6B-4bit_short-chat_2026-10-17T12-35-30Z.json |

Warm anchor median over the sitting: 220.7 tok/s (n=3; head 219.9; tail 220.7, 220.8). Ratio to the reference 223.0: 0.990 (within the 5 % rule).
