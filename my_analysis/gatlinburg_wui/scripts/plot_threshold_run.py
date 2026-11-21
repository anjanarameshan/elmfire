#!/usr/bin/env python3
"""Map of one forest ember-threshold run (domain_north30/thrN/spot2, seeds 1-3) against the MTBS perimeter.

Usage: python plot_threshold_run.py PERIMETER.shp THRESHOLD   (e.g. 0.001 -> folder thr0p001)
       python plot_threshold_run.py PERIMETER.shp FOLDER "TITLE"   (any run folder under domain_north30, e.g. leafoff_p01)
       python plot_threshold_run.py PERIMETER.shp RUNDIR "TITLE"   (any directory holding seed_*/; inputs from seed_1/inputs,
                                                                   map written next to it as <RUNDIR>_map.png)
Left: number of seeds (of 3) that burned each cell. Right: time of arrival (earliest seed that burned the cell, EST).
Both: MTBS perimeter, building line (northing 3,953,384 m), burned building cells (black dots = burned in >= 2 seeds).
Writes domain_north30/thrN_map.png.
"""
import sys, glob, os
import numpy as np
from osgeo import gdal, ogr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

gdal.UseExceptions(); ogr.UseExceptions()
D = "domain_north30"; Y0 = 3953384.0; AC = 900 / 4046.856; T0 = 11.0
thr = sys.argv[2]; name = thr if os.path.isdir("%s/%s" % (D, thr)) else "thr" + (thr.zfill(4) if thr.isdigit() else thr.replace(".", "p"))
if glob.glob(thr.rstrip("/") + "/seed_*"):
    RUN = thr.rstrip("/"); INP = RUN + "/seed_1/inputs"; OUTPNG = RUN + "_map.png"; name = RUN
else:
    RUN = "%s/%s/spot2" % (D, name); INP = D + "/inputs_spot2"; OUTPNG = "%s/%s_map.png" % (D, name)
L = gdal.Open(INP + "/landscape.tif"); gt = L.GetGeoTransform(); nx, ny = L.RasterXSize, L.RasterYSize
fuel = L.GetRasterBand(4).ReadAsArray(); cnt = gdal.Open(INP + "/bldg_count.tif").ReadAsArray()
m = gdal.GetDriverByName("MEM").Create("", nx, ny, 1, gdal.GDT_Byte); m.SetGeoTransform(gt); m.SetProjection(L.GetProjection())
pds = ogr.Open(sys.argv[1]); gdal.RasterizeLayer(m, [1], pds.GetLayer(), burn_values=[1]); per = m.ReadAsArray() == 1
T = [gdal.Open(f).ReadAsArray() for f in sorted(glob.glob(RUN + "/seed_*/outputs/time_of_arrival_*.tif"))]
B = [t > 0 for t in T]; fr = np.sum(B, 0); n = len(B)
toa = np.where(fr > 0, np.min([np.where(b, T0 + t / 3600, np.inf) for b, t in zip(B, T)], 0), np.nan)
tot = np.mean([b.sum() for b in B]) * AC; ins = np.mean([(b & per).sum() for b in B]) * AC
bld = np.mean([cnt[(fuel == 91) & per & b].sum() for b in B])
yc = gt[3] + (np.arange(ny) + 0.5) * gt[5]; north = np.repeat((yc >= Y0)[:, None], nx, 1); obs_n = per & north
nor = np.mean([(b & north).sum() for b in B]) * AC; sor = np.mean([2 * (b & obs_n).sum() / ((b & north).sum() + obs_n.sum()) for b in B])
bout = np.mean([cnt[(fuel == 91) & ~per & b].sum() for b in B])
print("%s: total %.0f (seeds %s), inside %.0f, outside %.0f, north %.0f (obs %.0f), Sorensen north %.2f, buildings in/out MTBS %.0f / %.0f" % (
    name, tot, ", ".join("%.0f" % (b.sum() * AC) for b in B), ins, tot - ins, nor, obs_n.sum() * AC, sor, bld, bout))

