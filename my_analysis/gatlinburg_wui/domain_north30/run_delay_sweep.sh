#!/bin/bash
# CELL_IGNITION_DELAY sweep on the domain extended 10.2 km north (original ELMFIRE build, observed spot fire 2).
# Usage: domain_north30/run_delay_sweep.sh   (from gatlinburg_wui)
cd "$(dirname "$0")/.."
for D in 100 300 600 1200 1800; do
  C=domain_north30/delay$(printf %04d $D)/spot2; mkdir -p $C; ln -sfn ../../inputs_spot2 $C/inputs
  for S in 1 2 3; do
    t0=$(date +%s)
    if [ $D = 100 ]; then scripts/run_wui_case.sh $C $S 16 > /dev/null 2>&1
    else IGN_DELAY=$D scripts/run_wui_case.sh $C $S 16 > /dev/null 2>&1; fi
    echo "delay $D seed $S finished in $(( ($(date +%s)-t0)/60 )) min" | tee -a $C/seed_$S/elmfire.log
  done
done
