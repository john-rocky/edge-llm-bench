#!/usr/bin/env python3
"""Hand-run catalog int4-vs-int8 sitting on the Galaxy S26, the way the
dashboard job does a sitting (scripts/dashboard_job.py attempt()): preflight,
hold, anchors.cells as its own campaign, admission, the payload, admission
re-judged on the payload's own anchor, SESSION.json in both dirs; then the
./bench profile pair into the same campaign dir. Never a dashboard-v1 campaign
name, so the weekly slot logic does not see it."""
import json, os, subprocess, sys, time
ROOT = "/Users/majimadaisuke/code/edge-llm-bench"
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import dashboard_job as dj  # noqa: E402

KEY = "s26"
DATE = time.strftime("%Y-%m-%d")
BASE = f"{DATE}-catalog-int4-vs-int8-{KEY}"
CELLS = "matrices/catalog-int4-vs-int8-android.cells"
PROFILE_CELLS = "matrices/catalog-int4-vs-int8-android-profile.cells"
NOTE = ("hand-run catalog X1/K1 session (int4-vs-int8 GPU pairs); admission by "
        "scripts/dashboard_job.admit, sitting driven like dashboard_job.attempt()")

schedule = json.load(open(dj.SCHEDULE))
dev = schedule["devices"][KEY]
platform = "android"
started = time.strftime("%F %T")
os.chdir(ROOT)
info = dj.preflight_android(dev, False)          # raises Busy / NotReady
dj.log("preflight ok")
hold = dj.hold_acquire(schedule, dev)
env = dj.device_env(dev)
rc_all = 0
try:
    anchor_camp = f"{BASE}-anchor"
    anchor_rel = dj.campaign_rel(anchor_camp, platform)
    rc = dj.run_matrix(schedule["anchors"], platform, anchor_camp, env, 45 * 60, False)
    admitted, reason, details = dj.admit(schedule, dev, anchor_rel, platform)
    dj.write_session(anchor_rel, {"campaign": anchor_rel, "phase": "anchor",
                                  "cells": schedule["anchors"], "device_key": KEY,
                                  "device_display": dev["display"],
                                  "device_identifier": dev["identifier"],
                                  "platform": platform, "attempt": 1,
                                  "started": started, "ended": time.strftime("%F %T"),
                                  "admitted": admitted,
                                  "verdict": "ADMITTED" if admitted else "ABORTED",
                                  "reason": reason, "anchor": details, "note": NOTE,
                                  "runner_exit": rc, **dj.campaign_notes(anchor_rel)})
    dj.log(f"admission: {'ADMITTED' if admitted else 'ABORTED'} — {reason}")
    if not admitted:
        sys.exit(4)

    rel = dj.campaign_rel(BASE, platform)
    rc = dj.run_matrix(CELLS, platform, BASE, env, 4 * 3600, False)
    expected, have = dj.cells_with_records(rel, CELLS, platform, dev["identifier"])
    own_ok, own_reason, own_details = dj.admit(schedule, dev, rel, platform)
    verdict = "TIMEOUT" if rc == 124 else "COMPLETED"
    dj.write_session(rel, {"campaign": rel, "phase": "payload", "cells": CELLS,
                           "device_key": KEY, "device_display": dev["display"],
                           "device_identifier": dev["identifier"], "platform": platform,
                           "attempt": 1, "started": started, "ended": time.strftime("%F %T"),
                           "admitted": bool(own_ok), "verdict": verdict, "reason": own_reason,
                           "anchor": own_details, "note": NOTE, "anchor_phase": anchor_rel,
                           "runner_exit": rc, "cells_expected": expected,
                           "cells_with_records": have, **dj.campaign_notes(rel)})
    dj.log(f"payload: {verdict}, records {have}/{expected}, admitted={own_ok} — {own_reason}")
    rc_all = rc

    # the per-op pair, same campaign dir (profiles/), after the speed rows
    cmd = [os.path.join(ROOT, "bench"), "profile", PROFILE_CELLS, "--campaign", BASE]
    dj.log("$ " + " ".join(cmd))
    e = dict(os.environ); e.update(env); e["PYTHONUNBUFFERED"] = "1"
    p = subprocess.run(cmd, env=e, cwd=ROOT)
    dj.log(f"bench profile exit {p.returncode}")
    rc_all |= p.returncode
finally:
    dj.hold_release(hold)
dj.log(f"=== done rc={rc_all}")
