"""Shared display tables for the result renderers (RESULTS.md and
LEADERBOARD.md must not drift on naming).

LOGICAL_MODELS: different runtimes pull weights from different HF orgs, so the
same logical model ends up under several string IDs; entries map a
case-insensitive substring of model.id to a canonical display name. Order
matters — first hit wins, so more specific patterns come first (see the OptiQ
and CQ4 comments: builds that must not pool stay distinct).
"""

DEVICE_DISPLAY = {
    "m4max": "Mac M4 Max",
    "m3air": "MacBook Air M3",
    "m4air": "MacBook Air M4",
    "m1pro": "MacBook Pro M1",
    "m2pro": "MacBook Pro M2",
    "m3pro": "MacBook Pro M3",
    "m4pro": "MacBook Pro M4",
    "m2max": "MacBook Pro M2 Max",
    "m3max": "MacBook Pro M3 Max",
    "iphone15pro": "iPhone 15 Pro",
    "iphone16pro": "iPhone 16 Pro",
    "iphone17pro": "iPhone 17 Pro",
    "iphone17promax": "iPhone 17 Pro Max",
    "iphone17air": "iPhone 17 Air",
    "ipadprom4": "iPad Pro M4",
    # modelIdentifier keys (campaign-shaped records carry the identifier, not a label)
    "Mac16,9": "Mac Studio (M4 Max)",
    "iPhone18,1": "iPhone 17 Pro",
    "SM-S942Q": "Galaxy S26",
}


LOGICAL_MODELS: list[tuple[str, str]] = [
    # Gemma 4
    ("gemma-4-26b-a4b", "Gemma 4 26B-A4B (MoE)"),
    ("gemma-4-31b",     "Gemma 4 31B"),
    # OptiQ before the generic e2b pattern: MLX has two 4-bit builds of E2B in the table
    # (quality-best QAT OptiQ vs speed-best PTQ) and they must not pool in the pivots.
    ("gemma-4-e2b-it-qat-optiq", "Gemma 4 E2B (QAT OptiQ)"),
    # Cactus ships two CQ4 lineages of E2B (same repo, different files) that must not
    # pool either: the pre-07-09 "uncalibrated" (the row: GSM8K 87.0) vs the shipped
    # default "calibrated" (footnote: GSM8K 3.0). Uncal pattern first — it contains cq4.
    ("gemma-4-e2b-it-cq4-uncal", "Gemma 4 E2B (CQ4 uncalibrated)"),
    ("gemma-4-e2b-it-cq4",       "Gemma 4 E2B (CQ4 shipped default)"),
    ("gemma-4-e2b",     "Gemma 4 E2B"),
    ("gemma-4-e4b",     "Gemma 4 E4B"),
    ("gemma4-e2b",      "Gemma 4 E2B"),
    ("gemma4-e4b",      "Gemma 4 E4B"),
    # Gemma 3
    ("gemma-3-270m",    "Gemma 3 270M"),
    ("gemma-3-1b",      "Gemma 3 1B"),
    # Qwen 3.5
    ("qwen3.5-35b-a3b", "Qwen 3.5 35B-A3B (MoE)"),
    ("qwen3.5-27b",     "Qwen 3.5 27B"),
    ("qwen3.5-9b",      "Qwen 3.5 9B"),
    ("qwen3.5-2b",      "Qwen 3.5 2B"),
    ("qwen3.5-0.8b",    "Qwen 3.5 0.8B"),
    # Qwen 3
    ("qwen3-4b",        "Qwen 3 4B"),
    ("qwen3-1.7b",      "Qwen 3 1.7B"),
    ("qwen3-0.6b",      "Qwen 3 0.6B"),
    # Qwen 2.5
    ("qwen2.5-0.5b",    "Qwen 2.5 0.5B"),
    ("qwen2.5-1.5b",    "Qwen 2.5 1.5B"),
    ("qwen2.5-3b",      "Qwen 2.5 3B"),
    ("qwen2.5-7b",      "Qwen 2.5 7B"),
    # LFM / Llama / others
    ("lfm2.5-350m",     "LFM 2.5 350M"),
    ("lfm-2.5-350m",    "LFM 2.5 350M"),
    ("llama-3.2-1b",    "Llama 3.2 1B"),
    ("llama-3.3-1b",    "Llama 3.3 1B"),
    ("llama-3.3-3b",    "Llama 3.3 3B"),
    ("smollm3-3b",      "SmolLM 3B"),
]


def logical_model(model_id: str) -> str:
    """Canonical display name for a model, collapsing per-runtime HF IDs."""
    needle = model_id.lower()
    for pat, name in LOGICAL_MODELS:
        if pat in needle:
            return name
    return model_id


def runtime_display(runtime: str) -> str:
    return {
        "mlx-swift": "mlx-swift",
        "llama.cpp": "llama.cpp",
        "coreml-llm": "coreml-llm",
        "executorch": "executorch",
        "anemll": "anemll",
        "litert-lm": "litert-lm",
        "apple-fm": "apple-fm",
        "core-ai": "core-ai",
    }.get(runtime, runtime)


# ---------------------------------------------------------------- atomic writes
#
# Two sittings may finish at the same moment (the job's lock is per device
# since 2026-09-08), and each regenerates results/summary/* and the dashboard.
# Every such derived file is written to a temp file in its directory and
# renamed into place, so a reader never sees a half-written file; the last
# writer wins, and since each rebuilds from raw the result is the same.

import contextlib as _contextlib
import tempfile as _tempfile


