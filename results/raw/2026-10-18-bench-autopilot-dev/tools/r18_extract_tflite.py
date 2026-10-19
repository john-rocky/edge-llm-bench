#!/usr/bin/env python3
"""r18_extract_tflite.py BUNDLE.litertlm OUT.tflite - copy a bundle's one TFLiteModel section to OUT (never
overwritten), with the header read the way repack_metadata.py reads it (litert_lm_builder 0.18.0). Prints the
section's offsets, bytes and sha256. Run: uv run --no-project --with litert-lm==0.18.0 python -I <this> ...
"""
import hashlib
import os
import sys

from litert_lm_builder import litertlm_core
from litert_lm_builder import litertlm_header_schema_py_generated as schema


def main(src, out):
    if os.path.exists(out):
        print(f"refusing to overwrite {out}", file=sys.stderr)
        return 2
    with open(src, "rb") as fh:
        prefix = fh.read(32)
        if prefix[:8] != litertlm_core.HEADER_MAGIC_BYTES:
            raise SystemExit(f"not a .litertlm bundle: {src}")
        off = litertlm_core.HEADER_END_LOCATION_BYTE_OFFSET
        header_end = int.from_bytes(prefix[off:off + 8], "little")
        fh.seek(0)
        head = fh.read(header_end)
    meta = schema.LiteRTLMMetaData.GetRootAs(head[litertlm_core.HEADER_BEGIN_BYTE_OFFSET:], 0)
    found = []
    for i in range(meta.SectionMetadata().ObjectsLength()):
        sec = meta.SectionMetadata().Objects(i)
        kind = litertlm_core.any_section_data_type_to_string(sec.DataType())
        if kind == "TFLiteModel":
            found.append((i, sec.BeginOffset(), sec.EndOffset()))
    if len(found) != 1:
        raise SystemExit(f"expected one TFLiteModel section, found {len(found)}")
    i, begin, end = found[0]
    h = hashlib.sha256()
    with open(src, "rb") as fh, open(out, "xb") as dst:
        fh.seek(begin)
        left = end - begin
        while left:
            chunk = fh.read(min(4 << 20, left))
            if not chunk:
                raise SystemExit("short read")
            h.update(chunk)
            dst.write(chunk)
            left -= len(chunk)
    print(f"section {i} TFLiteModel begin {begin} end {end} bytes {end - begin} sha256 {h.hexdigest()} -> {out}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
