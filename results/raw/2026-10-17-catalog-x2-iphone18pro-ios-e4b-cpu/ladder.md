# 2026-10-17-catalog-x2-iphone18pro-ios-e4b-cpu — ladder (median [min–max] over rounds; spread = max/min − 1; Δ = decode median vs the smallest allocation)

Engine stamped: v0.18.0; build configuration: Release; records in the ladder: 16; unmapped records (no launch line): 0.


## litert-lm-cpu — litert-community/gemma-4-E4B-it-litert-lm — long-context-2048-gen256-noref

| regime | ctx | rounds | decode tok/s | spread | Δ vs smallest | prefill tok/s | TTFT ms | prompt tok | out tok (short) | stop | thermal start→end | resident peak MiB |
|---|---:|---|---|---:|---:|---|---|---|---|---|---|---|
| warm | 2304 | 1,2,3 | 13.7 [13.2–13.8] n=3 | 4.2 % | +0.0 % | 347 [347–347] n=3 | 4926 [4921–4931] n=3 | 1654 | 256 [256–256] n=3 (0) | length×3 | fair→fair,nominal→fair | 3208 [3208–5464] n=3 |
| warm | 4096 | 1,2,3 | 12.1 [11.3–12.1] n=3 | 6.8 % | -12.3 % | 292 [291–292] n=3 | 5828 [5820–5855] n=3 | 1654 | 256 [256–256] n=3 (0) | length×3 | fair→serious | 3425 [3425–3426] n=3 |
| warm | 8192 | 1,2 | 11.5 [11.3–11.7] n=2 | 4.4 % | -16.3 % | 217 [217–217] n=2 | 7801 [7796–7806] n=2 | 1654 | 256 [256–256] n=2 (0) | length×2 | nominal→fair,nominal→serious | 4048 [4048–4048] n=2 |
| cold | 2304 | 2,3 | 14.5 [14.4–14.5] n=2 | 0.5 % | +0.0 % | 376 [374–377] n=2 | 4597 [4582–4612] n=2 | 1654 | 256 [256–256] n=2 (0) | length×2 | fair→fair,nominal→nominal | 3196 [3196–3196] n=2 |
| cold | 4096 | 1,2,3 | 13.6 [13.5–13.6] n=3 | 0.5 % | -6.2 % | 315 [314–315] n=3 | 5460 [5459–5473] n=3 | 1654 | 256 [256–256] n=3 (0) | length×3 | fair→fair | 3414 [3414–3415] n=3 |
| cold | 8192 | 1,2 | 12.0 [11.8–12.3] n=2 | 4.0 % | -16.9 % | 222 [211–234] n=2 | 7930 [7297–8563] n=2 | 1654 | 256 [256–256] n=2 (0) | length×2 | fair→nominal,nominal→nominal | 4041 [4037–4045] n=2 |

First-ever cold records (the allocation's first launch of the sitting, load time > 2× the cell's median; kept apart, not in the cold rows above): ctx 2304 round 1: decode 14.4, prefill 373, load 2.99 s, resident peak 5453 MiB.
