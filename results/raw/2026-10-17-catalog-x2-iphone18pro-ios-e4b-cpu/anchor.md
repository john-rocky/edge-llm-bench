# Anchor launches (head = round 0, tail = round 99)

| when | arm | model | regime | decode tok/s | out tok | thermal start→end | file |
|---|---|---|---|---|---|---|---|
| head | mlx-swift | Qwen3-0.6B-4bit | cold | 221.3 | 128 | fair→fair | mlx-swift_mlx-community_Qwen3-0.6B-4bit_short-chat_2026-10-17T12-36-04Z.json |
| head | mlx-swift | Qwen3-0.6B-4bit | warm | 220.1 | 128 | fair→fair | mlx-swift_mlx-community_Qwen3-0.6B-4bit_short-chat_2026-10-17T12-36-05Z.json |
| head | mlx-swift | Qwen3-0.6B-4bit | warm | 219.8 | 128 | fair→fair | mlx-swift_mlx-community_Qwen3-0.6B-4bit_short-chat_2026-10-17T12-36-06Z.json |
| tail | mlx-swift | Qwen3-0.6B-4bit | cold | 221.7 | 128 | fair→fair | mlx-swift_mlx-community_Qwen3-0.6B-4bit_short-chat_2026-10-17T13-18-39Z.json |
| tail | mlx-swift | Qwen3-0.6B-4bit | warm | 221.2 | 128 | fair→fair | mlx-swift_mlx-community_Qwen3-0.6B-4bit_short-chat_2026-10-17T13-18-40Z.json |
| tail | mlx-swift | Qwen3-0.6B-4bit | warm | 220.8 | 128 | fair→fair | mlx-swift_mlx-community_Qwen3-0.6B-4bit_short-chat_2026-10-17T13-18-41Z.json |

Warm anchor median over the sitting: 220.5 tok/s (n=4; head 220.1, 219.8; tail 221.2, 220.8). Ratio to the reference 223.0: 0.989 (within the 5 % rule).
