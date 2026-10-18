# 2026-10-17-catalog-x2-iphone18pro-ios-e4b-cpu-s2 — ladder (median [min–max] over rounds; spread = max/min − 1; Δ = decode median vs the smallest allocation)

Engine stamped: v0.18.0; build configuration: Release; records in the ladder: 22; unmapped records (no launch line): 0.


## litert-lm-cpu — litert-community/gemma-4-E4B-it-litert-lm — long-context-2048-gen256-noref

| regime | ctx | rounds | decode tok/s | spread | Δ vs smallest | prefill tok/s | TTFT ms | prompt tok | out tok (short) | stop | thermal start→end | resident peak MiB |
|---|---:|---|---|---:|---:|---|---|---|---|---|---|---|
| warm | 2304 | 1,2,3 | 13.8 [12.7–13.9] n=3 | 9.1 % | +0.0 % | 347 [346–353] n=3 | 4926 [4842–4940] n=3 | 1654 | 256 [256–256] n=3 (0) | length×3 | fair→fair,fair→serious,nominal→nominal | 3207 [3207–3207] n=3 |
| warm | 4096 | 1,2,3,4 | 12.7 [12.0–13.1] n=4 | 9.2 % | -7.7 % | 293 [292–296] n=4 | 5814 [5755–5835] n=4 | 1654 | 256 [256–256] n=4 (0) | length×4 | fair→serious,nominal→fair,nominal→nominal | 3426 [3425–3426] n=4 |
| warm | 8192 | 1,2,3,4 | 11.2 [10.4–11.4] n=4 | 9.3 % | -18.7 % | 217 [217–218] n=4 | 7787 [7752–7818] n=4 | 1654 | 256 [256–256] n=4 (0) | length×4 | fair→serious,nominal→fair | 4000 [3999–4000] n=4 |
| cold | 2304 | 1,2,3 | 14.4 [14.0–14.5] n=3 | 3.2 % | +0.0 % | 373 [323–375] n=3 | 4640 [4607–5970] n=3 | 1654 | 256 [256–256] n=3 (0) | length×3 | fair→fair,nominal→nominal | 3196 [3196–3196] n=3 |
| cold | 4096 | 1,2,3,4 | 13.7 [13.5–13.8] n=4 | 2.0 % | -4.9 % | 317 [314–320] n=4 | 5414 [5377–5474] n=4 | 1654 | 256 [256–256] n=4 (0) | length×4 | fair→fair,nominal→nominal | 3415 [3414–3415] n=4 |
| cold | 8192 | 1,2,3,4 | 12.2 [12.2–12.3] n=4 | 1.0 % | -14.9 % | 232 [232–233] n=4 | 7331 [7317–7361] n=4 | 1654 | 256 [256–256] n=4 (0) | length×4 | fair→fair,nominal→nominal | 3988 [3987–3988] n=4 |

No first-ever cold record (every allocation's first launch loaded within 2× the cell's median load time).
