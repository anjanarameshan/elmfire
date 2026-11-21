#!/usr/bin/env python3
"""
Initial fire and spot-fire ignitions for the observation-based Chimney Tops 2 run.

  - writes phi.tif with phi = -1 inside a circle of START_ACRES around the origin
    (ELMFIRE treats phi <= 0 cells as already burning at the start)
  - converts each spot fire (lat, lon, hours after start) to x, y, t, moved to the
    nearest burnable cell if it falls on a non-burnable one

Usage: prepare_start.py INPUTS_DIR IGN_LON IGN_LAT START_ACRES "LAT,LON,HOURS" ["LAT,LON,HOURS" ...]
Prints one line "x y t_seconds" per spot fire.
"""
import math
import os
import sys

import numpy as np
from osgeo import gdal, osr

gdal.UseExceptions()
inp, lon0, lat0, acres = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
ds = gdal.Open(os.path.join(inp, "phi.tif"), gdal.GA_Update)
gt = ds.GetGeoTransform()
ll = osr.SpatialReference()
ll.ImportFromEPSG(4326)
ll.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
tr = osr.CoordinateTransformation(ll, osr.SpatialReference(wkt=ds.GetProjection()))
ny, nx = ds.RasterYSize, ds.RasterXSize
X = gt[0] + (np.arange(nx) + 0.5) * gt[1]
Y = gt[3] + (np.arange(ny) + 0.5) * gt[5]

x0, y0, _ = tr.TransformPoint(lon0, lat0)
r = math.sqrt(acres * 4046.8564 / math.pi)
phi = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
inside = np.hypot(X[None, :] - x0, Y[:, None] - y0) <= r
phi[inside] = -1.0
ds.GetRasterBand(1).WriteArray(phi)
ds = None
sys.stderr.write(f"Initial fire: {inside.sum() * gt[1] ** 2 / 4046.8564:.1f} acres (radius {r:.0f} m) around the origin\n")

fuel = gdal.Open(os.path.join(inp, "fbfm40.tif")).ReadAsArray()
for spec in sys.argv[5:]:
    lat, lon, hours = (float(v) for v in spec.split(","))
    x, y, _ = tr.TransformPoint(lon, lat)
    j, i = int((x - gt[0]) / gt[1]), int((y - gt[3]) / gt[5])
    if fuel[i, j] <= 100:                      # non-burnable: nearest burnable cell within ~600 m
        win = fuel[i - 20:i + 21, j - 20:j + 21] > 100
        ii, jj = np.where(win)
        k = np.argmin((ii - 20) ** 2 + (jj - 20) ** 2)
        i, j = i - 20 + ii[k], j - 20 + jj[k]
        x, y = X[j], Y[i]
    sys.stderr.write(f"Spot fire at lat {lat}, lon {lon}: x={x:.0f} y={y:.0f}, fuel {fuel[i, j]}, {hours} h after start\n")
    print(f"{x:.1f} {y:.1f} {hours * 3600:.0f}")
