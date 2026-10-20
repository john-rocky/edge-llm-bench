#!/usr/bin/env python3
"""Compare the B runs (asr-npu-v1, docs/asr-npu-v1.md): the same encoder inputs through a model's AOT
file on the NPU and its f32 file on the CPU (NpuCompareTest), output by output.

  compare.py --compare-dir .build/asr-npu/compare --mel-dir .build/asr-npu/mel --out <REC>/b-compare.json
             [--tdt-tokenizer tdt-tokenizer.json] [--ctc-tokenizer ctc-tokenizer.json]

Per window and output (CPU = reference): element count, NaN / Inf on each side, max |Δ| and mean |Δ|
over the elements finite on both sides, the reference's max |x|, cosine over all elements (none when
a side has a non-finite value) and over the finite ones.
- CTC (b-ctc-*): logits [1, T, V]: per frame the argmax (NaN as -inf) on each side, the frames that
  agree; the app's view of each side (CtcDecoder: Kotlin's maxByOrNull, where NaN compares greater
  than any number, then repeats collapsed): token ids and pieces.
- TDT (b-tdt-*): the encoder output [1, 1024, T], cosine per frame too; decode / decode_1 on the CPU's
  encoder output on both sides: per frame of token slot 0 the token argmax (the first V - 5 logits)
  and the duration argmax (the last 5), the frames that agree, the app's view (Kotlin argmax) of the
  NPU's own decode on its own encoder output.
The line (docs/asr-npu-v1.md, set before the runs): a window "differs" when cosine < 0.99 (a
non-finite NPU value counts as differing) or, for CTC, the argmax agrees on fewer than 90 % of the
frames. The all-zero input (<kind>-zeros.f32) is compared the same way and reported outside the line.
"""
import argparse
import hashlib
import json
import pathlib
import sys

import numpy as np

LINE_COSINE = 0.99
LINE_ARGMAX = 0.90
DURATIONS = 5


def f32(path):
    return np.fromfile(path, dtype="<f4")


