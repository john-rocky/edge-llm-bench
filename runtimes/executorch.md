# ExecuTorch (CoreML backend)

PyTorch's mobile inference stack, with a CoreML delegate that targets the ANE/GPU.

- Repository: <https://github.com/pytorch/executorch>
- License: BSD
- Backend: CoreML delegate (ANE/GPU) on iOS, plus XNNPACK CPU fallback

## Strengths

- PyTorch-native model authoring path — useful for teams that already have PyTorch models.
- CoreML delegate gives ANE/GPU access without writing CoreML manually.
- Active investment from Meta + community.

## Weaknesses

- Newer than llama.cpp / MLX / CoreML-LLM, fewer reference iOS apps.
- Model export pipeline is involved (`torch.export` → ExecuTorch program → CoreML delegation).
- iOS XCFramework distribution exists but build-from-source is non-trivial.

## Status

Optional future target. Stub adapter only.
