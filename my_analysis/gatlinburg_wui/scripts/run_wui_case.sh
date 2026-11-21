#!/bin/bash
# Run one ELMFIRE realisation of a Gatlinburg ember / structure-ignition case.
# Usage: run_wui_case.sh CASE_DIR SEED HOURS
#   env PHYS_DUR=1: USE_PHYSICAL_SPOTTING_DURATION (guide 1.11.1) - burning cells emit embers for a
#   physically derived time (vegetation: cell size / local spread rate; buildings: HRR curve)
#   instead of the fixed TAU_EMBERGEN
#   CASE_DIR/inputs must hold the rasters from build_wui_inputs.py.
#   Output goes to CASE_DIR/seed_<SEED>/ (time of arrival, ember flux, hourly burned area).
# Ember model (ELMFIRE elmfire_spotting.f90): embers generated per MW of fire (PER-MW),
# empirical spotting distance, Eulerian accumulation on the grid, physical ignition criterion
# (UMD / De Beer: accumulated ember mass and local wind); buildings burn with the UCB/UMD
# building model (USE_BLDG_SPREAD_MODEL, type 2) using the building rasters.
set -e
CASE=$(cd "$1" && pwd); SEED=$2; HOURS=$3
[ "${PHYS_DUR:-0}" = 1 ] && PHYS=.TRUE. || PHYS=.FALSE.
#   env ACCUM=EULERIAN|LAGRANGIAN (default EULERIAN); DIFF_WILD=.TRUE.|.FALSE. (default .TRUE.: vegetation
#   ignites once any ember lands; .FALSE.: vegetation uses the same physical ember-load criterion as buildings);
#   BARRIERS=1 uses CASE_DIR/inputs/barrier.tif (road/river widths, guide 1.10)
ACCUM=${ACCUM:-EULERIAN}; DIFF_WILD=${DIFF_WILD:-.TRUE.}
BARR=""; [ "${BARRIERS:-0}" = 1 ] && BARR="USE_BARRIERS                   = .TRUE.
BARRIER_FILENAME               = 'barrier'"
#   env DTMAX=<s>: cap the adaptive time step (SIMULATION_DTMAX; ELMFIRE default 600 s when unset)
DTM=""; [ -n "${DTMAX:-}" ] && DTM="SIMULATION_DTMAX = ${DTMAX}"
#   env EMBER_CONS=1: USE_EMBER_CONSUMPTION (ember-pile burnout, De Beer model; ELMFIRE default off)
CONS=""; [ "${EMBER_CONS:-0}" = 1 ] && CONS="USE_EMBER_CONSUMPTION                    = .TRUE."
#   env SAMPLING=<n>: EMBER_SAMPLING_FACTOR, real embers per Lagrangian particle (default 2000 as in ms_st09)
SAMPLING=${SAMPLING:-2000.0}
#   env CRITFLIN=<kW/m>: CRITICAL_SPOTTING_FIRELINE_INTENSITY, cells below it emit no embers (default 0 as in ms_st09)
#   env TAU=<s>: TAU_EMBERGEN, seconds each burning cell emits embers (default 10 as in ms_st09)
#   env BLDG_TYPE=1|2: BLDG_SPREAD_MODEL_TYPE (1 = Hamada, 2 = UCB/UMD WU-E; default 2 as in ms_st09)
CRITFLIN=${CRITFLIN:-0.}   # written as 304*value: a single value after (:) fills only element 0 in a Fortran namelist
#   env IGN_DELAY=<s>: CELL_IGNITION_DELAY, time from ember ignition of a vegetation cell to a fully developed
#   burning cell (ELMFIRE default 100 s when unset); env LOCAL_IGN=<s>: LOCAL_IGNITION_TIME (default 30 s)
DELAY=""; [ -n "${IGN_DELAY:-}" ] && DELAY="CELL_IGNITION_DELAY                      = ${IGN_DELAY}"
LIGN=""; [ -n "${LOCAL_IGN:-}" ] && LIGN="LOCAL_IGNITION_TIME                      = ${LOCAL_IGN}"
#   env EMBER_VEGE=<g/MW>: EMBER_GR_PER_MW_VEGE, ember mass generated per MW of vegetation fire (ELMFIRE default 33.3)
EGEN=""; [ -n "${EMBER_VEGE:-}" ] && EGEN="EMBER_GR_PER_MW_VEGE                     = ${EMBER_VEGE}"
#   env EMBER_BLDG=<g/MW>: EMBER_GR_PER_MW_BLDG, ember mass generated per MW of building fire (ELMFIRE default 10)
EGENB=""; [ -n "${EMBER_BLDG:-}" ] && EGENB="EMBER_GR_PER_MW_BLDG                     = ${EMBER_BLDG}"
#   env PEPS=<p>: P_EPS, spotting-distance cutoff quantile (largest distance = 1 - P_EPS quantile; default 0.001 as in
#   ms_st09, ELMFIRE namelist default 0.01); env GROUND_OUT=1: also dump crown fire, spread rate and flame length
GOUT=""; [ "${GROUND_OUT:-0}" = 1 ] && GOUT="DUMP_CROWN_FIRE        = .TRUE.
DUMP_SPREAD_RATE       = .TRUE.
DUMP_FLAME_LENGTH      = .TRUE."
#   env HEAT_OUT=1: also dump total flame-contact and radiant heat received per cell (WU-E building model, final dump)
HOUT=""; [ "${HEAT_OUT:-0}" = 1 ] && HOUT="DUMP_TOTAL_DFC_RECEIVED = .TRUE.
DUMP_TOTAL_RAD_RECEIVED = .TRUE."
#   env IGN_MODEL=PHYSICAL|SIMPLE|DIRECT: IGNITION_MODEL (default PHYSICAL as in ms_st09). SIMPLE: any ember load
#   ignites with probability PIGN (vegetation) or the building table's P_IGNITION (buildings) over the ignition time;
#   env PIGN=<percent>: PIGN for vegetation (written only when set; ELMFIRE default 1 %)
#   env BLDG_SPREAD=.FALSE.: building model off, building cells (fuel 91) do not burn; embers still land and are
#   counted on them in ember_flux (elmfire_spotting.f90 ~725, no fuel check)
IGNM=${IGN_MODEL:-PHYSICAL}
PIGNL=""; [ -n "${PIGN:-}" ] && PIGNL="PIGN                                     = ${PIGN}
PIGN_MAX                                 = ${PIGN}
PIGN_MIN                                 = ${PIGN}"
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
BLDG_AREA_FILENAME             = 'bldg_area'
BLDG_FOOTPRINT_FRAC_FILENAME   = 'bldg_footprint_frac'
BLDG_FUEL_MODEL_FILENAME       = 'bldg_fuel_model'
BLDG_NONBURNABLE_FRAC_FILENAME = 'bldg_nonburnable_frac'
BLDG_SEPARATION_DIST_FILENAME  = 'bldg_separation'
$BARR
/
&OUTPUTS
OUTPUTS_DIRECTORY      = './outputs'
DTDUMP                 = 3600.
DUMP_FLIN              = .TRUE.
DUMP_TIME_OF_ARRIVAL   = .TRUE.
DUMP_SURFACE_FIRE      = .TRUE.
DUMP_TRANSIENT_ACREAGE = .TRUE.
DUMP_EMBER_FLUX        = .TRUE.
ACCUMULATE_EMBER_FLUX  = .TRUE.
DUMP_EMBER_IGNITION    = .TRUE.
CONVERT_TO_GEOTIFF     = .TRUE.
$GOUT
$HOUT
/
&TIME_CONTROL
SIMULATION_DT    = 30.0
TARGET_CFL       = 0.4
SIMULATION_TSTOP = $((HOURS * 3600))
$DTM
/
&SIMULATOR
NUM_IGNITIONS = 0
/
&SPOTTING
ENABLE_SPOTTING                          = .TRUE.
ENABLE_SURFACE_FIRE_SPOTTING             = .TRUE.
USE_SUPERSEDED_SPOTTING                  = .FALSE.
GENERATION_MODEL                         = 'PER-MW'
SPOTTING_DISTANCE_MODEL                  = 'EMPIRICAL'
ACCUMULATION_MODEL                       = '$ACCUM'
IGNITION_MODEL                           = '$IGNM'
DIFF_WILDLAND_IGNITION                   = $DIFF_WILD
CRITICAL_SPOTTING_FIRELINE_INTENSITY(:)  = 304*$CRITFLIN
GLOBAL_SURFACE_FIRE_SPOTTING_PERCENT     = 100.
GLOBAL_SURFACE_FIRE_SPOTTING_PERCENT_MAX = 100.
GLOBAL_SURFACE_FIRE_SPOTTING_PERCENT_MIN = 100.
TAU_EMBERGEN                             = ${TAU:-10.0}
USE_PHYSICAL_SPOTTING_DURATION           = $PHYS
P_EPS                                    = ${PEPS:-0.001}
EMBER_SAMPLING_FACTOR                    = $SAMPLING
$CONS
$DELAY
$LIGN
$EGEN
$EGENB
$PIGNL
/
&WUI
USE_BLDG_SPREAD_MODEL                 = ${BLDG_SPREAD:-.TRUE.}
BLDG_SPREAD_MODEL_TYPE                = ${BLDG_TYPE:-2}
USE_CONSTANT_BLDG_SPREAD_MODEL_PARAMS = .FALSE.
GLOBAL_HARDENING_FACTOR               = 1.0
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
#   env ELMFIRE_EXE=<path>: run another ELMFIRE build (e.g. my_analysis/elmfire_variant, receptive-fraction
#   experiment, which reads env ELMFIRE_EMBER_RECEPTIVE_FRAC); default is the original elmfire_$ELMFIRE_VER
${ELMFIRE_EXE:-elmfire_$ELMFIRE_VER} ./elmfire.data > elmfire.log 2>&1 || echo "ELMFIRE exit code $?" >> elmfire.log
echo "seed $SEED finished in $(( ($(date +%s) - START) / 60 )) min" >> elmfire.log
tail -1 elmfire.log