def sha256(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def cosine(a, b):
    a = a.astype(np.float64)
    b = b.astype(np.float64)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return None
    return float(np.dot(a, b) / (na * nb))


def metrics(ref, out):
    fin = np.isfinite(ref) & np.isfinite(out)
    d = np.abs(ref[fin].astype(np.float64) - out[fin].astype(np.float64))
    all_finite = bool(np.isfinite(ref).all() and np.isfinite(out).all())
    return {
        "count": int(ref.size),
        "nan_cpu": int(np.isnan(ref).sum()), "inf_cpu": int(np.isinf(ref).sum()),
        "nan_npu": int(np.isnan(out).sum()), "inf_npu": int(np.isinf(out).sum()),
        "zeros_npu": int((out == 0).sum()),
        "max_abs_diff": float(d.max()) if d.size else None,
        "mean_abs_diff": float(d.mean()) if d.size else None,
        "cpu_max_abs": float(np.abs(ref[np.isfinite(ref)]).max()) if np.isfinite(ref).any() else None,
        "npu_max_abs": float(np.abs(out[np.isfinite(out)]).max()) if np.isfinite(out).any() else None,
        "cosine": cosine(ref, out) if all_finite else None,
        "cosine_finite": cosine(ref[fin], out[fin]) if fin.any() else None,
        "all_finite": all_finite,
    }


def argmax_nan_low(x, axis=-1):
    return np.argmax(np.where(np.isnan(x), -np.inf, x), axis=axis)


def kotlin_argmax(row):
    """Kotlin's maxByOrNull over Float (compareTo: NaN greater than any number, equal to NaN)."""
    if np.isnan(row[0]):
        return 0
    nan = np.flatnonzero(np.isnan(row))
    return int(nan[0]) if nan.size else int(np.argmax(row))


def pieces(vocab, ids):
    return [vocab.get(int(i), f"<{int(i)}>") for i in ids]


def load_vocab(path):
    if not path:
        return {}
    d = json.loads(pathlib.Path(path).read_text())
    v = d["model"]["vocab"]
    inv = {i: k for k, i in v.items()} if isinstance(v, dict) else {i: p[0] for i, p in enumerate(v)}
    for t in d.get("added_tokens", []):
        inv[t["id"]] = t["content"]
    return inv


def ctc_view(logits, blank):
    ids = [kotlin_argmax(r) for r in logits]
    collapsed = [i for n, i in enumerate(ids) if n == 0 or i != ids[n - 1]]
    return [i for i in collapsed if i != blank]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--compare-dir", required=True)
    ap.add_argument("--mel-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tdt-tokenizer", default="")
    ap.add_argument("--ctc-tokenizer", default="")
    args = ap.parse_args()
    cdir = pathlib.Path(args.compare_dir)
    result = {"line": {"cosine_below": LINE_COSINE, "ctc_argmax_agreement_below": LINE_ARGMAX,
                       "non_finite_npu_value": "differs"}, "models": {}}
    vocab = {"tdt": load_vocab(args.tdt_tokenizer), "ctc": load_vocab(args.ctc_tokenizer)}
    for kind in ("ctc", "tdt"):
        cpu_json, npu_json = cdir / f"b-{kind}-cpu.json", cdir / f"b-{kind}-npu.json"
        if not (cpu_json.exists() and npu_json.exists()):
            result["models"][kind] = {"missing": [str(p.name) for p in (cpu_json, npu_json) if not p.exists()]}
            continue
        cpu, npu = json.loads(cpu_json.read_text()), json.loads(npu_json.read_text())
        rec = {"cpu_model": cpu["model"], "cpu_model_sha256": cpu.get("model_sha256"), "npu_model": npu["model"],
               "npu_model_sha256": npu.get("model_sha256"), "load_ms": {"cpu": cpu["load_ms"], "npu": npu["load_ms"]},
               "signatures_npu": npu.get("signatures"), "windows": []}
        for w, (cw, nw) in enumerate(zip(cpu["encode"], npu["encode"])):
            if cw["input_sha256"] != nw["input_sha256"]:
                raise SystemExit(f"{kind} window {w}: the two runs read different inputs")
            ref, out = f32(cdir / cw["outputs"][0]["file"]), f32(cdir / nw["outputs"][0]["file"])
            m = metrics(ref, out)
            win = {"window": w, "input": pathlib.Path(cw["input"]).name, "input_sha256": cw["input_sha256"],
                   "encode_ms": {"cpu": cw["run_ms"], "npu": nw["run_ms"]},
                   "repeats_bit_identical": {"cpu": cw["repeats_bit_identical"], "npu": nw["repeats_bit_identical"]},
                   "encoder_output": m}
            differs = m["cosine"] is None or m["cosine"] < LINE_COSINE
            if kind == "ctc":
                T = 63
                V = len(ref) // T
                r2, o2 = ref.reshape(T, V), out.reshape(T, V)
                agree = int((argmax_nan_low(r2) == argmax_nan_low(o2)).sum())
                blank = V - 1
                cpu_ids, npu_ids = ctc_view(r2, blank), ctc_view(o2, blank)
                win["argmax"] = {"frames": T, "agree": agree, "share": agree / T,
                                 "nan_frames_npu": int(np.isnan(o2).any(axis=1).sum())}
                win["app_view"] = {"cpu_ids": cpu_ids, "cpu_pieces": pieces(vocab["ctc"], cpu_ids),
                                   "npu_ids": npu_ids, "npu_pieces": pieces(vocab["ctc"], npu_ids)}
                differs = differs or agree / T < LINE_ARGMAX
            else:
                T = 63
                r2, o2 = ref.reshape(1024, T), out.reshape(1024, T)
                per = [cosine(r2[:, t], o2[:, t]) if np.isfinite(o2[:, t]).all() else None for t in range(T)]
                fin = [p for p in per if p is not None]
                win["encoder_frames"] = {"frames": T, "non_finite_npu_frames": sum(p is None for p in per),
                                         "cosine_min": min(fin) if fin else None,
                                         "cosine_median": float(np.median(fin)) if fin else None}
            win["differs"] = bool(differs)
            win["in_line"] = "zeros" not in win["input"]
            rec["windows"].append(win)
        if kind == "tdt":
            T = 63
            dec = []
            by_key = {}
            for side, rep in (("cpu", cpu), ("npu", npu)):
                for d in rep.get("decode", []):
                    src = pathlib.Path(d["encoder_output"]).name
                    by_key[(side, d["signature"], src)] = d
            for (side, sig, src), d in sorted(by_key.items()):
                if side != "npu" or not src.startswith("b-tdt-cpu.enc."):
                    continue
                w = src.split(".enc.")[1].split(".")[0]
                cref = by_key.get(("cpu", sig, f"b-tdt-cpu.enc.{w}.out0.f32"))
                if cref is None:
                    continue
                if cref["encoder_output_sha256"] != d["encoder_output_sha256"]:
                    raise SystemExit(f"decode {sig} {w}: the two runs decoded different encoder outputs")
                outs = []
                for o, (co, no) in enumerate(zip(cref["outputs"], d["outputs"])):
                    a, b = f32(cdir / co["file"]), f32(cdir / no["file"])
                    m = metrics(a, b)
                    if o == 0:
                        slots = 4 if sig == "decode" else 1
                        V = a.size // (T * slots)
                        a4, b4 = a.reshape(T, slots, V)[:, 0, :], b.reshape(T, slots, V)[:, 0, :]
                        tok_a, tok_b = argmax_nan_low(a4[:, :V - DURATIONS]), argmax_nan_low(b4[:, :V - DURATIONS])
                        dur_a, dur_b = argmax_nan_low(a4[:, V - DURATIONS:]), argmax_nan_low(b4[:, V - DURATIONS:])
                        m["slot0"] = {"frames": T, "token_agree": int((tok_a == tok_b).sum()),
                                      "duration_agree": int((dur_a == dur_b).sum()),
                                      "cpu_tokens_first8": tok_a[:8].tolist(), "npu_tokens_first8": tok_b[:8].tolist(),
                                      "npu_kotlin_argmax_first8": [kotlin_argmax(r[:V - DURATIONS]) for r in b4[:8]]}
                    outs.append(m)
                dec.append({"signature": sig, "window": w, "encoder_output": src,
                            "encoder_output_sha256": d["encoder_output_sha256"], "tokens": d["tokens"], "outputs": outs})
            # The app's path: the NPU's decode / decode_1 on the NPU's own encoder output.
            own = []
            for (side, sig, src), d in sorted(by_key.items()):
                if side != "npu" or src.startswith("b-tdt-cpu."):
                    continue
                o0 = d["outputs"][0]
                b = f32(cdir / o0["file"])
                slots = 4 if sig == "decode" else 1
                V = b.size // (T * slots)
                b4 = b.reshape(T, slots, V)[:, 0, :]
                ids = [kotlin_argmax(r[:V - DURATIONS]) for r in b4]
                durs = [kotlin_argmax(r[V - DURATIONS:]) for r in b4]
                own.append({"signature": sig, "encoder_output": src, "stats": o0,
                            "kotlin_token_argmax": {"distinct": sorted(set(ids))[:10], "token0_frames": ids.count(0)},
                            "kotlin_duration_argmax": {"distinct": sorted(set(durs)), "duration0_frames": durs.count(0)}})
            rec["decode_on_cpu_encoder_output"] = dec
            rec["npu_decode_on_npu_encoder_output"] = own
        rec["windows_in_line"] = sum(w["in_line"] for w in rec["windows"])
        rec["windows_in_line_differing"] = sum(w["differs"] for w in rec["windows"] if w["in_line"])
        result["models"][kind] = rec
    pathlib.Path(args.out).write_text(json.dumps(result, indent=1) + "\n")
    for kind, rec in result["models"].items():
        if "missing" in rec:
            print(f"{kind}: missing {rec['missing']}")
            continue
        for w in rec["windows"]:
            m = w["encoder_output"]
            extra = f" argmax {w['argmax']['agree']}/{w['argmax']['frames']}" if "argmax" in w else ""
            print(f"{kind} w{w['window']} {w['input']}: cosine {m['cosine']} (finite {m['cosine_finite']}) max|d| {m['max_abs_diff']} "
                  f"nan_npu {m['nan_npu']} inf_npu {m['inf_npu']}{extra} -> {'DIFFERS' if w['differs'] else 'same'}")
            if "app_view" in w:
                print(f"   cpu {''.join(w['app_view']['cpu_pieces'])!r}  npu {''.join(w['app_view']['npu_pieces'])!r}")
        for d in rec.get("decode_on_cpu_encoder_output", []):
            m = d["outputs"][0]
            print(f"tdt {d['signature']} {d['window']} on the CPU's encoder output: cosine {m['cosine']} nan_npu {m['nan_npu']} "
                  f"tokens agree {m['slot0']['token_agree']}/63 durations {m['slot0']['duration_agree']}/63")
    return 0


if __name__ == "__main__":
    sys.exit(main())
