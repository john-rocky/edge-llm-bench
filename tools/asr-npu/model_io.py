#!/usr/bin/env python3
"""Print every signature of .tflite files with its inputs and outputs (name, tensor, shape, type)
and the custom ops of each subgraph, read from the flatbuffer (asr-npu-v1, docs/asr-npu-v1.md).
The file is memory-mapped and only the model's tables are read, not its weights.

Usage: model_io.py <model.tflite>... [--json out.json]
"""
import argparse
import json
import mmap
import pathlib
import sys

import tflite

TYPES = {getattr(tflite.TensorType, k): k for k in dir(tflite.TensorType) if not k.startswith("_")}
BUILTINS = {getattr(tflite.BuiltinOperator, k): k for k in dir(tflite.BuiltinOperator) if not k.startswith("_")}


def describe(path):
    with open(path, "rb") as f:
        buf = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        model = tflite.Model.GetRootAs(buf, 0)
        subgraphs = []
        for s in range(model.SubgraphsLength()):
            g = model.Subgraphs(s)
            ops = {}
            for o in range(g.OperatorsLength()):
                code = model.OperatorCodes(g.Operators(o).OpcodeIndex())
                if code.CustomCode():
                    name = "CUSTOM:" + code.CustomCode().decode()
                else:
                    b = max(code.BuiltinCode(), code.DeprecatedBuiltinCode())
                    name = BUILTINS.get(b, str(b))
                ops[name] = ops.get(name, 0) + 1
            subgraphs.append({"index": s, "name": (g.Name() or b"").decode(), "operators": g.OperatorsLength(),
                              "op_counts": dict(sorted(ops.items(), key=lambda kv: -kv[1])[:8])})

        def tensor(g, i):
            t = g.Tensors(i)
            return {"tensor": (t.Name() or b"").decode(), "shape": t.ShapeAsNumpy().tolist() if t.ShapeLength() else [],
                    "type": TYPES.get(t.Type(), str(t.Type()))}

        sigs = []
        for k in range(model.SignatureDefsLength()):
            sd = model.SignatureDefs(k)
            g = model.Subgraphs(sd.SubgraphIndex())
            sigs.append({
                "key": sd.SignatureKey().decode(),
                "subgraph": sd.SubgraphIndex(),
                "inputs": [{"name": sd.Inputs(i).Name().decode(), **tensor(g, sd.Inputs(i).TensorIndex())}
                           for i in range(sd.InputsLength())],
                "outputs": [{"name": sd.Outputs(i).Name().decode(), **tensor(g, sd.Outputs(i).TensorIndex())}
                            for i in range(sd.OutputsLength())],
            })
        rec = {"file": pathlib.Path(path).name, "bytes": pathlib.Path(path).stat().st_size,
               "signatures": sigs, "subgraphs": subgraphs}
        del model
        buf.close()
        return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("models", nargs="+")
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    out = [describe(p) for p in args.models]
    for rec in out:
        print(f"== {rec['file']} ({rec['bytes']} B)")
        for s in rec["signatures"]:
            print(f"  signature {s['key']} (subgraph {s['subgraph']})")
            for io in ("inputs", "outputs"):
                for t in s[io]:
                    print(f"    {io[:-1]} {t['name']}: {t['shape']} {t['type']} ({t['tensor']})")
        for g in rec["subgraphs"][:4]:
            print(f"  subgraph {g['index']} {g['name']!r}: {g['operators']} ops {g['op_counts']}")
        if len(rec["subgraphs"]) > 4:
            print(f"  ... {len(rec['subgraphs']) - 4} more subgraphs (in --json)")
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(out, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
