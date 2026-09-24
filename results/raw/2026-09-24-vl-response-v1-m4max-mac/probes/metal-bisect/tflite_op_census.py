"""Count builtin ops per subgraph of a .tflite and flag RESIZE_BILINEAR nodes whose inputs are all constants.

usage: tflite_op_census.py <model.tflite> [more.tflite ...]
"""
import sys, collections
from ai_edge_litert import schema_py_generated as schema

names = {v: k for k, v in vars(schema.BuiltinOperator).items() if isinstance(v, int)}
for path in sys.argv[1:]:
    buf = open(path, "rb").read()
    m = schema.Model.GetRootAsModel(buf, 0)
    codes = [m.OperatorCodes(i) for i in range(m.OperatorCodesLength())]
    def opname(c):
        b = max(c.BuiltinCode(), c.DeprecatedBuiltinCode())
        return names.get(b, str(b)) if b != schema.BuiltinOperator.CUSTOM else "CUSTOM:" + (c.CustomCode() or b"?").decode()
    print("==", path, "subgraphs", m.SubgraphsLength())
    for si in range(m.SubgraphsLength()):
        sg = m.Subgraphs(si)
        sg_inputs = set(sg.InputsAsNumpy().tolist())
        # a tensor is "runtime" if it is a subgraph input or produced by an op
        produced = set()
        cnt = collections.Counter()
        resize_notes = []
        for oi in range(sg.OperatorsLength()):
            op = sg.Operators(oi)
            n = opname(codes[op.OpcodeIndex()])
            cnt[n] += 1
            if n.startswith("RESIZE"):
                ins = [t for t in op.InputsAsNumpy().tolist() if t >= 0]
                runtime = [t for t in ins if t in sg_inputs or t in produced]
                resize_notes.append(f"{n}@op{oi}: inputs {ins} runtime {runtime}")
            for t in op.OutputsAsNumpy().tolist():
                produced.add(t)
        name = sg.Name().decode() if sg.Name() else f"subgraph{si}"
        print(f"  [{name}] ops={sum(cnt.values())} " + ", ".join(f"{k}:{v}" for k, v in sorted(cnt.items(), key=lambda kv: -kv[1])[:12]))
        for r in resize_notes:
            print("    ", r)
