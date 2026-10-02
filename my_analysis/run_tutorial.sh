#!/bin/bash
# Run an ELMFIRE tutorial from a copy, so the original tutorials/ folder is never modified.
#
# Usage: ./run_tutorial.sh <tutorial-name>      e.g. ./run_tutorial.sh 01-constant-wind
# The copy is made in my_analysis/runs/<tutorial-name>/ (replaced on every run).

set -e -o pipefail

NAME=${1:?Usage: ./run_tutorial.sh <tutorial-name>  (e.g. 01-constant-wind)}
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SRC=$HERE/../tutorials
RUNS=$HERE/runs

# Make sure this repo's ELMFIRE build is on PATH even if ~/.bashrc wasn't loaded
BIN=$(cd "$HERE/../build/linux/bin" && pwd)
case ":$PATH:" in *":$BIN:"*) ;; *) export PATH=$PATH:$BIN ;; esac
# Tutorials that download data (e.g. 03-real-fuels) need these
export ELMFIRE_BASE_DIR=${ELMFIRE_BASE_DIR:-$(cd "$HERE/.." && pwd)}
export CLOUDFIRE_SERVER=${CLOUDFIRE_SERVER:-worldgen.cloudfire.io}

if [ ! -d "$SRC/$NAME" ]; then
   echo "No tutorial named '$NAME'. Available:"; ls "$SRC" | grep -v functions
   exit 1
fi

mkdir -p "$RUNS"
rm -rf "$RUNS/$NAME" "$RUNS/functions"
cp -r "$SRC/$NAME" "$RUNS/$NAME"
cp -r "$SRC/functions" "$RUNS/functions"   # 01-run.sh sources ../functions/functions.sh

cd "$RUNS/$NAME"
./01-run.sh 2>&1 | tee run.log
echo "Done. Outputs in $RUNS/$NAME/outputs"
