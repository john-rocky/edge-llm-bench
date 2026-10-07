#!/usr/bin/env python3
"""Read what an exported LLM .pte declares, without running the model.

- metadata methods (get_max_seq_len, get_max_context_len, get_bos_id,
  get_eos_ids, use_kv_cache, enable_dynamic_shape, ...): executed through the
  installed executorch.runtime; these constants are what llama_main reads;
- the forward method's input shapes (static upper bounds as serialized);
- which backends the forward method delegates to, the number of delegate calls
  and the operators left outside every delegate (portable / optimized kernels);
- with --find-dim N: every tensor value whose sizes contain N (e.g. the KV cache
  buffers allocated at the export's max sequence length), grouped by shape.

Metadata methods are the methods without inputs; a method that takes inputs
(forward, text_decoder, ...) is described, never executed.

Prints one JSON object. Run it with the export venv's python, from a working
directory that is not the parent of an `executorch` source tree.
"""
import argparse
import collections
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pte", type=Path)
    ap.add_argument("--find-dim", type=int, help="group the tensor values whose sizes contain this dim")
    args = ap.parse_args()

    from executorch.exir._serialize._program import deserialize_pte_binary
    from executorch.exir import schema
    from executorch.runtime import Runtime

    pte = deserialize_pte_binary(args.pte.read_bytes())
    program = pte.program
    out = {"pte": str(args.pte), "bytes": args.pte.stat().st_size, "methods": {}}
    for plan in program.execution_plan:
        delegates = collections.Counter(d.id for d in plan.delegates)
        kernels = collections.Counter()
        delegate_calls = 0
        for chain in plan.chains:
            for ins in chain.instructions:
                arg = ins.instr_args
                if isinstance(arg, schema.KernelCall):
                    op = plan.operators[arg.op_index]
                    kernels[op.name + (f".{op.overload}" if op.overload else "")] += 1
                elif isinstance(arg, schema.DelegateCall):
                    delegate_calls += 1
        inputs = []
        for idx in plan.inputs:
            v = plan.values[idx].val
            if isinstance(v, schema.Tensor):
                inputs.append({"sizes": list(v.sizes), "scalar_type": str(v.scalar_type),
                               "dynamism": str(v.shape_dynamism)})
            else:
                inputs.append({"value": type(v).__name__})
        out["methods"][plan.name] = {"delegates": dict(delegates), "delegateCalls": delegate_calls,
                                     "nonDelegatedKernels": dict(kernels), "inputs": inputs,
                                     "nonConstBufferSizes": list(plan.non_const_buffer_sizes)}
        if args.find_dim is not None:
            groups = collections.OrderedDict()
            for v in plan.values:
                t = v.val
                if not isinstance(t, schema.Tensor) or args.find_dim not in list(t.sizes):
                    continue
                kind = "constant" if t.data_buffer_idx > 0 else ("planned" if t.allocation_info else "unplanned")
                key = (tuple(t.sizes), str(t.scalar_type), str(t.shape_dynamism), kind)
                g = groups.setdefault(key, {"sizes": list(t.sizes), "scalar_type": str(t.scalar_type),
                                            "dynamism": str(t.shape_dynamism), "kind": kind, "count": 0, "names": []})
                g["count"] += 1
                name = t.extra_tensor_info.fully_qualified_name if t.extra_tensor_info else None
                if name and len(g["names"]) < 4:
                    g["names"].append(name)
            out["methods"][plan.name][f"tensorsWithDim{args.find_dim}"] = list(groups.values())

    runtime = Runtime.get()
    prog = runtime.load_program(args.pte)
    metadata = {}
    for name in sorted(prog.method_names):
        if out["methods"].get(name, {}).get("inputs"):
            continue  # takes inputs: a model method, not a metadata constant
        try:
            result = prog.load_method(name).execute([])
            vals = [r.tolist() if hasattr(r, "tolist") else r for r in result]
            metadata[name] = vals[0] if len(vals) == 1 else vals
        except Exception as e:  # keep the failure visible, never guess a value
            metadata[name] = f"error: {type(e).__name__}: {e}"
    out["metadata"] = metadata
    out["pythonRuntimeBackends"] = sorted(runtime.backend_registry.registered_backend_names)
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
