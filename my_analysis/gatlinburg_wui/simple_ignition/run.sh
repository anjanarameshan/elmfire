#!/bin/bash
# SIMPLE (probabilistic) ember ignition, observed spot point, 3 seeds; otherwise identical to ms_st09/spot2.
cd "$(dirname "$0")/.."
for s in 1 2 3; do IGN_MODEL=SIMPLE PIGN=90 scripts/run_wui_case.sh simple_ignition/spot2 $s 16 & done; wait
echo "all runs finished $(date +%H:%M)"
