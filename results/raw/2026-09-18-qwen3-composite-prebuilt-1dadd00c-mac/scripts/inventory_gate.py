#!/usr/bin/env python3
"""Hard gate before any benchmark leg (2026-09-18, v2): did --use_sdpa_composite_for_prefill=True take effect, and did the
weights / the other composites move? Compares two tflite_ops.py inventories (A = the export under test, B = the reference):
  * prefill_1024: A and B must carry the odml.sdpa_transposed counts given as the 4th/5th args (N = layers for a prefill-flag
    export, 0 for an 11-flag file); decode: both N;
  * these top-level rows must be identical in both signatures: FULLY_CONNECTED, every other STABLEHLO_COMPOSITE except
    odml.sdpa_transposed / odml.runtime_bmm (which the prefill composite absorbs), EMBEDDING_LOOKUP, and the FC weight-inventory
    lines (dtype / block size / shapes) that follow the op table;
  * every other row difference is printed as INFO (attention-op movement into the composite, exporter drift) for the record.
Usage: inventory_gate.py <ops_A.txt> <ops_B.txt> <layers> <expected_prefill_sdpa_in_A> <expected_prefill_sdpa_in_B>   -> exit 0 PASS, exit 6 FAIL."""
import re, sys
KEEP = re.compile(r"^\d+\s+(FULLY_CONNECTED|EMBEDDING_LOOKUP|STABLEHLO_COMPOSITE:odml\.(?!sdpa_transposed|runtime_bmm)\S+)$")
def parse(path):
    sg = {}; cur = None
    for line in open(path, errors="replace"):
        m = re.match(r"== subgraph (\d+): (\S+)\s+\((\d+) ops\)", line)
        if m:
            cur = m.group(2); sg[cur] = {"ops": int(m.group(3)), "rows": [], "fc": []}; continue
        if cur in ("prefill_1024", "decode"):
            t = line.rstrip("\n").strip()
            if re.match(r"^\d+\s+\S", t): sg[cur]["rows"].append(t)
            elif t and not t.startswith(("in ", "out ")): sg[cur]["fc"].append(t)
    return sg
def comp(rows, name):
    for r in rows:
        m = re.match(r"^(\d+)\s+STABLEHLO_COMPOSITE:%s$" % re.escape(name), r)
        if m: return int(m.group(1))
    return 0
a, b, n, want_a_prefill, want_b_prefill = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
A, B = parse(a), parse(b)
fail, info = [], []
for sig in ("prefill_1024", "decode"):
    if sig not in A or sig not in B: fail.append(f"signature {sig} missing (A: {sig in A}, B: {sig in B})"); continue
    sa, sb = comp(A[sig]["rows"], "odml.sdpa_transposed"), comp(B[sig]["rows"], "odml.sdpa_transposed")
    want_a, want_b = (want_a_prefill, want_b_prefill) if sig == "prefill_1024" else (n, n)
    if (sa, sb) != (want_a, want_b): fail.append(f"{sig}: odml.sdpa_transposed A={sa} B={sb}, expected {want_a}/{want_b}")
    ka = sorted(r for r in A[sig]["rows"] if KEEP.match(r)); kb = sorted(r for r in B[sig]["rows"] if KEEP.match(r))
    if ka != kb: fail.append(f"{sig}: weight/composite rows differ — only in A: {sorted(set(ka)-set(kb))}; only in B: {sorted(set(kb)-set(ka))}")
    if A[sig]["fc"] != B[sig]["fc"]: fail.append(f"{sig}: FC weight inventory differs — A: {A[sig]['fc'][:6]} … B: {B[sig]['fc'][:6]} …")
    oa = sorted(set(A[sig]["rows"]) - set(B[sig]["rows"]) - set(ka)); ob = sorted(set(B[sig]["rows"]) - set(A[sig]["rows"]) - set(kb))
    info.append(f"{sig}: ops A={A[sig]['ops']} B={B[sig]['ops']}; sdpa_transposed {sa} vs {sb}; runtime_bmm {comp(A[sig]['rows'],'odml.runtime_bmm')} vs {comp(B[sig]['rows'],'odml.runtime_bmm')}; other rows only in A: {oa}; only in B: {ob}")
for i in info: print("INFO " + i)
if fail:
    print("INVENTORY GATE FAIL:"); [print("  - " + f) for f in fail]; sys.exit(6)
print("INVENTORY GATE PASS")
