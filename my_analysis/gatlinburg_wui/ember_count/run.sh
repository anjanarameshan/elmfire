#!/bin/bash
# Non-burnable buildings, ms_st09 ember model (PER-MW, EMPIRICAL, Eulerian, PHYSICAL), 16 h, 10 seeds per location.
# ember_flux on each cell = embers landed per 30 m cell, building cells included.
# Usage: ember_count/run.sh [LOCATION ...]   (default: spot2 and the four 1 km shifts)
cd "$(dirname "$0")/.."
for loc in ${@:-spot2 spot2_N1km spot2_S1km spot2_E1km spot2_W1km}; do
  mkdir -p ember_count/nobldg/$loc; ln -sfn $(pwd)/ms_st09/$loc/inputs ember_count/nobldg/$loc/inputs
  for s in 1 2 3 4 5 6 7 8 9 10; do
    BLDG_SPREAD=.FALSE. scripts/run_wui_case.sh ember_count/nobldg/$loc $s 16 > /dev/null &
  done; wait; echo "$loc done"
done
