#!/usr/bin/env python3
"""Ignition pathway of buildings: heat from burning forest vs heat from burning neighbouring buildings.

Usage: python analyse_ignition_pathway.py PERIMETER.shp
Runs: ignition_pathway/<location>/seed_<n> (same set-up as ms_st09, run with the pathway-diagnostic build
my_analysis/elmfire_variant/build/linux/bin/elmfire_1.1_pathway; spread outputs are byte-identical to ms_st09).
Diagnostic rasters (per building cell, WU-E heat flux at its last unignited time step):
  path_frac_bldg = share of the heat coming from burning building cells (rest: burning vegetation cells)
  path_frac_dfc  = share of the heat by direct flame contact (rest: radiation)
  path_q         = total heat flux, kW/m2
Classes (building-weighted, inside the MTBS perimeter): mostly forest (< 25 % of heat from buildings),
mixed (25-75 %), mostly buildings (> 75 %).
Writes ignition_pathway/pathway_summary.csv and ignition_pathway/ignition_pathway.png.
"""
import sys, glob, os
import numpy as np
from osgeo import gdal, ogr, osr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D

gdal.UseExceptions(); ogr.UseExceptions()
shp = sys.argv[1]
LOCS = [("spot2", "observed"), ("spot2_N1km", "N 1 km"), ("spot2_S1km", "S 1 km"), ("spot2_E1km", "E 1 km"), ("spot2_W1km", "W 1 km")]
CLS = ["mostly forest", "mixed", "mostly buildings"]
COL = ["#b5651d", "#9a9a9a", "#6a3d9a"]
T0 = 11.0   # simulation start, 28 Nov 11:00 EST


def rd(p):
    ds = gdal.Open(p); return ds.GetRasterBand(1).ReadAsArray()


L = gdal.Open("ms_st09/spot2/inputs/landscape.tif"); gt = L.GetGeoTransform(); fuel = L.GetRasterBand(4).ReadAsArray()
cnt = rd("ms_st09/spot2/inputs/bldg_count.tif")
m = gdal.GetDriverByName("MEM").Create("", L.RasterXSize, L.RasterYSize, 1, gdal.GDT_Byte)
m.SetGeoTransform(gt); m.SetProjection(L.GetProjection())
pds = ogr.Open(shp); gdal.RasterizeLayer(m, [1], pds.GetLayer(), burn_values=[1]); per = m.ReadAsArray() == 1
bldg = fuel == 91; bper = bldg & per


def classify(fb):
    return np.where(fb < 0.25, 0, np.where(fb > 0.75, 2, 1))


rows, hourly = [], np.zeros((3, 17))
for loc, lab in LOCS:
    for d in sorted(glob.glob("ignition_pathway/%s/seed_*" % loc), key=lambda s: int(s.rsplit("_", 1)[1])):
        if not (os.path.exists(d + "/elmfire.log") and "finished" in open(d + "/elmfire.log").read()):
            continue
        o = d + "/outputs/"
        t = rd(glob.glob(o + "time_of_arrival_*.tif")[0]); fb = rd(glob.glob(o + "path_frac_bldg_*.tif")[0])
        fd = rd(glob.glob(o + "path_frac_dfc_*.tif")[0])
        ig = bper & (t > 0) & (fb >= 0)
        c = classify(fb[ig]); w = cnt[ig]
        n = [w[c == k].sum() for k in range(3)]
        hrs = np.clip((t[ig] / 3600).astype(int), 0, 16)
        for k in range(3):
            hourly[k] += np.bincount(hrs[c == k], weights=w[c == k], minlength=17)
        rows.append((lab, int(d.rsplit("_", 1)[1]), int(w.sum()), *n,
                     np.average(fb[ig], weights=w), np.average(fd[ig], weights=w),
                     int(cnt[bper & (t > 0) & (fb < 0)].sum())))

with open("ignition_pathway/pathway_summary.csv", "w") as f:
    f.write("location,seed,buildings_ignited_in_perimeter,mostly_forest,mixed,mostly_buildings,"
            "mean_share_heat_from_buildings,mean_share_flame_contact,ignited_without_record\n")
    for r in rows:
        f.write("%s,%d,%d,%d,%d,%d,%.3f,%.3f,%d\n" % r)

print("%-10s %5s %8s %14s %8s %17s %11s %11s" % ("location", "runs", "ignited", "mostly forest", "mixed",
                                                 "mostly buildings", "heat bldg", "flame cont."))
summ = []
for _, lab in LOCS:
    R = np.array([r[2:8] for r in rows if r[0] == lab], float)
    if not len(R):
        continue
    a = R.mean(0); summ.append((lab, a))
    print("%-10s %5d %8.0f %8.0f (%2.0f%%) %4.0f (%2.0f%%) %9.0f (%2.0f%%) %10.0f%% %10.0f%%" % (
        lab, len(R), a[0], a[1], 100 * a[1] / a[0], a[2], 100 * a[2] / a[0], a[3], 100 * a[3] / a[0], 100 * a[4], 100 * a[5]))
R = np.array([r[2:8] for r in rows], float); a = R.mean(0)
print("%-10s %5d %8.0f %8.0f (%2.0f%%) %4.0f (%2.0f%%) %9.0f (%2.0f%%) %10.0f%% %10.0f%%" % (
    "all", len(R), a[0], a[1], 100 * a[1] / a[0], a[2], 100 * a[2] / a[0], a[3], 100 * a[3] / a[0], 100 * a[4], 100 * a[5]))
print("ignited building cells without a heat record (all runs):", sum(r[8] for r in rows))

# ---------------- figure ----------------
fig = plt.figure(figsize=(17, 7.6), facecolor="white")
gs = fig.add_gridspec(2, 2, width_ratios=[1.05, 1], height_ratios=[1, 1], wspace=0.18, hspace=0.38)