rr, cc = np.where(per | (fr > 0)); pad = 25
r0, r1, c0, c1 = max(rr.min() - pad, 0), min(rr.max() + pad, ny), max(cc.min() - pad, 0), min(cc.max() + pad, nx)
ext = [(gt[0] + c0 * gt[1]) / 1000, (gt[0] + c1 * gt[1]) / 1000, (gt[3] + r1 * gt[5]) / 1000, (gt[3] + r0 * gt[5]) / 1000]
by, bx = np.where(((fuel == 91) & (fr >= 2))[r0:r1, c0:c1])
bxk = (gt[0] + (c0 + bx + 0.5) * gt[1]) / 1000; byk = (gt[3] + (r0 + by + 0.5) * gt[5]) / 1000

fig, ax = plt.subplots(1, 2, figsize=(9.6, 9.4), sharey=True)
for k, a in enumerate(ax):
    a.imshow(per[r0:r1, c0:c1], extent=ext, cmap=ListedColormap(["#ffffff", "#eef0f2"]), interpolation="nearest")
    if k == 0:
        a.imshow(np.ma.masked_equal(fr[r0:r1, c0:c1], 0), extent=ext, cmap=ListedColormap(["#fdd9b5", "#f08c3a", "#b33a06"]),
                 vmin=0.5, vmax=3.5, interpolation="nearest")
        a.set_title("Burned in how many of %d seeds" % n, loc="left", fontsize=11.5, color="#1f2328")
    else:
        bounds = [11, 15, 17, 19, 21, 23, 27.01]
        cm = ListedColormap(["#fde725", "#7ad151", "#22a884", "#2a788e", "#414487", "#440154"])
        im = a.imshow(toa[r0:r1, c0:c1], extent=ext, cmap=cm, norm=BoundaryNorm(bounds, cm.N), interpolation="nearest")
        cb = fig.colorbar(im, ax=a, fraction=0.035, pad=0.02, ticks=bounds[:-1] + [27])
        cb.ax.set_yticklabels(["%02d:00" % (b % 24) for b in bounds[:-1]] + ["03:00"], fontsize=8.5)
        cb.set_label("fire arrival, 28-29 Nov (EST), earliest seed", color="#57606a")
        a.set_title("When the fire arrived", loc="left", fontsize=11.5, color="#1f2328")
    a.contour(np.flipud(per[r0:r1, c0:c1]).astype(float), levels=[0.5], colors="#1f2328", linewidths=1.0, extent=ext, origin="lower")
    a.axhline(Y0 / 1000, color="#1f2328", lw=1, ls="--")
    a.scatter(bxk, byk, s=2.5, color="black", lw=0)
    a.set_aspect("equal"); a.set_xlabel("UTM 17N easting (km)", color="#57606a"); a.tick_params(colors="#57606a", labelsize=8.5)
ax[0].set_ylabel("northing (km)", color="#57606a")
ax[0].text(0.02, 0.985, "seed mean: total %s ac\ninside MTBS %s / outside %s\nbuildings in burned cells (MTBS) %.0f" % (
    format(round(tot), ","), format(round(ins), ","), format(round(tot - ins), ","), bld), transform=ax[0].transAxes, va="top",
    fontsize=9, color="#1f2328", bbox=dict(facecolor="white", edgecolor="#d0d7de", boxstyle="round,pad=0.4"))
fig.legend(handles=[Patch(color=c, label="burned in %d of %d seeds" % (i + 1, n)) for i, c in enumerate(["#fdd9b5", "#f08c3a", "#b33a06"])] +
           [Patch(facecolor="#eef0f2", edgecolor="#1f2328", label="MTBS observed burn perimeter"),
            Line2D([], [], color="#1f2328", ls="--", label="building line"),
            Line2D([], [], marker="o", ls="", color="black", ms=3, label="building cell burned (>= 2 seeds)")],
           loc="lower center", ncol=3, frameon=False, fontsize=9)
fig.suptitle((sys.argv[3] if len(sys.argv) > 3 else "Forest ember threshold %s embers/m² (about %s per 30 m cell)" % (
    thr, "%g" % (float(thr) * 900))) + ", 28 Nov 11:00 - 29 Nov 03:00", x=0.01, ha="left", fontsize=10.5, weight="bold", color="#1f2328")
fig.tight_layout(rect=(0, 0.07, 1, 0.96)); fig.savefig(OUTPNG, dpi=150, facecolor="white")
print("wrote " + OUTPNG)
