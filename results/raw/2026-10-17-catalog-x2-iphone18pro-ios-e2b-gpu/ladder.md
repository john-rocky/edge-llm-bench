# 2026-10-17-catalog-x2-iphone18pro-ios-e2b-gpu — ladder (median [min–max] over rounds; spread = max/min − 1; Δ = decode median vs the smallest allocation)

Engine stamped: v0.18.0; build configuration: Release; records in the ladder: 36; unmapped records (no launch line): 0.


## litert-lm — litert-community/gemma-4-E2B-it-litert-lm — long-context-2048-gen256-noref

| regime | ctx | rounds | decode tok/s | spread | Δ vs smallest | prefill tok/s | TTFT ms | prompt tok | out tok (short) | stop | thermal start→end | resident peak MiB |
|---|---:|---|---|---:|---:|---|---|---|---|---|---|---|
| warm | 2304 | 1,2,3,4,5,6 | 84.7 [84.6–84.8] n=6 | 0.2 % | +0.0 % | 4571 [4549–4665] n=6 | 394 [385–397] n=6 | 1654 | 256 [256–256] n=6 (0) | length×6 | nominal→nominal | 715 [714–1490] n=6 |
| warm | 4096 | 1,2,3,4,5,6 | 82.7 [82.6–82.9] n=6 | 0.4 % | -2.3 % | 3882 [3871–3917] n=6 | 459 [455–461] n=6 | 1654 | 256 [256–256] n=6 (0) | length×6 | nominal→nominal | 720 [718–1494] n=6 |
| warm | 8192 | 1,2,3,4,5,6 | 76.9 [76.8–76.9] n=6 | 0.2 % | -9.3 % | 2966 [2942–2980] n=6 | 592 [590–597] n=6 | 1654 | 256 [256–256] n=6 (0) | length×6 | nominal→nominal | 729 [728–730] n=6 |
| cold | 2304 | 2,3,4,5,6 | 84.7 [84.7–84.8] n=5 | 0.1 % | +0.0 % | 4621 [4596–4647] n=5 | 392 [390–394] n=5 | 1654 | 256 [256–256] n=5 (0) | length×5 | nominal→nominal | 705 [704–705] n=5 |
| cold | 4096 | 2,3,4,5,6 | 82.9 [82.8–83.0] n=5 | 0.1 % | -2.2 % | 3940 [3929–3957] n=5 | 454 [452–455] n=5 | 1654 | 256 [256–256] n=5 (0) | length×5 | nominal→nominal | 709 [708–709] n=5 |
| cold | 8192 | 1,2,3,4,5,6 | 76.8 [76.8–76.9] n=6 | 0.2 % | -9.4 % | 2986 [2983–3004] n=6 | 590 [587–593] n=6 | 1654 | 256 [256–256] n=6 (0) | length×6 | nominal→nominal | 723 [719–728] n=6 |

First-ever cold records (the allocation's first launch of the sitting, load time > 2× the cell's median; kept apart, not in the cold rows above): ctx 2304 round 1: decode 80.6, prefill 4720, load 1.42 s, resident peak 1490 MiB; ctx 4096 round 1: decode 80.0, prefill 3998, load 1.43 s, resident peak 1484 MiB.
