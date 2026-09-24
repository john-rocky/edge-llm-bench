"""Rebuild the .tflite truncated after op <oi> (unused tensors/buffers pruned) and compare CPU vs Metal.

usage: probe_metal_prefix.py <encoder.tflite> <image> <oi>   -> prints "RESULT <oi> <opname> <cosine> <maxdiff> <n>"
"""
import sys, os, tempfile, numpy as np
import flatbuffers
from PIL import Image
from ai_edge_litert import schema_py_generated as schema
from ai_edge_litert.compiled_model import CompiledModel
from ai_edge_litert.options import Options
from ai_edge_litert.hardware_accelerator import HardwareAccelerator

path, img, oi = sys.argv[1], sys.argv[2], int(sys.argv[3])
buf = open(path, "rb").read()
mt = schema.ModelT.InitFromObj(schema.Model.GetRootAsModel(buf, 0))
sg = mt.subgraphs[0]
onames = {v: k for k, v in vars(schema.BuiltinOperator).items() if isinstance(v, int)}
code = mt.operatorCodes[sg.operators[oi].opcodeIndex]
opname = onames.get(max(code.builtinCode, code.deprecatedBuiltinCode), "?")
ops = sg.operators[: oi + 1]
out_t = int(sg.operators[oi].outputs[0])
keep = set(int(t) for t in sg.inputs) | {out_t}
for op in ops:
    keep |= {int(t) for t in list(op.inputs) + list(op.outputs) if t >= 0}
old_ids = sorted(keep)
remap = {o: n for n, o in enumerate(old_ids)}
new_tensors = [sg.tensors[o] for o in old_ids]
# prune buffers: keep buffer 0 (empty) + those referenced by kept tensors
buf_ids = sorted({0} | {t.buffer for t in new_tensors})
bmap = {o: n for n, o in enumerate(buf_ids)}
for t in new_tensors:
    t.buffer = bmap[t.buffer]
mt.buffers = [mt.buffers[b] for b in buf_ids]
for op in ops:
    op.inputs = np.array([remap[int(t)] if t >= 0 else -1 for t in op.inputs], dtype=np.int32)
    op.outputs = np.array([remap[int(t)] for t in op.outputs], dtype=np.int32)
sg.operators = ops
sg.tensors = new_tensors
sg.inputs = np.array([remap[int(t)] for t in sg.inputs], dtype=np.int32)
sg.outputs = np.array([remap[out_t]], dtype=np.int32)
mt.metadata = []  # drop metadata/buffer references we did not remap
mt.metadataBuffer = None
mt.signatureDefs = []
b = flatbuffers.Builder(1024)
b.Finish(mt.Pack(b), file_identifier=b"TFL3")
tmp = os.path.join(tempfile.mkdtemp(), f"prefix_op{oi}.tflite")
open(tmp, "wb").write(b.Output())

shape = [int(d) for d in sg.tensors[remap[out_t]].shape]
n = int(np.prod(shape)) if shape else 1
im = Image.open(img).convert("RGB").resize((512, 512), Image.BILINEAR)
x = (np.asarray(im, dtype=np.float32) / 255.0 - 0.5) / 0.5
x = x.reshape(32, 16, 32, 16, 3).transpose(0, 2, 1, 3, 4).reshape(1, 1024, 768).astype(np.float32)

def run(acc):
    opts = Options(); opts.hardware_accelerators = acc
    cm = CompiledModel.from_file(tmp, options=opts)
    ins = cm.create_input_buffers(0); outs = cm.create_output_buffers(0)
    ins[0].write(x); cm.run_by_index(0, ins, outs)
    return np.asarray(outs[0].read(n, np.float32), dtype=np.float64)

yc = run(HardwareAccelerator.CPU)
yg = run(HardwareAccelerator.GPU)
cos = float((yc * yg).sum() / (np.linalg.norm(yc) * np.linalg.norm(yg) + 1e-30))
print(f"RESULT {oi} {opname} {cos:.6f} {np.abs(yc - yg).max():.4e} {n} shape={shape} cpu_max={np.abs(yc).max():.3f} gpu_max={np.abs(yg).max():.3f}", flush=True)
