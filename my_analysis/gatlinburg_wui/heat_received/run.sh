#!/bin/bash
# Heat received by building cells: ember_calibration/x100 set-up (ember generation x100), spot fire 2, 16 h,
# with DUMP_TOTAL_DFC_RECEIVED and DUMP_TOTAL_RAD_RECEIVED on. Usage: heat_received/run.sh [SEEDS (default 1)]
cd "$(dirname "$0")/.."
for s in ${1:-1}; do
  HEAT_OUT=1 EMBER_VEGE=3330 EMBER_BLDG=1000 scripts/run_wui_case.sh heat_received/x100/spot2 $s 16 &
done; wait
echo "all runs finished $(date +%H:%M)"
