# The model's Hugging Face cache entry as the driver copied it from the host (refs/main, the snapshot link, the blob:
# no download), as dev, in step 1's venv: what huggingface_hub finds offline (the path, the blob, the sha256 of the
# bytes) and, with one metadata request to the Hub (no download), whether a billed run's hf_hub_download would
# download (huggingface_hub's dry_run). Exit 3 when it would: the billed run is not started.
. ~/elb-venv/bin/activate
python3 - <<'EOF'
import hashlib, inspect, os, sys
import huggingface_hub
from huggingface_hub import hf_hub_download
R, F = "litert-community/Qwen3-1.7B", "Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm"
home = os.path.expanduser("~")
print("## huggingface_hub", huggingface_hub.__version__)
p = hf_hub_download(R, F, local_files_only=True)
b = os.path.realpath(p)
h = hashlib.sha256()
with open(b, "rb") as fh:
    for chunk in iter(lambda: fh.read(1 << 22), b""):
        h.update(chunk)
print("## offline:", p.replace(home, "~"), "->", b.replace(home, "~"))
print("## bytes", os.path.getsize(b), "sha256", h.hexdigest())
if "dry_run" not in inspect.signature(hf_hub_download).parameters:
    print("## dry_run: not in this huggingface_hub"); sys.exit(0)
info = hf_hub_download(R, F, dry_run=True)
print("## dry_run (one metadata request):", {k: getattr(info, k, None) for k in ("will_download", "commit_hash", "file_size", "is_cached")})
sys.exit(3 if getattr(info, "will_download", True) else 0)
EOF
