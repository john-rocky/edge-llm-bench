"""Variants of the FC+ADD(const) head of the folded encoder, CPU vs Metal.

  prefix2-rank3  : as exported (FC out [1024,768] + const [1,1024,768])
  prefix2-reshape3: FC out -> RESHAPE [1,1024,768], then ADD with the rank-3 const
  prefix2-rank4  : FC out -> RESHAPE [1,1,1024,768], const reshaped to [1,1,1024,768]
  prefix2-input  : the const becomes a second model input (fed from the original buffer)
  full-input     : the whole encoder with the table fed as a second input
usage: probe_variants.py <encoder.tflite> <image> <outdir> [variant ...]
"""
import sys, os, numpy as np, flatbuffers
from PIL import Image
from ai_edge_litert import schema_py_generated as schema
from ai_edge_litert.compiled_model import CompiledModel
from ai_edge_litert.options import Options
from ai_edge_litert.hardware_accelerator import HardwareAccelerator

path, img, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
variants = sys.argv[4:] or ["prefix2-rank3", "prefix2-reshape3", "prefix2-rank4", "prefix2-input", "full-input"]
os.makedirs(outdir, exist_ok=True)
buf = open(path, "rb").read()
RESHAPE = schema.BuiltinOperator.RESHAPE

def load():
    return schema.ModelT.InitFromObj(schema.Model.GetRootAsModel(buf, 0))

def prune(mt, ops, out_t, extra_inputs=()):
    sg = mt.subgraphs[0]
    keep = set(int(t) for t in sg.inputs) | {out_t} | set(extra_inputs)
    for op in ops:
        keep |= {int(t) for t in list(op.inputs) + list(op.outputs) if t >= 0}
    old = sorted(keep); remap = {o: n for n, o in enumerate(old)}
    tensors = [sg.tensors[o] for o in old]
    bids = sorted({0} | {t.buffer for t in tensors}); bmap = {o: n for n, o in enumerate(bids)}
    for t in tensors: t.buffer = bmap[t.buffer]
    mt.buffers = [mt.buffers[b] for b in bids]
    for op in ops:
        op.inputs = np.array([remap[int(t)] if t >= 0 else -1 for t in op.inputs], dtype=np.int32)
        op.outputs = np.array([remap[int(t)] for t in op.outputs], dtype=np.int32)
    sg.operators = ops; sg.tensors = tensors
    sg.inputs = np.array([remap[int(t)] for t in list(sg.inputs) + list(extra_inputs)], dtype=np.int32)
    sg.outputs = np.array([remap[out_t]], dtype=np.int32)
    mt.metadata = []; mt.metadataBuffer = None; mt.signatureDefs = []
    return remap

def new_tensor(sg, like, shape, name, buffer=0):
    t = schema.TensorT(); t.shape = np.array(shape, dtype=np.int32); t.type = like.type; t.buffer = buffer
    t.name = name; t.quantization = None
    sg.tensors.append(t); return len(sg.tensors) - 1

def new_const_i32(mt, sg, values, name):
    b = schema.BufferT(); b.data = np.array(values, dtype=np.int32).view(np.uint8); mt.buffers.append(b)
    t = schema.TensorT(); t.shape = np.array([len(values)], dtype=np.int32); t.type = schema.TensorType.INT32
    t.buffer = len(mt.buffers) - 1; t.name = name; sg.tensors.append(t); return len(sg.tensors) - 1

def reshape_opcode(mt):
    for i, c in enumerate(mt.operatorCodes):
        if max(c.builtinCode, c.deprecatedBuiltinCode) == RESHAPE: return i
    c = schema.OperatorCodeT(); c.builtinCode = RESHAPE; c.deprecatedBuiltinCode = RESHAPE; c.version = 1
    mt.operatorCodes.append(c); return len(mt.operatorCodes) - 1

def make_reshape(mt, sg, src, shape, name):
    shp_t = new_const_i32(mt, sg, shape, name + "_shape")
    dst = new_tensor(sg, sg.tensors[src], shape, name)
    op = schema.OperatorT(); op.opcodeIndex = reshape_opcode(mt)
    op.inputs = np.array([src, shp_t], dtype=np.int32); op.outputs = np.array([dst], dtype=np.int32)
    op.builtinOptionsType = schema.BuiltinOptions.ReshapeOptions
    ro = schema.ReshapeOptionsT(); ro.newShape = np.array(shape, dtype=np.int32); op.builtinOptions = ro
    return op, dst

