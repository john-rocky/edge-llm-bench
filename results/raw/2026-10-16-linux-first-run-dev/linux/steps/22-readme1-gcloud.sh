# README step 1, gcloud, as dev. Signed in = the Mac's gcloud config copied in by the driver (`gcloud auth login`
# needs a browser: not run here); the project set as README.md line 103 prints it; the token checked without
# printing it; the bucket's input prefix listed (read only).
gcloud config set project litert-edge-portal || exit 1
printf '## core/project = %s\n' "$(gcloud config get-value project 2>/dev/null)"
gcloud auth print-access-token > /dev/null && echo TOKEN_OK || exit 1
gcloud storage ls gs://litert-edge-portal-devicerun/automation/inputs/edge-llm-bench/ || exit 1
