"""List large constant tensors of a tflite (dtype, shape, quantization) and which op consumes them."""
import sys, numpy as np
from ai_edge_litert import schema_py_generated as schema
tnames = {v: k for k, v in vars(schema.TensorType).items() if isinstance(v, int)}
onames = {v: k for k, v in vars(schema.BuiltinOperator).items() if isinstance(v, int)}
for path in sys.argv[1:]:
    m = schema.Model.GetRootAsModel(open(path, "rb").read(), 0)
    sg = m.Subgraphs(0); codes = [m.OperatorCodes(i) for i in range(m.OperatorCodesLength())]
    consumers = {}
    for oi in range(sg.OperatorsLength()):
        op = sg.Operators(oi); n = onames.get(max(codes[op.OpcodeIndex()].BuiltinCode(), codes[op.OpcodeIndex()].DeprecatedBuiltinCode()), "?")
        for t in op.InputsAsNumpy().tolist(): consumers.setdefault(t, []).append(f"{n}@{oi}")
    print("==", path)
    for ti in range(sg.TensorsLength()):
        t = sg.Tensors(ti); buf = m.Buffers(t.Buffer())
        size = 0
        if buf is not None:
            size = buf.DataLength() or (buf.Size() if hasattr(buf, "Size") else 0)
        shape = t.ShapeAsNumpy().tolist() if t.ShapeLength() else []
        n = int(np.prod(shape)) if shape else 0
        if size > 0 and n >= 100_000:
            q = t.Quantization(); qs = q.ScaleLength() if q is not None else 0
            print(f"  t{ti} {tnames.get(t.Type(), t.Type())} {shape} bytes={size} scales={qs} name={t.Name().decode()[:60]} -> {consumers.get(ti, [])[:3]}")
