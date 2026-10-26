"""One process: create a GPU Benchmark N times with one cache dir and print the wall time of each call."""
import sys
import time

import litert_lm

model, cache_dir, n, label = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
print(f"PY_START {label} t={time.time():.3f}", flush=True)
for i in range(1, n + 1):
    print(f"CALL_BEGIN {label} call={i} t={time.time():.3f}", flush=True)
    t0 = time.monotonic()
    b = litert_lm.Benchmark(model, backend=litert_lm.Backend.GPU(), prefill_tokens=1024,
                            decode_tokens=32, max_num_tokens=2048, cache_dir=cache_dir)
    info = b.run()
    wall = time.monotonic() - t0
    g = lambda k: getattr(info, k, float("nan"))
    print(f"CALL_END {label} call={i} t={time.time():.3f} wall_s={wall:.2f} init_s={g('init_time_in_second'):.2f} "
          f"ttft_s={g('time_to_first_token_in_second'):.3f} prefill_tok_s={g('last_prefill_tokens_per_second'):.1f} "
          f"decode_tok_s={g('last_decode_tokens_per_second'):.1f}", flush=True)
    if hasattr(b, "close"):
        b.close()
    del b
