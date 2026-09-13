#!/usr/bin/env python3
"""Static weight bytes per decode step of a .litertlm bundle, read off the
decode signature's graph: every constant tensor an op consumes, deduplicated by
buffer, grouped by consumer op type. Embedding tables consumed by GATHER are
listed apart (one row per token, not the table). Needs the ai_edge_litert wheel.

  python weight_bytes.py <bundle.litertlm> [...]
"""
import collections
import json
import sys

from ai_edge_litert.schema_py_generated import (BlockwiseQuantization, BuiltinOperator, Model,
                                                QuantizationDetails)

NAMES = {v: k for k, v in vars(BuiltinOperator).items() if isinstance(v, int)}
TYPES = {0: "F32", 1: "F16", 2: "I32", 3: "U8", 4: "I64", 6: "BOOL", 7: "I16", 9: "I8",
         16: "U16", 17: "I4", 18: "BF16"}


def buf_bytes(m, bi):
    b = m.Buffers(bi)
    n = b.DataLength()
    if n == 0 and hasattr(b, "Size"):
        try:
            n = b.Size()
        except Exception:
            n = 0
    return n


def walk(path):
    data = open(path, "rb").read()
    off = data.find(b"TFL3") - 4
    m = Model.GetRootAs(data[off:], 0)
    codes = [NAMES.get(m.OperatorCodes(i).BuiltinCode(), "?") for i in range(m.OperatorCodesLength())]
    sigs = {}
    for i in range(m.SignatureDefsLength()):
        sd = m.SignatureDefs(i)
        sigs[sd.SubgraphIndex()] = sd.SignatureKey().decode()
    out = {"file": path, "signatures": sigs, "graphs": {}}
    for si in range(m.SubgraphsLength()):
        sg = m.Subgraphs(si)
        name = sigs.get(si) or (sg.Name().decode() if sg.Name() else f"sg{si}")
        if not (name == "decode" or name.startswith("prefill")):
            continue
        seen = {}          # buffer index -> (bytes, type, shape, consumers)
        by_op = collections.Counter()
        by_op_n = collections.Counter()
        blockwise = collections.Counter()
        for oi in range(sg.OperatorsLength()):
            op = sg.Operators(oi)
            c = codes[op.OpcodeIndex()]
            for k in range(op.InputsLength()):
                ti = op.Inputs(k)
                if ti < 0:
                    continue
                t = sg.Tensors(ti)
                bi = t.Buffer()
                n = buf_bytes(m, bi)
                if n == 0:
                    continue
                shape = [int(t.Shape(j)) for j in range(t.ShapeLength())]
                key = bi
                if key not in seen:
                    seen[key] = [n, TYPES.get(t.Type(), str(t.Type())), shape, set(), t.Name().decode()]
                    by_op[c] += n
                    by_op_n[c] += 1
                seen[key][3].add(c)
                q = t.Quantization()
                if q is not None and q.DetailsType() == QuantizationDetails.BlockwiseQuantization:
                    bq = BlockwiseQuantization()
                    bq.Init(q.Details().Bytes, q.Details().Pos)
                    for side in (bq.Scales(), bq.ZeroPoints()):
                        if side is None or side < 0:
                            continue
                        st = sg.Tensors(side)
                        sb = st.Buffer()
                        sn = buf_bytes(m, sb)
                        if sn == 0 or sb in seen:
                            continue
                        # the side tensor is read wherever its weight is: share the consumer set
                        seen[sb] = [sn, TYPES.get(st.Type(), str(st.Type())), [int(st.Shape(j)) for j in range(st.ShapeLength())], seen[key][3], "blockwise-side:" + st.Name().decode()]
                        by_op[c] += sn
                        by_op_n[c] += 1
                        blockwise[c] += sn
        total = sum(v[0] for v in seen.values())
        gather = sum(v[0] for v in seen.values() if v[3] <= {"GATHER", "EMBEDDING_LOOKUP"})
        big = sorted(seen.values(), key=lambda v: -v[0])[:8]
        out["graphs"][name] = {
            "ops": sg.OperatorsLength(),
            "const_bytes_total": total,
            "const_bytes_gather_only": gather,
            "const_bytes_streamed": total - gather,
            "blockwise_side_bytes_by_op": dict(blockwise),
            "by_consumer_op": {k: [v, by_op_n[k]] for k, v in sorted(by_op.items(), key=lambda kv: -kv[1])},
            "largest": [{"bytes": v[0], "type": v[1], "shape": v[2], "ops": sorted(v[3]), "name": v[4][:80]} for v in big],
        }
    return out


if __name__ == "__main__":
    for p in sys.argv[1:]:
        r = walk(p)
        print(json.dumps(r, indent=1))
