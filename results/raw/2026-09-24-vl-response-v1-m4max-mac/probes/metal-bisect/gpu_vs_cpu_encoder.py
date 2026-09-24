"""Run one vision-encoder tflite on CPU and on the Mac GPU (Metal) with ai_edge_litert CompiledModel and compare."""
import sys, glob, numpy as np
from PIL import Image
from ai_edge_litert.compiled_model import CompiledModel
from ai_edge_litert.options import Options, CpuOptions, GpuOptions
from ai_edge_litert.hardware_accelerator import HardwareAccelerator
d, img = sys.argv[1], sys.argv[2]
path = glob.glob(f"{d}/*vision_encoder*.tflite")[0]
im = Image.open(img).convert("RGB").resize((512, 512), Image.BILINEAR)
x = (np.asarray(im, dtype=np.float32) / 255.0 - 0.5) / 0.5
x = x.reshape(32, 16, 32, 16, 3).transpose(0, 2, 1, 3, 4).reshape(1, 1024, 768).astype(np.float32)
import os
def run(acc):
    opts = Options(); opts.hardware_accelerators = acc
    if acc == HardwareAccelerator.GPU and os.environ.get("ENFORCE_F32") == "1":
        opts.gpu_options.enforce_f32 = True; print("gpu enforce_f32=True")

    m = CompiledModel.from_file(path, options=opts)
    print("fully accelerated:", m.is_fully_accelerated() if hasattr(m, "is_fully_accelerated") else "?")
    ins = m.create_input_buffers(0); outs = m.create_output_buffers(0)
    ins[0].write(x); m.run_by_index(0, ins, outs)
    return np.asarray(outs[0].read(1 * 1024 * 768, np.float32)).reshape(1, 1024, 768)
try:
    yc = run(HardwareAccelerator.CPU).astype(np.float64); print("cpu ok", yc.shape, "max|.|", np.abs(yc).max())
    yg = run(HardwareAccelerator.GPU).astype(np.float64); print("gpu ok", yg.shape, "max|.|", np.abs(yg).max())
    cos = float((yc * yg).sum() / (np.linalg.norm(yc) * np.linalg.norm(yg)))
    print(f"cpu-vs-gpu cosine {cos:.6f} max|diff| {np.abs(yc-yg).max():.3e}")
except Exception as e:
    print("ERR", type(e).__name__, str(e)[:400])
