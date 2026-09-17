#!/usr/bin/env bash
# Submit request.json to Device Run (or resume an existing operation), wait, pull the
# session directory, decode the LiteRT-LM metrics protos and print the numbers.
#   run_session.sh post                      # POST request.json (billed), then poll/pull/decode
#   run_session.sh resume <operation-name>   # skip the POST; poll/pull/decode an existing operation
# C (output dir), PROJECT, BUCKET, PROTO_DIR can be overridden in the environment.
set -euo pipefail
C=${C:-results/raw/2026-09-17-ddp-litert-lm-caiman-35}
PROJECT=${PROJECT:-litert-edge-portal}
BUCKET=${BUCKET:-gs://litert-edge-portal-devicerun}
# PROTO_DIR holds runtime/proto/litert_lm_metrics.proto and runtime/proto/engine.proto from the LiteRT-LM tag that
# built the binary (git show v0.17.0:runtime/proto/<file> > $PROTO_DIR/runtime/proto/<file>).
PROTO_DIR=${PROTO_DIR:-$HOME/code/LiteRT-LM}
BASE=https://devicerun.googleapis.com/v1alpha
API=$BASE/projects/$PROJECT/locations/global
MODE=${1:-}
mkdir -p "$C"
token() { gcloud auth print-access-token; }

case "$MODE" in
  post)
    echo "### CMD: curl -s -X POST -H 'Authorization: Bearer \$TOKEN' -H 'Content-Type: application/json' -d @$C/request.json $API/sessions | tee $C/operation-create.json"
    date '+# submitted %Y-%m-%d %H:%M:%S %Z'
    curl -s -X POST -H "Authorization: Bearer $(token)" -H "Content-Type: application/json" -d @"$C/request.json" "$API/sessions" | tee "$C/operation-create.json"; echo
    OP=$(python3 -c "import json; print(json.load(open('$C/operation-create.json'))['name'])")
    ;;
  resume)
    OP=$2
    ;;
  *) echo "usage: $0 post | resume <operation-name>" >&2; exit 2;;
esac
echo "OP=$OP"

echo "### CMD: until curl -s -H 'Authorization: Bearer \$TOKEN' $BASE/\$OP | tee $C/operation.json | grep -q '\"done\": true'; do sleep 30; done"
n=0
until curl -s -H "Authorization: Bearer $(token)" "$BASE/$OP" | tee "$C/operation.json" | grep -q '"done": true'; do
  n=$((n+1)); echo "poll $n $(date '+%H:%M:%S') not done"; sleep 30
done
date '+# done %Y-%m-%d %H:%M:%S %Z'
python3 - "$C/operation.json" <<'PY'
import json, sys
o = json.load(open(sys.argv[1]))
m = o["metadata"]; print("createTime", m.get("createTime"), "endTime", m.get("endTime"), "target", m.get("target"))
r = o["response"]["sessionReport"]
print("result", r.get("result"), r.get("startTime"), r.get("endTime"))
for j in r.get("jobReports", []):
    for e in j.get("executionReports", []):
        print(" exec", e.get("id"), e.get("startTime"), e.get("endTime"), e.get("result"))
        for f in e.get("outputFiles", []):
            print("  ", f["gcsOutputFile"]["path"])
PY
S=$(python3 -c "import json; print(json.load(open('$C/operation.json'))['metadata']['target'].split('/')[-1])")
echo "S=$S"
echo "### CMD: curl -s -H 'Authorization: Bearer \$TOKEN' $API/sessions/$S | tee $C/session.json"
curl -s -H "Authorization: Bearer $(token)" "$API/sessions/$S" > "$C/session.json"
echo "### CMD: gsutil -m -q cp -r $BUCKET/automation/sessions/$S/ $C/ddp-session/"
mkdir -p "$C/ddp-session" && gsutil -m -q cp -r "$BUCKET/automation/sessions/$S/" "$C/ddp-session/"
echo "### CMD: find $C/ddp-session -type f | sort"
find "$C/ddp-session" -type f | sort
for pb in $(find "$C/ddp-session" -name 'metrics_*.pb' | sort); do
  echo "### CMD: protoc --proto_path=$PROTO_DIR --decode=litert.lm.proto.LitertLmMetricsList runtime/proto/litert_lm_metrics.proto < $pb"
  (cd "$PROTO_DIR" && protoc --proto_path=. --decode=litert.lm.proto.LitertLmMetricsList runtime/proto/litert_lm_metrics.proto < "$OLDPWD/$pb")
done
for log in $(find "$C/ddp-session" -name '*.log' -path '*output*' | sort); do
  echo "### CMD: grep -E 'Time to first token|Prefill Turn|Prefill Speed|Decode Turn|Decode Speed|Init Total|Peak' $log"
  grep -E 'Time to first token|Prefill Turn|Prefill Speed|Decode Turn|Decode Speed|Init Total|Peak' "$log" || true
done
for x in $(find "$C/ddp-session" -name '*.exit' | sort); do echo "$x: $(cat "$x")"; done
