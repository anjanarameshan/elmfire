#!/usr/bin/env python3
"""Slope at the Gatlinburg buildings (1,614 footprints in MTBS; 10 m USGS 3DEP DEM, vulnerability/features_topo.csv).
Left: map of buildings coloured by slope class. Right: number of labelled buildings and share burned (label A) per class.
Writes fragility_concept/building_slopes.png.
"""
import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

t = {r["id"]: r for r in csv.DictReader(open("vulnerability/features_topo.csv"))}
f = list(csv.DictReader(open("vulnerability/features.csv")))
x = np.array([float(r["x"]) for r in f]) / 1e3; y = np.array([float(r["y"]) for r in f]) / 1e3
s = np.array([float(t[r["id"]]["slope_deg"]) for r in f]); o = np.array([int(r["y_A"]) for r in f])
bins = [(0, 5, "0–5°", "#cde2fb"), (5, 15, "5–15°", "#86b6ef"), (15, 25, "15–25°", "#3987e5"), (25, 90, "> 25°", "#184f95")]
INK, MUTED, GRID = "#1f2328", "#57606a", "#e6e6e6"
fig, ax = plt.subplots(1, 2, figsize=(13, 6.6), gridspec_kw=dict(width_ratios=[1.05, 1]))
a = ax[0]
for lo, hi, lab, c in bins:
    m = (s >= lo) & (s < hi)
    a.scatter(x[m], y[m], s=7, color=c, lw=0.2, edgecolor="#7a8794", label="%s (%d)" % (lab, m.sum()))
a.set_aspect("equal"); a.set_xlabel("UTM 17N easting (km)", color=MUTED); a.set_ylabel("northing (km)", color=MUTED)
a.legend(title="slope at building (all 1,614)", fontsize=8.5, title_fontsize=9, frameon=False, loc="upper left", markerscale=2.5)
a.set_title("Buildings inside the MTBS perimeter, by slope", loc="left", color=INK, fontsize=11)
a = ax[1]
k = o >= 0; n, sh = [], []
for lo, hi, lab, c in bins:
    m = k & (s >= lo) & (s < hi); n.append(m.sum()); sh.append(o[m].mean())
xs = np.arange(len(bins))
bars = a.bar(xs, n, color=[b[3] for b in bins], width=0.62, edgecolor="white", linewidth=2)
for i, (nn, p) in enumerate(zip(n, sh)):
    a.text(i, nn + 8, "%d buildings\n%.0f %% burned" % (nn, 100 * p), ha="center", va="bottom", fontsize=9, color=INK)
a.set_xticks(xs); a.set_xticklabels([b[2] for b in bins]); a.set_xlabel("slope at building (10 m DEM)", color=MUTED)
a.set_ylabel("labelled buildings (survived / damaged / destroyed)", color=MUTED); a.set_ylim(0, max(n) * 1.25)
a.set_title("Labelled buildings per slope class and share burned", loc="left", color=INK, fontsize=11)
for a in ax:
    a.spines[["top", "right"]].set_visible(False); a.tick_params(colors=MUTED, labelsize=8.5)
ax[1].grid(axis="y", color=GRID, lw=0.6); ax[1].set_axisbelow(True)
fig.suptitle("Gatlinburg 2016: building slope (median %.0f°, 10–90 %%: %.0f–%.0f°) and observed losses (raw, not adjusted for vegetation)" % (
    np.median(s), *np.percentile(s, [10, 90])), x=0.01, ha="left", fontsize=11.5, weight="bold", color=INK)
fig.tight_layout(rect=(0, 0, 1, 0.95)); fig.savefig("fragility_concept/building_slopes.png", dpi=150, facecolor="white")
print("wrote fragility_concept/building_slopes.png")
