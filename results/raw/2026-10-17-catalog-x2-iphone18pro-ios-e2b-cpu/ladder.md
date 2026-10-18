# 2026-10-17-catalog-x2-iphone18pro-ios-e2b-cpu — ladder (median [min–max] over rounds; spread = max/min − 1; Δ = decode median vs the smallest allocation)

Rounds selected: 1,2,3,4,5.

Engine stamped: v0.18.0; build configuration: Release; records in the ladder: 30; unmapped records (no launch line): 0.


## litert-lm-cpu — litert-community/gemma-4-E2B-it-litert-lm — long-context-2048-gen256-noref

| regime | ctx | rounds | decode tok/s | spread | Δ vs smallest | prefill tok/s | TTFT ms | prompt tok | out tok (short) | stop | thermal start→end | resident peak MiB |
|---|---:|---|---|---:|---:|---|---|---|---|---|---|---|
| warm | 2304 | 1,2,3,4,5 | 32.6 [32.6–32.9] n=5 | 1.1 % | +0.0 % | 753 [749–762] n=5 | 2270 [2242–2281] n=5 | 1654 | 256 [256–256] n=5 (0) | length×5 | fair→fair,nominal→nominal | 1684 [1683–2520] n=5 |
| warm | 4096 | 1,2,3,4,5 | 30.0 [29.9–30.1] n=5 | 0.7 % | -7.9 % | 601 [600–604] n=5 | 2830 [2815–2835] n=5 | 1654 | 256 [256–256] n=5 (0) | length×5 | fair→fair,nominal→nominal | 1900 [1899–1902] n=5 |
| warm | 8192 | 1,2,3,4,5 | 25.7 [25.6–25.8] n=5 | 0.6 % | -21.1 % | 414 [410–415] n=5 | 4083 [4072–4126] n=5 | 1654 | 256 [256–256] n=5 (0) | length×5 | fair→fair,nominal→nominal | 2436 [2435–2437] n=5 |
| cold | 2304 | 2,3,4,5 | 33.3 [33.2–33.4] n=4 | 0.4 % | +0.0 % | 801 [799–802] n=4 | 2155 [2154–2161] n=4 | 1654 | 256 [256–256] n=4 (0) | length×4 | fair→fair | 1671 [1670–1672] n=4 |
| cold | 4096 | 1,2,3,4,5 | 30.6 [30.5–30.7] n=5 | 0.8 % | -8.2 % | 637 [635–638] n=5 | 2696 [2688–2700] n=5 | 1654 | 256 [256–256] n=5 (0) | length×5 | fair→fair,nominal→nominal | 1888 [1887–1965] n=5 |
| cold | 8192 | 1,2,3,4,5 | 26.1 [26.0–26.1] n=5 | 0.5 % | -21.6 % | 434 [432–435] n=5 | 3917 [3909–3936] n=5 | 1654 | 256 [256–256] n=5 (0) | length×5 | fair→fair,nominal→nominal | 2424 [2423–2425] n=5 |

First-ever cold records (the allocation's first launch of the sitting, load time > 2× the cell's median; kept apart, not in the cold rows above): ctx 2304 round 1: decode 32.7, prefill 733, load 1.61 s, resident peak 2508 MiB.
