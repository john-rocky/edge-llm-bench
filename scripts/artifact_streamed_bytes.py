#!/usr/bin/env python3
"""Bytes a decode step streams from an artifact — the number behind the
`streamed_bytes` fields of models/artifact-bytes.json (the `bw util` column).

  python3 scripts/artifact_streamed_bytes.py gguf        <file.gguf | URL>   [--dump]
  python3 scripts/artifact_streamed_bytes.py safetensors <dir or file...>    [--dump]
  python3 scripts/artifact_streamed_bytes.py litertlm    <file.litertlm>     [--dump]

Rule (docs/dashboard-cells-v1.md, "bandwidth-utilization column"): a dense
decode step reads every weight once, so streamed bytes = the artifact's tensor
bytes, minus tables that are GATHERED per token rather than read whole:
  - Gemma 4's per-layer-embedding table (`per_layer_token_embd.weight` in GGUF,
    `embed_tokens_per_layer.*` in the MLX safetensors, the `per_layer_embedder`
    TFLite section of a .litertlm);
  - a .litertlm's separate `embedder` lookup-table section (the tied output
    projection inside the decode graph is streamed and stays counted);
  - a .litertlm's audio / vision / eoa / eoi / mtp_drafter sections, which the
    text decode signature does not run (the MTP drafter only under speculative
    decoding, which the rows here do not enable).
Tied embeddings (Qwen3, Gemma 4) are streamed as the LM head and stay in.
What is left is an estimate of bytes per token, not a bus counter; a
container's own headers and a GGUF's metadata are not tensor bytes and are
not counted.

GGUF and safetensors need only the standard library (a GGUF can be read from
a URL: the first 64 MB hold the header). A .litertlm needs `flatbuffers`, the
LiteRT-LM header schema (python `litert_lm_builder`, from the LiteRT-LM repo's
builder package) and `ai_edge_litert`'s generated TFLite schema — run it from
an environment that has them (the litertlm-convert venv on the bench host).
"""
import fnmatch
import glob
import json
import os
import struct
import sys
import urllib.request

# ggml type -> (name, block size, type size in bytes): tensor bytes = n / block * size
GGML_TYPE = {0: ("F32", 1, 4), 1: ("F16", 1, 2), 2: ("Q4_0", 32, 18), 3: ("Q4_1", 32, 20),
             6: ("Q5_0", 32, 22), 7: ("Q5_1", 32, 24), 8: ("Q8_0", 32, 34), 9: ("Q8_1", 32, 36),
             10: ("Q2_K", 256, 84), 11: ("Q3_K", 256, 110), 12: ("Q4_K", 256, 144),
             13: ("Q5_K", 256, 176), 14: ("Q6_K", 256, 210), 15: ("Q8_K", 256, 292),
             16: ("IQ2_XXS", 256, 66), 17: ("IQ2_XS", 256, 74), 18: ("IQ3_XXS", 256, 98),
             19: ("IQ1_S", 256, 50), 20: ("IQ4_NL", 32, 18), 21: ("IQ3_S", 256, 110),
             22: ("IQ2_S", 256, 82), 23: ("IQ4_XS", 256, 136), 24: ("I8", 1, 1), 25: ("I16", 1, 2),
             26: ("I32", 1, 4), 27: ("I64", 1, 8), 28: ("F64", 1, 8), 29: ("IQ1_M", 256, 56),
             30: ("BF16", 1, 2), 34: ("TQ1_0", 256, 54), 35: ("TQ2_0", 256, 66)}
GATHERED_GGUF = ["per_layer_token_embd.weight"]
GATHERED_SAFETENSORS = ["*embed_tokens_per_layer.*"]
# .litertlm: only the section carrying the `decode` signature streams; inside
# it, an input-embedding lookup table that is separate from the output head
# (the mixed_int4 Qwen3 bundles keep an int8 lookup table beside an int4 head;
# Gemma 4's lookup table is its own `embedder` section) is gathered.
LITERTLM_STREAMED_SIGS = {"decode"}
GATHERED_LITERTLM_TENSORS = ["*embed_tokens_weight*", "*lookup_embedding_table*"]


