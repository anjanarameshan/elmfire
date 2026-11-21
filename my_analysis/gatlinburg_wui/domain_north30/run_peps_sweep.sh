#!/bin/bash
# P_EPS = 0.01 (ELMFIRE namelist default; earlier runs 0.001) with the forest ember threshold (variant build
# elmfire_1.1_threshold), plus a ground-fire-only run (spotting off via CRITFLIN 1e9). All dump crown fire,
# spread rate and flame length (GROUND_OUT=1). Same domain and inputs as the threshold sweep.
# Usage: domain_north30/run_peps_sweep.sh   (from gatlinburg_wui). Folders p01thrN/ (0.001 -> p01thr0p001), groundonly/.
cd "$(dirname "$0")/.."
EXE=$(cd ../elmfire_variant/build/linux/bin && pwd)/elmfire_1.1_threshold
for N in ${VALUES:-0.00001 0.0001 0.0003 0.0005 0.001}; do
  (C=domain_north30/p01thr$(echo $N | sed 's/\./p/')/spot2; mkdir -p $C; ln -sfn ../../inputs_spot2 $C/inputs
   for S in 1 2 3; do
     ELMFIRE_EXE=$EXE ELMFIRE_VEG_EMBER_THRESHOLD=$N PEPS=0.01 GROUND_OUT=1 scripts/run_wui_case.sh $C $S 16 > /dev/null 2>&1
     echo "P_EPS 0.01 threshold $N seed $S: $(tail -1 $C/seed_$S/outputs/acres_*.csv | awk -F, '{printf "%.0f", $2}') ac at 16 h" | tee -a $C/seed_$S/elmfire.log
   done) &
done
(C=domain_north30/groundonly/spot2; mkdir -p $C; ln -sfn ../../inputs_spot2 $C/inputs
 CRITFLIN=1E9 GROUND_OUT=1 scripts/run_wui_case.sh $C 1 16 > /dev/null 2>&1
 echo "ground fire only seed 1: $(tail -1 $C/seed_1/outputs/acres_*.csv | awk -F, '{printf "%.0f", $2}') ac at 16 h") &
wait
