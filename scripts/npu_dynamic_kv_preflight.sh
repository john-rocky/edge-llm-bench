#!/usr/bin/env bash
# Day-0 preflight for the NPU dynamic KV cache growth (LiteRT-LM main 5e3bd6377,
# 2026-09-26 "Grow the NPU dynamic KV cache on demand during prefill and decode").
# No device, no model: answers "is the path in the tag, and is it alive in the
# binary we would run?" — docs/day0-npu-dynamic-kv-v1.md explains the three gates.
#
#   scripts/npu_dynamic_kv_preflight.sh <tag> [path/to/litert_lm_advanced_main]
#
# Exit 0 = every gate passed (go measure); 1 = at least one gate failed (nothing to
# measure yet; the printed line says which); 2 = usage / gh error.
set -u
TAG="${1:-}"; BIN="${2:-}"
[ -n "$TAG" ] || { echo "usage: $0 <tag> [path/to/litert_lm_advanced_main]" >&2; exit 2; }
REPO=google-ai-edge/LiteRT-LM
COMMIT=5e3bd637758fb0ae2dcbd85fb028f1b609dbee3e
rc=0

# Gate 1 — is the commit in the tag? (ahead-of-tag list no longer contains it)
ahead=$(gh api "repos/$REPO/compare/$TAG...main" --jq '[.commits[].sha] | index("'"$COMMIT"'")' 2>&1) \
  || { echo "gate1 ERROR gh compare failed: $ahead" >&2; exit 2; }
if [ "$ahead" = "null" ]; then
  echo "gate1 PASS  $COMMIT is in $TAG (not ahead of it on main)"
else
  echo "gate1 FAIL  $COMMIT is still ahead of $TAG on main (position $ahead) — the tag does not carry it"
  rc=1
fi

# Gate 2 — does the binary we run carry the growth code? (the env-var name is a
# literal in llm_litert_npu_compiled_model_executor.cc after 5e3bd6377)
# Gate 3 — is NpuDynamismHelper compiled with LITERT_ENABLE_FABRIC_INTEGRATION?
# ("ResizeInputTensor failed for" exists only inside the #if block of
# llm_litert_npu_dynamism.cc; without the define HasDynamicKVCache() is a stub
# returning false and no bundle is ever treated as dynamic)
[ -n "$BIN" ] || BIN="android/bin/$TAG/litert_lm_advanced_main"
if [ -f "$BIN" ]; then
  if strings "$BIN" | grep -q 'LITERT_LM_NPU_DYNAMIC_KV_CACHE_INITIAL_SIZE'; then
    echo "gate2 PASS  $BIN carries the dynamic-growth code (LITERT_LM_NPU_DYNAMIC_KV_CACHE_INITIAL_SIZE present)"
  else
    echo "gate2 FAIL  $BIN has no LITERT_LM_NPU_DYNAMIC_KV_CACHE_INITIAL_SIZE literal — built before 5e3bd6377"
    rc=1
  fi
  if strings "$BIN" | grep -q 'ResizeInputTensor failed for'; then
    echo "gate3 PASS  $BIN was built with LITERT_ENABLE_FABRIC_INTEGRATION (dynamism helper is live)"
  else
    echo "gate3 FAIL  $BIN lacks the fabric branch of llm_litert_npu_dynamism.cc — HasDynamicKVCache() is the stub; rebuild with --copt=-DLITERT_ENABLE_FABRIC_INTEGRATION (OSS deps only: litert_compiled_model / litert_ranked_tensor_type) or no bundle is dynamic"
    rc=1
  fi
else
  echo "gate2 SKIP  no binary at $BIN (build it: LITERTLM_TAG=$TAG android/scripts/build_litert_lm_main.sh, then re-run with the path)"
  echo "gate3 SKIP  same binary"
  rc=1
fi

# Gate 4 — a bundle the helper would accept: a kv_cache_k / kv_cache_v / kv_cache_c
# signature input with a -1 dimension. The public npu_export (litert-torch main
# 2026-10-02) has no such option; this prints the check for any candidate file.
cat <<'MSG'
gate4 INFO  a dynamic bundle is one whose prefill/decode signature has a kv_cache_* input with a -1 dim:
            python3 ~/code/litertlm-convert/npu_g270_ship/3508_chunk_probe/inspect_bundle.py <bundle.litertlm> --sigs prefill_128,decode | grep -E 'kv_cache_[kvc].*-1'
            (no hit = static bundle = 5e3bd6377 does nothing for it; the cache_length wall of litert-torch#1226 stands)
MSG
exit $rc