def gguf_tensors(path):
    """-> [(name, type_name, dims, bytes)] from a GGUF header (file or URL)."""
    if path.startswith(("http://", "https://")):
        req = urllib.request.Request(path, headers={"Range": "bytes=0-67108863",
                                                    "User-Agent": "edge-llm-bench"})
        blob = urllib.request.urlopen(req, timeout=120).read()
    else:
        with open(path, "rb") as fh:
            blob = fh.read(64 << 20)
    pos = 0

    def rd(fmt):
        nonlocal pos
        sz = struct.calcsize(fmt)
        v = struct.unpack("<" + fmt, blob[pos:pos + sz])
        pos += sz
        return v

    def rstr():
        nonlocal pos
        n, = rd("Q")
        s = blob[pos:pos + n].decode("utf-8", "replace")
        pos += n
        return s

    def rval(t):
        if t == 0 or t == 7:
            return rd("B")[0]
        if t == 1:
            return rd("b")[0]
        if t == 2:
            return rd("H")[0]
        if t == 3:
            return rd("h")[0]
        if t == 4:
            return rd("I")[0]
        if t == 5:
            return rd("i")[0]
        if t == 6:
            return rd("f")[0]
        if t == 8:
            return rstr()
        if t == 9:
            et, = rd("I")
            n, = rd("Q")
            return [rval(et) for _ in range(n)]
        if t == 10:
            return rd("Q")[0]
        if t == 11:
            return rd("q")[0]
        if t == 12:
            return rd("d")[0]
        raise ValueError(f"gguf value type {t}")

    if blob[:4] != b"GGUF":
        raise ValueError("not a GGUF file")
    pos = 4
    rd("I")
    nt, nkv = rd("QQ")
    for _ in range(nkv):
        rstr()
        t, = rd("I")
        rval(t)
    out = []
    for _ in range(nt):
        name = rstr()
        nd, = rd("I")
        dims = rd("Q" * nd)
        typ, = rd("I")
        rd("Q")
        ne = 1
        for d in dims:
            ne *= d
        tn, bs, ts = GGML_TYPE[typ]
        out.append((name, tn, list(dims), ne // bs * ts))
    return out


def safetensors_tensors(paths):
    """-> [(name, dtype, shape, bytes)] over one or more .safetensors files."""
    out = []
    for p in paths:
        with open(p, "rb") as fh:
            n, = struct.unpack("<Q", fh.read(8))
            hdr = json.loads(fh.read(n))
        for k, v in hdr.items():
            if k == "__metadata__":
                continue
            a, b = v["data_offsets"]
            out.append((k, v["dtype"], v["shape"], b - a))
    return out


def litertlm_sections(path):
    """-> [(index, type, size, signature names, tensor bytes)] of a .litertlm.
    Needs flatbuffers + the LiteRT-LM header schema + ai_edge_litert."""
    sys.path.insert(0, os.path.expanduser("~/code/litertlm-convert/manifest"))
    from litert_lm_builder import litertlm_core  # noqa: E402
    from litert_lm_builder import litertlm_header_schema_py_generated as schema  # noqa: E402
    from ai_edge_litert import schema_py_generated as tfl  # noqa: E402
    with open(path, "rb") as fh:
        head = fh.read(1 << 20)
    o = litertlm_core.HEADER_END_LOCATION_BYTE_OFFSET
    hdr_end = int.from_bytes(head[o:o + 8], "little")
    meta = schema.LiteRTLMMetaData.GetRootAs(
        bytearray(head[litertlm_core.HEADER_BEGIN_BYTE_OFFSET:hdr_end]), 0)
    out = []
    with open(path, "rb") as fh:
        for i in range(meta.SectionMetadata().ObjectsLength()):
            so = meta.SectionMetadata().Objects(i)
            dtype = litertlm_core.any_section_data_type_to_string(so.DataType())
            size = so.EndOffset() - so.BeginOffset()
            if "TFLite" not in dtype:
                out.append((i, dtype, size, [], 0, []))
                continue
            fh.seek(so.BeginOffset())
            m = tfl.Model.GetRootAs(bytearray(fh.read(size)), 0)
            sigs = [m.SignatureDefs(k).SignatureKey().decode() for k in range(m.SignatureDefsLength())]
            seen, total, gathered = set(), 0, []
            for g in range(m.SubgraphsLength()):
                sg = m.Subgraphs(g)
                for t in range(sg.TensorsLength()):
                    tn = sg.Tensors(t)
                    b = tn.Buffer()
                    if b in seen or b >= m.BuffersLength():
                        continue
                    bb = m.Buffers(b)
                    n = bb.DataLength()
                    if n == 0:
                        try:
                            n = bb.Size()
                        except Exception:  # noqa: BLE001 — older schema without Size()
                            n = 0
                    if n:
                        seen.add(b)
                        total += n
                        name = tn.Name().decode() if tn.Name() else ""
                        if any(fnmatch.fnmatchcase(name, p) for p in GATHERED_LITERTLM_TENSORS):
                            gathered.append({"name": name[-80:], "bytes": n})
            out.append((i, dtype, size, sigs, total, gathered))
    return out


def report(kind, total, gathered, detail):
    print(json.dumps({"kind": kind, "tensor_bytes": total, "gathered_bytes": gathered,
                      "streamed_bytes": total - gathered, "detail": detail}, indent=1))


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    kind, args = sys.argv[1], [a for a in sys.argv[2:] if a != "--dump"]
    dump = "--dump" in sys.argv
    if kind == "gguf":
        tensors = gguf_tensors(args[0])
        total = sum(t[3] for t in tensors)
        gathered = [t for t in tensors if any(fnmatch.fnmatchcase(t[0], p) for p in GATHERED_GGUF)]
        if dump:
            for t in sorted(tensors, key=lambda x: -x[3])[:20]:
                print(f"  {t[3]:>13,} {t[1]:<6} {t[2]} {t[0]}")
        report("gguf", total, sum(t[3] for t in gathered),
               {"gathered": [{"name": t[0], "type": t[1], "bytes": t[3]} for t in gathered],
                "tensors": len(tensors)})
    elif kind == "safetensors":
        paths = []
        for a in args:
            paths += sorted(glob.glob(os.path.join(a, "model*.safetensors"))) if os.path.isdir(a) else [a]
        tensors = safetensors_tensors(paths)
        total = sum(t[3] for t in tensors)
        gathered = [t for t in tensors if any(fnmatch.fnmatchcase(t[0], p) for p in GATHERED_SAFETENSORS)]
        if dump:
            for t in sorted(tensors, key=lambda x: -x[3])[:20]:
                print(f"  {t[3]:>13,} {t[1]:<5} {t[2]} {t[0]}")
        report("safetensors", total, sum(t[3] for t in gathered),
               {"gathered": [{"name": t[0], "dtype": t[1], "bytes": t[3]} for t in gathered],
                "files": [os.path.basename(p) for p in paths], "tensors": len(tensors)})
    elif kind == "litertlm":
        secs = litertlm_sections(args[0])
        total = sum(s[4] for s in secs)
        streamed = [s for s in secs if LITERTLM_STREAMED_SIGS & set(s[3])]
        if not streamed:
            raise SystemExit("no TFLite section carries a 'decode' signature")
        if dump:
            for s in secs:
                print(f"  section {s[0]}: {s[1]:<18} {s[2]:>13,} B tensors={s[4]:,} sigs={s[3]}")
                for gth in s[5]:
                    print(f"      gathered {gth['bytes']:>13,} …{gth['name']}")
        lookup = sum(gth["bytes"] for s in streamed for gth in s[5])
        st = sum(s[4] for s in streamed) - lookup
        report("litertlm", total, total - st,
               {"streamed_sections": [{"index": s[0], "signatures": s[3], "tensor_bytes": s[4],
                                       "gathered_lookup_tables": s[5]} for s in streamed],
                "skipped_sections": [{"index": s[0], "type": s[1], "signatures": s[3], "tensor_bytes": s[4]}
                                     for s in secs if s not in streamed and s[4]]})
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
