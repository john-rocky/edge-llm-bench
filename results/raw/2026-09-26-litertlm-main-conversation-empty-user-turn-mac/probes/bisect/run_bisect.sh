#!/bin/bash
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin
export GIT_LFS_SKIP_SMUDGE=1
S=/private/tmp/claude-501/-Users-majimadaisuke-code-edge-llm-bench/298ce1ca-383c-4dd7-939a-363aeef8d8bc/scratchpad/capi
cd ~/code/litert-lm-bisect-wt || exit 1
echo "### CMD: git bisect start 1dadd00c e9fd8c53 && git bisect run bisect_step.sh   # $(date '+%F %T %Z')" >> "$S/runlog.log"
git bisect start 1dadd00c e9fd8c53 >> "$S/bisect/bisect.log" 2>&1
git bisect run "$S/bisect/bisect_step.sh" >> "$S/bisect/bisect_run.log" 2>&1
echo "BISECT RUN EXIT=$? $(date '+%T')" >> "$S/bisect/bisect.log"
git bisect log >> "$S/bisect/bisect_gitlog.txt" 2>&1
