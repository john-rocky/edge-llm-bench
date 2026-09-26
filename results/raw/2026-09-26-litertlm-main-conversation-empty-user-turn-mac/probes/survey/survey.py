#!/usr/bin/env python3
"""For every .litertlm file under the litert-community org, fetch its first 3 MB and classify the
stored chat template: 'parts' (handles a content sequence), 'string-guard' (sets content='' when
content is not a string), 'jinja-other' (a template without either idiom), 'no-jinja'."""
import json, re, subprocess, sys, urllib.request
OUT = sys.argv[1]
def get(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "edge-llm-bench-survey"})))
repos = get("https://huggingface.co/api/models?author=litert-community&limit=1000")
rows = []
for r in sorted(repos, key=lambda x: x["id"]):
    try:
        info = get(f"https://huggingface.co/api/models/{r['id']}?blobs=true")
    except Exception as e:
        rows.append({"repo": r["id"], "error": str(e)}); continue
    for s in info.get("siblings", []):
        f = s["rfilename"]
        if not f.endswith(".litertlm"):
            continue
        url = f"https://huggingface.co/{r['id']}/resolve/main/{f}"
        try:
            data = subprocess.run(["curl", "-sL", "-r", "0-3000000", url], capture_output=True, timeout=120).stdout
        except Exception as e:
            rows.append({"repo": r["id"], "file": f, "error": str(e)}); continue
        text = data.decode("latin-1")
        has_jinja = "{%-" in text or "{{-" in text or "{% " in text
        parts = bool(re.search(r"format_content|content is sequence|content is iterable|for item in content|for content in message|content\['type'\]|item\['type'\]|content\.type ==", text))
        guard = bool(re.search(r"if message\.content is string %\}\s*\{%- set content = message\.content %\}\s*\{%- else %\}\s*\{%- set content = '' %\}", text))
        rows.append({"repo": r["id"], "file": f, "size": s.get("size"), "sha256": (s.get("lfs") or {}).get("sha256", "")[:12],
                     "jinja": has_jinja, "parts": parts, "string_guard": guard,
                     "cls": "parts" if parts else ("string-guard" if guard else ("jinja-other" if has_jinja else "no-jinja"))})
        print(rows[-1], flush=True)
json.dump(rows, open(OUT, "w"), indent=1)
print("done", len(rows))
