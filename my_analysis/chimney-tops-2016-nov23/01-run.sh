#!/bin/bash
# Hindcast of a historical US fire with ELMFIRE: 2016 Chimney Tops 2 Fire - full event from Nov 23, leaf-off canopy
# (Great Smoky Mountains National Park / Gatlinburg, Tennessee).
# Based on tutorials/03-real-fuels, but uses real historical weather from CloudFire
# instead of the constant values in wx.csv.
#
# Fire facts (NPS / Wikipedia): reported 2016-11-23 ~17:20-17:30 EST (22:20-22:30 UTC) at
# Chimney Tops, ~35.629 N, 83.478 W. Slow growth Nov 23-27; extreme winds on Nov 28
# (40-50 mph sustained, gusts to 87 mph) drove it into Gatlinburg that evening.
# Final size ~17,000-17,900 acres (~11,000 in the park, ~6,000 in Sevier County).
#
# Usage: ./01-run.sh      (run from this folder; needs internet for the CloudFire download)

set -e -o pipefail

# ---- Inputs: change these for another US fire ----
FIRE_NAME=chimneytops2016
IGN_LAT=35.62889            # ignition latitude  (deg N) - Chimney Tops (approximate)
IGN_LON=-83.47833           # ignition longitude (deg E, negative = west)
# Full event: from the reported ignition to the end of Nov 29 (local time).
START_UTC="2016-11-23 22:00" # Wed Nov 23, 17:00 EST (UTC = EST + 5 h); weather must start on the hour
IGN_DELAY_S=0               # ignite at the start (17:00 EST; reported 17:30). ELMFIRE ends at t=0 if T_IGN>0 (no fire yet)
RUN_HOURS=150               # hours of weather downloaded: to 2016-11-30 04:00 UTC (Tue Nov 29, 23:00 EST)
SIM_HOURS=150               # hours actually simulated (<= RUN_HOURS). Small = quick test
DTDUMP_S=3600               # save hourly burned-area maps + acreage every this many seconds
BUFFER_KM=20                # domain half-width around the ignition (km)
FUEL_VERSION=1.4.0          # LANDFIRE version; 1.4.0 ~ 2014 fuels, i.e. before this fire
SPOTTING=yes                # yes = add the ember model settings in spotting.in; no = surface spread only
ADJ_FACTOR=${ADJ_FACTOR:-1.0} # spread-rate multiplier applied everywhere (adj raster); 1 = unchanged.
                            # Can also be given on the command line: ADJ_FACTOR=4 ./01-run.sh
# Leaf-off canopy: LANDFIRE canopy cover is leaf-on (summer). In late November the hardwoods are
# bare, so they shelter the flames from wind much less. Canopy cover (cc) is multiplied by this
# factor where the fuel model is broadleaf litter (TL2=182, TL6=186, TL9=189); conifer litter and
# other fuels are unchanged. 1.0 = off. The value is an assumption (bare trunks/branches remain).
LEAF_OFF_CC_FACTOR=${LEAF_OFF_CC_FACTOR:-0.6}   # 0.3 was far too strong (113,000+ ac by Nov 28)
LEAF_OFF_FUELS="182 186 189"
# Spotting controls (override spotting.in; can be given on the command line, e.g. SPOT_PIGN=20 ./01-run.sh)
SPOT_PIGN=${SPOT_PIGN:-100}       # % chance that landed embers ignite a cell (tutorial 05: 100)
SPOT_PERCENT=${SPOT_PERCENT:-100} # % chance that a burning cell throws embers at all (tutorial 05: 100)
SPOT_CRIT=${SPOT_CRIT:-0}         # minimum fireline intensity (kW/m) for a cell to throw embers (tutorial 05: 0)
MAX_ACRES=${MAX_ACRES:-45000}     # watchdog: stop ELMFIRE if the fire passes this size (3x the MTBS area)
# ---- End inputs ----

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$HERE"
export ELMFIRE_BASE_DIR=${ELMFIRE_BASE_DIR:-$(cd "$HERE/../.." && pwd)}
export CLOUDFIRE_SERVER=${CLOUDFIRE_SERVER:-worldgen.cloudfire.io}
BIN=$ELMFIRE_BASE_DIR/build/linux/bin
case ":$PATH:" in *":$BIN:"*) ;; *) export PATH=$PATH:$BIN ;; esac

. "$ELMFIRE_BASE_DIR/tutorials/functions/functions.sh"   # read-only use of the tutorial helpers
set_elmfire_version

SIMULATION_TSTOP=$((SIM_HOURS * 3600))

