#!/usr/bin/env python3
"""Map of the 30 % ember-receptive run next to the 20 % and 40 % runs, inside AND outside the MTBS perimeter.

Usage: python plot_receptive30.py PERIMETER.shp
Runs: spread_reduction/step5_receptiveXX/spot2, XX = 20 30 40, seeds 1-3 (variant build, forest cells ember-receptive
with probability XX %, one draw per cell; fire free to spread outside the perimeter).
Shading = number of seeds (of 3) that burned the cell. Black line = MTBS perimeter; dashed = building line
(northing 3,953,384 m, southern edge of the continuous built-up area; observed MTBS area north of it 6,428 ac on grid).
Numbers per panel (seed means): total, inside / outside MTBS, north of the building line, overlap with the observed
north area (Sorensen), buildings in burned building cells inside MTBS.
Writes receptive30_map.png and receptive30_summary.txt.
"""
import sys, glob
import numpy as np
from osgeo import gdal, ogr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

gdal.UseExceptions(); ogr.UseExceptions()
Y0 = 3953384.0; AC = 900 / 4046.856
L = gdal.Open("ms_st09/spot2/inputs/landscape.tif"); gt = L.GetGeoTransform(); nx, ny = L.RasterXSize, L.RasterYSize
fuel = L.GetRasterBand(4).ReadAsArray(); cnt = gdal.Open("ms_st09/spot2/inputs/bldg_count.tif").ReadAsArray()
m = gdal.GetDriverByName("MEM").Create("", nx, ny, 1, gdal.GDT_Byte); m.SetGeoTransform(gt); m.SetProjection(L.GetProjection())
pds = ogr.Open(sys.argv[1]); gdal.RasterizeLayer(m, [1], pds.GetLayer(), burn_values=[1]); per = m.ReadAsArray() == 1
yc = gt[3] + (np.arange(ny) + 0.5) * gt[5]; north = np.repeat((yc >= Y0)[:, None], nx, 1)
obs = per & north; bper = (fuel == 91) & per

runs = {}
for f in (20, 30, 40):
    B = [gdal.Open(p).ReadAsArray() > 0 for p in sorted(glob.glob("spread_reduction/step5_receptive%d/spot2/seed_*/outputs/time_of_arrival_*.tif" % f))]
    st = [((b).sum() * AC, (b & per).sum() * AC, (b & ~per).sum() * AC, (b & north).sum() * AC,
           2 * (b & obs).sum() / ((b & north).sum() + obs.sum()), cnt[bper & b].sum()) for b in B]
    runs[f] = (np.sum(B, 0), len(B), np.mean(st, 0))

lines = ["Ember-receptive runs (seed means); observed MTBS %.0f ac, north of the building line %.0f ac" % (per.sum() * AC, obs.sum() * AC),
         "f     seeds  total ac  inside ac  outside ac  north-of-line ac  Sorensen(north)  buildings ignited in MTBS"]
for f, (_, n, s) in runs.items():
    lines.append("%2d %%  %5d  %8.0f  %9.0f  %10.0f  %16.0f  %15.2f  %8.0f" % (f, n, *s))
txt = "\n".join(lines); print(txt); open("receptive30_summary.txt", "w").write(txt + "\n")

# extent: everything burned in any run + the perimeter, 1 km margin
anyb = per.copy()
for f in runs:
    anyb |= runs[f][0] > 0
r_, c_ = np.where(anyb); pad = 33
r0, r1, c0, c1 = max(r_.min() - pad, 0), min(r_.max() + pad, ny), max(c_.min() - pad, 0), min(c_.max() + pad, nx)
ext = [(gt[0] + c0 * gt[1]) / 1000, (gt[0] + c1 * gt[1]) / 1000, (gt[3] + r1 * gt[5]) / 1000, (gt[3] + r0 * gt[5]) / 1000]
cmap = ListedColormap(["#fdd9b5", "#f08c3a", "#b33a06"])
fig, ax = plt.subplots(1, 3, figsize=(16, 8.6), sharey=True)
for k, f in enumerate(runs):
    a = ax[k]; fr, n, s = runs[f]
    img = np.ma.masked_equal(fr[r0:r1, c0:c1], 0).astype(float)
    a.imshow(per[r0:r1, c0:c1], extent=ext, cmap=ListedColormap(["#ffffff", "#eef0f2"]), interpolation="nearest")
    a.imshow(img, extent=ext, cmap=cmap, vmin=0.5, vmax=3.5, interpolation="nearest")
    a.contour(np.flipud(per[r0:r1, c0:c1]).astype(float), levels=[0.5], colors="#1f2328", linewidths=1.0,
              extent=ext, origin="lower")
    a.axhline(Y0 / 1000, color="#1f2328", lw=1, ls="--")
    a.set_title(("%d %% of forest cells ember-receptive" % f) + ("   <- new run" if f == 30 else ""), loc="left",
                fontsize=11.5, weight="bold" if f == 30 else "normal", color="#1f2328")
    a.text(0.02, 0.985, "total %s ac  (inside MTBS %s, outside %s)\nnorth of building line %s ac  (observed 6,428)\n"
           "overlap with observed, north: %.2f\nbuildings ignited in MTBS: %.0f" % (
               format(round(s[0]), ","), format(round(s[1]), ","), format(round(s[2]), ","), format(round(s[3]), ","), s[4], s[5]),
           transform=a.transAxes, va="top", fontsize=9, color="#1f2328",
           bbox=dict(facecolor="white", edgecolor="#d0d7de", boxstyle="round,pad=0.4"))
    a.set_xlabel("UTM 17N easting (km)", color="#57606a"); a.tick_params(colors="#57606a", labelsize=8.5)
    a.set_aspect("equal")
ax[0].set_ylabel("northing (km)", color="#57606a")
fig.legend(handles=[Patch(color=c, label="burned in %d of %d seeds" % (i + 1, runs[30][1])) for i, c in enumerate(cmap.colors)] +
           [Patch(facecolor="#eef0f2", edgecolor="#1f2328", label="MTBS observed burn perimeter"),
            Line2D([], [], color="#1f2328", ls="--", label="building line (southern edge of built-up area)")],
           loc="lower center", ncol=5, frameon=False, fontsize=9.5)
fig.suptitle("ELMFIRE ember-receptive runs, 28 Nov 11:00 - 29 Nov 03:00 EST (seeds 1-3), burned area inside and outside the perimeter",
             x=0.01, ha="left", fontsize=12.5, weight="bold", color="#1f2328")
fig.tight_layout(rect=(0, 0.04, 1, 0.97)); fig.savefig("receptive30_map.png", dpi=150, facecolor="white")
print("wrote receptive30_map.png, receptive30_summary.txt")
