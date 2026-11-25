#!/usr/bin/env python3
"""Device- and network-free selftest of the session-anchor and text-check rules in scripts/regression_diff.py (CI).

Synthetic device-runs rows stand in for results/summary/device-runs.csv: one Mac payload cell of
the engine under test (llama.cpp, 100 -> 80 tok/s across two sittings on two days) and two anchor
cells (mlx-swift, then litert-lm, the order of the anchors file). An anchor normalizes the pair
only when its rows carry the same engine version, harness stamp and engine artifact on both sides
(ANCHOR_IDENTITY); the first anchor that passes on both sides normalizes both. Pins:

  (a) the same engine on both sides -> the anchor normalizes (OK, ~0 %, via the mlx-swift anchor)
  (b) the anchor's engine version differs -> INFO-ONLY, the line names the version change
  (c) the anchor's harness stamp differs -> INFO-ONLY
  (d) one side's anchor rows do not carry a field the other side's do (an empty artifact; a row
      with no harness_stamp key at all) -> INFO-ONLY
  (e) the build differs under one version and stamp (engine_artifact only, as the Android
      LiteRT-LM GPU builds v0.19.0 and v0.19.0-pregpu) -> INFO-ONLY
  (f) both sides lack the same field (rows written before the artifact was stamped) -> normalizes
  (g) the first anchor moved, the second did not -> normalized through the second
  (h) both anchors moved (the Mac yardstick swap: MLX version, LiteRT-LM stamp) -> INFO-ONLY,
      both moves named
  (i) the first anchor usable on one side only (n=1 on the other) -> both sides through the
      second: one anchor for the pair, never one per side
  (j) the engine under test's own anchor stays excluded (an mlx-swift payload goes through the
      litert-lm anchor even when the mlx-swift anchor did not move)
  (k) a same-day pair takes no anchor: the raw delta is the verdict
  (l) every candidate run failed the text check -> TEXT-FAIL, exit 1
  (m) one failed candidate outlier beside three passing runs -> OK from the three, the left-out
      count printed

  python3 scripts/regression_diff_selftest.py     # exit 0 = pass
"""
import argparse
import contextlib
import io
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import regression_diff as rd  # noqa: E402

_fails = []

DEVICE = "Mac16,9"
MLX = ("mlx-swift", "mlx-community/Qwen3-0.6B-4bit")
LRT = ("litert-lm", "litert-community/Qwen3-0.6B/dynamic_wi4b32_afp32")
PAYLOAD = ("llama.cpp", "unsloth/Qwen3-1.7B-GGUF")
MLX_V1, MLX_V2 = "60bd0d7880c82980f9481f8be78862e9b63c58a3", "ca661dc6885f8603e911746838b60d312439a368"
STAMP = "2026-07-30-protocol-r4"
LRT_STAMP2 = STAMP + "+litert-cap-engine-kvfilter-off"
LRT_ART = "CLiteRTLM_mac.xcframework.zip@v0.19.0 sha256:65ddc8f1"
FLAT_ART, PREGPU_ART = "de8c840290ff971a", "11c2cde974b6e1d2"
BASE_DAY, CAND_DAY = "2026-11-15", "2026-11-22"
PAYLOAD_LABEL = f"{DEVICE} {PAYLOAD[0]} {PAYLOAD[1]} short-chat warm"


def ok(cond, msg):
    print(("  ok  " if cond else "  FAIL ") + msg)
    if not cond:
        _fails.append(msg)


def row(campaign, day, arm, value, ident, cold="False"):
    version, stamp, artifact = ident
    r = {"source": f"results/raw/{campaign}/x.jsonl", "campaign": f"results/raw/{campaign}",
         "timestamp": f"{day}T03:00:00Z", "runtime": arm[0], "device": DEVICE, "model_id": arm[1],
         "task": "short-chat", "prompt_version": "", "context_tokens": "", "cold_run": cold,
         "first_ever": "False", "thermal_initial": "nominal", "quantization": "4-bit",
         "decode_tps": str(value), "prefill_tps": "", "ttft_ms": "", "mem_footprint_median_mb": "",
         "energy_j_per_tok": "", "engine_version": version, "harness_stamp": stamp,
         "engine_artifact": artifact}
    if stamp is None:  # a row with no harness_stamp field at all
        del r["harness_stamp"]
    return r


