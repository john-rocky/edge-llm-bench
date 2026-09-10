# 2026-09-10 11:43–11:46 JST — Galaxy S26, GPU backend after the manifest fix: fast, and empty

Same device, model (`gemma3-270m-it-q8.litertlm`, sha256 757e9119…) and engine AAR as the CPU runs;
the app manifest now declares the OpenCL vendor libraries. The GPU backend initialised (1537/1537
decode and 1667/1667 prefill nodes on the LITERT_CL delegate; the AAR ships no
`libLiteRtTopKOpenClSampler.so`, so the sampler fell back to the statically linked one — a warning,
logged) and the engine reported decode 66.45 / 66.97 / 66.68 tok/s, prefill 696 / 695 / 680 tok/s,
TTFT 44 ms, 128 generated tokens every run (the cap; CPU stops at 44 at its own EOS).

**The generated text was empty in all three runs and in all eight gate answers.** Gate: FAIL, form
0/8 ("empty"), correct 0/8 — the case the gate exists for (a number without an answer must not rank).
The three speed records are therefore quarantined as `*.json.gate-fail` and stay out of the summary.

## Cross-check: the bundle, not the APK

`native-gpu-crosscheck/` (not an `app-path*` dir, so never ingested): the native lane's
`litert_lm_main` v0.16.0 on the same phone, same file, `--backend=gpu`, one run — decode 41.85 tok/s,
4076 generated tokens, and the whole response is `<pad><pad><pad>…` (the Kotlin API returns the same
stream as an empty string). The model card of `litert-community/gemma-3-270m-it` states it itself:
"Gemma3 270M via LiteRT-LM with GPU acceleration is WIP and will be coming soon." So this q8 bundle
is CPU-only by its publisher's own note; the APK's GPU path is mechanically fine, and a
GPU-published bundle is what a GPU row needs.
