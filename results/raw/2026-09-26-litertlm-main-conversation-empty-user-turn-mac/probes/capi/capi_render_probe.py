#!/usr/bin/env python3
"""Call the LiteRT-LM C API directly through ctypes (no Swift package, no app):
open one libCLiteRTLM_mac.dylib, create a CPU engine from a .litertlm bundle,
create a conversation, render the preface and one user message through the
bundle's prompt template, then send the same message and print the reply head
and the prompt token count the engine's benchmark info reports.

usage: capi_render_probe.py <libCLiteRTLM_mac.dylib> <bundle.litertlm> [max_output_tokens]
"""
import ctypes
import json
import os
import sys
import time

dylib = os.path.abspath(sys.argv[1])
model = os.path.abspath(sys.argv[2])
max_out = int(sys.argv[3]) if len(sys.argv) > 3 else 48
prompt = "Explain what on-device AI means in simple terms."
# The same shape the Swift package's Message.toJson produces for Message(prompt):
# {"role": "user", "content": [{"type": "text", "text": <prompt>}]}
message_json = json.dumps(
    {"role": "user", "content": [{"type": "text", "text": prompt}]},
    separators=(",", ":"))

lib = ctypes.CDLL(dylib, mode=ctypes.RTLD_GLOBAL)
P = ctypes.c_void_p
S = ctypes.c_char_p
proto = {
    "litert_lm_engine_settings_create": (P, [S, S, S, S]),
    "litert_lm_engine_settings_set_max_num_tokens": (None, [P, ctypes.c_int]),
    "litert_lm_engine_settings_set_num_threads": (None, [P, ctypes.c_int]),
    "litert_lm_engine_settings_enable_benchmark": (None, [P]),
    "litert_lm_engine_create": (P, [P]),
    "litert_lm_engine_delete": (None, [P]),
    "litert_lm_engine_settings_delete": (None, [P]),
    "litert_lm_conversation_create": (P, [P, P]),
    "litert_lm_conversation_delete": (None, [P]),
    "litert_lm_conversation_render_preface_to_string": (S, [P]),
    "litert_lm_conversation_render_message_to_string": (S, [P, S]),
    "litert_lm_conversation_optional_args_create": (P, []),
    "litert_lm_conversation_optional_args_set_max_output_tokens": (None, [P, ctypes.c_int]),
    "litert_lm_conversation_optional_args_delete": (None, [P]),
    "litert_lm_conversation_send_message": (P, [P, S, S, P]),
    "litert_lm_json_response_get_string": (S, [P]),
    "litert_lm_json_response_delete": (None, [P]),
    "litert_lm_conversation_get_benchmark_info": (P, [P]),
    "litert_lm_benchmark_info_get_num_prefill_turns": (ctypes.c_int, [P]),
    "litert_lm_benchmark_info_get_prefill_token_count_at": (ctypes.c_int, [P, ctypes.c_int]),
    "litert_lm_benchmark_info_delete": (None, [P]),
    "litert_lm_get_last_error_message": (S, []),
    "litert_lm_clear_last_error": (None, []),
}
fn = {}
for name, (res, args) in proto.items():
    try:
        f = getattr(lib, name)
    except AttributeError:
        fn[name] = None
        continue
    f.restype = res
    f.argtypes = args
    fn[name] = f


def last_error():
    f = fn["litert_lm_get_last_error_message"]
    if f is None:
        return "<no litert_lm_get_last_error_message export>"
    m = f()
    return m.decode("utf-8", "replace") if m else "<none>"


def show(label, s):
    if s is None:
        print(f"{label}: NULL (last error: {last_error()})")
    else:
        print(f"{label}: {json.dumps(s.decode('utf-8', 'replace'))}")


print(f"dylib={dylib}")
print(f"bundle={model}")
print(f"message_json={message_json}")
missing = [k for k, v in fn.items() if v is None]
print(f"missing_exports={missing}")

t0 = time.time()
settings = fn["litert_lm_engine_settings_create"](model.encode(), b"cpu", None, None)
assert settings, f"settings_create failed: {last_error()}"
fn["litert_lm_engine_settings_set_max_num_tokens"](settings, 1280)
fn["litert_lm_engine_settings_set_num_threads"](settings, 4)
if fn["litert_lm_engine_settings_enable_benchmark"]:
    fn["litert_lm_engine_settings_enable_benchmark"](settings)
engine = fn["litert_lm_engine_create"](settings)
assert engine, f"engine_create failed: {last_error()}"
print(f"engine_created_in_s={time.time() - t0:.1f}")
conv = fn["litert_lm_conversation_create"](engine, None)
assert conv, f"conversation_create failed: {last_error()}"

show("render_preface", fn["litert_lm_conversation_render_preface_to_string"](conv))
show("render_message", fn["litert_lm_conversation_render_message_to_string"](conv, message_json.encode()))

args = fn["litert_lm_conversation_optional_args_create"]()
fn["litert_lm_conversation_optional_args_set_max_output_tokens"](args, max_out)
t1 = time.time()
resp = fn["litert_lm_conversation_send_message"](conv, message_json.encode(), None, args)
if not resp:
    print(f"send_message: NULL (last error: {last_error()})")
else:
    text = fn["litert_lm_json_response_get_string"](resp).decode("utf-8", "replace")
    print(f"send_message_response_json={text[:600]!r}")
    fn["litert_lm_json_response_delete"](resp)
print(f"send_message_in_s={time.time() - t1:.1f}")
info = fn["litert_lm_conversation_get_benchmark_info"](conv)
if info:
    n = fn["litert_lm_benchmark_info_get_num_prefill_turns"](info)
    counts = [fn["litert_lm_benchmark_info_get_prefill_token_count_at"](info, i) for i in range(n)]
    print(f"benchmark_prefill_turns={n} prefill_token_counts={counts}")
    fn["litert_lm_benchmark_info_delete"](info)
else:
    print(f"benchmark_info: NULL (last error: {last_error()})")
fn["litert_lm_conversation_optional_args_delete"](args)
fn["litert_lm_conversation_delete"](conv)
fn["litert_lm_engine_delete"](engine)
fn["litert_lm_engine_settings_delete"](settings)
print("done")
