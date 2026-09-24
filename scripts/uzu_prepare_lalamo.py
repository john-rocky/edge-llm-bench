#!/usr/bin/env python3
"""Adapt pinned ungated exports to uzu 0.5.30's file schema.

No tensor conversion or quantization: only JSON fields and safetensors names
change. Fail closed for gates, other architectures or unexpected fields.
Evidence is for smoke compatibility only, not a performance measurement.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import shutil
import struct


def sha256(path, offset=0):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        f.seek(offset)
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def compatible_config(source, architecture="qwen3"):
    cfg = json.loads(json.dumps(source))
    assert cfg["type"] == "LanguageModelConfig"
    codec = cfg["token_codec_config"]
    assert codec["type"] == "ChatCodecConfig"
    # The pinned engine rejects this newer, additional field. Its SDK handles
    # reasoning controls separately. Preserve the actual Jinja template verbatim.
    reasoning = codec.pop("reasoning_config")
    default_effort = "no_reasoning" if architecture == "gemma4-e2b" else "medium"
    assert reasoning == {"default_reasoning_effort": default_effort, "field_name": "enable_thinking",
                         "reasoning_effort_to_field_value": {"medium": True, "no_reasoning": False}}
    trans = cfg["decoder_config"]["transformer_config"]
    if architecture == "gemma4-e2b":
        assert trans["model_dim"] == 1536 and len(trans["layer_configs"]) == 35
        assert cfg["decoder_config"]["ple_model_config"]["ple_dim"] == 256
    else:
        assert architecture == "qwen3"
        # Pinned Qwen3 0.6B/1.7B/4B source configs; reject other architectures.
        expected_layers, expected_heads = {1024: (28, 16), 2048: (28, 16), 2560: (36, 32)}[trans["model_dim"]]
        assert len(trans["layer_configs"]) == expected_layers
    for index, layer in enumerate(trans["layer_configs"]):
        mixer = layer["mixer_config"]
        assert mixer["type"] == "AttentionConfig"
        assert mixer.pop("has_gate") is False, "gated attention cannot use this rename"
        if architecture == "gemma4-e2b":
            assert mixer["is_kv_sharing"] == (index >= 15)
            assert mixer["num_heads"] == 8 and mixer["num_groups"] == 1
            assert mixer["head_dim"] == (512 if index % 5 == 4 else 256)
        else:
            assert mixer["is_kv_sharing"] is False
            assert mixer["num_heads"] == expected_heads and mixer["num_groups"] == 8 and mixer["head_dim"] == 128
        mixer["qkv_projection_config"] = mixer.pop("qkvg_projection_config")
        mixer["has_qkv_biases"] = mixer.pop("has_qkvg_biases")
        mixer["gate_projection_config"] = None
    assert codec["prompt_template"] == source["token_codec_config"]["prompt_template"]
    return cfg


def rename(name):
    return name.replace(".mixer.qkvg_projection.", ".mixer.qkv_projection.")


def adapt(source, output, converter_commit="d1cfe68e9b0cee64705b83e4bde1bf650a01cb1a", architecture="qwen3"):
    cfg_path = source / "config.json"
    cfg = compatible_config(json.loads(cfg_path.read_text()), architecture)
    layers = len(cfg["decoder_config"]["transformer_config"]["layer_configs"])
    encoding_name = "gemma-4" if architecture == "gemma4-e2b" else "qwen3"
    weights = source / "model.safetensors"
    with weights.open("rb") as f:
        size = struct.unpack("<Q", f.read(8))[0]
        header = json.loads(f.read(size))
    renamed = {rename(k): v for k, v in header.items()}
    metadata = header["__metadata__"]
    renamed["__metadata__"] = {rename(k): v for k, v in metadata.items()}
    assert len(renamed) == len(header)
    assert len(renamed["__metadata__"]) == len(metadata)
    renamed_count = sum(rename(k) != k for k in header)
    allowed_counts = (layers,) if architecture == "gemma4-e2b" else (layers, layers * 3)
    assert renamed_count in allowed_counts, "expected dense or MLX QKV tensors in each layer"
    assert sum(rename(k) != k for k in metadata) == layers
    # Fixed-size padding is legal safetensors JSON whitespace. Keeping the
    # original header length also preserves every absolute tensor byte offset.
    wire = json.dumps(renamed, separators=(",", ":"), ensure_ascii=False).encode()
    assert len(wire) <= size
    output.mkdir(parents=True, exist_ok=False)
    (output / "config.json").write_text(json.dumps(cfg, indent=2) + "\n")
    # model_by_path reads encoding.json; nagare requires an EncodingConfig
    # independently of the engine's token_codec_config. Use the SDK's bundled
    # model-family chat protocol (supports ReasoningEffort.Disabled).
    (output / "encoding.json").write_text(json.dumps({"type": "hanashi", "name": encoding_name}, separators=(",", ":")) + "\n")
    shutil.copyfile(source / "tokenizer.json", output / "tokenizer.json")
    with weights.open("rb") as src, (output / "model.safetensors").open("wb") as dst:
        dst.write(struct.pack("<Q", size))
        dst.write(wire + b" " * (size - len(wire)))
        src.seek(8 + size)
        shutil.copyfileobj(src, dst, length=1 << 20)
    before = sha256(weights, 8 + size)
    after = sha256(output / "model.safetensors", 8 + size)
    assert before == after
    assert (source / "tokenizer.json").read_bytes() == (output / "tokenizer.json").read_bytes()
    return {
        "capturePurpose": "smoke compatibility only; not a measurement",
        "converterCommit": converter_commit, "engineVersion": "uzu 0.5.30",
        "source": str(source), "output": str(output), "tensorPayloadSha256Before": before,
        "tensorPayloadSha256After": after, "tensorPayloadUnchanged": True,
        "tensorPayloadBytes": weights.stat().st_size - 8 - size,
        "tensorNamesRenamed": renamed_count, "metadataNamesRenamed": layers,
        "promptTemplateUnchanged": True, "tokenizerUnchanged": True,
        "architecture": architecture, "sdkChatEncoding": {"type": "hanashi", "name": encoding_name},
        "changes": ["remove unsupported token_codec_config.reasoning_config metadata",
                    "ungated attention qkvg_projection_config -> qkv_projection_config",
                    "has_qkvg_biases -> has_qkv_biases; has_gate=false -> gate_projection_config=null",
                    "rename qkvg_projection to qkv_projection in tensor and metadata names only",
                    f"add encoding.json selecting uzu 0.5.30 bundled {encoding_name} chat protocol"],
        "tensorDtypes": dict(collections.Counter(v["dtype"] for k, v in header.items() if k != "__metadata__")),
        "weightSpecs": dict(collections.Counter(json.loads(v)["type"] for v in metadata.values())),
        "files": [{"file": p.name, "bytes": p.stat().st_size, "sha256": sha256(p)}
                  for p in sorted(output.iterdir())],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--architecture", choices=["qwen3", "gemma4-e2b"], default="qwen3")
    ap.add_argument("--converter-commit", default="d1cfe68e9b0cee64705b83e4bde1bf650a01cb1a",
                    choices=["d1cfe68e9b0cee64705b83e4bde1bf650a01cb1a"])
    args = ap.parse_args()
    report = adapt(args.source.resolve(), args.output.resolve(), args.converter_commit, args.architecture)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
