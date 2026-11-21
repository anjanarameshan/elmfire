#!/bin/bash
# Ember-ignition hardening factor test: ms_st09/spot2 set-up (Eulerian, PHYSICAL, default ember generation), observed
# spot point, 16 h; only HARDENING_FACTOR of ST09 changed in a copy of building_fuel_models.csv (default 7.0).
# Usage: hardening/run.sh H [SEEDS (default "1 2 3")]   (inputs folder hardening/H<H>/spot2/inputs must exist)
cd "$(dirname "$0")/.."
for s in ${2:-1 2 3}; do scripts/run_wui_case.sh hardening/H$1/spot2 $s 16 & done; wait
echo "H=$1 runs finished $(date +%H:%M)"
