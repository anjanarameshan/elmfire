#!/usr/bin/env python3
"""Side-by-side maps of one seed for the baseline and spread-reduction tests.

Usage: python plot_spread_tests_map.py PERIMETER.shp SEED OUT.png LABEL=CASE_DIR [LABEL=CASE_DIR ...]
  e.g. "Baseline (Eulerian)=ms_st09/spot2" "Lagrangian, 1 particle = 100 embers=spread_reduction/step3_lag100/spot2"
Colours: burned by surface spread (orange), burned after ember ignition (red), building cell ignited (black),
building cell not ignited (green), MTBS perimeter (blue line), spot fire (cyan triangle).
Title per panel: burned acres; buildings ignited inside the MTBS perimeter (by embers).
"""
import sys, glob
import numpy as np
from osgeo import gdal, ogr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D

gdal.UseExceptions(); ogr.UseExceptions()
shp, seed, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
cases = [a.rsplit("=", 1) for a in sys.argv[4:]]


def rd(p, k=1):
    ds = gdal.Open(p); return ds.GetRasterBand(k).ReadAsArray()


base_in = cases[0][1] + "/inputs"
L = gdal.Open(base_in + "/landscape.tif"); gt = L.GetGeoTransform(); fuel = L.GetRasterBand(4).ReadAsArray()
cnt = rd(base_in + "/bldg_count.tif"); phi = rd(base_in + "/phi.tif")
m = gdal.GetDriverByName("MEM").Create("", L.RasterXSize, L.RasterYSize, 1, gdal.GDT_Byte)
m.SetGeoTransform(gt); m.SetProjection(L.GetProjection())
pds = ogr.Open(shp); gdal.RasterizeLayer(m, [1], pds.GetLayer(), burn_values=[1]); per = m.ReadAsArray() == 1
bldg = fuel == 91; bper = bldg & per; ac = gt[1] ** 2 / 4046.86

# perimeter outline in km (projected) and plot window from the baseline burned area + perimeter
lyr = pds.GetLayer(); lyr.ResetReading(); rings = []
for ft in lyr:
    g = ft.GetGeometryRef()
    from osgeo import osr
    g = g.Clone(); g.TransformTo(osr.SpatialReference(wkt=L.GetProjection()))
    polys = [g.GetGeometryRef(i) for i in range(g.GetGeometryCount())] if "MULTI" in g.GetGeometryName() else [g]
    for pg in polys:
        r = pg.GetGeometryRef(0); rings.append(np.array([r.GetPoint_2D(i) for i in range(r.GetPointCount())]))
x0, y0 = gt[0], gt[3]
t0 = rd(glob.glob("%s/seed_%d/outputs/time_of_arrival_*.tif" % (cases[0][1], seed))[0])
ii, jj = np.where((t0 > 0) | per)
r0, r1 = max(ii.min() - 20, 0), min(ii.max() + 20, fuel.shape[0] - 1)
c0, c1 = max(jj.min() - 20, 0), min(jj.max() + 20, fuel.shape[1] - 1)
ext = [(c0 * gt[1]) / 1e3, ((c1 + 1) * gt[1]) / 1e3, -((r1 + 1) * gt[1]) / 1e3, -(r0 * gt[1]) / 1e3]
sl = (slice(r0, r1 + 1), slice(c0, c1 + 1))
sy, sx = np.argwhere(phi < 0).mean(0)

n = len(cases); ncol = n if n <= 3 else 3; nrow = (n + ncol - 1) // ncol
fig, axs = plt.subplots(nrow, ncol, figsize=(6.4 * ncol, 7.4 * nrow), squeeze=False)
for ax in axs.flat[n:]:
    ax.axis("off")
for ax, (label, case) in zip(axs.flat, cases):
    o = "%s/seed_%d/outputs" % (case, seed)
    t = rd(glob.glob(o + "/time_of_arrival_*.tif")[0]); e = rd(glob.glob(o + "/ember_ignition_*.tif")[0]) > 0
    b = t > 0
    ax.imshow(np.where(bldg[sl], 1.0, np.nan), extent=ext, cmap=ListedColormap(["#39a845"]), interpolation="nearest")
    ax.imshow(np.where((b & ~e & ~bldg)[sl], 1.0, np.nan), extent=ext, cmap=ListedColormap(["#f4a259"]), interpolation="nearest")
    ax.imshow(np.where((b & e & ~bldg)[sl], 1.0, np.nan), extent=ext, cmap=ListedColormap(["#c0392b"]), interpolation="nearest")
    ax.imshow(np.where((b & bldg)[sl], 1.0, np.nan), extent=ext, cmap=ListedColormap(["#111111"]), interpolation="nearest")
    ei, ej = np.where((b & e & bldg)[sl])       # building cells ignited by embers: circled
    ax.scatter((c0 + ej + 0.5) * gt[1] / 1e3, -(r0 + ei + 0.5) * gt[1] / 1e3, s=90, facecolors="none", edgecolors="#e600e6", linewidths=2, zorder=6)
    for q in rings:
        ax.plot((q[:, 0] - x0) / 1e3, (q[:, 1] - y0) / 1e3, color="#1f5fbf", lw=1.4)
    ax.plot((sx + 0.5) * gt[1] / 1e3, -(sy + 0.5) * gt[1] / 1e3, "^", color="#00e5ff", mec="k", ms=11, zorder=5)
    ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
    ax.set_xlabel("km"); ax.tick_params(labelsize=8)
    ax.set_title("%s\nburned %s ac | buildings ignited in perimeter: %d of %d (by embers: %d)"
                 % (label, format(round(b.sum() * ac), ","), cnt[bper & b].sum(), cnt[bper].sum(), cnt[bper & b & e].sum()), fontsize=10.5)
fig.legend(handles=[Line2D([], [], ls="", marker="s", color="#f4a259", ms=9, label="burned by surface spread"),
                    Line2D([], [], ls="", marker="s", color="#c0392b", ms=9, label="burned after ember ignition"),
                    Line2D([], [], ls="", marker="s", color="#111111", ms=9, label="building cell ignited"),
                    Line2D([], [], ls="", marker="s", color="#39a845", ms=9, label="building cell not ignited"),
                    Line2D([], [], ls="", marker="o", mfc="none", mec="#e600e6", mew=2, ms=10, label="building ignited by embers"),
                    Line2D([], [], color="#1f5fbf", lw=1.6, label="MTBS perimeter"),
                    Line2D([], [], ls="", marker="^", color="#00e5ff", mec="k", ms=10, label="spot fire 2")],
           loc="lower center", ncol=7, fontsize=10, frameon=False)
fig.suptitle("Observed spot fire 2, seed %d, 28 Nov 11:00 → 29 Nov 03:00 EST" % seed, fontsize=13, weight="bold")
fig.tight_layout(rect=(0, 0.05 / nrow, 1, 1 - 0.04 / nrow)); fig.savefig(out, dpi=140, facecolor="white")
print("wrote", out)
