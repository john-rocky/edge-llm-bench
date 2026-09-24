"""Minimal repro from the real graph: FULLY_CONNECTED + ADD(const). Variant A keeps the const rank-3
[1,1024,768] (as exported); variant B reshapes the same const to rank-2 [1024,768]. Saves both tflites."""
import sys, os, numpy as np, flatbuffers
from PIL import Image
from ai_edge_litert import schema_py_generated as schema
from ai_edge_litert.compiled_model import CompiledModel
from ai_edge_litert.options import Options
from ai_edge_litert.hardware_accelerator import HardwareAccelerator
path, img, outdir = sys.argv[1], sys.argv[2], sys.argv[3]; os.makedirs(outdir, exist_ok=True)
buf = open(path, "rb").read()
def build(rank2):
    mt = schema.ModelT.InitFromObj(schema.Model.GetRootAsModel(buf, 0)); sg = mt.subgraphs[0]
    ops = sg.operators[:2]; out_t = int(ops[1].outputs[0])
    keep = set(int(t) for t in sg.inputs) | {out_t}
    for op in ops: keep |= {int(t) for t in list(op.inputs) + list(op.outputs) if t >= 0}
    old = sorted(keep); remap = {o: n for n, o in enumerate(old)}
    tensors = [sg.tensors[o] for o in old]
    bids = sorted({0} | {t.buffer for t in tensors}); bmap = {o: n for n, o in enumerate(bids)}
    for t in tensors: t.buffer = bmap[t.buffer]
    mt.buffers = [mt.buffers[b] for b in bids]
    for op in ops:
        op.inputs = np.array([remap[int(t)] if t >= 0 else -1 for t in op.inputs], dtype=np.int32)
        op.outputs = np.array([remap[int(t)] for t in op.outputs], dtype=np.int32)
    const_t = tensors[int(ops[1].inputs[1])]
    if rank2:
        shp = [int(d) for d in const_t.shape]; assert shp[0] == 1; const_t.shape = np.array(shp[1:], dtype=np.int32)
        # ADD output is [1,1024,768] in the original; with two rank-2 inputs make it rank-2 too
        o = tensors[int(ops[1].outputs[0])]; o.shape = np.array([int(d) for d in o.shape][1:], dtype=np.int32)
    sg.operators = ops; sg.tensors = tensors
    sg.inputs = np.array([remap[int(t)] for t in sg.inputs], dtype=np.int32); sg.outputs = np.array([remap[out_t]], dtype=np.int32)
    mt.metadata = []; mt.metadataBuffer = None; mt.signatureDefs = []
    b = flatbuffers.Builder(1024); b.Finish(mt.Pack(b), file_identifier=b"TFL3")
    p = os.path.join(outdir, f"fc_add_const_rank{'2' if rank2 else '3'}.tflite"); open(p, "wb").write(b.Output())
    return p, [int(d) for d in tensors[int(ops[1].outputs[0])].shape]
im = Image.open(img).convert("RGB").resize((512, 512), Image.BILINEAR)
x = ((np.asarray(im, dtype=np.float32) / 255.0 - 0.5) / 0.5).reshape(32, 16, 32, 16, 3).transpose(0, 2, 1, 3, 4).reshape(1, 1024, 768).astype(np.float32)
def run(p, acc, n):
    opts = Options(); opts.hardware_accelerators = acc
    cm = CompiledModel.from_file(p, options=opts); ins = cm.create_input_buffers(0); outs = cm.create_output_buffers(0)
    ins[0].write(x); cm.run_by_index(0, ins, outs); return np.asarray(outs[0].read(n, np.float32), dtype=np.float64)
for rank2 in (False, True):
    p, shp = build(rank2); n = int(np.prod(shp))
    yc = run(p, HardwareAccelerator.CPU, n); yg = run(p, HardwareAccelerator.GPU, n)
    cos = float((yc * yg).sum() / (np.linalg.norm(yc) * np.linalg.norm(yg)))
    print(f"REPRO const rank{'2' if rank2 else '3'} {os.path.basename(p)} {os.path.getsize(p)/1e6:.1f} MB out {shp}: cpu-vs-gpu cosine {cos:.6f} max|diff| {np.abs(yc-yg).max():.4e}", flush=True)
