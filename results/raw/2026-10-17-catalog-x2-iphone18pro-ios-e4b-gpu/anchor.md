# Anchor launches (head = round 0, tail = round 99)

| when | arm | model | regime | decode tok/s | out tok | thermal start→end | file |
|---|---|---|---|---|---|---|---|
| head | mlx-swift | Qwen3-0.6B-4bit | cold | 231.5 | 128 | nominal→nominal | mlx-swift_mlx-community_Qwen3-0.6B-4bit_short-chat_2026-10-17T11-11-54Z.json |
| head | mlx-swift | Qwen3-0.6B-4bit | warm | 221.3 | 128 | nominal→nominal | mlx-swift_mlx-community_Qwen3-0.6B-4bit_short-chat_2026-10-17T11-11-55Z.json |
| head | mlx-swift | Qwen3-0.6B-4bit | warm | 221.6 | 128 | nominal→nominal | mlx-swift_mlx-community_Qwen3-0.6B-4bit_short-chat_2026-10-17T11-11-56Z.json |
| tail | mlx-swift | Qwen3-0.6B-4bit | cold | 221.7 | 128 | fair→fair | mlx-swift_mlx-community_Qwen3-0.6B-4bit_short-chat_2026-10-17T11-52-24Z.json |
| tail | mlx-swift | Qwen3-0.6B-4bit | warm | 220.2 | 128 | fair→fair | mlx-swift_mlx-community_Qwen3-0.6B-4bit_short-chat_2026-10-17T11-52-25Z.json |
| tail | mlx-swift | Qwen3-0.6B-4bit | warm | 219.6 | 128 | fair→fair | mlx-swift_mlx-community_Qwen3-0.6B-4bit_short-chat_2026-10-17T11-52-26Z.json |

Warm anchor median over the sitting: 220.8 tok/s (n=4; head 221.3, 221.6; tail 220.2, 219.6). Ratio to the reference 223.0: 0.990 (within the 5 % rule).
