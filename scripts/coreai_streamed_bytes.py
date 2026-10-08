#!/usr/bin/env python3
"""Bytes a decode step streams from a Core AI bundle — the `streamed_bytes` of the Core AI stock
arm's entries in models/artifact-bytes.json (arm core-ai-ane; the `bw util` column).

  <python with coreai> scripts/coreai_streamed_bytes.py <bundle dir> [--dump]
  <python with coreai> scripts/coreai_streamed_bytes.py --check     # exit 1 if an entry disagrees
  <python with coreai> scripts/coreai_streamed_bytes.py --update    # write streamed_* into the entries

Rule (the one of scripts/artifact_streamed_bytes.py and docs/dashboard-cells-v1.md, "bandwidth-
utilization column"): a dense decode step reads every weight once, so streamed bytes = the
artifact's tensor bytes minus tables GATHERED per token rather than read whole. A bundle's tensors
are its main .aimodel's (metadata.json `assets.main`), counted from the export's own census:
`AIModelAssetSummary.storage_types` (`coreai.authoring.asset.AIModelAsset.summary(
include_statistics=True)`), which counts the ELEMENTS stored per storage type — the palettization
indices (UInt4 / UInt6 / UInt8), the Int8 embedding table, Float16 look-up tables and norms, a few
Int32 / UInt32 / UInt64 constants. Bytes = elements x bit width / 8 per type, summed; a type without
a known width stops the script (never guessed).
  - The Int8 embedding table stays counted: it is the tied output head. Every extend_* function
    takes `embedding_table` as an input and returns logits over the whole vocabulary, and the
    census's Int8 count is that table (vocabulary x hidden) plus at most a few scalars — the
    script checks both before it counts (load_embeddings / gather_embeddings_* read the same
    table for the input side).
  - Gemma 4's per-layer-embedding sidecar (`auxiliary_assets.per_layer_embeddings`, a safetensors
    file beside the .aimodel) is gathered per token: the runner passes a token's rows in as
    `ple_embeddings`. It is outside the .aimodel, so outside the census; the entry's `bytes`
    (the whole bundle) holds it, `streamed_bytes` does not.
The tokenizer and metadata files are not tensor bytes. What is left is an estimate of bytes per
token from the export's census — the Neural Engine exposes no bus counter.

Needs Apple's `coreai` Python package (the apple/coreai-models venv the exports were made with,
e.g. ~/code/apple-coreai-models-main/.venv/bin/python); the registry side is stdlib only.
"""
import argparse
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join(ROOT, "models", "artifact-bytes.json")
ARM = "core-ai-ane"
TOOL = "scripts/coreai_streamed_bytes.py"
# storage type -> bits per element (AIModelAssetSummary.storage_types names)
BITS = {"UInt1": 1, "UInt2": 2, "UInt3": 3, "UInt4": 4, "Int4": 4, "UInt6": 6, "UInt8": 8, "Int8": 8,
        "UInt16": 16, "Int16": 16, "Float16": 16, "BFloat16": 16, "UInt32": 32, "Int32": 32,
        "Float32": 32, "UInt64": 64, "Int64": 64, "Float64": 64}
SHAPE = re.compile(r"NDArray \((\w+)(?:, ([\d × ]+))?\)")


def shape_of(t):
    """'NDArray (Int8, 262144 × 1 × 1536)' -> ('Int8', (262144, 1, 1536))."""
    m = SHAPE.fullmatch(str(t).strip())
    if not m:
        raise ValueError(f"unreadable tensor type {t!r}")
    dims = tuple(int(x) for x in m.group(2).split("×")) if m.group(2) else ()
    return m.group(1), dims


