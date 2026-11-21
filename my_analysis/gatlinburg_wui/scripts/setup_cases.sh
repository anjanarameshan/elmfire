#!/bin/bash
# Build the scenario folders: observed spot fire 2 (Jimenez et al. 2018 Fig. 1, ~11:30 EST 28 Nov,
# 1.5 miles from the park boundary toward Gatlinburg) and the same spot moved 1 km N, E, S, W.
# Usage: setup_cases.sh BUILDINGS.gpkg TAG
B=$1; TAG=$2
cd "$(dirname "$0")/.."
BASE=../chimney-tops-2016-nov27-cloudfire-all-adj1/inputs   # all-CloudFire inputs, band 1 = 27 Nov 18:00 UTC
FIRST=23; NB=17                                              # band 23 = 28 Nov 16:00 UTC (11:00 EST); 17 bands -> 29 Nov 08:00 UTC
LAT=35.690; LON=-83.497; DLAT=0.00899; DLON=0.01107          # 1 km in latitude / longitude at 35.69 N
for c in "spot2:$LAT:$LON" "spot2_N1km:$(echo "$LAT+$DLAT"|bc -l):$LON" "spot2_S1km:$(echo "$LAT-$DLAT"|bc -l):$LON" \
         "spot2_E1km:$LAT:$(echo "$LON+$DLON"|bc -l)" "spot2_W1km:$LAT:$(echo "$LON-$DLON"|bc -l)"; do
   IFS=: read NAME la lo <<< "$c"
   mkdir -p $TAG/$NAME
   echo "== $NAME ($la, $lo)"
   ~/venvs/elmfire/bin/python -W ignore scripts/build_wui_inputs.py $BASE $B $TAG/$NAME/inputs $la $lo $FIRST $NB 1 2>&1 | tail -1
done
