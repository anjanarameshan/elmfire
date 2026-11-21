#!/usr/bin/env python3
"""Fire spread (time of arrival) maps, one run per ignition location.
Usage: python fire_spread_map.py PERIMETER.shp PARENT SEED LOC [LOC ...]
Each burned cell is coloured by the hour the fire reached it (time_of_arrival, hours after the start of spot
fire 2, 28 Nov 2016 11:00 EST); white contours every 2 h; star = ignition; blue dots = buildings.
Writes PARENT/fire_spread_seed<SEED>.png.
"""
import sys, glob
import numpy as np
import pandas as pd
from osgeo import gdal, ogr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm

gdal.UseExceptions(); ogr.UseExceptions()
SHP, PARENT, SEED, LOCS = sys.argv[1], sys.argv[2].rstrip("/"), sys.argv[3], sys.argv[4:]
NAMES = {"spot2": "reported", "spot2_N1km": "1 km north", "spot2_S1km": "1 km south",
         "spot2_E1km": "1 km east", "spot2_W1km": "1 km west"}
T0 = 11.0   # spot fire 2 start, hour of day (EST)
L = gdal.Open(f"{PARENT}/{LOCS[0]}/inputs/landscape.tif"); gt = L.GetGeoTransform()
m = gdal.GetDriverByName("MEM").Create("", L.RasterXSize, L.RasterYSize, 1, gdal.GDT_Byte)
m.SetGeoTransform(gt); m.SetProjection(L.GetProjection())
pds = ogr.Open(SHP); gdal.RasterizeLayer(m, [1], pds.GetLayer(), burn_values=[1]); per = m.ReadAsArray() == 1
f = pd.read_csv("vulnerability/features.csv")

pad = 900; x0, x1, y0, y1 = f.x.min() - pad, f.x.max() + pad, f.y.min() - 2200, f.y.max() + pad
c0, c1 = int((x0 - gt[0]) / gt[1]), int((x1 - gt[0]) / gt[1]); r0, r1 = int((y1 - gt[3]) / gt[5]), int((y0 - gt[3]) / gt[5])
ext = [(gt[0] + c0 * gt[1]) / 1e3, (gt[0] + c1 * gt[1]) / 1e3, (gt[3] + r1 * gt[5]) / 1e3, (gt[3] + r0 * gt[5]) / 1e3]
bounds = np.arange(0, 17, 1); cmap = plt.get_cmap("viridis_r", 16); norm = BoundaryNorm(bounds, cmap.N)

fig, ax = plt.subplots(2, 3, figsize=(15.5, 13), constrained_layout=True); ax = ax.ravel()
for a, loc in zip(ax, LOCS):
    o = f"{PARENT}/{loc}/seed_{SEED}/outputs"
    toa = gdal.Open(glob.glob(o + "/time_of_arrival_*.tif")[0]).ReadAsArray().astype(float)
    h = np.where(toa > 0, toa / 3600.0, np.nan)
    phi = gdal.Open(f"{PARENT}/{loc}/inputs/phi.tif").ReadAsArray(); ri, ci = np.where(phi < 0)
    acres = pd.read_csv(glob.glob(o + "/acres_*.csv")[0], header=None).iloc[-1, 1]
    a.imshow(per[r0:r1, c0:c1], extent=ext, cmap=ListedColormap(["#ffffff", "#f3f4f6"]), interpolation="nearest")
    im = a.imshow(np.ma.masked_invalid(h[r0:r1, c0:c1]), extent=ext, cmap=cmap, norm=norm, interpolation="nearest")
    hh = np.ma.masked_invalid(np.flipud(h[r0:r1, c0:c1]))
    a.contour(hh, levels=[2, 4, 6, 8, 10, 12, 14], colors="white", linewidths=0.6, extent=ext, origin="lower")
    a.contour(np.flipud(per[r0:r1, c0:c1]).astype(float), levels=[0.5], colors="#1f2328", linewidths=0.8, extent=ext, origin="lower")
    a.scatter(f.x / 1e3, f.y / 1e3, s=1.5, c="#c2412d", lw=0, alpha=0.6)
    a.scatter((gt[0] + (ci.mean() + .5) * gt[1]) / 1e3, (gt[3] + (ri.mean() + .5) * gt[5]) / 1e3, marker="*", s=260,
              c="#e0661f", edgecolors="#1f2328", lw=1, zorder=5)
    a.set_title(f"Spot fire 2, {NAMES[loc]} (seed {SEED}) · {float(acres):,.0f} acres in 16 h", fontsize=11)
    a.set_aspect("equal"); a.set_xlim(ext[0], ext[1]); a.set_ylim(ext[2], ext[3])
    a.set_xlabel("UTM 17N easting (km)"); a.set_ylabel("northing (km)")
for a in ax[len(LOCS):]:
    a.remove()
cb = fig.colorbar(im, ax=ax[:len(LOCS)], shrink=0.45, ticks=bounds[::2])
cb.set_label("hours after ignition (0 = 28 Nov 2016, 11:00 EST)")
fig.suptitle("Fire spread, time of arrival · ELMFIRE v1.1, buildings non-burnable · star = ignition, white lines every 2 h, "
             "red dots = buildings, black line = MTBS perimeter", fontsize=12)
out = f"{PARENT}/fire_spread_seed{SEED}.png"; fig.savefig(out, dpi=110); print(out)