# A: map, observed location seed 1
ax = fig.add_subplot(gs[:, 0])
o = "ignition_pathway/spot2/seed_1/outputs/"
t = rd(glob.glob(o + "time_of_arrival_*.tif")[0]); fb = rd(glob.glob(o + "path_frac_bldg_*.tif")[0])
ii, jj = np.where(bper)          # zoom to the buildings inside the perimeter
r0, r1 = max(ii.min() - 15, 0), min(ii.max() + 15, fuel.shape[0] - 1)
c0, c1 = max(jj.min() - 15, 0), min(jj.max() + 15, fuel.shape[1] - 1)
sl = (slice(r0, r1 + 1), slice(c0, c1 + 1))
ext = [c0 * gt[1] / 1e3, (c1 + 1) * gt[1] / 1e3, -(r1 + 1) * gt[1] / 1e3, -r0 * gt[1] / 1e3]
ax.imshow(np.where(((t > 0) & ~bldg)[sl], 1.0, np.nan), extent=ext, cmap=ListedColormap(["#e4e4e4"]), interpolation="nearest")
ax.imshow(np.where((bldg & ~(t > 0))[sl], 1.0, np.nan), extent=ext, cmap=ListedColormap(["#39a845"]), interpolation="nearest")
cl = np.where(bldg & (t > 0) & (fb >= 0), classify(fb), -1)[sl].astype(float); cl[cl < 0] = np.nan
ax.imshow(cl, extent=ext, cmap=ListedColormap(COL), vmin=-0.5, vmax=2.5, interpolation="nearest")
lyr = pds.GetLayer(); lyr.ResetReading()
for ft in lyr:
    g = ft.GetGeometryRef().Clone(); g.TransformTo(osr.SpatialReference(wkt=L.GetProjection()))
    for pg in ([g.GetGeometryRef(i) for i in range(g.GetGeometryCount())] if "MULTI" in g.GetGeometryName() else [g]):
        q = np.array(pg.GetGeometryRef(0).GetPoints())[:, :2]
        ax.plot((q[:, 0] - gt[0]) / 1e3, (q[:, 1] - gt[3]) / 1e3, color="#1f5fbf", lw=1.3)
ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3]); ax.set_xlabel("km"); ax.tick_params(labelsize=8)
ax.set_title("A. Where the heat came from when each building cell ignited\n(observed spot fire, seed 1)", fontsize=11, loc="left")
ax.legend(handles=[Line2D([], [], ls="", marker="s", color=COL[k], ms=9, label="%s heat" % CLS[k]) for k in range(3)] +
          [Line2D([], [], ls="", marker="s", color="#39a845", ms=9, label="building cell not ignited"),
           Line2D([], [], ls="", marker="s", color="#e4e4e4", ms=9, label="burned forest"),
           Line2D([], [], color="#1f5fbf", lw=1.5, label="MTBS perimeter")],
          loc="lower left", fontsize=8.5, framealpha=0.95)

# B: buildings per class, per ignition location (mean of runs)
ax = fig.add_subplot(gs[0, 1])
labs = [s[0] for s in summ]; y = np.arange(len(labs))[::-1]
left = np.zeros(len(labs))
for k in range(3):
    v = np.array([s[1][1 + k] for s in summ])
    ax.barh(y, v, left=left, color=COL[k], edgecolor="white", linewidth=2, height=0.62, label=CLS[k])
    for yi, l, vi, tot in zip(y, left, v, [s[1][0] for s in summ]):
        if vi / tot > 0.08:
            ax.text(l + vi / 2, yi, "%.0f%%" % (100 * vi / tot), ha="center", va="center", fontsize=8.5, color="white")
    left += v
for yi, tot in zip(y, left):
    ax.text(tot + 15, yi, "%.0f" % tot, va="center", fontsize=8.5, color="#333333")
ax.set_yticks(y); ax.set_yticklabels(labs, fontsize=9); ax.set_xlim(0, left.max() * 1.1)
ax.set_xlabel("buildings ignited inside the MTBS perimeter (mean of 10 runs)", fontsize=9)
ax.set_title("B. Source of heat at ignition, by spot-fire location", fontsize=11, loc="left")
ax.spines[["top", "right"]].set_visible(False); ax.tick_params(labelsize=8)

# C: ignitions per hour by class (all runs, mean per run)
ax = fig.add_subplot(gs[1, 1])
nrun = len(rows); hrs = np.arange(17); bot = np.zeros(17)
for k in range(3):
    ax.bar(hrs, hourly[k] / nrun, bottom=bot, color=COL[k], edgecolor="white", linewidth=1, width=0.85, label=CLS[k])
    bot += hourly[k] / nrun
ax.set_xticks(hrs[::2]); ax.set_xticklabels(["%02d:00" % ((T0 + h) % 24) for h in hrs[::2]], fontsize=8)
ax.set_ylabel("buildings ignited per hour", fontsize=9); ax.set_xlabel("time (EST), 28-29 Nov 2016", fontsize=9)
ax.set_title("C. Source of heat over time (mean of all %d runs)" % nrun, fontsize=11, loc="left")
ax.spines[["top", "right"]].set_visible(False); ax.tick_params(labelsize=8); ax.grid(axis="y", color="#eeeeee"); ax.set_axisbelow(True)

fig.suptitle("Building ignition pathway in ELMFIRE (WU-E model): forest-to-building vs building-to-building heat",
             fontsize=13, weight="bold", x=0.02, ha="left")
fig.savefig("ignition_pathway/ignition_pathway.png", dpi=150, facecolor="white", bbox_inches="tight")
print("wrote ignition_pathway/ignition_pathway.png and ignition_pathway/pathway_summary.csv")
