#!/usr/bin/env python3
"""Ember landings on non-burnable buildings for each ignition location, side by side with the observed damage.

Usage: python ember_count_locations_map.py PERIMETER.shp PARENT LOC [LOC ...]
  PARENT/LOC/ember_count_by_building.csv from ember_count_check.py; land shaded by share of runs burned.
Writes PARENT/ember_count_locations_map.png.
"""
import sys, glob
import numpy as np
import pandas as pd
from osgeo import gdal, ogr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, LogNorm

gdal.UseExceptions(); ogr.UseExceptions()
SHP, PARENT, LOCS = sys.argv[1], sys.argv[2].rstrip("/"), sys.argv[3:]
NAMES = {"spot2": "reported", "spot2_N1km": "1 km north", "spot2_S1km": "1 km south",
         "spot2_E1km": "1 km east", "spot2_W1km": "1 km west"}
t0 = gdal.Open(glob.glob(f"{PARENT}/{LOCS[0]}/seed_1/outputs/time_of_arrival_*.tif")[0]); gt = t0.GetGeoTransform()
ny, nx = t0.RasterYSize, t0.RasterXSize
m = gdal.GetDriverByName("MEM").Create("", nx, ny, 1, gdal.GDT_Byte); m.SetGeoTransform(gt); m.SetProjection(t0.GetProjection())
pds = ogr.Open(SHP); gdal.RasterizeLayer(m, [1], pds.GetLayer(), burn_values=[1]); per = m.ReadAsArray() == 1

F = {l: pd.read_csv(f"{PARENT}/{l}/ember_count_by_building.csv") for l in LOCS}
f0 = F[LOCS[0]]
pad = 400; x0, x1, y0, y1 = f0.x.min() - pad, f0.x.max() + pad, f0.y.min() - pad, f0.y.max() + pad
c0, c1 = int((x0 - gt[0]) / gt[1]), int((x1 - gt[0]) / gt[1]); r0, r1 = int((y1 - gt[3]) / gt[5]), int((y0 - gt[3]) / gt[5])
ext = [(gt[0] + c0 * gt[1]) / 1e3, (gt[0] + c1 * gt[1]) / 1e3, (gt[3] + r1 * gt[5]) / 1e3, (gt[3] + r0 * gt[5]) / 1e3]
X, Y = f0.x.values / 1e3, f0.y.values / 1e3
vmax = max(f.mean_all.max() for f in F.values())

fig, ax = plt.subplots(2, 3, figsize=(15, 13.5), sharex=True, sharey=True, constrained_layout=True)
ax = ax.ravel()
for a in ax:
    a.imshow(per[r0:r1, c0:c1], extent=ext, cmap=ListedColormap(["#ffffff", "#f3f4f6"]), interpolation="nearest")
    a.contour(np.flipud(per[r0:r1, c0:c1]).astype(float), levels=[0.5], colors="#1f2328", linewidths=0.9, extent=ext, origin="lower")
    a.set_aspect("equal"); a.set_xlim(ext[0], ext[1]); a.set_ylim(ext[2], ext[3])

k = f0.y_A.values
for v, col, lab in [(-1, "#c4c7cc", "new / unsure"), (0, "#4a8fc9", "not destroyed"), (1, "#c2412d", "destroyed")]:
    s = k == v; ax[0].scatter(X[s], Y[s], s=6, c=col, lw=0, label=f"{lab} ({s.sum()})")
ax[0].set_title("Observed damage", fontsize=12); ax[0].legend(loc="lower left", fontsize=9, markerscale=2)

for a, l in zip(ax[1:], LOCS):
    seeds = sorted(glob.glob(f"{PARENT}/{l}/seed_*/outputs"))
    P = np.mean([gdal.Open(glob.glob(s + "/time_of_arrival_*.tif")[0]).ReadAsArray() > 0 for s in seeds], 0)
    a.imshow(np.ma.masked_equal(P[r0:r1, c0:c1], 0), extent=ext, cmap="Oranges", vmin=0, vmax=1.6, alpha=0.6, interpolation="nearest")
    f = F[l]; z = f.mean_all.values; zero = z <= 0; o = np.argsort(z[~zero])
    a.scatter(X[zero], Y[zero], s=4, c="#d0d3d6", lw=0)
    sc = a.scatter(X[~zero][o], Y[~zero][o], s=7, c=z[~zero][o], cmap="viridis", norm=LogNorm(0.1, vmax), lw=0)
    lab = f[f.y_A >= 0]
    a.set_title(f"Spot fire 2, {NAMES.get(l, l)} ({len(seeds)} runs)\n"
                f"embers on: destroyed {(lab[lab.y_A == 1].p_ember > 0).mean():.0%} · "
                f"not destroyed {(lab[lab.y_A == 0].p_ember > 0).mean():.0%}", fontsize=10.5)
fig.colorbar(sc, ax=ax[1:], shrink=0.5, label="embers landed on the building's 30 m cell, mean per run (grey = none)")
for a in ax[3:]:
    a.set_xlabel("UTM 17N easting (km)")
for a in ax[::3]:
    a.set_ylabel("northing (km)")
fig.suptitle("Gatlinburg, ELMFIRE v1.1 with non-burnable buildings, 16 h · orange = land burned (share of runs) · "
             "black line = MTBS perimeter", fontsize=12)
fig.savefig(PARENT + "/ember_count_locations_map.png", dpi=110)
print(PARENT + "/ember_count_locations_map.png")
