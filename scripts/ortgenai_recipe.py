#!/usr/bin/env python3
"""Recipe labels of ONNX Runtime GenAI model folders (quant-label-rule): read from the
model, never typed.

  python3 scripts/ortgenai_recipe.py <model dir> --model-id <repo> --folder <path in repo> \\
      --revision <sha> [--register]

A GenAI folder (genai_config.json + model.onnx [+ model.onnx.data] + tokenizer) carries its
recipe in the graph: the MatMulNBits / GatherBlockQuantized nodes' bits, block_size and
accuracy_level, the dtypes of their scales and zero points, and the dtype of the KV inputs
and the logits. describe() reads those facts with the `onnx` package (the graph only; external
data is not loaded) plus the folder's config.json quantization block; label() turns them into
the string a record carries as model.quantization, e.g. for onnx-community/Qwen3-0.6B-ONNX
onnxruntime/cpu_and_mobile/cpu-int4-kld-block-128 at da145310: "int4 + int8 mixed MatMulNBits
(92 int4 / 105 int8 of 197; per-layer int8 overrides as published), block 128, asymmetric
uint8 zero points, fp32 scales, accuracy_level 4; int8 block-128 GatherBlockQuantized
embedding; fp32 activations and KV (onnx-community cpu-int4-kld-block-128, Olive 0.11.0.dev0 +
ORT GenAI model builder, PR #3 2026-04-20)". "int4" alone would be wrong: more than half of
those MatMulNBits are 8-bit.

--register writes the entry into models/ortgenai-recipes.json (it also reads the Hub commit of
the revision for the provenance tail). The drivers (scripts/ortgenai_mac.py,
android/bench/run_cell.py) look the label up there by (model id, folder, model.onnx sha256)
with lookup(), which is stdlib only, and refuse a folder the registry does not know, printing
the command that registers it. BENCH_ORTGENAI_RECIPES points lookup() at another registry
file (android/bench/selftest.py).
"""
import argparse
import collections
import datetime
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join(ROOT, "models", "ortgenai-recipes.json")
DTYPE = {"FLOAT": "fp32", "FLOAT16": "fp16", "BFLOAT16": "bf16", "UINT8": "uint8", "INT8": "int8"}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def registry_path():
    return os.environ.get("BENCH_ORTGENAI_RECIPES") or REGISTRY


def load_registry(path=None):
    path = path or registry_path()
    if not os.path.exists(path):
        return {"recipes": []}
    with open(path) as fh:
        return json.load(fh)


def lookup(model_id, folder, model_onnx_sha256, path=None):
    """The registered entry of this exact folder (its model.onnx by sha256), or None."""
    for e in load_registry(path).get("recipes", []):
        if (e.get("model_id"), e.get("folder"), e.get("model_onnx_sha256")) == (model_id, folder, model_onnx_sha256):
            return e
    return None


def register_command(model_dir, model_id, folder, revision):
    return (f"<ortgenai venv>/bin/python scripts/ortgenai_recipe.py {model_dir} --model-id {model_id} "
            f"--folder {folder} --revision {revision or '<hf revision>'} --register")