@_contextlib.contextmanager
def atomic_write(path, mode="w", **kwargs):
    """`with atomic_write(p) as fh:` — fh is a temp file beside p; on a clean
    exit it replaces p in one rename, on an exception it is removed."""
    d = _os.path.dirname(_os.path.abspath(path)) or "."
    fd, tmp = _tempfile.mkstemp(prefix="." + _os.path.basename(path) + ".", dir=d)
    _os.close(fd)
    try:
        with open(tmp, mode, **kwargs) as fh:
            yield fh
        _os.replace(tmp, path)
    except BaseException:
        try:
            _os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------- bandwidth utilization
#
# bw util % = decode tok/s x artifact bytes / the device's memory-bandwidth
# ceiling. Decode of a dense LLM streams (roughly) the whole weight set once per
# token, so this is the share of the device's memory bandwidth the arm turns
# into tokens — a recipe-normalized reading: a 4-bit artifact and an 8-bit one
# of the same model are different byte counts, and the column shows that
# instead of hiding it in tok/s. Two registries, both cited:
#   devices/memory-bandwidth.json  ceiling per device.modelIdentifier (vendor
#                                  figure, a derivation from a vendor clock, a
#                                  marked estimate, or null = n/a)
#   models/artifact-bytes.json     bytes of the artifact each arm loads
#                                  (HF file sizes at a revision, or a local
#                                  bundle's weight file; scripts/artifact_bytes.py)
# Artifact bytes are an UPPER bound on the bytes streamed per token (embedding
# tables are gathered, not streamed; a .litertlm carries its tokenizer), so the
# figure is a comparable proxy, not a measured bus counter.

import json as _json
import os as _os

_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
BANDWIDTH_JSON = _os.path.join(_ROOT, "devices", "memory-bandwidth.json")
ARTIFACT_BYTES_JSON = _os.path.join(_ROOT, "models", "artifact-bytes.json")


def _load_json(path):
    try:
        with open(path) as fh:
            return _json.load(fh)
    except (OSError, ValueError):
        return {}


def bandwidth_ceiling(device_identifier: str):
    """-> (gbps, basis, source) for a record's device.modelIdentifier, or
    (None, basis, source) when the registry says nothing citable exists."""
    d = _load_json(BANDWIDTH_JSON).get("devices", {}).get(device_identifier)
    if not d:
        return None, "unregistered", ""
    return d.get("gbps"), d.get("basis", ""), d.get("source", "")


def artifact_entry(arm: str, model_id: str, platform: str = ""):
    """The registry entry for (arm, model id), or None. `arm` is the
    device-runs.csv runtime string (Android LiteRT carries its backend:
    litert-lm-cpu / litert-lm-gpu). An entry with a `platform` wins over a
    platform-less one for that platform."""
    best = None
    for e in _load_json(ARTIFACT_BYTES_JSON).get("artifacts", []):
        if e.get("arm") != arm or e.get("model_id") != model_id:
            continue
        plat = e.get("platform") or ""
        if plat and plat != platform:
            continue
        if best is None or (plat and not (best.get("platform") or "")):
            best = e
    return best


def artifact_bytes(arm: str, model_id: str, platform: str = ""):
    """Bytes a decode step reads for this cell: the entry's `streamed_bytes`
    (artifact minus per-token-gathered tables, scripts/artifact_streamed_bytes.py)
    when present, else the whole artifact's `bytes`; None = not registered."""
    e = artifact_entry(arm, model_id, platform)
    if not e:
        return None
    return e.get("streamed_bytes") or e.get("bytes")


def bandwidth_utilization(decode_tps, arm: str, model_id: str,
                          device_identifier: str, platform: str = ""):
    """-> dict(pct, bytes, artifact_bytes, streamed, gbps, basis) or None when
    any input is missing. pct = decode_tps * bytes / (gbps * 1e9) * 100, with
    bytes = the per-token figure (streamed_bytes if registered, else the
    artifact)."""
    if not decode_tps:
        return None
    e = artifact_entry(arm, model_id, platform)
    gbps, basis, _ = bandwidth_ceiling(device_identifier)
    nbytes = (e.get("streamed_bytes") or e.get("bytes")) if e else None
    if not nbytes or not gbps:
        return None
    return {"pct": decode_tps * nbytes / (gbps * 1e9) * 100.0,
            "bytes": nbytes, "artifact_bytes": e.get("bytes"),
            "streamed": bool(e.get("streamed_bytes")),
            "gbps": gbps, "basis": basis}


def fmt_bw(u, estimate_mark: str = "~") -> str:
    """'12.3%' — prefixed with `estimate_mark` when the ceiling is not a vendor
    figure (estimate / derived), so a reader never mistakes it for one."""
    if not u:
        return "—"
    mark = "" if u["basis"] == "vendor" else estimate_mark
    return f"{mark}{u['pct']:.1f}%"


def corrected_quant(runtime: str, model_id: str, quant: str) -> tuple[str, bool]:
    """Apply the audited in-place quantization-label correction (quant-label-rule):
    Gemma-4 .litertlm bundles are the wNa8o8 mobile schema, not uniform int4 —
    early rows recorded "INT4 (QAT)" before the 2026-07-17 audit corrected the
    label for the SAME artifact. Scope is deliberately narrow (litert-lm +
    gemma-4 only); other labels render as recorded. Returns (label, corrected?).
    """
    if (runtime == "litert-lm" and "gemma-4" in model_id.lower()
            and quant == "INT4 (QAT)"):
        return "wNa8o8 (int2/int4/int8 + int8 activations, QAT)", True
    return quant, False
