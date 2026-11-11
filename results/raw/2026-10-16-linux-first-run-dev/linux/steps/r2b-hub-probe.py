"""r2b: what this interpreter's huggingface_hub gives for the round's model: the HF cache blob the snapshot links to,
model_info's sibling for the file (size and LFS sha256, read the way android/ddp/run_ddp.py model_file reads them on a
billed run) and paths-info (LFS sha256, xet hash). Run on the Mac (huggingface_hub 1.8.0) and in the container (2.2.0);
the home directory printed as ~. Read only: two GETs to the Hub, no token, no download."""
import os
import sys

import huggingface_hub
from huggingface_hub import HfApi, hf_hub_download

REPO, FILE = "litert-community/Qwen3-1.7B", "Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm"
home = os.path.expanduser("~")
print(f"python {sys.version.split()[0]}, huggingface_hub {huggingface_hub.__version__}")
try:
    local = hf_hub_download(REPO, FILE, local_files_only=True)
    blob = os.path.realpath(local)
    print(f"cache snapshot {local.replace(home, '~')}")
    print(f"cache blob     {blob.replace(home, '~')} ({os.path.getsize(blob)} bytes)")
except Exception as exc:  # noqa: BLE001 — no cache entry on this host
    print(f"cache: no entry ({type(exc).__name__})")
api = HfApi()
info = api.model_info(REPO, files_metadata=True)
entry = next((f for f in info.siblings if f.rfilename == FILE), None)
lfs = getattr(entry.lfs, "sha256", None) if entry and entry.lfs else None
print(f"model_info(files_metadata=True) at {info.sha}: sibling size {entry.size if entry else None}, "
      f"lfs {type(entry.lfs).__name__ if entry else None}, lfs.sha256 {lfs}")
for f in api.get_paths_info(REPO, [FILE]):
    print(f"get_paths_info: {type(f).__name__} size {getattr(f, 'size', None)}, "
          f"lfs.sha256 {getattr(getattr(f, 'lfs', None), 'sha256', None)}, "
          f"xet_hash {getattr(f, 'xet_hash', '(no attribute)')}")
