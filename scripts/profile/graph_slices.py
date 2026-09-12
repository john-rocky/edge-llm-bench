#!/usr/bin/env python3
"""Static walk of the tflite inside a .litertlm: per decode / prefill signature,
count SLICE / DYNAMIC_UPDATE_SLICE / STRIDED_SLICE / GATHER / CONCATENATION ops
and the bytes of their largest input — what one step copies per op, read off
the graph rather than the profiler. Needs the ai_edge_litert wheel.

  python3 scripts/profile/graph_slices.py <bundle.litertlm>
"""
import collections
import sys

import numpy as np
from ai_edge_litert.schema_py_generated import BuiltinOperator, Model

DT = {0: 4, 1: 2, 2: 4, 3: 1, 9: 1, 6: 1, 7: 1, 16: 2}  # tensor type -> bytes (INT4 counted as 2 per pair)
NAMES = {v: k for k, v in vars(BuiltinOperator).items() if isinstance(v, int)}
OPS = ("SLICE", "DYNAMIC_UPDATE_SLICE", "STRIDED_SLICE", "GATHER", "CONCATENATION")


def main(path):
    data = open(path, "rb").read()
    off = data.find(b"TFL3") - 4
    m = Model.GetRootAs(data[off:], 0)
    codes = [NAMES.get(m.OperatorCodes(i).BuiltinCode(), "?") for i in range(m.OperatorCodesLength())]
    sigs = {}
    for i in range(m.SignatureDefsLength()):
        sd = m.SignatureDefs(i)
        sigs[sd.SubgraphIndex()] = sd.SignatureKey().decode()
    print("signatures:", sigs)
    for si in range(m.SubgraphsLength()):
        sg = m.Subgraphs(si)
        name = sigs.get(si) or (sg.Name().decode() if sg.Name() else f"sg{si}")
        if not (name == "decode" or name.startswith("prefill")):
            continue
        stats = collections.defaultdict(lambda: [0, 0, collections.Counter()])
        for oi in range(sg.OperatorsLength()):
            op = sg.Operators(oi)
            c = codes[op.OpcodeIndex()]
            if c not in OPS:
                continue
            best, shape = 0, None
            for k in range(op.InputsLength()):
                ti = op.Inputs(k)
                if ti < 0:
                    continue
                t = sg.Tensors(ti)
                shp = tuple(int(t.Shape(j)) for j in range(t.ShapeLength()))
                b = int(np.prod(shp)) * DT.get(t.Type(), 4)
                if b > best:
                    best, shape = b, (shp, t.Type())
            s = stats[c]
            s[0] += 1
            s[1] += best
            s[2][shape] += 1
        print(f"== {path.split('/')[-1][:48]} {name}: ops {sg.OperatorsLength()}")
        for c, (n, byt, shapes) in stats.items():
            print(f"   {c:22s} n={n:4d} sum(largest input)={byt / 1e6:8.1f} MB  top shapes: {shapes.most_common(3)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
