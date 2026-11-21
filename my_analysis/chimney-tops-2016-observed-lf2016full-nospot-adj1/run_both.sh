#!/bin/bash
# LANDFIRE 2016 (full download), HRRR wind (no gust/downslope factor), ELMFIRE spotting on,
# no observed spot-fire ignitions; adj 1 then adj 2.
cd "$(dirname "$0")/.."
F=$(pwd)/fuel-test/lf2016_full/fbfm40_lf2016_complete.tif
for adj in 1 2; do
  (cd chimney-tops-2016-observed-lf2016full-nospot-adj$adj && FUEL_TIF=$F ADJ_FACTOR=$adj GUST_F=0 WIND_FACTOR=1.0 SPOT_FIRES="" ./01-run.sh > run.log 2>&1)
done
