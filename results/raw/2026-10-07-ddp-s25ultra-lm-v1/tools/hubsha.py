import json, os, sys, urllib.request
FILES = [("Qwen3-0.6B", "qwen3_0_6b_mixed_int4.litertlm"), ("Qwen3-1.7B", "Qwen3_1.7B.litertlm"),
         ("Qwen3-1.7B", "Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm"), ("Qwen3-4B", "qwen3_4b_mixed_int4.litertlm"),
         ("gemma-4-E2B-it-litert-lm", "gemma-4-E2B-it.litertlm"), ("gemma-4-E4B-it-litert-lm", "gemma-4-E4B-it.litertlm")]
hub = os.path.expanduser("~/.cache/huggingface/hub")
bad = 0
for repo, f in FILES:
    with urllib.request.urlopen(f"https://huggingface.co/api/models/litert-community/{repo}/tree/main", timeout=60) as r:
        tree = json.load(r)
    with urllib.request.urlopen(f"https://huggingface.co/api/models/litert-community/{repo}", timeout=60) as r:
        head = json.load(r)["sha"]
    e = next(x for x in tree if x["path"] == f)
    sha, size = e["lfs"]["oid"], e["lfs"]["size"]
    snaps = os.path.join(hub, f"models--litert-community--{repo}", "snapshots")
    local = None
    for s in os.listdir(snaps):
        p = os.path.join(snaps, s, f)
        if os.path.exists(p):
            local = (s, os.path.basename(os.path.realpath(p)), os.path.getsize(p), os.path.realpath(p))
    ok = local and local[1] == sha and local[2] == size
    bad += 0 if ok else 1
    print(f"{'SAME' if ok else 'DIFF'} litert-community/{repo} {f} hub_main={head[:8]} hub_lfs_sha256={sha} size={size} local_snapshot={local[0][:8] if local else None} local_blob={local[1] if local else None}")
sys.exit(1 if bad else 0)
