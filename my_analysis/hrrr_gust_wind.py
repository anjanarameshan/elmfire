#!/usr/bin/env python3
"""
Gust-informed wind from HRRR: ws_eff = ws + f * (gust_20ft - ws), per cell and hour.

ws is HRRR's hourly-average wind at 20 ft (from hrrr_winds.py), gust is HRRR's surface
gust at 10 m, converted to 20 ft with the same factor (0.87). f = 0 gives the average
wind, f = 1 the gust speed. Direction (wd.tif) is unchanged.

Usage:
    python hrrr_gust_wind.py HRRR_DIR F OUT_DIR
Writes OUT_DIR/ws.tif, OUT_DIR/wd.tif
"""
import os
import shutil
import sys

import numpy as np
from osgeo import gdal

gdal.UseExceptions()
TEN_M_TO_20FT = 0.87


def main():
    src, f, out = sys.argv[1], float(sys.argv[2]), sys.argv[3]
    os.makedirs(out, exist_ok=True)
    ds = gdal.Open(os.path.join(src, "ws.tif"))
    ws = ds.ReadAsArray().astype(float)
    gust = gdal.Open(os.path.join(src, "gust.tif")).ReadAsArray().astype(float) * TEN_M_TO_20FT
    eff = ws + f * np.maximum(gust - ws, 0.0)
    d = gdal.GetDriverByName("GTiff").CreateCopy(os.path.join(out, "ws.tif"), ds, options=["COMPRESS=DEFLATE"])
    for b in range(eff.shape[0]):
        d.GetRasterBand(b + 1).WriteArray(eff[b].astype(np.float32))
    d = None
    shutil.copy(os.path.join(src, "wd.tif"), os.path.join(out, "wd.tif"))
    print(f"f={f}: mean wind {ws.mean():.1f} -> {eff.mean():.1f} mph, max {ws.max():.1f} -> {eff.max():.1f} mph; wrote {out}")


if __name__ == "__main__":
    main()