def world(mlx_base, mlx_cand, lrt_base=None, lrt_cand=None, mlx_cand_vals=(160, 161),
          lrt_cand_vals=(40, 40.2), cand_day=CAND_DAY, payload=PAYLOAD,
          payload_idents=(("b11721", "", "a1"), ("b12359", "", "a2"))):
    """Rows of two sittings: the payload 100 -> 80 tok/s, the mlx-swift anchor 200.5 -> a
    candidate median of mlx_cand_vals, the litert-lm anchor 50.1 -> lrt_cand_vals (when given)."""
    rows = []
    for v in (100, 100.5, 99.5):
        rows.append(row("camp-base-mac", BASE_DAY, payload, v, payload_idents[0]))
    for v in (80, 80.4, 79.6):
        rows.append(row("camp-cand-mac", cand_day, payload, v, payload_idents[1]))
    for v in (200, 201):
        rows.append(row("camp-base-mac", BASE_DAY, MLX, v, mlx_base))
    for v in mlx_cand_vals:
        rows.append(row("camp-cand-mac", cand_day, MLX, v, mlx_cand))
    if lrt_base is not None:
        for v in (50, 50.2):
            rows.append(row("camp-base-mac", BASE_DAY, LRT, v, lrt_base))
        for v in lrt_cand_vals:
            rows.append(row("camp-cand-mac", cand_day, LRT, v, lrt_cand))
    return rows


def run(rows, anchors_path, eut=PAYLOAD[0], label=PAYLOAD_LABEL):
    """run_device over rows; returns (the payload cell's decode record, the printed text)."""
    rd.RECORDS.clear()
    rd.load_csv = lambda name: [dict(r) for r in rows]
    args = argparse.Namespace(baseline="campaign:camp-base", candidate="campaign:camp-cand",
                              anchors=anchors_path, engine_under_test=eut, min_n=3,
                              spread_limit=5.0, threshold_pct=5.0)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = rd.run_device(args)
    recs = [r for r in rd.RECORDS if r["cell"] == label and r.get("metric") == "decode_tps"]
    out = buf.getvalue()
    line = next((ln for ln in out.splitlines() if label in ln), "")
    return rc, (recs[0] if len(recs) == 1 else None), line


def anchor_cell(rec):
    return ((rec or {}).get("anchor") or {}).get("cell")


