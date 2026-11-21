#!/bin/bash
# Forest ember-load threshold sweep (variant build elmfire_1.1_threshold, env ELMFIRE_VEG_EMBER_THRESHOLD =
# accumulated embers per m2 a forest cell needs before it can be ignited by embers; buildings unchanged).
# Same domain and inputs as the delay sweep (extended 10.2 km north, no barriers, default ember generation and delay).
# Usage: [VALUES="0.01 0.1"] domain_north30/run_threshold_sweep.sh   (from gatlinburg_wui); values run in parallel,
# seeds 1-3 in turn. Folder thrN/ with the dot as p (0.01 -> thr0p01).
cd "$(dirname "$0")/.."
EXE=$(cd ../elmfire_variant/build/linux/bin && pwd)/elmfire_1.1_threshold
for N in ${VALUES:-1 10 100 1000}; do
  (C=domain_north30/thr$(echo $N | sed 's/^[0-9]*$/000&/; s/^0*\([0-9]\{4\}\)$/\1/; s/\./p/')/spot2; mkdir -p $C; ln -sfn ../../inputs_spot2 $C/inputs
   for S in 1 2 3; do
     t0=$(date +%s)
     ELMFIRE_EXE=$EXE ELMFIRE_VEG_EMBER_THRESHOLD=$N scripts/run_wui_case.sh $C $S 16 > /dev/null 2>&1
     echo "threshold $N seed $S finished in $(( ($(date +%s)-t0)/60 )) min, $(tail -1 $C/seed_$S/outputs/acres_*.csv | awk -F, '{printf "%.0f", $2}') ac at 16 h" | tee -a $C/seed_$S/elmfire.log
   done) &
done
wait
