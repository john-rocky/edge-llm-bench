#!/usr/bin/env python3
"""Compare upstream engine releases against this repo's pins and print the drift
table plus the exact next command (`./bench release-watch`).

Uses `gh` for the GitHub API (already a repo prerequisite). Read-only: bumping a
pin stays a human decision — the flow is documented in docs/OPERATIONS.md.
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def gh_json(args):
    try:
        out = subprocess.check_output(["gh", *args], text=True, stderr=subprocess.DEVNULL)
        return json.loads(out)
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
        return None


def latest_release(repo):
    d = gh_json(["api", f"repos/{repo}/releases/latest"])
    return d.get("tag_name") if d else None


# the llama.cpp release assets the bench runs (iPhone + Mac, Android) and the Mac CLI tar
LLAMA_ASSETS = ("llama-{tag}-xcframework.zip", "llama-{tag}-bin-android-arm64.tar.gz",
                "llama-{tag}-bin-macos-arm64.tar.gz")


def latest_with_assets(repo, names):
    """The newest release (published_at) that carries every asset in `names` (with {tag} filled in).
    llama.cpp publishes two kinds: the b-builds, prereleases with the binaries, and versioned
    releases (v0.7.0, 2026-10-15) with release notes and a nightly-tag.txt naming the b-build they
    are (b11669); releases/latest returns the versioned one, which has nothing to install."""
    d = gh_json(["api", f"repos/{repo}/releases?per_page=40"])
    if not isinstance(d, list):
        return None
    full = [r for r in d if {n.format(tag=r.get("tag_name")) for n in names}
            <= {a.get("name") for a in r.get("assets") or []}]
    return max(full, key=lambda r: r.get("published_at") or "")["tag_name"] if full else None


def main():
    lock = json.load(open(os.path.join(ROOT, "environment.lock.json")))
    arms = lock["arms"]
    rows = []

    litert = arms.get("litert-lm", {})
    litert_pinned = sorted({c.get("tag") for c in litert.get("captures", {}).values()
                            if c.get("tag")})[-1] if litert.get("captures") else litert.get("default_tag")
    rows.append(("litert-lm", "google-ai-edge/LiteRT-LM",
                 latest_release("google-ai-edge/LiteRT-LM"), litert_pinned,
                 "./bench regress matrices/release-regression-litert.cells "
                 "--engine litert-lm  (bump LITERTLM_TAG in bootstrap.sh first)"))

    rows.append(("llama.cpp", "ggml-org/llama.cpp",
                 latest_with_assets("ggml-org/llama.cpp", LLAMA_ASSETS),
                 arms.get("llama.cpp", {}).get("tag"),
                 "docs/OPERATIONS.md 'An engine shipped a release', llama.cpp: the lock, "
                 "android/engine-pins.json, the Vendored xcframework + .tag, "
                 "android/scripts/fetch_llama_android.sh"))

    coreai = arms.get("coreai-models", {})
    rows.append(("core-ai", "apple/coreai-models",
                 latest_release("apple/coreai-models"),
                 coreai.get("tag"),
                 "best-effort arm: PLE models still need the unpublished "
                 "COREAI_STATIC_INPUTS patch"))

    mlx = arms.get("mlx-swift-lm", {})
    head = gh_json(["api", "repos/ml-explore/mlx-swift-examples/commits/main",
                    "--jq", "{sha: .sha}"])
    rows.append(("mlx-swift-lm", "ml-explore/mlx-swift-examples",
                 (head or {}).get("sha", "")[:8] or None,
                 (mlx.get("revision") or "")[:8],
                 "pinned BY REVISION in project.yml (floating-branch incident) — "
                 "bump deliberately, never track main"))

    print(f"{'arm':14} {'pinned':12} {'latest':12}  action")
    print("-" * 100)
    drift = False
    for arm, repo, latest, pinned, action in rows:
        mark = ""
        if latest is None:
            latest = "(unknown)"  # API miss is not drift
        elif pinned and str(latest) != str(pinned):
            mark = "  <-- DRIFT"
            drift = True
        print(f"{arm:14} {str(pinned):12} {str(latest):12}{mark}")
        if mark:
            print(f"{'':14} next: {action}")
    if not drift:
        print("\nall pins current.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
