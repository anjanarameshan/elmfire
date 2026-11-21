#!/usr/bin/env python3
"""
Assumed downslope wind enhancement (a stand-in for a mountain-wave model such as WRF).

Wind speed is multiplied by up to FACTOR where the wind blows down a broad slope:
    ws_new = ws * (1 + (FACTOR - 1) * a * s)
    a = cos(angle between the wind and the downhill direction), 0 where the wind blows uphill
    s = min(1, slope / SLOPE_FULL), slope as rise/run, SLOPE_FULL = 0.15 (a 15 % grade)
Slope and downhill direction are taken from the terrain averaged onto the wind grid (600 m),
so they describe whole mountain sides, not small gullies. Wind direction is unchanged.

Usage: python downslope_wind.py WIND_DIR DEM.tif FACTOR OUT_DIR
"""
import os
import shutil
import sys

import numpy as np
from osgeo import gdal

gdal.UseExceptions()
SLOPE_FULL = 0.15
src, dem_fn, factor, out = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
os.makedirs(out, exist_ok=True)
ws_ds = gdal.Open(os.path.join(src, "ws.tif"))
gt = ws_ds.GetGeoTransform()
nx, ny = ws_ds.RasterXSize, ws_ds.RasterYSize
ws = ws_ds.ReadAsArray().astype(float)
wd = gdal.Open(os.path.join(src, "wd.tif")).ReadAsArray().astype(float)

# Terrain averaged onto the wind grid
dem = gdal.Warp("", dem_fn, format="MEM", outputBounds=(gt[0], gt[3] + ny * gt[5], gt[0] + nx * gt[1], gt[3]),
                xRes=gt[1], yRes=-gt[5], resampleAlg="average").ReadAsArray().astype(float)
dem[dem < -1000] = np.nan
dem = np.where(np.isnan(dem), np.nanmean(dem), dem)
dzdy, dzdx = np.gradient(dem, -gt[5], gt[1])       # rows run north -> south
dzdy = -dzdy                                        # make +y = north
slope = np.hypot(dzdx, dzdy)
down_e, down_n = -dzdx / np.maximum(slope, 1e-9), -dzdy / np.maximum(slope, 1e-9)

to_e, to_n = -np.sin(np.radians(wd)), -np.cos(np.radians(wd))     # direction the wind blows towards
align = np.clip(to_e * down_e[None] + to_n * down_n[None], 0, 1)
weight = align * np.clip(slope / SLOPE_FULL, 0, 1)[None]
new = ws * (1 + (factor - 1) * weight)

d = gdal.GetDriverByName("GTiff").CreateCopy(os.path.join(out, "ws.tif"), ws_ds, options=["COMPRESS=DEFLATE"])
for b in range(new.shape[0]):
    d.GetRasterBand(b + 1).WriteArray(new[b].astype(np.float32))
d = None
shutil.copy(os.path.join(src, "wd.tif"), os.path.join(out, "wd.tif"))
print(f"Downslope wind x{factor:g}: {100 * (weight > 0.5).mean():.0f} % of cell-hours raised by more than half the "
      f"factor; mean wind {ws.mean():.1f} -> {new.mean():.1f} mph, max {ws.max():.1f} -> {new.max():.1f} mph")
