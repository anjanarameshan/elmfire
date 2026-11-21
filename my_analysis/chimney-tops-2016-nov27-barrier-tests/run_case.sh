#!/bin/bash
# Run one barrier-test case folder with ELMFIRE (inputs/, elmfire.data already prepared).
export ELMFIRE_BASE_DIR=$HOME/elmfire-1
BIN=$ELMFIRE_BASE_DIR/build/linux/bin; export PATH=$PATH:$BIN
. "$ELMFIRE_BASE_DIR/tutorials/functions/functions.sh"; set_elmfire_version
cd "$1"; S=$(date +%s)
elmfire_$ELMFIRE_VER ./elmfire.data > elmfire.log 2>&1 || echo "ELMFIRE exit code $?" >> elmfire.log
echo "finished in $(( ($(date +%s) - S) / 60 )) min" >> elmfire.log
