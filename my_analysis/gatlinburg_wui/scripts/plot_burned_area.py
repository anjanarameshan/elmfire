#!/usr/bin/env python3
"""Burned area vs time for the 50-run stochastic study (ms_st09: 5 spot locations x 10 seeds).

Usage: python plot_burned_area.py CASES_DIR OUT.png
Burned area at time t = number of cells with 0 < time_of_arrival <= t, x 30 m x 30 m.
Run start (t = 0): 28 Nov 2016 11:00 EST.
"""
import sys, glob, os
import numpy as np
from osgeo import gdal
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

gdal.UseExceptions()
cases_dir, out = sys.argv[1:3]
CASES = [("spot2", "Observed"), ("spot2_N1km", "1 km N"), ("spot2_S1km", "1 km S"), ("spot2_E1km", "1 km E"), ("spot2_W1km", "1 km W")]
COL = {"spot2": "#c8551b", "spot2_N1km": "#d7191c", "spot2_S1km": "#2f6690", "spot2_E1km": "#4daf4a", "spot2_W1km": "#984ea3"}
plt.rcParams.update({"font.size": 14, "axes.spines.top": False, "axes.spines.right": False})

hours = np.arange(0, 16.01, 0.25)
fig, ax = plt.subplots(figsize=(13, 7.2))
for c, lab in CASES:
    curves = []
    for s in range(1, 11):
        d = gdal.Open(glob.glob(os.path.join(cases_dir, c, "seed_%d" % s, "outputs", "time_of_arrival_*.tif"))[0])
        cell_ac = d.GetGeoTransform()[1] ** 2 / 4046.856
        t = d.GetRasterBand(1).ReadAsArray()
        t = np.sort(t[t > 0]) / 3600.0
        curves.append(np.searchsorted(t, hours, side="right") * cell_ac)
    curves = np.array(curves)
    ax.fill_between(hours, curves.min(0), curves.max(0), color=COL[c], alpha=0.18, lw=0)
    ax.plot(hours, curves.mean(0), color=COL[c], lw=2.8, label="%s  (%s ac)" % (lab, format(round(curves[:, -1].mean()), ",")))
    print(lab, "final mean %.0f min %.0f max %.0f" % (curves[:, -1].mean(), curves[:, -1].min(), curves[:, -1].max()))
ticks = np.arange(0, 17, 2)
ax.set_xticks(ticks); ax.set_xticklabels(["%02d:00" % ((11 + t) % 24) for t in ticks])
ax.set_xlabel("time (EST), 28 Nov 11:00 → 29 Nov 03:00")
ax.set_ylabel("burned area (acres, cumulative)")
ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: format(int(x), ",")))
ax.legend(loc="upper left", frameon=False, fontsize=13, title="spot fire  (mean at 03:00)", title_fontsize=13)
ax.set_title("Burned area from the spot fire. Line = mean of 10 runs; band = min–max over the 10 seeds", fontsize=13, color="#6a7383")
fig.tight_layout(); fig.savefig(out, dpi=150, facecolor="white")
