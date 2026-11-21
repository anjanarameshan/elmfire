#!/bin/bash
# After the adj=2 upgrade run finishes: if it overshot the observed area (15,002 ac) or was stopped
# by the watchdog, start the same set-up with adj=1 in ../chimney-tops-2016-observed-vegupgrade-adj1
cd "$(dirname "$0")"
until grep -q "Done (\|Stopped: fire passed\|All .* tries" run.log; do sleep 20; done
AC=$(tail -1 run.log | awk -F, '{printf "%d", $2}')
if grep -q "Stopped: fire passed" run.log || [ "${AC:-0}" -gt 15002 ]; then
   N=../chimney-tops-2016-observed-vegupgrade-adj1
   rm -rf $N; mkdir -p $N
   cp 01-run.sh elmfire.data.in spotting.in prepare_start.py $N/
   cp -r fuel hrrr_wind $N/
   cd $N && FUEL_TIF=$(cd .. && pwd)/fuel-test/veg/fbfm40_vegetation_upgrade.tif ADJ_FACTOR=1 ./01-run.sh > run.log 2>&1
   echo "adj=2 burned ${AC} ac (overshoot) -> adj=1 run finished: $(tail -1 run.log)"
else
   echo "adj=2 burned ${AC} ac, not above 15,002 ac -> adj=1 run not started"
fi