# Download fuel/topography (LANDFIRE) and hourly historical weather for the domain.
# Re-download whenever the settings that define the download change.
DOWNLOAD_SETTINGS="$IGN_LAT $IGN_LON $START_UTC $RUN_HOURS $BUFFER_KM $FUEL_VERSION"
if [ ! -f ./fuel/$FIRE_NAME.tar ] || [ "$(cat ./fuel/settings.txt 2>/dev/null)" != "$DOWNLOAD_SETTINGS" ]; then
   rm -rf ./fuel
   "$ELMFIRE_BASE_DIR/cloudfire/fuel_wx_ign.py" \
      --name=$FIRE_NAME --outdir=./fuel \
      --center_lat=$IGN_LAT --center_lon=$IGN_LON \
      --west_buffer=$BUFFER_KM --east_buffer=$BUFFER_KM \
      --south_buffer=$BUFFER_KM --north_buffer=$BUFFER_KM \
      --fuel_source=landfire --fuel_version=$FUEL_VERSION \
      --do_wx=True --wx_type=historical --wx_start_time="$START_UTC" --wx_num_hours=$RUN_HOURS \
      --do_ignition=False
   echo "$DOWNLOAD_SETTINGS" > ./fuel/settings.txt
else
   echo "Settings unchanged - reusing ./fuel/$FIRE_NAME.tar"
fi

SCRATCH=./scratch
INPUTS=./inputs
OUTPUTS=./outputs
rm -f -r $SCRATCH $INPUTS $OUTPUTS
mkdir $SCRATCH $INPUTS $OUTPUTS
cp elmfire.data.in $INPUTS/elmfire.data
if [ "$SPOTTING" = "yes" ]; then
   cat spotting.in >> $INPUTS/elmfire.data
   sed -i -e "s/^PIGN  *=.*/PIGN = $SPOT_PIGN/" -e "s/^PIGN_MAX  *=.*/PIGN_MAX = $SPOT_PIGN/" \
          -e "s/^PIGN_MIN  *=.*/PIGN_MIN = $SPOT_PIGN/" \
          -e "s/^CRITICAL_SPOTTING_FIRELINE_INTENSITY(:)  *=.*/CRITICAL_SPOTTING_FIRELINE_INTENSITY(:) = $SPOT_CRIT/" \
          -e "s/^GLOBAL_SURFACE_FIRE_SPOTTING_PERCENT_MAX  *=.*/GLOBAL_SURFACE_FIRE_SPOTTING_PERCENT_MAX = $SPOT_PERCENT/" \
          -e "s/^GLOBAL_SURFACE_FIRE_SPOTTING_PERCENT_MIN  *=.*/GLOBAL_SURFACE_FIRE_SPOTTING_PERCENT_MIN = $SPOT_PERCENT/" \
          $INPUTS/elmfire.data
   echo "Spotting: ON (spotting.in) - ignition prob $SPOT_PIGN %, cells spotting $SPOT_PERCENT %, min intensity $SPOT_CRIT kW/m"
else
   echo "Spotting: OFF"
fi

# Unpack; keep the weather (ws, wd, m1, m10, m100, lh, lw: one band per hour)
tar -xf ./fuel/$FIRE_NAME.tar -C $INPUTS
rm -f $INPUTS/ignition*.tif $INPUTS/forecast_cycle.txt

# Spread-rate adjustment: ELMFIRE multiplies the Rothermel surface spread rate by adj
if [ "$ADJ_FACTOR" != "1.0" ] && [ "$ADJ_FACTOR" != "1" ]; then
   gdal_calc.py --quiet -A $INPUTS/adj.tif --outfile=$SCRATCH/adj.tif --calc="A*$ADJ_FACTOR" \
      --NoDataValue=-9999 --type=Float32 --co="COMPRESS=DEFLATE"
   mv $SCRATCH/adj.tif $INPUTS/adj.tif
fi
echo "Spread-rate adjustment factor (adj): $ADJ_FACTOR"

# Leaf-off canopy cover for deciduous (broadleaf litter) cells, before building the landscape
if [ "$LEAF_OFF_CC_FACTOR" != "1.0" ] && [ "$LEAF_OFF_CC_FACTOR" != "1" ]; then
   COND=`for f in $LEAF_OFF_FUELS; do printf "(B==%s)|" $f; done | sed 's/|$//'`
   gdal_calc.py --quiet -A $INPUTS/cc.tif -B $INPUTS/fbfm40.tif --outfile=$SCRATCH/cc.tif \
      --calc="numpy.where($COND, numpy.round(A*$LEAF_OFF_CC_FACTOR), A)" \
      --NoDataValue=-9999 --type=Int16 --co="COMPRESS=DEFLATE"
   mv $SCRATCH/cc.tif $INPUTS/cc.tif
fi
echo "Leaf-off canopy cover factor: $LEAF_OFF_CC_FACTOR (fuel models $LEAF_OFF_FUELS)"

create_landscape $INPUTS fbfm40

# Ignition point in the domain's projected coordinates (the tile is centred on it)
A_SRS=`gdalsrsinfo -o proj4 $INPUTS/landscape.tif | xargs`
read X_IGN Y_IGN _ <<< `echo "$IGN_LON $IGN_LAT" | gdaltransform -s_srs EPSG:4326 -t_srs "$A_SRS"`
echo "Ignition at x=$X_IGN y=$Y_IGN ($A_SRS)"

