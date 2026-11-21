#!/bin/bash
# Run 01-run.sh for several spread-rate adjustment factors; each result is saved in results_adj<F>/
cd "$(dirname "$0")"
for F in "$@"; do
   S=$(date +%s)
   ADJ_FACTOR=$F ./01-run.sh > run_adj$F.log 2>&1
   rm -rf results_adj$F; mkdir -p results_adj$F
   cp -r outputs results_adj$F/; mv run_adj$F.log results_adj$F/run.log
   echo "adj=$F finished in $(( ($(date +%s)-S)/60 )) min: $(tail -1 results_adj$F/run.log)" >> sweep.log
done
