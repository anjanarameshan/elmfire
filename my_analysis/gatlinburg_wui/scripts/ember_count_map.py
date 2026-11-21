#!/usr/bin/env python3
"""Map of ember landings on non-burnable buildings (ember_count/nobldg) next to the observed damage.

Usage: python ember_count_map.py PERIMETER.shp RUNDIR [RUNDIR ...]   (after ember_count_check.py with the same RUNDIRs;
several RUNDIRs = runs pooled, e.g. the five ignition locations)
Panels: observed label y_A; share of runs in which fire reached a neighbouring cell (p_arrival) over the burn
probability of the land; mean embers landed per run on the building's cell (mean_all, ember_flux).
Writes RUNDIR/ember_count_map.png.
"""
import sys, glob
import numpy as np
import pandas as pd
from osgeo import gdal, ogr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, LogNorm
from matplotlib.lines import Line2D

gdal.UseExceptions(); ogr.UseExceptions()
import os
RUNS = [r.rstrip("/") for r in sys.argv[2:]]
RUN = RUNS[0] if len(RUNS) == 1 else os.path.commonpath(RUNS)
SUF = "" if len(RUNS) == 1 else "_all"
seeds = [s for r in RUNS for s in sorted(glob.glob(r + "/seed_*/outputs"))]
t0 = gdal.Open(glob.glob(seeds[0] + "/time_of_arrival_*.tif")[0]); gt = t0.GetGeoTransform()
P = np.mean([gdal.Open(glob.glob(s + "/time_of_arrival_*.tif")[0]).ReadAsArray() > 0 for s in seeds], 0)
ny, nx = P.shape
m = gdal.GetDriverByName("MEM").Create("", nx, ny, 1, gdal.GDT_Byte); m.SetGeoTransform(gt); m.SetProjection(t0.GetProjection())
pds = ogr.Open(sys.argv[1]); gdal.RasterizeLayer(m, [1], pds.GetLayer(), burn_values=[1]); per = m.ReadAsArray() == 1

f = pd.read_csv(RUN + "/ember_count_by_building%s.csv" % SUF)
X, Y = f.x.values / 1e3, f.y.values / 1e3
pad = 400; x0, x1, y0, y1 = f.x.min() - pad, f.x.max() + pad, f.y.min() - pad, f.y.max() + pad
c0, c1 = int((x0 - gt[0]) / gt[1]), int((x1 - gt[0]) / gt[1]); r0, r1 = int((y1 - gt[3]) / gt[5]), int((y0 - gt[3]) / gt[5])
ext = [(gt[0] + c0 * gt[1]) / 1e3, (gt[0] + c1 * gt[1]) / 1e3, (gt[3] + r1 * gt[5]) / 1e3, (gt[3] + r0 * gt[5]) / 1e3]

fig, ax = plt.subplots(1, 3, figsize=(17, 7.6), sharey=True, constrained_layout=True)
for a in ax:
    a.imshow(per[r0:r1, c0:c1], extent=ext, cmap=ListedColormap(["#ffffff", "#f3f4f6"]), interpolation="nearest")
    a.contour(np.flipud(per[r0:r1, c0:c1]).astype(float), levels=[0.5], colors="#1f2328", linewidths=0.9, extent=ext, origin="lower")
    a.set_xlabel("UTM 17N easting (km)"); a.set_aspect("equal")
ax[0].set_ylabel("northing (km)")

# 1 observed
k = f.y_A.values
for v, col, lab in [(-1, "#c4c7cc", "new / unsure"), (0, "#4a8fc9", "not destroyed"), (1, "#c2412d", "destroyed")]:
    s = k == v; ax[0].scatter(X[s], Y[s], s=7, c=col, lw=0, label=f"{lab} ({s.sum()})")
ax[0].set_title("Observed damage (aerial photo review)")
ax[0].legend(loc="lower left", fontsize=9, frameon=True, markerscale=2)

# 2 fire reach
im = ax[1].imshow(np.ma.masked_equal(P[r0:r1, c0:c1], 0), extent=ext, cmap="Oranges", vmin=0, vmax=1, alpha=0.75, interpolation="nearest")
sc = ax[1].scatter(X, Y, s=7, c=f.p_arrival, cmap="Greys", vmin=0, vmax=1, lw=0.2, edgecolors="#555")
ax[1].set_title("Fire reach, buildings non-burnable (%d runs)" % len(seeds))
fig.colorbar(im, ax=ax[1], shrink=0.6, label="land: share of runs burned  ·  dots: share of runs fire reached the building")

# 3 embers
z = f.mean_all.values; zero = z <= 0
ax[2].scatter(X[zero], Y[zero], s=6, c="#d7d9dc", lw=0, label=f"no embers in any run ({zero.sum()})")
o = np.argsort(z[~zero])
sc = ax[2].scatter(X[~zero][o], Y[~zero][o], s=9, c=z[~zero][o], cmap="viridis", norm=LogNorm(0.1, max(z.max(), 1)), lw=0)
fig.colorbar(sc, ax=ax[2], shrink=0.6, label="embers landed on the building's 30 m cell, mean per run")
ax[2].set_title("Embers landed on each building (never burns)")
ax[2].legend(loc="lower left", fontsize=9, markerscale=2)

for a in ax:
    a.set_xlim(ext[0], ext[1]); a.set_ylim(ext[2], ext[3])
fig.suptitle("Gatlinburg, %s, 16 h · ELMFIRE with non-burnable buildings · black line = MTBS perimeter" % ", ".join(os.path.basename(r) for r in RUNS), fontsize=12)
fig.savefig(RUN + "/ember_count_map%s.png" % SUF, dpi=130)
print(RUN + "/ember_count_map%s.png" % SUF)
