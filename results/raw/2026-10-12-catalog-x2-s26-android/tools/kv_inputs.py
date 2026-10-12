#!/usr/bin/env python3
"""KV-cache inputs of a .litertlm's decode signature: name group, shape, dtype, scales (static read, nothing runs).

  python3 tools/kv_inputs.py <bundle.litertlm> [--signature decode]

Needs the litert_lm_builder and ai_edge_litert wheels (checked with litert-lm-builder 0.17.0, ai-edge-litert 2.2.0).
The section is found through the .litertlm header (model_type tf_lite_prefill_decode), not the first "TFL3" in the
file: on Gemma 4 bundles that one is the embedder section. A shape entry of 32003 is the export's placeholder for the
allocation; the engine rewrites it to --max_num_tokens at load.
"""
import argparse, collections, io, mmap, sys

from ai_edge_litert.schema_py_generated import Model, TensorType
from litert_lm_builder import litertlm_peek

TT = {v: k for k, v in vars(TensorType).items() if isinstance(v, int)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle")
    ap.add_argument("--signature", default="decode")
    a = ap.parse_args()
    meta = litertlm_peek.read_litertlm_header(a.bundle, io.StringIO())
    secs = meta.SectionMetadata()
    sec = next(secs.Objects(i) for i in range(secs.ObjectsLength())
               if litertlm_peek.get_model_type(secs.Objects(i)) == "tf_lite_prefill_decode")
    fh = open(a.bundle, "rb")
    mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
    m = Model.GetRootAs(memoryview(mm)[sec.BeginOffset():sec.EndOffset()], 0)
    sd = next(m.SignatureDefs(i) for i in range(m.SignatureDefsLength())
              if m.SignatureDefs(i).SignatureKey().decode() == a.signature)
    sg = m.Subgraphs(sd.SubgraphIndex())
    print(f"section tf_lite_prefill_decode @ {sec.BeginOffset()}..{sec.EndOffset()}; signatures "
          f"{[m.SignatureDefs(i).SignatureKey().decode() for i in range(m.SignatureDefsLength())]}; "
          f"{a.signature}: {sd.InputsLength()} inputs, subgraph {sd.SubgraphIndex()} ({sg.OperatorsLength()} ops)")
    groups = collections.defaultdict(list)
    for j in range(sd.InputsLength()):
        tm = sd.Inputs(j)
        name = tm.Name().decode()
        t = sg.Tensors(tm.TensorIndex())
        shape = [t.Shape(k) for k in range(t.ShapeLength())]
        q = t.Quantization()
        scales = q.ScaleLength() if q is not None else 0
        if name.startswith("kv_cache"):
            stem, layer = name.rsplit("_", 1)
            groups[(stem, tuple(shape), TT.get(t.Type()), scales)].append(int(layer))
        else:
            print(f"input {name} {shape} {TT.get(t.Type())}")
    for (stem, shape, dtype, scales), layers in sorted(groups.items()):
        print(f"{stem} x{len(layers)}: shape {list(shape)} rank {len(shape)} {dtype} scales {scales} layers {sorted(layers)}")


if __name__ == "__main__":
    sys.exit(main())
