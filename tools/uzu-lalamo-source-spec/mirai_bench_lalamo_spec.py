"""Pinned smoke sources: mlx-community Qwen3 affine 4-bit, group size 64.

The built-in 0.6B ModelSpec targets a different Qwen-hosted group-128 file.
Reuse its architecture/reasoning metadata, replacing only the weights/config
origin; tokenizer and generation files remain the original Qwen3 base files.
"""
from dataclasses import replace

from lalamo.model_import.model_specs.qwen import QWEN_MODELS
from lalamo.model_import.origins import HuggingFaceOrigin


def specs() -> tuple:
    return tuple(
        replace(next(model for model in QWEN_MODELS if model.name == f"Qwen3-{size}-MLX-4bit"),
                origin=HuggingFaceOrigin(repo=f"mlx-community/Qwen3-{size}-4bit"))
        for size in ("0.6B", "1.7B", "4B")
    )