def pack(mt, name):
    b = flatbuffers.Builder(1024); b.Finish(mt.Pack(b), file_identifier=b"TFL3")
    p = os.path.join(outdir, name + ".tflite"); open(p, "wb").write(b.Output()); return p

im = Image.open(img).convert("RGB").resize((512, 512), Image.BILINEAR)
x = ((np.asarray(im, dtype=np.float32) / 255.0 - 0.5) / 0.5).reshape(32, 16, 32, 16, 3).transpose(0, 2, 1, 3, 4).reshape(1, 1024, 768).astype(np.float32)
mt0 = load(); sg0 = mt0.subgraphs[0]
const_id = int(sg0.operators[1].inputs[1])
table = np.frombuffer(bytes(mt0.buffers[sg0.tensors[const_id].buffer].data), dtype=np.float32).reshape([int(d) for d in sg0.tensors[const_id].shape]).copy()
print("const table", table.shape, flush=True)

def run(p, acc, feeds, n):
    opts = Options(); opts.hardware_accelerators = acc
    if acc == HardwareAccelerator.GPU and os.environ.get("ENFORCE_F32") == "1": opts.gpu_options.enforce_f32 = True
    cm = CompiledModel.from_file(p, options=opts); ins = cm.create_input_buffers(0); outs = cm.create_output_buffers(0)
    for i, f in enumerate(feeds): ins[i].write(np.ascontiguousarray(f))
    cm.run_by_index(0, ins, outs); return np.asarray(outs[0].read(n, np.float32), dtype=np.float64)

def report(tag, p, feeds, shape):
    n = int(np.prod(shape))
    try:
        yc = run(p, HardwareAccelerator.CPU, feeds, n); yg = run(p, HardwareAccelerator.GPU, feeds, n)
        cos = float((yc * yg).sum() / (np.linalg.norm(yc) * np.linalg.norm(yg)))
        print(f"VARIANT {tag:<18} out {shape}: cpu-vs-gpu cosine {cos:.6f} max|diff| {np.abs(yc - yg).max():.4e}  ({os.path.getsize(p)/1e6:.1f} MB)", flush=True)
    except Exception as e:
        print(f"VARIANT {tag:<18} ERR {str(e)[:160]}", flush=True)

for v in variants:
    mt = load(); sg = mt.subgraphs[0]
    if v == "prefix2-rank3":
        ops = sg.operators[:2]; out_t = int(ops[1].outputs[0]); prune(mt, ops, out_t)
        report(v, pack(mt, v), [x], [1, 1024, 768])
    elif v == "prefix2-reshape3":
        fc, add = sg.operators[0], sg.operators[1]
        rs, mid = make_reshape(mt, sg, int(fc.outputs[0]), [1, 1024, 768], "fc_out_3d")
        add.inputs = np.array([mid, int(add.inputs[1])], dtype=np.int32)
        ops = [fc, rs, add]; out_t = int(add.outputs[0]); prune(mt, ops, out_t)
        report(v, pack(mt, v), [x], [1, 1024, 768])
    elif v == "prefix2-rank4":
        fc, add = sg.operators[0], sg.operators[1]
        rs, mid = make_reshape(mt, sg, int(fc.outputs[0]), [1, 1, 1024, 768], "fc_out_4d")
        c = sg.tensors[int(add.inputs[1])]; c.shape = np.array([1, 1, 1024, 768], dtype=np.int32)
        o = sg.tensors[int(add.outputs[0])]; o.shape = np.array([1, 1, 1024, 768], dtype=np.int32)
        add.inputs = np.array([mid, int(add.inputs[1])], dtype=np.int32)
        ops = [fc, rs, add]; out_t = int(add.outputs[0]); prune(mt, ops, out_t)
        report(v, pack(mt, v), [x], [1, 1, 1024, 768])
    elif v == "prefix2-input":
        add = sg.operators[1]; c = sg.tensors[int(add.inputs[1])]; c.buffer = 0
        ops = sg.operators[:2]; out_t = int(ops[1].outputs[0]); prune(mt, ops, out_t, extra_inputs=[int(add.inputs[1])])
        report(v, pack(mt, v), [x, table], [1, 1024, 768])
    elif v == "full-input":
        add = sg.operators[1]; c = sg.tensors[int(add.inputs[1])]; c.buffer = 0
        ops = list(sg.operators); out_t = int(sg.outputs[0]); prune(mt, ops, out_t, extra_inputs=[int(add.inputs[1])])
        report(v, pack(mt, v), [x, table], [1, 1024, 768])