def describe(model_dir):
    """The facts a label is built from: quantized ops (op, bits, block, accuracy level, scale
    and zero-point dtypes, count), KV and logits dtypes, producer, opsets, metadata, node count,
    and the config.json quantization block (needs the `onnx` package)."""
    import onnx
    from onnx import helper
    m = onnx.load(os.path.join(model_dir, "model.onnx"), load_external_data=False)
    inits = {i.name: i for i in m.graph.initializer}
    name = onnx.TensorProto.DataType.Name

    def init_type(node, index):
        if len(node.input) > index and node.input[index] and node.input[index] in inits:
            return name(inits[node.input[index]].data_type)
        return None

    ops = collections.Counter()
    for n in m.graph.node:
        if n.op_type in ("MatMulNBits", "GatherBlockQuantized"):
            a = {x.name: helper.get_attribute_value(x) for x in n.attribute}
            # MatMulNBits (A, B, scales, zero_points); GatherBlockQuantized (data, indices, scales, zero_points)
            ops[(n.op_type, a.get("bits"), a.get("block_size"), a.get("accuracy_level"),
                 init_type(n, 2), init_type(n, 3))] += 1
    kv = sorted({name(i.type.tensor_type.elem_type) for i in m.graph.input if i.name.startswith("past_key_values")})
    logits = sorted({name(o.type.tensor_type.elem_type) for o in m.graph.output if o.name == "logits"})
    facts = {"producer": m.producer_name, "producerVersion": m.producer_version,
             "opsets": {o.domain or "ai.onnx": o.version for o in m.opset_import},
             "metadata": {p.key: p.value for p in m.metadata_props}, "nodes": len(m.graph.node),
             "quantizedOps": [{"op": k[0], "bits": k[1], "blockSize": k[2], "accuracyLevel": k[3],
                               "scaleType": k[4], "zeroPointType": k[5], "count": c}
                              for k, c in sorted(ops.items(), key=str)],
             "kvTypes": kv, "logitsTypes": logits}
    cfg_path = os.path.join(model_dir, "config.json")
    if os.path.exists(cfg_path):
        with open(cfg_path) as fh:
            q = json.load(fh).get("quantization_config") or {}
        overrides = q.get("overrides") or {}
        facts["config"] = {k: q.get(k) for k in ("quant_method", "bits", "group_size", "symmetric") if k in q}
        facts["config"]["overrideBits"] = dict(sorted(collections.Counter(
            str(v.get("bits")) for v in (overrides.values() if isinstance(overrides, dict) else overrides)
            if isinstance(v, dict)).items()))
    return facts


def _one_or_all(values, fmt):
    values = sorted(set(values), key=lambda v: (v is None, v))
    return fmt(values[0]) if len(values) == 1 else " / ".join(fmt(v) for v in values)


def label(facts, model_id, folder, source):
    """facts (describe()) + where the folder comes from -> the record's quantization string.
    `source`: the publication note, e.g. "PR #3 2026-04-20" (source_note())."""
    mm = [q for q in facts["quantizedOps"] if q["op"] == "MatMulNBits"]
    if not mm:
        raise ValueError("no MatMulNBits node: not a GenAI int-N folder this labeller knows")
    bits = collections.Counter()
    for q in mm:
        bits[q["bits"]] += q["count"]
    total = sum(bits.values())
    widths = sorted(bits)
    if len(widths) > 1:
        head = (" + ".join(f"int{b}" for b in widths) + " mixed MatMulNBits ("
                + " / ".join(f"{bits[b]} int{b}" for b in widths) + f" of {total}")
    else:
        head = f"int{widths[0]} MatMulNBits ({total} of {total}"
    over = (facts.get("config") or {}).get("overrideBits") or {}
    if over:
        head += "; per-layer " + " / ".join(f"int{b}" for b in sorted(over)) + " overrides as published"
    parts = [head + ")",
             _one_or_all([q["blockSize"] for q in mm], lambda v: f"block {v}")]
    zps = {q["zeroPointType"] for q in mm}
    if zps == {None}:
        parts.append("symmetric (no zero points)")
    else:
        parts.append(_one_or_all([q["zeroPointType"] for q in mm],
                                 lambda v: f"asymmetric {DTYPE.get(v, v)} zero points" if v else "no zero points"))
    parts.append(_one_or_all([q["scaleType"] for q in mm], lambda v: f"{DTYPE.get(v, v)} scales"))
    parts.append(_one_or_all([q["accuracyLevel"] for q in mm], lambda v: f"accuracy_level {v}"))
    text = ", ".join(parts)
    gbq = [q for q in facts["quantizedOps"] if q["op"] == "GatherBlockQuantized"]
    if gbq:
        text += "; " + ", ".join(f"int{q['bits']} block-{q['blockSize']} GatherBlockQuantized embedding" for q in gbq)
    kv = [DTYPE.get(t, t) for t in facts.get("kvTypes", [])]
    logits = [DTYPE.get(t, t) for t in facts.get("logitsTypes", [])]
    if kv and kv == logits:
        text += f"; {'/'.join(kv)} activations and KV"
    else:
        text += f"; {'/'.join(logits) or '?'} activations, {'/'.join(kv) or '?'} KV"
    tail = [f"{model_id.split('/', 1)[0]} {os.path.basename(folder.rstrip('/'))}"]
    builder = []
    if (facts.get("metadata") or {}).get("olive_version"):
        builder.append(f"Olive {facts['metadata']['olive_version']}")
    if facts.get("producer") == "onnxruntime-genai":
        builder.append("ORT GenAI model builder")
    if builder:
        tail.append(" + ".join(builder))
    if source:
        tail.append(source)
    return f"{text} ({', '.join(tail)})"


