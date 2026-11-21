#!/bin/bash
# Run one ELMFIRE realisation with non-burnable buildings and the older (superseded) stochastic
# spotting model, as in Theodori et al. (2026, Tubbs; supplementary Tables S1-S2), to get the
# number of ember landings on every cell, including building cells that never burn.
# Usage: run_ember_count.sh CASE_DIR SEED HOURS
#   CASE_DIR/inputs must hold the rasters from build_wui_inputs.py (same as run_wui_case.sh).
#   Output: CASE_DIR/seed_<SEED>/outputs/ember_flux (landings per cell, summed over the run) and
#   time of arrival / flame length.
# Differences from run_wui_case.sh:
#   - USE_BLDG_SPREAD_MODEL = .FALSE.: building cells (fuel 91) are non-burnable, no house-to-house spread
#   - USE_SUPERSEDED_SPOTTING = .TRUE.: each landing adds 1 to EMBER_FLUX on the landing cell
#     (elmfire_spotting_superseded.f90), whatever the fuel there, so EMBER_FLUX is a landing count
#   - STOCHASTIC_SPOTTING: per run, crown cells 1-2 %, surface cells 0.1-1 % of cells above 1000 kW/m
#     throw 1-5 embers; PIGN 100 % (first ember on vegetation ignites). Theodori's values.
#     Lognormal distance parameters are not given in their tables; the ELMFIRE guide example
#     (p. 31-32) is used: mean 5-10, normalised variance 250-600, wind exp 0.4-0.7, intensity exp 0.2-0.4.
#   env CRITFLIN=<kW/m>: CRITICAL_SPOTTING_FIRELINE_INTENSITY (default 1000 as in Theodori; Gatlinburg fires rarely
#   pass 1000 kW/m, so 0 is needed for embers to be thrown at all, as in ms_st09)
#   env SURF_PCT=<lo,hi>, CROWN_PCT=<lo,hi>: percent of igniting cells that throw embers (defaults 0.1,1.0 and
#   1.0,2.0 as in Theodori). Each cell gets one chance, when it ignites (elmfire_level_set.f90 ~1229).
set -e
CASE=$(cd "$1" && pwd); SEED=$2; HOURS=$3
SPCT=${SURF_PCT:-0.1,1.0}; CPCT=${CROWN_PCT:-1.0,2.0}
export ELMFIRE_BASE_DIR=$(cd "$(dirname "$0")/../../.." && pwd)
BIN=$ELMFIRE_BASE_DIR/build/linux/bin
case ":$PATH:" in *":$BIN:"*) ;; *) export PATH=$PATH:$BIN ;; esac
. "$ELMFIRE_BASE_DIR/tutorials/functions/functions.sh"
set_elmfire_version

RUN=$CASE/seed_$SEED
rm -rf $RUN; mkdir -p $RUN/outputs $RUN/scratch
ln -s $CASE/inputs $RUN/inputs
cat > $RUN/elmfire.data <<EOF
&INPUTS
FUELS_AND_TOPOGRAPHY_DIRECTORY = './inputs'
LANDSCAPE_FILENAME             = 'landscape'
ADJ_FILENAME                   = 'adj'
PHI_FILENAME                   = 'phi'
DT_METEOROLOGY                 = 3600.0
WEATHER_DIRECTORY              = './inputs'
WS_FILENAME                    = 'ws'
WD_FILENAME                    = 'wd'
M1_FILENAME                    = 'm1'
M10_FILENAME                   = 'm10'
M100_FILENAME                  = 'm100'
USE_CONSTANT_LH                = .FALSE.
MLH_FILENAME                   = 'lh'
USE_CONSTANT_LW                = .FALSE.
MLW_FILENAME                   = 'lw'
/
&OUTPUTS
OUTPUTS_DIRECTORY      = './outputs'
DTDUMP                 = 3600.
DUMP_FLIN              = .TRUE.
DUMP_FLAME_LENGTH      = .TRUE.
DUMP_TIME_OF_ARRIVAL   = .TRUE.
DUMP_SURFACE_FIRE      = .TRUE.
DUMP_TRANSIENT_ACREAGE = .TRUE.
DUMP_EMBER_FLUX        = .TRUE.
ACCUMULATE_EMBER_FLUX  = .TRUE.
CONVERT_TO_GEOTIFF     = .TRUE.
/
&TIME_CONTROL
SIMULATION_DT    = 30.0
TARGET_CFL       = 0.4
SIMULATION_TSTOP = $((HOURS * 3600))
/
&SIMULATOR
NUM_IGNITIONS = 0
/
&SPOTTING
ENABLE_SPOTTING                          = .TRUE.
USE_SUPERSEDED_SPOTTING                  = .TRUE.
STOCHASTIC_SPOTTING                      = .TRUE.
ENABLE_SURFACE_FIRE_SPOTTING             = .TRUE.
SPOTTING_DISTRIBUTION_TYPE               = 'LOGNORMAL'
CRITICAL_SPOTTING_FIRELINE_INTENSITY(:)  = 304*${CRITFLIN:-1000.}
CROWN_FIRE_SPOTTING_PERCENT_MIN          = ${CPCT%,*}
CROWN_FIRE_SPOTTING_PERCENT_MAX          = ${CPCT#*,}
GLOBAL_SURFACE_FIRE_SPOTTING_PERCENT_MIN = ${SPCT%,*}
GLOBAL_SURFACE_FIRE_SPOTTING_PERCENT_MAX = ${SPCT#*,}
NEMBERS_MIN                              = 1
NEMBERS_MAX_LO                           = 5
NEMBERS_MAX_HI                           = 5
MEAN_SPOTTING_DIST_MIN                   = 5.0
MEAN_SPOTTING_DIST_MAX                   = 10.0
NORMALIZED_SPOTTING_DIST_VARIANCE_MIN    = 250.0
NORMALIZED_SPOTTING_DIST_VARIANCE_MAX    = 600.0
SPOT_WS_EXP_LO                           = 0.4
SPOT_WS_EXP_HI                           = 0.7
SPOT_FLIN_EXP_LO                         = 0.2
SPOT_FLIN_EXP_HI                         = 0.4
PIGN_MIN                                 = 100.0
PIGN_MAX                                 = 100.0
/
&WUI
USE_BLDG_SPREAD_MODEL = .FALSE.
/
&MISCELLANEOUS
MISCELLANEOUS_INPUTS_DIRECTORY = './inputs'
PATH_TO_GDAL                   = 'auto'
SCRATCH                        = './scratch'
/
&MONTE_CARLO
SEED = $SEED
/
EOF
cd $RUN
START=$(date +%s)
elmfire_$ELMFIRE_VER ./elmfire.data > elmfire.log 2>&1 || echo "ELMFIRE exit code $?" >> elmfire.log
echo "seed $SEED finished in $(( ($(date +%s) - START) / 60 )) min" >> elmfire.log
tail -1 elmfire.log
