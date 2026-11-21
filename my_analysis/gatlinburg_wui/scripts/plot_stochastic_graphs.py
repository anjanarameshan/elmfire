#!/usr/bin/env python3
"""Graphs from the 50-run stochastic study (ms_st09: 5 spot locations x 10 seeds).

Usage: python plot_stochastic_graphs.py CASES_DIR PERIMETER.shp OUT_PREFIX
Writes OUT_PREFIX_1_per_location.png   buildings ignited inside the MTBS perimeter, 10 runs per location
       OUT_PREFIX_2_convergence.png    running mean vs number of runs
       OUT_PREFIX_3_over_time.png      cumulative buildings ignited vs clock time (EST)
       OUT_PREFIX_4_ember_vs_threshold.png  ember mass load on building cells vs the ST09 ignition threshold
Run start: 28 Nov 2016 11:00 EST (t = 0); building cell = fuel 91; count = bldg_count of ignited cells.
"""
import sys, glob, os
import numpy as np
from osgeo import gdal, ogr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

gdal.UseExceptions(); ogr.UseExceptions()
cases_dir, shp, outp = sys.argv[1:4]
CASES = [("spot2", "Observed"), ("spot2_N1km", "1 km N"), ("spot2_S1km", "1 km S"), ("spot2_E1km", "1 km E"), ("spot2_W1km", "1 km W")]
COL = {"spot2": "#c8551b", "spot2_N1km": "#d7191c", "spot2_S1km": "#2f6690", "spot2_E1km": "#4daf4a", "spot2_W1km": "#984ea3"}
NAVY, GREY, BG = "#14213d", "#6a7383", "#f7f5f0"
plt.rcParams.update({"font.size": 14, "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": BG, "axes.facecolor": BG})


def band(p, k=1):
    d = gdal.Open(p); return d.GetRasterBand(k).ReadAsArray()


inp = os.path.join(cases_dir, "spot2", "inputs")
L = gdal.Open(inp + "/landscape.tif"); fuel = L.GetRasterBand(4).ReadAsArray()
cnt = band(inp + "/bldg_count.tif")
m = gdal.GetDriverByName("MEM").Create("", L.RasterXSize, L.RasterYSize, 1, gdal.GDT_Byte)
m.SetGeoTransform(L.GetGeoTransform()); m.SetProjection(L.GetProjection())
pds = ogr.Open(shp); gdal.RasterizeLayer(m, [1], pds.GetLayer(), burn_values=[1]); per = m.ReadAsArray() == 1
bper = (fuel == 91) & per
cell_area = L.GetGeoTransform()[1] ** 2

counts, times, psi_max = {}, {}, []
for c, _ in CASES:
    counts[c], times[c] = [], []
    for s in range(1, 11):
        o = os.path.join(cases_dir, c, "seed_%d" % s, "outputs")
        t = band(glob.glob(o + "/time_of_arrival_*.tif")[0])
        ign = bper & (t > 0)
        counts[c].append(cnt[ign].sum())
        times[c].append((t[ign] / 3600.0, cnt[ign]))
        e = band(o + "/ember_flux.tif")
        psi_max.append(e[bper])
psi_all = np.concatenate(psi_max) / cell_area * 0.2 / 1e4   # every building cell in every run, g/cm2
total_in_per = int(cnt[bper].sum())

# ---------- 1. per location ----------
fig, ax = plt.subplots(figsize=(13, 7.2))
rng = np.random.default_rng(0)
for i, (c, lab) in enumerate(CASES):
    v = np.array(counts[c]); x = i + rng.uniform(-0.12, 0.12, v.size)
    ax.scatter(x, v, s=90, color=COL[c], alpha=0.85, edgecolor="white", zorder=3)
    ax.plot([i - 0.28, i + 0.28], [v.mean()] * 2, color=NAVY, lw=3, zorder=4)
    ax.text(i + 0.32, v.mean(), "%d" % round(v.mean()), va="center", fontsize=14, weight="bold", color=NAVY)
ax.set_xticks(range(len(CASES))); ax.set_xticklabels([l for _, l in CASES], fontsize=15)
ax.set_ylabel("buildings ignited inside the MTBS perimeter")
ax.set_ylim(850, 1350)
ax.set_title("Each dot = one run (10 seeds per location); bar = mean.  %d mapped buildings (Microsoft) inside the perimeter"
             % total_in_per, fontsize=13, color=GREY)
fig.tight_layout(); fig.savefig(outp + "_1_per_location.png", dpi=150); plt.close(fig)

# ---------- 2. convergence ----------
fig, ax = plt.subplots(figsize=(13, 7.2))
for c, lab in CASES:
    v = np.array(counts[c]); rm = np.cumsum(v) / np.arange(1, 11)
    ax.plot(range(1, 11), rm, marker="o", lw=2.5, ms=7, color=COL[c], label=lab)
    se = v.std(ddof=1) / np.sqrt(10)
    ax.fill_between([9.6, 10.4], rm[-1] - se, rm[-1] + se, color=COL[c], alpha=0.25, lw=0)
