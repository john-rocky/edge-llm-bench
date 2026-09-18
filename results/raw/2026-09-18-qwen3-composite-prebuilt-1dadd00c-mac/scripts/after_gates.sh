#!/bin/zsh
# After run_all.sh (2026-09-18): the 0.6B 12-flag export scored 6/8 on Metal (capital → "东京.", rhyme → "violets") against 7/8
# for the published 11-flag file on the same dylib (rhyme only). Two separations, one process per question:
#   (a) the flag-only control (11 flags at 1e2d37f) on the new dylib, Metal — same exporter drift, no prefill composite;
#   (b) the 12-flag file on the CPU path (--backend=cpu, XNNPACK; the composites run decomposed there) — is "东京" in the graph
#       or in the Metal path? (09-17: the published 11-flag file on CPU missed the same prompt with "Hachioji.")
set -u
S=${S:?}; PY=$HOME/venvs/lt094dev/bin/python3; [ -x "$PY" ] || PY=python3
NEW=$S/run-1dadd00c; M=$S/models; RUNLOG=$S/legs/runlog.txt
echo "=== after_gates start $(date '+%F %T')  load=$(uptime | sed 's/.*load averages: //')"
echo "### CMD: python3 gate8q_adv.py --run $NEW --label new_06b_11n --json $S/legs/gate8q_new_06b_11n.json $M/p1024_06b_11flags_1e2d37f/model.litertlm  # $(date '+%F %T')" >> $RUNLOG
$PY $S/scripts/gate8q_adv.py --run $NEW --label new_06b_11n --json $S/legs/gate8q_new_06b_11n.json $M/p1024_06b_11flags_1e2d37f/model.litertlm 2>&1 | tail -10
echo "### CMD: python3 gate8q_adv_backend.py --backend cpu --run $NEW --label cpu_06b_12 --json $S/legs/gate8q_cpu_06b_12.json $M/p1024_06b_12flags/model.litertlm  # $(date '+%F %T')" >> $RUNLOG
$PY $S/scripts/gate8q_adv_backend.py --backend cpu --run $NEW --label cpu_06b_12 --json $S/legs/gate8q_cpu_06b_12.json $M/p1024_06b_12flags/model.litertlm 2>&1 | tail -10
echo "=== after_gates done $(date '+%F %T')"
