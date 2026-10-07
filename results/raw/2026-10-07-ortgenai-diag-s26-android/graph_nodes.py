"""Node table of the GenAI model graph, for splitting an ORT profile by op kind
(ORT GenAI Galaxy S26 1K prefill diagnosis, round r2b, 2026-10-07).

An ORT profile event names its node (`name`) and op type (`args.op_name`) but
not a MatMulNBits node's bit width; this table carries it from model.onnx, with
K / N / block_size / accuracy_level, so profile_summary.py can put int4 and int8
MatMulNBits apart and compute each node's multiply-accumulates for a prompt of
M tokens (M x K x N).

usage: python -I graph_nodes.py <model.onnx> <out.json>
Reads the graph only (no initializer data is decoded beyond the protobuf load).
"""
import collections
import json
import sys

import onnx


def main(model_path, out_path):
    model = onnx.load(model_path, load_external_data=False)
    graph = model.graph
    nodes = {}
    counts = collections.Counter()
    for node in graph.node:
        attrs = {a.name: onnx.helper.get_attribute_value(a) for a in node.attribute}
        entry = {"op_type": node.op_type}
        if node.op_type == "MatMulNBits":
            for key in ("bits", "block_size", "accuracy_level", "K", "N"):
                if key in attrs:
                    entry[key] = int(attrs[key])
            counts[f"MatMulNBits bits={entry.get('bits')}"] += 1
        else:
            counts[node.op_type] += 1
        nodes[node.name] = entry
    outputs = []
    for out in graph.output:
        dims = [d.dim_param or d.dim_value for d in out.type.tensor_type.shape.dim]
        outputs.append({"name": out.name, "elem_type": out.type.tensor_type.elem_type, "dims": dims})
    table = {
        "model": model_path,
        "opsets": {o.domain or "ai.onnx": o.version for o in model.opset_import},
        "node_count": len(graph.node),
        "op_counts": dict(sorted(counts.items())),
        "outputs": [o for o in outputs if o["name"] == "logits"],
        "nodes": nodes,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(table, f, indent=1, sort_keys=False)
    print(json.dumps({k: table[k] for k in ("node_count", "op_counts", "outputs")}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