ax.set_xticks(range(1, 11)); ax.set_xlabel("number of runs averaged (seeds 1 … N)")
ax.set_ylabel("running mean of buildings ignited")
ax.legend(ncol=5, loc="upper center", bbox_to_anchor=(0.5, 1.12), frameon=False, fontsize=13)
ax.text(10.45, 900, "shaded: ± SE\nafter 10 runs\n(< 1 %)", fontsize=12, color=GREY, va="bottom")
fig.tight_layout(); fig.savefig(outp + "_2_convergence.png", dpi=150); plt.close(fig)

# ---------- 3. over time ----------
hours = np.arange(0, 16.01, 0.25)
fig, ax = plt.subplots(figsize=(13, 7.2))
for c, lab in CASES:
    curves = np.array([[w[th <= h].sum() for h in hours] for th, w in times[c]])
    ax.fill_between(hours, curves.min(0), curves.max(0), color=COL[c], alpha=0.18, lw=0)
    ax.plot(hours, curves.mean(0), color=COL[c], lw=2.8, label=lab)
ticks = np.arange(0, 17, 2)
ax.set_xticks(ticks); ax.set_xticklabels(["%02d:00" % ((11 + t) % 24) for t in ticks])
ax.set_xlabel("time (EST), 28 Nov 11:00 → 29 Nov 03:00")
ax.set_ylabel("buildings ignited inside the perimeter (cumulative)")
ax.legend(loc="upper left", frameon=False, fontsize=13)
ax.set_title("Line = mean of 10 runs; band = min–max over the 10 seeds", fontsize=13, color=GREY)
fig.tight_layout(); fig.savefig(outp + "_3_over_time.png", dpi=150); plt.close(fig)

# ---------- 4. ember pile vs threshold (histogram, log scale) ----------
H = 7.0
crit = lambda v: 0.211 / ((v + 0.073) * (4.111 - v))
need_best = crit(1.35) / H          # most favourable roof wind seen in the runs (1.35 m/s)
need_eve = crit(0.85) / H           # 30 mph at 20 ft -> 0.85 m/s at the roof
v = psi_all[psi_all > 0]
with plt.rc_context({"figure.facecolor": "white", "axes.facecolor": "white"}):
    fig, ax = plt.subplots(figsize=(13, 7.2))
    ax.hist(v, bins=np.logspace(-10, -1, 46), color="#2f6690", alpha=0.85)
    ax.set_xscale("log")
    top = ax.get_ylim()[1] * 1.3; ax.set_ylim(0, top)
    ax.axvline(v.max(), color="#14213d", lw=2.5)
    ax.text(v.max() * 0.8, top * 0.92, "largest load on any building\nin the perimeter, 50 runs:\n%.4f g/cm²" % v.max(), ha="right", va="top",
            fontsize=12.5, color="#14213d")
    ax.axvline(need_best, color="#c8551b", lw=2.5, ls="--")
    ax.axvspan(need_best, 1e-1, color="#c8551b", alpha=0.08)
    ax.text(1.4e-2, top * 0.92, "needed to ignite\n(ST09 threshold):\n%.4f g/cm²\nat the strongest wind\nin our weather input\n(47.6 mph at 20 ft\n= 1.35 m/s at roof)"
            % need_best, fontsize=12.5, color="#c8551b", va="top")
    ax.annotate("", xy=(v.max(), top * 0.45), xytext=(need_best, top * 0.45), arrowprops=dict(arrowstyle="<->", color=GREY, lw=1.8))
    ax.text(np.sqrt(v.max() * need_best), top * 0.42, "%.1f×\nshort" % (need_best / v.max()), ha="center", va="top",
            fontsize=13, color=GREY, weight="bold")
    ax.set_xticks([10.0 ** k for k in range(-10, 0)])
    ax.set_xticklabels(["$10^{%d}$" % k for k in range(-10, 0)])
    tr = matplotlib.transforms.blended_transform_factory(ax.transData, ax.transAxes)
    for val, txt, col, ha in ((v.max(), "%.4f" % v.max(), "#14213d", "right"), (need_best, "%.4f" % need_best, "#c8551b", "left")):
        ax.text(val * (0.9 if ha == "right" else 1.1), 0.02, txt, transform=tr, ha=ha, va="bottom", fontsize=12, weight="bold", color=col,
                bbox=dict(fc="white", ec="none", pad=1.5))
    ax.set_xlabel("ember mass load ψ on a building cell (g/cm², log scale; $10^{-3}$ = 0.001, $10^{-2}$ = 0.01)")
    ax.set_ylabel("number of building cells (50 runs together)")
    ax.set_title("Ember load on building cells inside the MTBS perimeter, all 50 runs; none reached the ST09 threshold (shaded = would ignite)",
                 fontsize=13, color=GREY)
    fig.tight_layout(); fig.savefig(outp + "_4_ember_vs_threshold.png", dpi=150, facecolor="white"); plt.close(fig)

for c, lab in CASES:
    vv = np.array(counts[c]); print(lab, "mean %.0f min %d max %d" % (vv.mean(), vv.min(), vv.max()))
print("cells", v.size, "median %.2e p99 %.2e max %.5f need %.5f %.5f" % (np.median(v), np.percentile(v, 99), v.max(), need_best, need_eve))
