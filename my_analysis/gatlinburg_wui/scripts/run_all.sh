#!/bin/bash
# Run the ensemble: NSEEDS seeds (default 10) for each case - observed spot fire 2 and the
# same spot moved 1 km N, S, E, W - so every case has the same number of runs.
# Usage: run_all.sh TAG [PARALLEL] [NSEEDS]
TAG=$1; PAR=${2:-4}; NSEEDS=${3:-10}
cd "$(dirname "$0")/.."
jobs_list=()
for c in spot2 spot2_N1km spot2_S1km spot2_E1km spot2_W1km; do for s in $(seq 1 $NSEEDS); do jobs_list+=("$TAG/$c $s"); done; done
for j in "${jobs_list[@]}"; do
   while [ $(pgrep -fc "run_wui_case.sh") -ge $PAR ]; do sleep 10; done
   set -- $j
   scripts/run_wui_case.sh $1 $2 16 > /dev/null 2>&1 &
   sleep 2
done
wait
echo "all runs finished $(date -u +%H:%M)"
