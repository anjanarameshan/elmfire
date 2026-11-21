#!/bin/bash
# Ember generation calibration: ms_st09/spot2 set-up (Eulerian, PHYSICAL ignition, any-ember vegetation), observed spot
# point, 16 h, ember mass per MW scaled x10 / x30 / x100 for vegetation (default 33.3 g/MW) and buildings (default 10 g/MW).
# Usage: [FACTORS="10 30 100"] ember_calibration/run.sh [SEEDS (default 1)]
cd "$(dirname "$0")/.."
for f in ${FACTORS:-10 30 100}; do
  for s in ${1:-1}; do
    EMBER_VEGE=$(python3 -c "print(33.3*$f)") EMBER_BLDG=$((10 * f)) scripts/run_wui_case.sh ember_calibration/x$f/spot2 $s 16 &
  done
done; wait
echo "all runs finished $(date +%H:%M)"
