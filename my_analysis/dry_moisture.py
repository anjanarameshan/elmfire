#!/usr/bin/env python3
"""
Drier dead fuel moisture scenarios for the 28 Nov 2016 downslope wind event.

CloudFire m1 / m10 (one band per hour) are capped, cell by cell, wherever the fuel is not
rain-wetted (CloudFire m1 <= 30 %):
  station : m1 <= Indian Grave 1-hr moisture for that hour (from temperature and humidity),
            m10 <= that value + 2. Applied in every hour.
  dryair  : m1 <= CAP (default 4 %), m10 <= CAP + 2, only from HOUR0 to HOUR1 (default 6-30 =
            28 Nov 00:00 UTC to 29 Nov 00:00 UTC). 4 % is roughly the equilibrium moisture of
            fine fuel at 10 % relative humidity, the upper limit Shadbolt et al. (2019) report
            for the air descending the lee slope; the dry layer was gone by 29 Nov 00:00 UTC.
m100, lh and lw are copied unchanged.

Usage:
    python dry_moisture.py RUN_INPUTS_DIR OUT_DIR station MOISTURE_CORRECTION.csv
    python dry_moisture.py RUN_INPUTS_DIR OUT_DIR dryair [CAP] [HOUR0] [HOUR1]
"""
import csv
import os
import shutil
import sys

import numpy as np
from osgeo import gdal

gdal.UseExceptions()
WET = 30.0


def main():
    inp, out, mode = sys.argv[1:4]
    os.makedirs(out, exist_ok=True)
    m1 = gdal.Open(os.path.join(inp, "m1.tif")).ReadAsArray().astype(np.float32)
    nb = m1.shape[0]
    if mode == "station":
        rows = list(csv.DictReader(open(sys.argv[4])))
        v = np.array([float(r["station_1hr_pct"]) if r["station_1hr_pct"] not in ("", "nan") else np.nan for r in rows])[:nb]
        ok = np.isfinite(v)
        cap = np.interp(np.arange(nb), np.flatnonzero(ok), v[ok])
    else:
        c = float(sys.argv[4]) if len(sys.argv) > 4 else 4.0
        h0 = int(sys.argv[5]) if len(sys.argv) > 5 else 6
        h1 = int(sys.argv[6]) if len(sys.argv) > 6 else 30
        cap = np.full(nb, np.inf)
        cap[h0:h1 + 1] = c
    dry = (m1 <= WET) & (m1 >= 0)
    for name, add in (("m1", 0.0), ("m10", 2.0)):
        src = gdal.Open(os.path.join(inp, f"{name}.tif"))
        a = src.ReadAsArray().astype(np.float32)
        a = np.where(dry, np.minimum(a, (cap + add)[:, None, None]), a).astype(np.float32)
        d = gdal.GetDriverByName("GTiff").CreateCopy(os.path.join(out, f"{name}.tif"), src, options=["COMPRESS=DEFLATE"])
        for b in range(nb):
            d.GetRasterBand(b + 1).WriteArray(a[b])
        d = None
    for name in ("m100", "lh", "lw"):
        shutil.copy(os.path.join(inp, f"{name}.tif"), os.path.join(out, f"{name}.tif"))
    print(f"{mode}: wrote m1, m10 (capped), m100, lh, lw to {out}")


if __name__ == "__main__":
    main()
