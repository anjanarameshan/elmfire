#!/bin/bash
# Keep running the (resumable) HRRR downloader until every expected file is verified.
# Usage: run_download_until_done.sh START END PRODUCTS [WORKERS]   e.g. 2016-11-27T12 2016-11-29T12 wrfprs 4
cd "$(dirname "$0")/.."
PY=${PY:-$HOME/venvs/elmfire/bin/python}
for pass in $(seq 1 200); do
   $PY -W ignore scripts/hrrr_download.py "$1" "$2" "$3" "${4:-4}" >> logs/pilot_download.out 2>&1
   tail -1 logs/download.log | grep -q "done: .* 0 not verified" && { echo "all files verified after pass $pass" >> logs/pilot_download.out; exit 0; }
   sleep 120   # network trouble or failed files: wait, then resume the partial files
done
