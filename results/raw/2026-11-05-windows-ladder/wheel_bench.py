# Control: Google's PyPI wheel (litert-lm-api) on this machine. Prints one JSON line per conversation.
import argparse, json, os, sys, time
ap = argparse.ArgumentParser()
ap.add_argument("model"); ap.add_argument("backend")
ap.add_argument("--ctx", type=int, default=2048)
ap.add_argument("--prompt", default="Explain what on-device AI means in simple terms.")
ap.add_argument("--max-out", type=int, default=128)
ap.add_argument("--iters", type=int, default=2)
ap.add_argument("--device", default="")
ap.add_argument("--dispatch", default="")
ap.add_argument("--cache", default="")
a = ap.parse_args()
import litert_lm
from litert_lm import interfaces
if a.backend == "gpu":
    kw = {}
    fields = getattr(interfaces.GPU, "__dataclass_fields__", {})
    print("GPU fields:", sorted(fields), flush=True)
    if a.device and "preferred_device_substr" in fields:
        kw["preferred_device_substr"] = a.device
    backend = litert_lm.Backend.GPU(**kw)
elif a.backend == "npu":
    kw = {"litert_dispatch_lib_dir": a.dispatch} if a.dispatch else {}
    backend = litert_lm.Backend.NPU(**kw)
else:
    backend = litert_lm.Backend.CPU()
print("version:", getattr(litert_lm, "__version__", "?"), flush=True)
t0 = time.time()
ekw = {"enable_benchmark": True}
if a.ctx:
    ekw["max_num_tokens"] = a.ctx
if a.cache:
    ekw["cache_dir"] = a.cache
with litert_lm.Engine(a.model, backend=backend, **ekw) as eng:
    print("engine_s", round(time.time() - t0, 2), flush=True)
    for i in range(a.iters):
        with eng.create_conversation() as c:
            t1 = time.time()
            r = c.send_message(a.prompt)
            b = c.get_benchmark_info()
            text = r["content"][0]["text"] if isinstance(r, dict) else str(r)
            print(json.dumps({"iter": i, "wall_s": round(time.time() - t1, 2), "init": b.init_time_in_second,
                              "ttft": b.time_to_first_token_in_second, "prefill_n": b.last_prefill_token_count,
                              "prefill_tps": b.last_prefill_tokens_per_second, "decode_n": b.last_decode_token_count,
                              "decode_tps": b.last_decode_tokens_per_second, "text": text[:160]}), flush=True)
