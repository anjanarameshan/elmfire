#!/bin/bash
# Robustness runs, started after the ignition_pathway batch (49 lines in its log).
cd "$(dirname "$0")/.."
while [ "$(wc -l < ignition_pathway/run_all.log)" -lt 49 ]; do sleep 60; done
# Hamada building model (type 1), original ELMFIRE binary, 5 locations x 10 seeds
for L in spot2 spot2_N1km spot2_S1km spot2_E1km spot2_W1km; do for s in $(seq 1 10); do
  [ $L = spot2 ] && [ $s = 1 ] && continue; echo "hamada/$L $s 1 orig"; done; done > robustness/joblist.txt
# building fuel classes ST10-12 (WU-E), pathway build, observed location x 10 seeds
for FM in 10 11 12; do for s in $(seq 1 10); do echo "bldg_ST$FM/spot2 $s 2 path"; done; done >> robustness/joblist.txt
cat robustness/joblist.txt | xargs -P 4 -L 1 sh -c '
  if [ "$3" = path ]; then export ELMFIRE_EXE=/home/anjana/elmfire-1/my_analysis/elmfire_variant/build/linux/bin/elmfire_1.1_pathway; fi
  BLDG_TYPE=$2 scripts/run_wui_case.sh robustness/$0 $1 16 > /dev/null 2>&1; echo "$0 $1 done"' >> robustness/run_all.log 2>&1
echo "queue finished"
