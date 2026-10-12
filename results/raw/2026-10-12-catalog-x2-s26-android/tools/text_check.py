#!/usr/bin/env python3
"""Per-record text table of a long-context round-mode campaign (catalog X2, 2026-10-12).

  python3 tools/text_check.py <campaign dir> [--records app-path-android] [--out <campaign>/text_check.md]

One row per LiteRT-LM record (iteration) under <campaign>/<records>/: the columns of
results/raw/2026-09-24-dashboard-longctx-v1-s26-android-gpu-retake/text_check.md, read from the record
(conditions.textCheck = run_cell's lexical screen, protocolFlags, invalidDecodeCount) and its decoded text
file. Sorted by allocation, then round. A lexical screen is not a semantic review: read the texts.
"""
import argparse, glob, hashlib, json, os

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("campaign")
ap.add_argument("--records", default="app-path-android")
ap.add_argument("--out")
a = ap.parse_args()
d = os.path.join(a.campaign, a.records)
rows, texts = [], {}
for f in sorted(glob.glob(os.path.join(d, "*.json"))):
    r = json.load(open(f))
    c, m = r.get("conditions", {}), r.get("metrics", {})
    if not str(r.get("runtime", "")).startswith("litert-lm"):
        continue
    name = r.get("provenance", {}).get("decodedText")
    text = open(os.path.join(d, name), errors="replace").read() if name and os.path.exists(os.path.join(d, name)) else ""
    texts.setdefault(hashlib.sha256(text.encode()).hexdigest(), []).append(r["id"])
    tc = c.get("textCheck") or {}
    ctx = c.get("contextTokens")
    rows.append((r["model"]["id"], ctx if isinstance(ctx, int) else 0, c.get("roundIndex") or 0,
                 c.get("launchIndex") or 0, c.get("iterationIndex") or 0, [
        c.get("roundIndex"), c.get("launchIndex"), r["runtime"], r["model"]["id"].split("/")[-1], c.get("contextTokens"),
        c.get("regime"), bool(m.get("firstEver")), m.get("promptTokenCount"), m.get("generatedTokenCount"),
        tc.get("alphanumericCount"), tc.get("status"), c.get("invalidDecodeCount"),
        ",".join(c.get("protocolFlags", [])), text[:200].replace("\n", "\\n").replace("|", "\\|")]))
rows.sort(key=lambda x: x[:5])
out = ["# Per-record text screen", "",
       "A lexical screen is not a semantic review (run_cell's textCheck). Flagged records stay visible and do not "
       "supply a rate. Every stored record of the campaign is shown.", "",
       "| round | launch | arm | model | allocation | regime | first-ever | prompt tok | output tok | alphanumeric "
       "| screen | Invalid decode | flags | first 200 decoded characters |",
       "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
out += ["| " + " | ".join("" if v is None else str(v) for v in row[5]) + " |" for row in rows]
out += ["", f"{len(texts)} distinct decoded texts cover {len(rows)} LiteRT records (by SHA-256); "
        f"short answers (< 254 tokens): {sum(1 for r in rows if (r[5][8] or 0) < 254)}; "
        f"Invalid decode lines: {sum(r[5][11] or 0 for r in rows)}."]
text = "\n".join(out) + "\n"
open(a.out or os.path.join(a.campaign, "text_check.md"), "w").write(text)
print(text)