def main():
    tmp = tempfile.mkdtemp(prefix="regression-diff-selftest-")
    anchors_path = os.path.join(tmp, "anchors.cells")
    with open(anchors_path, "w") as fh:
        fh.write(f"mac {MLX[0]} {MLX[1]} short-chat anchor=1 runs=3\n"
                 f"mac {LRT[0]} {LRT[1]} short-chat anchor=1 runs=3\n")
    same = (MLX_V1, STAMP, "")
    lrt = ("v0.19.0", STAMP, LRT_ART)

    print("--- (a) the same engine on both sides")
    rc, rec, line = run(world(same, same), anchors_path)
    ok(rec and rec["verdict"] == "OK" and anchor_cell(rec) == f"{MLX[0]} {MLX[1]} short-chat"
       and abs(rec["anchor"]["normalized_delta_pct"] - (-0.06)) < 0.01 and rc == 0,
       f"normalized through the mlx-swift anchor: OK at -0.06 % (raw -20 %) ({rec and rec['verdict']}, "
       f"{anchor_cell(rec)}, {rec and (rec.get('anchor') or {}).get('normalized_delta_pct')})")

    print("--- (b) the anchor's engine version differs")
    rc, rec, line = run(world(same, (MLX_V2, STAMP, "")), anchors_path)
    ok(rec and rec["verdict"] == "INFO-ONLY" and "anchor" not in rec and rc == 0,
       f"INFO-ONLY, no anchor in the record ({rec and rec['verdict']})")
    ok(f"engine_version {MLX_V1} -> {MLX_V2}" in line and "use a same-session A/B" in line,
       f"the line names the move ({line[line.find('anchor engine moved'):][:140]})")

    print("--- (c) the anchor's harness stamp differs")
    rc, rec, line = run(world(same, (MLX_V1, STAMP + "+x", "")), anchors_path)
    ok(rec and rec["verdict"] == "INFO-ONLY" and f"harness_stamp {STAMP} -> {STAMP}+x" in line,
       f"INFO-ONLY, the stamp named ({rec and rec['verdict']})")

    print("--- (d) one side does not carry a field")
    rc, rec, line = run(world((MLX_V1, STAMP, ""), (MLX_V1, STAMP, "mlx-swift-lm@3.33.0")), anchors_path)
    ok(rec and rec["verdict"] == "INFO-ONLY" and "engine_artifact (none) -> mlx-swift-lm@3.33.0" in line,
       f"an artifact on the candidate side only: INFO-ONLY ({rec and rec['verdict']})")
    rc, rec, line = run(world((MLX_V1, None, ""), same), anchors_path)
    ok(rec and rec["verdict"] == "INFO-ONLY" and f"harness_stamp (none) -> {STAMP}" in line,
       f"base rows with no harness_stamp key at all: INFO-ONLY ({rec and rec['verdict']})")

    print("--- (e) the build differs under one version and stamp")
    rc, rec, line = run(world((MLX_V1, STAMP, FLAT_ART), (MLX_V1, STAMP, PREGPU_ART)), anchors_path)
    ok(rec and rec["verdict"] == "INFO-ONLY" and f"engine_artifact {FLAT_ART} -> {PREGPU_ART}" in line
       and "engine_version" not in line.split("anchor engine moved")[-1],
       f"only the artifact differs: INFO-ONLY, the artifact named ({rec and rec['verdict']})")

    print("--- (f) both sides lack the same field")
    rc, rec, line = run(world((MLX_V1, STAMP, ""), (MLX_V1, STAMP, "")), anchors_path)
    ok(rec and rec["verdict"] == "OK" and anchor_cell(rec) == f"{MLX[0]} {MLX[1]} short-chat",
       f"no artifact on either side: normalized as before ({rec and rec['verdict']}, {anchor_cell(rec)})")

    print("--- (g) the first anchor moved, the second did not")
    rc, rec, line = run(world(same, (MLX_V2, STAMP, ""), lrt, lrt, mlx_cand_vals=(100, 101)), anchors_path)
    ok(rec and rec["verdict"] == "OK" and anchor_cell(rec) == f"{LRT[0]} {LRT[1]} short-chat"
       and abs(rec["anchor"]["base_median"] - 50.1) < 1e-6 and abs(rec["anchor"]["cand_median"] - 40.1) < 1e-6,
       f"through the litert-lm anchor on both sides, OK ({rec and rec['verdict']}, {anchor_cell(rec)}; "
       f"the moved mlx-swift anchor would have read +59.6 %)")
    rc, rec, line = run(world(same, same, lrt, lrt, mlx_cand_vals=(100, 101)), anchors_path)
    ok(rec and rec["verdict"] == "IMPROVED" and anchor_cell(rec) == f"{MLX[0]} {MLX[1]} short-chat",
       f"the same rows with the mlx-swift anchor unmoved: its own drift normalizes, IMPROVED "
       f"({rec and rec['verdict']}, {anchor_cell(rec)})")

    print("--- (h) both anchors moved (the Mac swap)")
    rc, rec, line = run(world(same, (MLX_V2, STAMP, ""), lrt, ("v0.19.0", LRT_STAMP2, LRT_ART)), anchors_path)
    ok(rec and rec["verdict"] == "INFO-ONLY" and f"engine_version {MLX_V1} -> {MLX_V2}" in line
       and f"harness_stamp {STAMP} -> {LRT_STAMP2}" in line,
       f"INFO-ONLY, both moves named ({rec and rec['verdict']})")

    print("--- (i) the first anchor usable on one side only")
    rows = world(same, same, lrt, lrt, mlx_cand_vals=(160,))
    rc, rec, line = run(rows, anchors_path)
    ok(rec and rec["verdict"] == "OK" and anchor_cell(rec) == f"{LRT[0]} {LRT[1]} short-chat"
       and abs(rec["anchor"]["base_median"] - 50.1) < 1e-6,
       f"both sides through the litert-lm anchor (n=1 mlx-swift on the candidate side), OK "
       f"({rec and rec['verdict']}, {anchor_cell(rec)}, base anchor "
       f"{rec and (rec.get('anchor') or {}).get('base_median')}; one per side would read +300 %)")

    print("--- (j) the engine under test's own anchor stays excluded")
    mlx_payload = ("mlx-swift", "mlx-community/gemma-4-e2b-it-4bit")
    label = f"{DEVICE} {mlx_payload[0]} {mlx_payload[1]} short-chat warm"
    rows = world(same, same, lrt, lrt, payload=mlx_payload,
                 payload_idents=((MLX_V1, STAMP, ""), (MLX_V2, STAMP, "")))
    rc, rec, line = run(rows, anchors_path, eut="mlx-swift", label=label)
    ok(rec and rec["verdict"] == "OK" and anchor_cell(rec) == f"{LRT[0]} {LRT[1]} short-chat",
       f"an mlx-swift payload goes through the litert-lm anchor ({rec and rec['verdict']}, {anchor_cell(rec)})")
    rows = world(same, same, lrt, ("v0.19.0", LRT_STAMP2, LRT_ART), payload=mlx_payload,
                 payload_idents=((MLX_V1, STAMP, ""), (MLX_V2, STAMP, "")))
    rc, rec, line = run(rows, anchors_path, eut="mlx-swift", label=label)
    ok(rec and rec["verdict"] == "INFO-ONLY" and f"harness_stamp {STAMP} -> {LRT_STAMP2}" in line,
       f"the litert-lm anchor moved and the mlx-swift one is the engine under test: INFO-ONLY "
       f"({rec and rec['verdict']})")

    print("--- (k) a same-day pair takes no anchor")
    rc, rec, line = run(world(same, (MLX_V2, STAMP, ""), cand_day=BASE_DAY), anchors_path)
    ok(rec and rec["verdict"] == "REGRESSION" and "anchor" not in rec and rc == 1,
       f"the raw -20 % is the verdict, exit 1 ({rec and rec['verdict']}, rc {rc})")

    print("--- (l) all candidate runs failed the text check")
    base = [dict(row("camp-base-mac", BASE_DAY, PAYLOAD, v, same), text_check="PASS")
            for v in (100, 101, 102)]
    cand = [dict(row("camp-cand-mac", BASE_DAY, PAYLOAD, v, same), text_check="FAIL:off-task")
            for v in (100, 101, 102)]
    rc, _, line = run(base + cand, None)
    ok(rc == 1 and line.startswith("TEXT-FAIL") and "candidate: 3 of 3" in line,
       "TEXT-FAIL for the candidate, exit 1")

    print("--- (m) one candidate outlier failed the text check")
    cand = [dict(r, text_check="PASS") for r in cand]
    outlier = dict(cand[0], decode_tps="150", text_check="FAIL:off-task")
    rc, rec, line = run(base + cand + [outlier], None)
    ok(rc == 0 and rec and rec["verdict"] == "OK" and rec["cand_n"] == 3
       and "text check FAIL left out: baseline 0/3, candidate 1/4" in line,
       "OK from the three passing candidate runs, with the exclusion printed")

    if _fails:
        print(f"\n{len(_fails)} failure(s); temp dir kept: {tmp}")
        return 1
    shutil.rmtree(tmp)
    print("\nselftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
