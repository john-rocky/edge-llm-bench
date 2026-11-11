# r2, after the session, as dev, in step 1's venv: the model's HF cache entry as huggingface_hub 2.2.0 wrote it (the
# blob's name) and the sha256 of its bytes. The Hub's paths-info for the file: lfs.oid 2a72330b…, xetHash 4194181f….
. ~/elb-venv/bin/activate
f=$(python3 -c 'from huggingface_hub import hf_hub_download; print(hf_hub_download("litert-community/Qwen3-1.7B", "Qwen3-1.7B_dynamic_wi4b32_afp32.litertlm", local_files_only=True))' 2>/dev/null)
[ -n "$f" ] || { echo '## the model is not in the HF cache'; exit 1; }
b=$(readlink -f "$f")
printf '## huggingface_hub %s\n## snapshot path %s\n## -> blob %s\n' "$(pip show huggingface_hub 2>/dev/null | sed -n 's/^Version: //p')" "$f" "$b"
printf '## blob name     %s\n' "$(basename "$b")"
printf '## sha256(bytes) %s\n' "$(sha256sum "$b" | cut -d' ' -f1)"
printf '## bytes %s\n' "$(stat -c %s "$b")"