def census(bundle):
    """-> dict with the bundle's .aimodel census and the checks the rule rests on."""
    from coreai.authoring.asset import AIModelAsset  # Apple's package: only this side needs it
    meta = json.load(open(os.path.join(bundle, "metadata.json")))
    aimodel = meta["assets"]["main"]
    summary = AIModelAsset.load(os.path.join(bundle, aimodel)).summary(include_statistics=True)
    types = [(t, int(n)) for t, n in summary.storage_types]
    unknown = [t for t, _ in types if t not in BITS]
    if unknown:
        raise SystemExit(f"{bundle}: storage types without a known bit width: {unknown}")
    names = list(summary.function_names)
    ins = {n: {k: shape_of(v) for k, v in summary.function_inputs(n)} for n in names}
    outs = {n: {k: shape_of(v) for k, v in summary.function_outputs(n)} for n in names}
    extend = [n for n in names if n.startswith("extend_")]
    takes = [n for n in names if n not in ("load_embeddings",) and not n.startswith("gather_embeddings_")]
    tables = {ins[n].get("embedding_table") for n in takes}
    if not extend or None in tables or len(tables) != 1:
        raise SystemExit(f"{bundle}: not every decode function takes one embedding_table "
                         f"(functions {names})")
    dtype, dims = tables.pop()
    vocab, hidden = dims[0], dims[-1]
    head = [n for n in extend if any(d and d[-1] == vocab for _, d in outs[n].values())]
    if dtype != "Int8" or head != extend:
        raise SystemExit(f"{bundle}: embedding_table {dtype} {dims}; extend functions with "
                         f"vocabulary-wide logits {head} of {extend}")
    int8 = dict(types).get("Int8", 0)
    if not 0 <= int8 - vocab * hidden < 16:
        raise SystemExit(f"{bundle}: Int8 census {int8:,} is not the {vocab} x {hidden} table "
                         "(+ scalars): another Int8 tensor would need its own rule")
    ple = (meta.get("auxiliary_assets") or {}).get("per_layer_embeddings")
    total = sum(n * BITS[t] for t, n in types)
    if total % 8:
        raise SystemExit(f"{bundle}: census bits {total} not a whole number of bytes")
    return {"aimodel": aimodel, "types": types, "streamed": total // 8, "vocab": vocab,
            "hidden": hidden, "extend_n": len(extend), "ple": ple,
            "ple_bytes": os.path.getsize(os.path.join(bundle, ple)) if ple else None}


def basis(c):
    terms = " + ".join(f"{t} {n:,} x {BITS[t]}" for t, n in c["types"])
    s = (f"coreai: {c['aimodel']} census (AIModelAssetSummary.storage_types, elements x bits / 8): "
         f"{terms} = {c['streamed']:,} B; the Int8 embedding table ({c['vocab']} x {c['hidden']}) is an "
         f"input of every extend_* function ({c['extend_n']}), which returns logits over the whole "
         f"vocabulary ({c['vocab']}): the tied LM head, counted")
    if c["ple"]:
        s += (f"; the per-layer-embedding sidecar {c['ple']} ({c['ple_bytes']:,} B, gathered per token "
              "into ple_embeddings) is in bytes only")
    return s + "; an estimate from the export's census (the Neural Engine has no bus counter)"


def bundle_of(entry):
    if not entry["source"].startswith("local:"):
        raise SystemExit(f"{entry['model_id']}: a {ARM} entry is a local: bundle")
    return os.path.expanduser(entry["source"][len("local:"):])


def folder_files(bundle):
    out = []
    for root, _, files in os.walk(bundle):
        out += [os.path.relpath(os.path.join(root, f), bundle) for f in files]
    return sorted(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bundle", nargs="?")
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--registry", default=REGISTRY)
    args = ap.parse_args()
    if args.bundle:
        c = census(os.path.abspath(os.path.expanduser(args.bundle)))
        if args.dump:
            for t, n in c["types"]:
                print(f"  {t:<8} {n:>15,} x {BITS[t]:>2} bit = {n * BITS[t] // 8:>15,} B")
        print(c["streamed"])
        print(basis(c))
        return 0
    if not (args.check or args.update):
        ap.error("a bundle dir, --check or --update")
    reg = json.load(open(args.registry))
    today = datetime.date.today().isoformat()
    rc, seen = 0, 0
    for e in reg["artifacts"]:
        if e["arm"] != ARM:
            continue
        seen += 1
        bundle = bundle_of(e)
        c = census(bundle)
        want = {"streamed_bytes": c["streamed"], "streamed_basis": basis(c), "streamed_tool": TOOL}
        # bytes = the whole bundle: every file of the folder is in the entry's files
        missing = sorted(set(folder_files(bundle)) - set(e["files"]))
        if args.update:
            e.update(want, streamed_checked=today)
            print(f"UPDATED {e['model_id']}: streamed_bytes {c['streamed']:,} of bytes {e['bytes']:,}")
            continue
        bad = [k for k, v in want.items() if e.get(k) != v]
        if missing:
            print(f"DIFF {e['model_id']}: files not in the entry: {missing}")
            rc = 1
        for k in bad:
            print(f"DIFF {e['model_id']}: {k} registry {e.get(k)!r} vs bundle {want[k]!r}")
            rc = 1
        if not bad and not missing:
            print(f"OK   {e['model_id']}: streamed_bytes {c['streamed']:,} of bytes {e['bytes']:,} "
                  f"({c['streamed'] / e['bytes'] * 100:.1f} %), basis as registered")
    if not seen:
        print(f"no {ARM} entry in {args.registry}")
        rc = 1
    if args.update:
        with open(args.registry, "w") as fh:
            json.dump(reg, fh, indent=1, ensure_ascii=False)
            fh.write("\n")
        print(f"wrote {os.path.relpath(args.registry, ROOT)}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
