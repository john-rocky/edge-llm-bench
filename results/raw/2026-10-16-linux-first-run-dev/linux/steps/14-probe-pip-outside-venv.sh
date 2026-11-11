# Probe (not a README step), as dev: pip outside a venv on Ubuntu 24.04 (PEP 668), the form that
# docs/OPERATIONS.md (DDP runbook prerequisites) and android/README.md (Prerequisites) print.
python3 -m pip install huggingface_hub; printf '## python3 -m pip install huggingface_hub rc=%s\n' "$?"
pip install huggingface_hub; printf '## pip install huggingface_hub rc=%s\n' "$?"
exit 0
