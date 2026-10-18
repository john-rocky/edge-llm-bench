# 2026-10-17-catalog-x2-iphone18pro-ios-prompt-probe — ladder (median [min–max] over rounds; spread = max/min − 1; Δ = decode median vs the smallest allocation)

Engine stamped: v0.18.0; build configuration: Release; records in the ladder: 4; unmapped records (no launch line): 0.


## litert-lm — litert-community/gemma-4-E2B-it-litert-lm — long-context-2048-gen256-noref

| regime | ctx | rounds | decode tok/s | spread | Δ vs smallest | prefill tok/s | TTFT ms | prompt tok | out tok (short) | stop | thermal start→end | resident peak MiB |
|---|---:|---|---|---:|---:|---|---|---|---|---|---|---|
| warm | 8192 | 1 | 76.8 [76.8–76.8] n=1 | 0.0 % | +0.0 % | 2994 [2994–2994] n=1 | 588 [588–588] n=1 | 1654 | 256 [256–256] n=1 (0) | length×1 | nominal→nominal | 1503 [1503–1503] n=1 |
| cold | 8192 | 1 | 70.7 [70.7–70.7] n=1 | 0.0 % | +0.0 % | 2240 [2240–2240] n=1 | 782 [782–782] n=1 | 1654 | 256 [256–256] n=1 (0) | length×1 | nominal→nominal | 1502 [1502–1502] n=1 |

## litert-lm — litert-community/gemma-4-E4B-it-litert-lm — long-context-2048-gen256-noref

| regime | ctx | rounds | decode tok/s | spread | Δ vs smallest | prefill tok/s | TTFT ms | prompt tok | out tok (short) | stop | thermal start→end | resident peak MiB |
|---|---:|---|---|---:|---:|---|---|---|---|---|---|---|
| warm | 8192 | 1 | 36.9 [36.9–36.9] n=1 | 0.0 % | +0.0 % | 1318 [1318–1318] n=1 | 1321 [1321–1321] n=1 | 1654 | 256 [256–256] n=1 (0) | length×1 | nominal→nominal | 2224 [2224–2224] n=1 |
| cold | 8192 | 1 | 33.4 [33.4–33.4] n=1 | 0.0 % | +0.0 % | 1121 [1121–1121] n=1 | 1959 [1959–1959] n=1 | 1654 | 256 [256–256] n=1 (0) | length×1 | nominal→nominal | 2698 [2698–2698] n=1 |
