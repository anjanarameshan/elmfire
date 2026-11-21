#!/bin/bash
# Hindcast of a historical US fire with ELMFIRE: 2016 Chimney Tops 2 Fire - with station-corrected fuel moisture
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
# The real fire smouldered in leaf litter Nov 23-27; ELMFIRE has no smouldering model, so a
# run started on Nov 23 dies out overnight (fine fuel moisture rises above extinction).
# Instead the run starts just before the Nov 28 wind event, from the origin point.
START_UTC="2016-11-27 18:00" # Sun Nov 27, 13:00 EST (UTC = EST + 5 h). Reported ignition: 2016-11-23 22:30 UTC
RUN_HOURS=34                # hours of weather downloaded: to 2016-11-29 04:00 UTC (Mon 23:00 EST), after rain arrived
SIM_HOURS=34                # hours actually simulated (<= RUN_HOURS). Small = quick test; set to 34 for the full run
DTDUMP_S=3600               # save hourly burned-area maps + acreage every this many seconds
BUFFER_KM=20                # domain half-width around the ignition (km)
FUEL_VERSION=1.4.0          # LANDFIRE version; 1.4.0 ~ 2014 fuels, i.e. before this fire
SPOTTING=yes                # yes = add the ember model settings in spotting.in; no = surface spread only
ADJ_FACTOR=${ADJ_FACTOR:-1.0} # spread-rate multiplier applied everywhere (adj raster); 1 = unchanged.
                            # Can also be given on the command line: ADJ_FACTOR=4 ./01-run.sh
# Fuel moisture correction with a weather station (see ../correct_moisture.py): yes/no
MOISTURE_FIX=${MOISTURE_FIX:-yes}
FIX_STATION_CSV=weather_stations/IGGT1.2016-11-30.csv   # Indian Grave RAWS (path inside my_analysis/)
FIX_STATION_WX=weather_stations/cloudfire_at_IGGT1       # CloudFire weather around the station
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
   echo "Spotting: ON (spotting.in)"
else
   echo "Spotting: OFF"
fi

# Unpack; keep the weather (ws, wd, m1, m10, m100, lh, lw: one band per hour)
tar -xf ./fuel/$FIRE_NAME.tar -C $INPUTS
rm -f $INPUTS/ignition*.tif $INPUTS/forecast_cycle.txt

# Correct CloudFire m1/m10 with the station (hourly factor station/CloudFire at the station)
if [ "$MOISTURE_FIX" = "yes" ]; then
   A=$ELMFIRE_BASE_DIR/my_analysis
   ~/venvs/elmfire/bin/python $A/correct_moisture.py $INPUTS "$START_UTC" $A/$FIX_STATION_CSV $A/$FIX_STATION_WX
else
   echo "Moisture correction: off"
fi

# Spread-rate adjustment: ELMFIRE multiplies the Rothermel surface spread rate by adj
if [ "$ADJ_FACTOR" != "1.0" ] && [ "$ADJ_FACTOR" != "1" ]; then
   gdal_calc.py --quiet -A $INPUTS/adj.tif --outfile=$SCRATCH/adj.tif --calc="A*$ADJ_FACTOR" \
      --NoDataValue=-9999 --type=Float32 --co="COMPRESS=DEFLATE"
   mv $SCRATCH/adj.tif $INPUTS/adj.tif
fi
echo "Spread-rate adjustment factor (adj): $ADJ_FACTOR"

create_landscape $INPUTS fbfm40

# Ignition point in the domain's projected coordinates (the tile is centred on it)
A_SRS=`gdalsrsinfo -o proj4 $INPUTS/landscape.tif | xargs`
read X_IGN Y_IGN _ <<< `echo "$IGN_LON $IGN_LAT" | gdaltransform -s_srs EPSG:4326 -t_srs "$A_SRS"`
echo "Ignition at x=$X_IGN y=$Y_IGN ($A_SRS)"

replace_line SIMULATION_TSTOP $SIMULATION_TSTOP no
replace_line DTDUMP $DTDUMP_S no
replace_line 'X_IGN(1)' $X_IGN no
replace_line 'Y_IGN(1)' $Y_IGN no

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

rm -rf ./partial_seed*
OK=no
for TRY in $(seq 1 $MAX_TRIES); do
   cp $INPUTS/elmfire.data.base $INPUTS/elmfire.data
   printf "\n&MONTE_CARLO\nSEED = %d\n/\n" $SEED >> $INPUTS/elmfire.data
   rm -rf $OUTPUTS; mkdir $OUTPUTS
   echo "ELMFIRE run $TRY/$MAX_TRIES (seed $SEED, $SIM_HOURS h) started $(date +%H:%M)"
   elmfire_$ELMFIRE_VER ./inputs/elmfire.data 2>&1 | tee elmfire_try$TRY.log || true
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

echo "Done (spotting: $SPOTTING, adj: $ADJ_FACTOR, moisture fix: $MOISTURE_FIX, $SIM_HOURS h). Fire size:"
cut -d, -f5,7,8 $OUTPUTS/fire_size_stats.csv
exit 0
