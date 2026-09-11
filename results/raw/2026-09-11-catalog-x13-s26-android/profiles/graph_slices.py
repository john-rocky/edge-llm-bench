"""Walk every subgraph of the tflite inside a .litertlm; per signature-named
subgraph, count SLICE / DYNAMIC_UPDATE_SLICE ops and the bytes of their largest
input (what a decode step copies per op)."""
import sys, collections, numpy as np
from ai_edge_litert.schema_py_generated import Model, BuiltinOperator
DT={0:4,1:2,2:4,3:1,9:1,6:1,7:1,16:2}  # tensor type -> bytes (FLOAT32 F16 INT32 UINT8 INT8 BOOL INT16 INT4≈0.5)
NAMES={v:k for k,v in vars(BuiltinOperator).items() if isinstance(v,int)}
data=open(sys.argv[1],'rb').read(); off=data.find(b'TFL3')-4
m=Model.GetRootAs(data[off:],0)
codes=[NAMES.get(m.OperatorCodes(i).BuiltinCode(),'?') for i in range(m.OperatorCodesLength())]
sigs={}
for i in range(m.SignatureDefsLength()):
    sd=m.SignatureDefs(i); sigs[sd.SubgraphIndex()]=sd.SignatureKey().decode()
print("signatures:",sigs)
for si in range(m.SubgraphsLength()):
    sg=m.Subgraphs(si); name=sigs.get(si) or (sg.Name().decode() if sg.Name() else f"sg{si}")
    if not (name=='decode' or name.startswith('prefill')): continue
    stats=collections.defaultdict(lambda:[0,0,collections.Counter()])
    for oi in range(sg.OperatorsLength()):
        op=sg.Operators(oi); c=codes[op.OpcodeIndex()]
        if c not in ('SLICE','DYNAMIC_UPDATE_SLICE','STRIDED_SLICE','GATHER','CONCATENATION'): continue
        best=0; shape=None
        for k in range(op.InputsLength()):
            ti=op.Inputs(k)
            if ti<0: continue
            t=sg.Tensors(ti); shp=tuple(int(t.Shape(j)) for j in range(t.ShapeLength()))
            b=int(np.prod(shp))*DT.get(t.Type(),4)
            if b>best: best=b; shape=(shp,t.Type())
        s=stats[c]; s[0]+=1; s[1]+=best; s[2][shape]+=1
    print(f"== {sys.argv[1].split('/')[-1][:48]} {name}: ops {sg.OperatorsLength()}")
    for c,(n,byt,shapes) in stats.items():
        print(f"   {c:22s} n={n:4d} sum(largest input)={byt/1e6:8.1f} MB  top shapes: {shapes.most_common(3)}")
