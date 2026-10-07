#!/usr/bin/env python3
"""Read what an exported LLM .pte declares, without running the model.

- metadata methods (get_max_seq_len, get_max_context_len, get_bos_id,
  get_eos_ids, use_kv_cache, enable_dynamic_shape, ...): executed through the
  installed executorch.runtime; these constants are what llama_main reads;
- the forward method's input shapes (static upper bounds as serialized);
- which backends the forward method delegates to, the number of delegate calls
  and the operators left outside every delegate (portable / optimized kernels).

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
                                     "nonDelegatedKernels": dict(kernels), "inputs": inputs}

    runtime = Runtime.get()
    prog = runtime.load_program(args.pte)
    metadata = {}
    for name in sorted(prog.method_names):
        if name == "forward" or name.startswith("forward"):
            continue
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
