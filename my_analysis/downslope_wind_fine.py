#!/usr/bin/env python3
"""
Downslope wind enhancement on a fine grid (default 100 m), so individual slopes get their own boost.

The HRRR wind (WIND_DIR, 600 m) is interpolated (bilinear) to a RES grid covering the fire domain.
Slope and downhill direction come from the DEM averaged to SMOOTH metres (whole mountain sides,
not gullies), then interpolated to the same grid. Wind speed is multiplied by
    1 + (FACTOR - 1) * a * s
    a = cos(angle between wind and downhill direction), 0 when the wind blows uphill
    s = min(1, slope / 0.15)
Only terrain and wind direction decide where the boost goes (no use of the observed perimeter).
ELMFIRE needs all weather rasters on one grid, so the fuel moisture rasters from MOIST_DIR are
interpolated to the same grid. Wind direction is unchanged.

Usage: python downslope_wind_fine.py WIND_DIR MOIST_DIR DEM.tif FACTOR OUT_DIR [RES] [SMOOTH]
"""
import os
import sys

import numpy as np
from osgeo import gdal

gdal.UseExceptions()
SLOPE_FULL = 0.15
wind_dir, moist_dir, dem_fn, factor, out = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), sys.argv[5]
res = float(sys.argv[6]) if len(sys.argv) > 6 else 100.0
smooth = float(sys.argv[7]) if len(sys.argv) > 7 else 300.0
os.makedirs(out, exist_ok=True)

dem_ds = gdal.Open(dem_fn)
g = dem_ds.GetGeoTransform()
bounds = (g[0], g[3] + dem_ds.RasterYSize * g[5], g[0] + dem_ds.RasterXSize * g[1], g[3])


def regrid(src, r, alg):
    return gdal.Warp("", src, format="MEM", outputBounds=bounds, xRes=r, yRes=r, resampleAlg=alg)


d = regrid(dem_ds, smooth, "average").ReadAsArray().astype(float)
d[d < -1000] = np.nan
d = np.where(np.isnan(d), np.nanmean(d), d)
gy, gx = np.gradient(d, smooth, smooth)
gy = -gy
slope = np.hypot(gx, gy)
mem = gdal.GetDriverByName("MEM")


def coarse_to_fine(a):
    t = mem.Create("", a.shape[1], a.shape[0], 1, gdal.GDT_Float32)
    t.SetGeoTransform((bounds[0], smooth, 0, bounds[3], 0, -smooth))
    t.SetProjection(dem_ds.GetProjection())
    t.GetRasterBand(1).WriteArray(a.astype(np.float32))
    return regrid(t, res, "bilinear").ReadAsArray().astype(float)


de, dn = coarse_to_fine(-gx / np.maximum(slope, 1e-9)), coarse_to_fine(-gy / np.maximum(slope, 1e-9))
sw = np.clip(coarse_to_fine(slope) / SLOPE_FULL, 0, 1)
norm = np.maximum(np.hypot(de, dn), 1e-9)
de, dn = de / norm, dn / norm

ws_ds = regrid(gdal.Open(os.path.join(wind_dir, "ws.tif")), res, "bilinear")
wd_src = gdal.Open(os.path.join(wind_dir, "wd.tif"))
ws = ws_ds.ReadAsArray().astype(float)
# interpolate direction as a vector to avoid wrap-around at 0/360
wd600 = wd_src.ReadAsArray().astype(float)


def vec_regrid(comp):
    t = mem.Create("", wd_src.RasterXSize, wd_src.RasterYSize, comp.shape[0], gdal.GDT_Float32)
    t.SetGeoTransform(wd_src.GetGeoTransform())
    t.SetProjection(wd_src.GetProjection())
    for b in range(comp.shape[0]):
        t.GetRasterBand(b + 1).WriteArray(comp[b].astype(np.float32))
    return regrid(t, res, "bilinear").ReadAsArray().astype(float)


U = vec_regrid(-np.sin(np.radians(wd600)))
V = vec_regrid(-np.cos(np.radians(wd600)))
wd = (np.degrees(np.arctan2(-U, -V)) + 360) % 360
nrm = np.maximum(np.hypot(U, V), 1e-9)
align = np.clip(U / nrm * de[None] + V / nrm * dn[None], 0, 1)
weight = align * sw[None]
new = ws * (1 + (factor - 1) * weight)

gt = ws_ds.GetGeoTransform()
drv = gdal.GetDriverByName("GTiff")


def write(name, arr):
    o = drv.Create(os.path.join(out, name + ".tif"), arr.shape[2], arr.shape[1], arr.shape[0], gdal.GDT_Float32,
                   ["COMPRESS=DEFLATE"])
    o.SetGeoTransform(gt)
    o.SetProjection(dem_ds.GetProjection())
    for b in range(arr.shape[0]):
        o.GetRasterBand(b + 1).SetNoDataValue(-9999)
        o.GetRasterBand(b + 1).WriteArray(arr[b].astype(np.float32))
    o = None


write("ws", new)
write("wd", wd)
for n in ("m1", "m10", "m100", "lh", "lw"):
    a = regrid(gdal.Open(os.path.join(moist_dir, n + ".tif")), res, "bilinear").ReadAsArray().astype(float)
    write(n, a if a.ndim == 3 else a[None])
print(f"Downslope wind x{factor:g} on a {res:.0f} m grid (terrain {smooth:.0f} m): {100 * (weight > 0.5).mean():.0f} % of "
      f"cell-hours raised by more than half the factor; mean wind {ws.mean():.1f} -> {new.mean():.1f} mph, "
      f"max {ws.max():.1f} -> {new.max():.1f} mph")
