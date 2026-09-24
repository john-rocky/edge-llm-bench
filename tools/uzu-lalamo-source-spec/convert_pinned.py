#!/usr/bin/env python3
"""Replay lalamo exports with the observed HF revisions fixed.

The original lalamo CLI fetches main and exposes no revision argument. This
launcher adds revision= only to its two HF lookup functions; it does not
change import, tensors, dtype or conversion. Smoke only, not a measurement.
"""
import functools
import sys

import huggingface_hub as hf

REVISIONS = {
    "Qwen/Qwen3-0.6B": "c1899de289a04d12100db370d81485cdf75e47ca",
    "mlx-community/Qwen3-0.6B-4bit": "73e3e38d981303bc594367cd910ea6eb48349da8",
    "Qwen/Qwen3-1.7B": "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e",
    "mlx-community/Qwen3-1.7B-4bit": "3b1b1768f8f8cf8351c712464f906e86c2b8269e",
    "Qwen/Qwen3-4B": "1cfa9a7208912126459214e8b04321603b3df60c",
    "mlx-community/Qwen3-4B-4bit": "4dcb3d101c2a062e5c1d4bb173588c54ea6c4d25",
    "google/gemma-4-E2B-it": "3e22461f65e89153144f8adb70e3b8c2cc9845a7",
}


def pin(function):
    @functools.wraps(function)
    def fetch(repo_id, *args, **kwargs):
        revision = REVISIONS[repo_id]  # refuse unexpected sources
        if kwargs.get("revision") not in (None, revision):
            raise ValueError(f"unexpected revision for {repo_id}")
        return function(repo_id, *args, **dict(kwargs, revision=revision))
    return fetch


def main():
    hf.hf_hub_download = pin(hf.hf_hub_download)
    hf.list_repo_files = pin(hf.list_repo_files)
    if sys.argv[1:] == ["--check-sources"]:
        import hashlib
        import json
        from pathlib import Path
        results = []
        for repo_id, revision in REVISIONS.items():
            path = Path(hf.hf_hub_download(repo_id, "config.json"))
            results.append({"repo": repo_id, "revision": revision,
                            "file": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                            "repoFiles": hf.list_repo_files(repo_id)})
        print(json.dumps({"capturePurpose": "smoke reproduction check; not a measurement", "sources": results}, indent=2))
        return
    from lalamo.main import app
    app()


if __name__ == "__main__":
    main()
