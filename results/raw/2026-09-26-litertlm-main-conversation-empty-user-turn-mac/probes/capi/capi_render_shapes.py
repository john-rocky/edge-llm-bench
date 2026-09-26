#!/usr/bin/env python3
"""Render several message JSON shapes through the C API of one dylib (CPU engine, no send)."""
import ctypes, json, os, sys
dylib, model = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
prompt = "Explain what on-device AI means in simple terms."
shapes = {
    "array_text": {"role": "user", "content": [{"type": "text", "text": prompt}]},
    "string": {"role": "user", "content": prompt},
    "array_two_text": {"role": "user", "content": [{"type": "text", "text": "Hello."}, {"type": "text", "text": prompt}]},
    "assistant_array_text": {"role": "assistant", "content": [{"type": "text", "text": prompt}]},
    "system_array_text": {"role": "system", "content": [{"type": "text", "text": "You are terse."}]},
}
lib = ctypes.CDLL(dylib, mode=ctypes.RTLD_GLOBAL)
P, S = ctypes.c_void_p, ctypes.c_char_p
lib.litert_lm_engine_settings_create.restype = P; lib.litert_lm_engine_settings_create.argtypes = [S, S, S, S]
lib.litert_lm_engine_settings_set_max_num_tokens.argtypes = [P, ctypes.c_int]
lib.litert_lm_engine_create.restype = P; lib.litert_lm_engine_create.argtypes = [P]
lib.litert_lm_conversation_create.restype = P; lib.litert_lm_conversation_create.argtypes = [P, P]
lib.litert_lm_conversation_render_message_to_string.restype = S; lib.litert_lm_conversation_render_message_to_string.argtypes = [P, S]
lib.litert_lm_conversation_delete.argtypes = [P]; lib.litert_lm_engine_delete.argtypes = [P]
st = lib.litert_lm_engine_settings_create(model.encode(), b"cpu", None, None); assert st
lib.litert_lm_engine_settings_set_max_num_tokens(st, 1280)
eng = lib.litert_lm_engine_create(st); assert eng
conv = lib.litert_lm_conversation_create(eng, None); assert conv
print(f"dylib={dylib}")
for name, shape in shapes.items():
    j = json.dumps(shape, separators=(",", ":"))
    r = lib.litert_lm_conversation_render_message_to_string(conv, j.encode())
    print(f"{name}: json={j}")
    print(f"{name}: render={'NULL' if r is None else json.dumps(r.decode('utf-8','replace'))}")
lib.litert_lm_conversation_delete(conv); lib.litert_lm_engine_delete(eng)
print("done")