def source_commit(model_id, revision):
    """The Hub commit of `revision`: {id, title, date, authors} (network)."""
    from huggingface_hub import HfApi
    c = HfApi().list_repo_commits(model_id, revision=revision)[0]
    if c.commit_id != revision:
        raise SystemExit(f"{model_id}: the newest commit up to {revision} is {c.commit_id}")
    return {"id": c.commit_id, "title": c.title, "date": c.created_at.date().isoformat(),
            "authors": list(c.authors or [])}


def source_note(commit):
    """'PR #3 2026-04-20' for a merged-PR commit title '... (#3)', else 'commit <sha8> <date>'."""
    m = re.search(r"\(#(\d+)\)\s*$", commit.get("title") or "")
    return f"PR #{m.group(1)} {commit['date']}" if m else f"commit {commit['id'][:8]} {commit['date']}"


def folder_files(model_dir):
    """{name: {bytes, sha256}} of every file in the folder (symlinks into an HF cache resolved)."""
    out = {}
    for name in sorted(os.listdir(model_dir)):
        p = os.path.realpath(os.path.join(model_dir, name))
        if os.path.isfile(p):
            out[name] = {"bytes": os.path.getsize(p), "sha256": sha256(p)}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model_dir")
    ap.add_argument("--model-id", required=True)
    ap.add_argument("--folder", required=True, help="the folder's path inside the HF repo (cells file=)")
    ap.add_argument("--revision", required=True, help="HF commit the folder was taken at (cells revision=)")
    ap.add_argument("--register", action="store_true", help=f"add or replace the entry in {os.path.relpath(REGISTRY, ROOT)}")
    args = ap.parse_args()
    facts = describe(args.model_dir)
    commit = source_commit(args.model_id, args.revision)
    files = folder_files(args.model_dir)
    entry = {"model_id": args.model_id, "revision": args.revision, "folder": args.folder,
             "model_onnx_sha256": files["model.onnx"]["sha256"],
             "label": label(facts, args.model_id, args.folder, source_note(commit)),
             "source_commit": commit, "files": files, "facts": facts,
             "registered": datetime.date.today().isoformat(), "tool": "scripts/ortgenai_recipe.py"}
    print(json.dumps(entry, indent=1, ensure_ascii=False))
    if args.register:
        reg = load_registry(REGISTRY)
        reg.setdefault("_doc", "Recipe label of each ONNX Runtime GenAI model folder the cells run, read "
                       "from its model.onnx by scripts/ortgenai_recipe.py --register (never typed). The "
                       "drivers look an entry up by (model_id, folder, model_onnx_sha256) and refuse a "
                       "folder that has none.")
        reg["recipes"] = [e for e in reg.get("recipes", [])
                          if (e.get("model_id"), e.get("folder")) != (args.model_id, args.folder)] + [entry]
        reg["recipes"].sort(key=lambda e: (e["model_id"], e["folder"]))
        with open(REGISTRY, "w") as fh:
            json.dump(reg, fh, indent=1, ensure_ascii=False)
            fh.write("\n")
        print(f"registered in {os.path.relpath(REGISTRY, ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