replace_line SIMULATION_TSTOP $SIMULATION_TSTOP no
replace_line DTDUMP $DTDUMP_S no
replace_line 'X_IGN(1)' $X_IGN no
replace_line 'Y_IGN(1)' $Y_IGN no
replace_line 'T_IGN(1)' $IGN_DELAY_S no

# Run ELMFIRE. The ember model can stop with "ERFINV_LOCAL(X) domain is |X| < 1" when a random
# draw lands exactly on the edge of its range (rare, but likely over millions of embers).
# Without changing the ELMFIRE source, retry with a different random seed: this only picks
# another random realization of the ember process.
SEED=2024          # ELMFIRE default
MAX_TRIES=5
cp $INPUTS/elmfire.data $INPUTS/elmfire.data.base
# Convert ELMFIRE's .bil rasters in a folder to GeoTIFF
convert_outputs() {
   for f in $1/*.bil; do
      [ -e "$f" ] || continue
      gdal_translate -q -a_srs "$A_SRS" -co "COMPRESS=DEFLATE" -co "ZLEVEL=9" $f $1/`basename $f .bil`.tif
   done
   rm -f $1/*.bil $1/*.hdr
}

# Watchdog: every 30 s, read the latest hourly burned-area map; stop ELMFIRE if the fire is too large
watchdog() {
   while sleep 30; do
      LATEST=$(ls $OUTPUTS/surface_fire_*_d*.bil 2>/dev/null | tail -1)
      [ -n "$LATEST" ] || continue
      AC=$(python3 -c "import numpy as np, sys; print(int((np.fromfile(sys.argv[1], '<i2') > 0).sum() * $CELL_AC))" "$LATEST")
      if [ "$AC" -gt "$MAX_ACRES" ]; then
         echo "$AC acres at hour $(basename $LATEST .bil | sed 's/.*_d0*//')" > $OUTPUTS/ABORTED_TOO_LARGE
         for p in $(pgrep -f "elmfire_$ELMFIRE_VER ./inputs/elmfire.data"); do
            [ "$(readlink /proc/$p/cwd)" = "$HERE" ] && kill $p
         done
         return 0
      fi
   done
}
CELL_AC=`gdalinfo $INPUTS/landscape.tif | grep 'Pixel Size' | cut -d'(' -f2 | cut -d, -f1 | awk '{print $1*$1/4046.8564}'`

rm -rf ./partial_seed* ./results_too_large
OK=no
for TRY in $(seq 1 $MAX_TRIES); do
   cp $INPUTS/elmfire.data.base $INPUTS/elmfire.data
   printf "\n&MONTE_CARLO\nSEED = %d\n/\n" $SEED >> $INPUTS/elmfire.data
   rm -rf $OUTPUTS; mkdir $OUTPUTS
   echo "ELMFIRE run $TRY/$MAX_TRIES (seed $SEED, $SIM_HOURS h) started $(date +%H:%M)"
   watchdog &
   WATCHDOG=$!
   elmfire_$ELMFIRE_VER ./inputs/elmfire.data 2>&1 | tee elmfire_try$TRY.log || true
   kill $WATCHDOG 2>/dev/null || true   # the watchdog may already have exited
   wait $WATCHDOG 2>/dev/null || true
   if [ -f $OUTPUTS/ABORTED_TOO_LARGE ]; then
      mv $OUTPUTS results_too_large; convert_outputs results_too_large; rm -rf $SCRATCH
      echo "Stopped: fire passed $MAX_ACRES acres ($(cat results_too_large/ABORTED_TOO_LARGE)). Hourly maps in results_too_large/"
      exit 2
   fi
   if ! grep -q "ERFINV_LOCAL" elmfire_try$TRY.log && ls $OUTPUTS/time_of_arrival*.bil > /dev/null 2>&1; then
      OK=yes; break
   fi
   # Keep what this try produced before it stopped (hourly burned-area maps, acreage table)
   mv $OUTPUTS partial_seed$SEED; convert_outputs partial_seed$SEED
   echo "ELMFIRE stopped on the ember random-number edge case at $(date +%H:%M); partial outputs in partial_seed$SEED/"
   SEED=$((SEED + 1))
done
rm -rf $SCRATCH

if [ $OK = no ]; then
   echo "All $MAX_TRIES tries stopped early. Partial results are in partial_seed*/ (acres_*.csv, surface_fire_*.tif)."
   exit 1
fi
echo "Finished with seed $SEED"

convert_outputs $OUTPUTS
gdal_contour -q -a time_s -i 3600 `ls $OUTPUTS/time_of_arrival*.tif` $OUTPUTS/hourly_isochrones.shp

echo "Done (spotting: $SPOTTING, adj: $ADJ_FACTOR, leaf-off cc: $LEAF_OFF_CC_FACTOR, $SIM_HOURS h). Fire size:"
cut -d, -f5,7,8 $OUTPUTS/fire_size_stats.csv
exit 0
