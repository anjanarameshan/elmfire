#!/usr/bin/env python3
"""Embers produced per burning vegetation cell, one run per ignition location (non-burnable-building runs).
Usage: python ember_production_map.py PERIMETER.shp PARENT SEED LOC [LOC ...]
  embers per cell = FLIN x 30 m x 33.3/1000 x 10 s ~= 10 x FLIN (PER-MW rule, TAU_EMBERGEN 10 s; intended amount)
Panels: map per location (vegetation cells that burned, coloured by embers produced; buildings as dots;
MTBS perimeter); the table gives the distribution for vegetation cells next to buildings (8 neighbours).
Writes PARENT/ember_production_seed<SEED>.png and prints a table.
"""
import sys, glob
import numpy as np
import pandas as pd
from osgeo import gdal, ogr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm, ListedColormap

gdal.UseExceptions(); ogr.UseExceptions()
SHP, PARENT, SEED, LOCS = sys.argv[1], sys.argv[2].rstrip("/"), sys.argv[3], sys.argv[4:]
NAMES = {"spot2": "reported", "spot2_N1km": "1 km north", "spot2_S1km": "1 km south",
         "spot2_E1km": "1 km east", "spot2_W1km": "1 km west"}
COL = {"spot2": "#1f2328", "spot2_N1km": "#2e6b9a", "spot2_S1km": "#b5501c", "spot2_E1km": "#4f8a5b", "spot2_W1km": "#8a5fb0"}
L = gdal.Open(f"{PARENT}/{LOCS[0]}/inputs/landscape.tif"); fm = L.GetRasterBand(4).ReadAsArray(); gt = L.GetGeoTransform()
veg = fm >= 100
m = gdal.GetDriverByName("MEM").Create("", L.RasterXSize, L.RasterYSize, 1, gdal.GDT_Byte)
m.SetGeoTransform(gt); m.SetProjection(L.GetProjection())
pds = ogr.Open(SHP); gdal.RasterizeLayer(m, [1], pds.GetLayer(), burn_values=[1]); per = m.ReadAsArray() == 1

f = pd.read_csv("vulnerability/features.csv")
c = ((f.x - gt[0]) / gt[1]).astype(int).values; r = ((f.y - gt[3]) / gt[5]).astype(int).values
near = np.zeros_like(veg)
for dy in (-1, 0, 1):
    for dx in (-1, 0, 1):
        if dy or dx:
            near[r + dy, c + dx] = True
near &= veg

pad = 900; x0, x1, y0, y1 = f.x.min() - pad, f.x.max() + pad, f.y.min() - 2200, f.y.max() + pad
c0, c1 = int((x0 - gt[0]) / gt[1]), int((x1 - gt[0]) / gt[1]); r0, r1 = int((y1 - gt[3]) / gt[5]), int((y0 - gt[3]) / gt[5])
ext = [(gt[0] + c0 * gt[1]) / 1e3, (gt[0] + c1 * gt[1]) / 1e3, (gt[3] + r1 * gt[5]) / 1e3, (gt[3] + r0 * gt[5]) / 1e3]

fig, ax = plt.subplots(2, 3, figsize=(15.5, 13), constrained_layout=True)
ax = ax.ravel(); norm = LogNorm(1, 1e5); rows = []
for a, loc in zip(ax, LOCS):
    o = f"{PARENT}/{loc}/seed_{SEED}/outputs"
    fl = gdal.Open(glob.glob(o + "/flin_*.tif")[0]).ReadAsArray().astype(float)
    toa = gdal.Open(glob.glob(o + "/time_of_arrival_*.tif")[0]).ReadAsArray()
    burned = veg & (toa > 0)
    emb = np.where(burned, 10 * np.clip(fl, 0, None), np.nan)          # embers produced per cell
    x = emb[burned & near]
    rows.append((NAMES[loc], int(burned.sum()), len(x), *np.percentile(x, [10, 50, 90, 99]), np.nansum(emb)))
    a.imshow(per[r0:r1, c0:c1], extent=ext, cmap=ListedColormap(["#ffffff", "#f3f4f6"]), interpolation="nearest")
    im = a.imshow(np.ma.masked_invalid(emb[r0:r1, c0:c1]), extent=ext, cmap="inferno_r", norm=norm, interpolation="nearest")
    a.contour(np.flipud(per[r0:r1, c0:c1]).astype(float), levels=[0.5], colors="#1f2328", linewidths=0.8, extent=ext, origin="lower")
    a.scatter(f.x / 1e3, f.y / 1e3, s=1.5, c="#2e6b9a", lw=0, alpha=0.7)
    a.set_title(f"Spot fire 2, {NAMES[loc]} (seed {SEED})\nmedian {np.median(x):.0f} embers per cell next to buildings", fontsize=11)
    a.set_aspect("equal"); a.set_xlim(ext[0], ext[1]); a.set_ylim(ext[2], ext[3])
    a.set_xlabel("UTM 17N easting (km)"); a.set_ylabel("northing (km)")
fig.colorbar(im, ax=ax[:5], shrink=0.45, label="embers produced by the burning vegetation cell (≈ 10 × FLIN, per 30 m cell)")

for a in ax[len(LOCS):]:
    a.remove()
fig.suptitle("Embers produced by burning vegetation · ELMFIRE v1.1, buildings non-burnable, one run per ignition point · "
             "blue dots = buildings, black line = MTBS perimeter", fontsize=12)
out = f"{PARENT}/ember_production_seed{SEED}.png"; fig.savefig(out, dpi=110)

t = pd.DataFrame(rows, columns=["ignition", "veg_cells_burned", "near_bldg_cells_burned", "p10", "median", "p90", "p99", "total_produced"])
print(t.round(0).to_string(index=False)); print(out)
t.round(1).to_csv(f"{PARENT}/ember_production_seed{SEED}.csv", index=False)
