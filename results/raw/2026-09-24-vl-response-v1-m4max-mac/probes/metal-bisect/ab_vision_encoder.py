"""A/B the vision encoder tflite of two unpacked bundles on the same pixel input (CPU interpreter).

usage: ab_vision_encoder.py <unpacked_dir_A> <unpacked_dir_B> <image.jpg>
Builds the LiteRT-LM patchified input the runtime hands the encoder: 512x512 resize,
/255 then (x-0.5)/0.5 normalization, 16x16 patches in (ph, pw, c) channel-last raster
order -> [1, 1024, 768] float32 (RESULTS.md, cleared by code read on 2026-08-13).
"""
import glob, sys, numpy as np
from PIL import Image
from ai_edge_litert.interpreter import Interpreter

A, B, IMG = sys.argv[1:4]
img = Image.open(IMG).convert("RGB").resize((512, 512), Image.BILINEAR)
x = np.asarray(img, dtype=np.float32) / 255.0
x = (x - 0.5) / 0.5                      # [512,512,3]
p = 16
x = x.reshape(512 // p, p, 512 // p, p, 3).transpose(0, 2, 1, 3, 4).reshape(1, 1024, p * p * 3).astype(np.float32)

def run(d):
    path = glob.glob(f"{d}/*vision_encoder*.tflite")[0]
    it = Interpreter(model_path=path, num_threads=4); it.allocate_tensors()
    ins = it.get_input_details(); outs = it.get_output_details()
    ops = None
    try:
        from ai_edge_litert import model_utils  # optional
    except Exception:
        pass
    it.set_tensor(ins[0]["index"], x.astype(ins[0]["dtype"])); it.invoke()
    return path, it.get_tensor(outs[0]["index"]).astype(np.float64)

pa, ya = run(A); pb, yb = run(B)
print("A", pa, ya.shape); print("B", pb, yb.shape)
cos = float((ya * yb).sum() / (np.linalg.norm(ya) * np.linalg.norm(yb)))
print(f"cosine {cos:.7f}  max|diff| {np.abs(ya - yb).max():.3e}  max|A| {np.abs(ya).max():.3e}  equal {np.array_equal(ya, yb)}")
