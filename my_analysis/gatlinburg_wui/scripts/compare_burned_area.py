#!/usr/bin/env python3
"""Model burned area over time vs the acreage timeline in the After Action Review.

Usage: python compare_burned_area.py PERIMETER.shp
Observed: Guthrie et al. (2017), After Action Review of the November 28, 2016, Firestorm, pp. 21-28 (acres of the whole
Chimney Tops 2 fire; the AAR notes these are "mostly estimates or interpolation from estimates ... from the GSMNP").
Runs: ms_st09/<location>/seed_1..10 (50 runs), no new runs. The simulations start 28 Nov 11:00 EST from the spot-fire
ignition, so they do not contain the ~500 acres burned in the park before then. Two comparisons are therefore made:
  total     model area vs AAR acres
  added     model area vs AAR acres minus the 500 acres reported at 11:30
Model area at time t = 30 m cells with 0 < time of arrival <= t; also shown: the part inside the MTBS perimeter.
Writes timeline/burned_area.csv, timeline/burned_area.png and prints the comparison at the AAR times.
"""
import sys, glob, os
import numpy as np
from osgeo import gdal, ogr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

gdal.UseExceptions(); ogr.UseExceptions()
OUT = "timeline"; os.makedirs(OUT, exist_ok=True)
T0 = 11.0
LOCS = [("spot2", "observed"), ("spot2_N1km", "N 1 km"), ("spot2_S1km", "S 1 km"), ("spot2_E1km", "E 1 km"), ("spot2_W1km", "W 1 km")]
LCOL = ["#222222", "#2b7bba", "#e07b24", "#7a3b8f", "#2e9c5a"]
# AAR acreage, clock hours EST on 28 Nov (24 = midnight, 26 = 02:00 on 29 Nov)
AAR = [(11.5, 500, "p.21"), (15.0, 2000, "p.22"), (17.0, 4000, "p.22"), (18.0, 5000, "p.23"), (19.0, 6000, "p.24"),
       (20.0, 7000, "p.24"), (21.0, 9000, "p.26"), (24.0, 16000, "p.26"), (26.0, 17000, "p.26")]
BASE = 500.0
AC = 900 / 4046.86

L = gdal.Open("ms_st09/spot2/inputs/landscape.tif"); gt = L.GetGeoTransform()
m = gdal.GetDriverByName("MEM").Create("", L.RasterXSize, L.RasterYSize, 1, gdal.GDT_Byte)
m.SetGeoTransform(gt); m.SetProjection(L.GetProjection())
pds = ogr.Open(sys.argv[1]); gdal.RasterizeLayer(m, [1], pds.GetLayer(), burn_values=[1]); per = m.ReadAsArray() == 1

hours = np.arange(11.0, 27.01, 0.25)
tot, ins, lab = [], [], []
for loc, l in LOCS:
    for s in range(1, 11):
        f = glob.glob("ms_st09/%s/seed_%d/outputs/time_of_arrival_*.tif" % (loc, s))
        if not f:
            continue
        ds = gdal.Open(f[0]); t = ds.GetRasterBand(1).ReadAsArray(); del ds
        b = t > 0; h = T0 + t[b] / 3600; hp = T0 + t[b & per] / 3600
        tot.append(np.searchsorted(np.sort(h), hours, "right") * AC)
        ins.append(np.searchsorted(np.sort(hp), hours, "right") * AC)
        lab.append(l)
tot, ins, lab = np.array(tot), np.array(ins), np.array(lab)
print("runs:", len(lab))

with open(OUT + "/burned_area.csv", "w") as f:
    f.write("location,seed_index,hour_EST," + "acres_total,acres_inside_MTBS\n")
    for i, l in enumerate(lab):
        for j, hh in enumerate(hours):
            f.write("%s,%d,%.2f,%.1f,%.1f\n" % (l, i % 10 + 1, hh, tot[i, j], ins[i, j]))


def hm(x):
    return "%02d:%02d" % (int(x) % 24, round((x % 1) * 60))


lines = ["Model burned area (50 runs, median [min-max]) vs After Action Review acres",
         "time   AAR total  AAR added since 11:30   model total              model inside MTBS"]
for hh, a, pg in AAR:
    j = np.argmin(abs(hours - hh))
    q = np.percentile(tot[:, j], [0, 50, 100]); qi = np.median(ins[:, j])
    lines.append("%s  %7.0f    %7.0f (%s)          %6.0f [%6.0f-%6.0f]   %6.0f" % (hm(hh), a, a - BASE, pg, q[1], q[0], q[2], qi))
lines.append("")
lines.append("Growth rate 18:00-24:00: AAR %.0f ac/h; model median %.0f ac/h" %
             ((16000 - 5000) / 6, np.median(tot[:, np.argmin(abs(hours - 24))] - tot[:, np.argmin(abs(hours - 18))]) / 6))
txt = "\n".join(lines); print(txt); open(OUT + "/burned_area_summary.txt", "w").write(txt + "\n")

# figure
fig, ax = plt.subplots(1, 2, figsize=(14, 5.4), facecolor="white")
for k, (a, ttl) in enumerate([(tot, "A. Total burned area"), (ins, "B. Burned area inside the MTBS perimeter")]):
    x = ax[k]
    for (loc, l), c in zip(LOCS, LCOL):
        sel = lab == l
        for row in a[sel]:
            x.plot(hours, row, color=c, lw=0.8, alpha=0.35)
        x.plot(hours, np.median(a[sel], 0), color=c, lw=2.2)
    ah = np.array([p[0] for p in AAR]); aa = np.array([p[1] for p in AAR])
    x.plot(ah, aa, "-", color="#c0392b", lw=2.5, zorder=5)
    x.scatter(ah, aa, s=46, color="#c0392b", edgecolors="white", linewidths=1.5, zorder=6)
    x.plot(ah, aa - BASE, "--", color="#c0392b", lw=1.6, zorder=5)
    x.set_xlim(11, 27); x.set_xticks(range(11, 28, 2)); x.set_xticklabels([hm(h) for h in range(11, 28, 2)], fontsize=8.5)
    x.set_xlabel("time (EST), 28-29 Nov 2016"); x.set_ylabel("acres"); x.grid(color="#eeeeee"); x.set_axisbelow(True)
    x.spines[["top", "right"]].set_visible(False); x.set_title(ttl, loc="left", fontsize=11)
ax[1].set_ylim(ax[0].get_ylim())
ax[0].legend(handles=[Line2D([], [], color=c, lw=2.2, label="model, spot fire " + l + " (median; thin = runs)") for (_, l), c in zip(LOCS, LCOL)] +
             [Line2D([], [], color="#c0392b", lw=2.5, marker="o", label="After Action Review (whole fire)"),
              Line2D([], [], color="#c0392b", lw=1.6, ls="--", label="After Action Review minus 500 ac before 11:30")],
             loc="upper left", fontsize=8, frameon=False)
fig.suptitle("Burned area over time: model (50 runs, start 28 Nov 11:00) vs After Action Review estimates", fontsize=12.5,
             weight="bold", x=0.02, ha="left")
fig.tight_layout(); fig.savefig(OUT + "/burned_area.png", dpi=150, facecolor="white")
print("wrote timeline/burned_area.png, burned_area.csv, burned_area_summary.txt")
