#!/bin/bash
# Ember-load threshold for forest (DIFF_WILDLAND_IGNITION = .FALSE.) with a sweep of EMBER_GR_PER_MW_VEGE
# (ELMFIRE default 33.3 g/MW; ember_tests/B_eulerian_physical with the default died at 23.6 ac).
# Same domain and inputs as the delay sweep (extended 10.2 km north, no barriers, default CELL_IGNITION_DELAY).
# Usage: domain_north30/run_egen_sweep.sh   (from gatlinburg_wui); the 4 values run in parallel, seeds 1-3 in turn.
cd "$(dirname "$0")/.."
for G in 100 300 1000 3000; do
  (C=domain_north30/egen$(printf %04d $G)/spot2; mkdir -p $C; ln -sfn ../../inputs_spot2 $C/inputs
   for S in 1 2 3; do
     t0=$(date +%s)
     DIFF_WILD=.FALSE. EMBER_VEGE=$G scripts/run_wui_case.sh $C $S 16 > /dev/null 2>&1
     echo "egen $G seed $S finished in $(( ($(date +%s)-t0)/60 )) min, $(tail -1 $C/seed_$S/outputs/acres_*.csv | awk -F, '{printf "%.0f", $2}') ac at 16 h" | tee -a $C/seed_$S/elmfire.log
   done) &
done
wait
