# 2026-10-17-catalog-x2-iphone18pro-ios-e4b-gpu — ladder (median [min–max] over rounds; spread = max/min − 1; Δ = decode median vs the smallest allocation)

Engine stamped: v0.18.0; build configuration: Release; records in the ladder: 36; unmapped records (no launch line): 0.


## litert-lm — litert-community/gemma-4-E4B-it-litert-lm — long-context-2048-gen256-noref

| regime | ctx | rounds | decode tok/s | spread | Δ vs smallest | prefill tok/s | TTFT ms | prompt tok | out tok (short) | stop | thermal start→end | resident peak MiB |
|---|---:|---|---|---:|---:|---|---|---|---|---|---|---|
| warm | 2304 | 1,2,3,4,5,6 | 38.5 [38.4–38.6] n=6 | 0.3 % | +0.0 % | 1707 [1702–1717] n=6 | 1032 [1028–1036] n=6 | 1654 | 256 [256–256] n=6 (0) | length×6 | fair→fair,nominal→nominal | 605 [540–2869] n=6 |
| warm | 4096 | 1,2,3,4,5,6 | 37.9 [37.9–37.9] n=6 | 0.2 % | -1.7 % | 1548 [1540–1550] n=6 | 1132 [1130–1138] n=6 | 1654 | 256 [256–256] n=6 (0) | length×6 | fair→fair,nominal→nominal | 818 [573–2189] n=6 |
| warm | 8192 | 1,2,3,4,5,6 | 36.9 [36.9–37.0] n=6 | 0.2 % | -4.1 % | 1313 [1310–1321] n=6 | 1324 [1315–1329] n=6 | 1654 | 256 [256–256] n=6 (0) | length×6 | fair→fair,nominal→nominal | 588 [560–591] n=6 |
| cold | 2304 | 2,3,4,5,6 | 35.5 [35.4–38.4] n=5 | 8.5 % | +0.0 % | 1491 [1319–1710] n=5 | 1709 [1034–1867] n=5 | 1654 | 256 [256–256] n=5 (0) | length×5 | fair→fair | 688 [655–789] n=5 |
| cold | 4096 | 2,3,4,5,6 | 37.5 [37.0–37.8] n=5 | 2.2 % | +5.4 % | 1497 [1482–1568] n=5 | 1214 [1170–1280] n=5 | 1654 | 256 [256–256] n=5 (0) | length×5 | fair→fair,nominal→nominal | 797 [559–878] n=5 |
| cold | 8192 | 1,2,3,4,5,6 | 35.4 [33.5–36.8] n=6 | 9.9 % | -0.3 % | 1238 [1122–1294] n=6 | 1678 [1350–2067] n=6 | 1654 | 256 [256–256] n=6 (0) | length×6 | fair→fair,nominal→nominal | 649 [548–839] n=6 |

First-ever cold records (the allocation's first launch of the sitting, load time > 2× the cell's median; kept apart, not in the cold rows above): ctx 2304 round 1: decode 36.5, prefill 1428, load 5.35 s, resident peak 2905 MiB; ctx 4096 round 1: decode 34.3, prefill 1506, load 4.79 s, resident peak 2490 MiB.
