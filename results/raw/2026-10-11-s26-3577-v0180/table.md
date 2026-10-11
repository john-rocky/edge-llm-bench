| run | backend | prompt | delegation (prefill_128 / decode) | OpenCL device created | registered accelerators | exit | peak VmHWM MB | output text |
|---|---|---|---|---|---|---|---|---|
| g1 | gpu | A | 2165/2165 LITERT_CL (decode), 2334/2334 LITERT_CL (prefill_128) | yes | CpuAccelerator; LiteRT GPU | 0 | 4 | The capital of France is Paris. |
| c1 | cpu | A | 1902/2165 TfLiteXNNPackDelegate (decode), 2075/2334 TfLiteXNNPackDelegate (prefill_128), 2706/2968 TfLiteXNNPackDelegate (decode), 2946/3206 TfLiteXNNPackDelegate (prefill_128) | no | CpuAccelerator; LiteRT GPU | 0 | 4 | The capital of France is Paris. |
| g2 | gpu | A | 2165/2165 LITERT_CL (decode), 2334/2334 LITERT_CL (prefill_128) | yes | CpuAccelerator; LiteRT GPU | 0 | 4 | The capital of France is Paris. |
| c2 | cpu | A | 1902/2165 TfLiteXNNPackDelegate (decode), 2075/2334 TfLiteXNNPackDelegate (prefill_128), 2706/2968 TfLiteXNNPackDelegate (decode), 2946/3206 TfLiteXNNPackDelegate (prefill_128) | no | CpuAccelerator; LiteRT GPU | 0 | 4 | The capital of France is Paris. |
| g3 | gpu | B | 2165/2165 LITERT_CL (decode), 2334/2334 LITERT_CL (prefill_128) | yes | CpuAccelerator; LiteRT GPU | 0 | 4 | Paris |
| c3 | cpu | B | 1902/2165 TfLiteXNNPackDelegate (decode), 2075/2334 TfLiteXNNPackDelegate (prefill_128), 2706/2968 TfLiteXNNPackDelegate (decode), 2946/3206 TfLiteXNNPackDelegate (prefill_128) | no | CpuAccelerator; LiteRT GPU | 0 | 4 | Paris |
| g4 | gpu | A | 2165/2165 LITERT_CL (decode), 2334/2334 LITERT_CL (prefill_128) | yes | CpuAccelerator; LiteRT GPU | 0 | 738 | The capital of France is Paris. |
| c4 | cpu | A | 1902/2165 TfLiteXNNPackDelegate (decode), 2075/2334 TfLiteXNNPackDelegate (prefill_128), 2706/2968 TfLiteXNNPackDelegate (decode), 2946/3206 TfLiteXNNPackDelegate (prefill_128) | no | CpuAccelerator; LiteRT GPU | 0 | 1904 | The capital of France is Paris. |
