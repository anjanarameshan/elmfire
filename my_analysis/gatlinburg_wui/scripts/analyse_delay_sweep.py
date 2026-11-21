#!/usr/bin/env python3
"""CELL_IGNITION_DELAY sweep on the domain extended north (domain_north30): maps and comparison with observations.

Usage: python analyse_delay_sweep.py PERIMETER.shp [delay|egen|thr]
  thr: runs domain_north30/thrN/spot2 (any prefix containing "thr", e.g. p01thr = P_EPS 0.01, works the same) - variant build, forest cells ignite from embers only above N embers/m2
  (env ELMFIRE_VEG_EMBER_THRESHOLD; folder thr0p001 = 0.001); writes thr_sweep_*.
  egen: runs domain_north30/egenGGGG/spot2 - forest ember-load threshold (DIFF_WILDLAND_IGNITION = .FALSE.) with
  EMBER_GR_PER_MW_VEGE = GGGG g/MW; writes egen_sweep_* instead of delay_sweep_*.
Runs: domain_north30/delayDDDD/spot2/seed_1..3 (original ELMFIRE build; DDDD = 0100 default, 0300, 0600, 1200, 1800 s).
CELL_IGNITION_DELAY = time from ember ignition of a vegetation cell to a fully developed burning cell.
Calibration target (chosen so the perimeter stays an independent test): burned area over time, After Action Review
(Guthrie et al. 2017, pp. 21-28), as acres added since 11:30 (AAR acres - 500). The AAR acres are for the whole
fire (also the main fire in the park, which these runs do not simulate), so model <= AAR - 500 is expected.
  score_AAR = mean |log(model / (AAR - 500))| over the AAR times 15:00-02:00 (0 = perfect)
Independent tests: MTBS perimeter - total, inside, outside, Sorensen (whole perimeter and north of the building
line, 3,953,384 m); buildings ignited inside MTBS. Domain-edge check: does the fire reach the top 3 rows?
Writes domain_north30/delay_sweep_summary.txt, delay_sweep.csv, delay_sweep_map.png.
"""
import sys, glob, os
import numpy as np
from osgeo import gdal, ogr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

gdal.UseExceptions(); ogr.UseExceptions()
D = "domain_north30"; K = sys.argv[2] if len(sys.argv) > 2 else "delay"; KL = "thr" if "thr" in K else K; Y0 = 3953384.0; T0 = 11.0; AC = 900 / 4046.856
AAR = [(15.0, 2000), (17.0, 4000), (18.0, 5000), (19.0, 6000), (20.0, 7000), (21.0, 9000), (24.0, 16000), (26.0, 17000)]
L = gdal.Open(D + "/inputs_spot2/landscape.tif"); gt = L.GetGeoTransform(); nx, ny = L.RasterXSize, L.RasterYSize
fuel = L.GetRasterBand(4).ReadAsArray(); cnt = gdal.Open(D + "/inputs_spot2/bldg_count.tif").ReadAsArray()
m = gdal.GetDriverByName("MEM").Create("", nx, ny, 1, gdal.GDT_Byte); m.SetGeoTransform(gt); m.SetProjection(L.GetProjection())
pds = ogr.Open(sys.argv[1]); gdal.RasterizeLayer(m, [1], pds.GetLayer(), burn_values=[1]); per = m.ReadAsArray() == 1
yc = gt[3] + (np.arange(ny) + 0.5) * gt[5]; north = np.repeat((yc >= Y0)[:, None], nx, 1)
obs_n = per & north; bper = (fuel == 91) & per
hours = np.arange(11.0, 27.01, 0.25)

runs = []
for c in sorted(glob.glob(D + "/%s*/spot2" % K)):
    delay = float(c.split(K)[1].split("/")[0].replace("p", "."))
    B, T = [], []
    for f in sorted(glob.glob(c + "/seed_*/outputs/time_of_arrival_*.tif")):
        t = gdal.Open(f).ReadAsArray(); B.append(t > 0); T.append(t)
    if not B:
        continue
    st = []
    for i, (b, t) in enumerate(zip(B, T)):
        h = np.sort(T0 + t[b] / 3600); curve = np.searchsorted(h, hours, "right") * AC
        mod = np.array([curve[np.argmin(abs(hours - hh))] for hh, _ in AAR])
        score = np.mean(np.abs(np.log(np.maximum(mod, 1) / np.array([a - 500 for _, a in AAR]))))
        st.append([b.sum() * AC, (b & per).sum() * AC, (b & ~per).sum() * AC, 2 * (b & per).sum() / (b.sum() + per.sum()),
                   (b & north).sum() * AC, 2 * (b & obs_n).sum() / ((b & north).sum() + obs_n.sum()),
                   cnt[bper & b].sum(), float(b[:3].any()), score, *mod])
        T[i] = curve
    runs.append((delay, np.sum(B, 0), len(B), np.mean(st, 0), np.array(st), np.array(T)))
runs.sort()

H = [{"delay": "delay_s", "egen": "ember_g_per_MW", "thr": "threshold_embers_per_m2"}[KL], "seeds", "total_ac", "inside_ac", "outside_ac", "sorensen_mtbs", "north_ac", "sorensen_north",
     "bldgs_ignited_mtbs", "reaches_top_edge_share", "score_AAR"] + ["model_ac_%02d00" % (hh % 24) for hh, _ in AAR]
with open(D + "/%s_sweep.csv" % K, "w") as f:
    f.write(",".join(H) + "\n")
    for d, _, n, s, _, _ in runs:
        f.write("%g,%d," % (d, n) + ",".join("%.3f" % v for v in s) + "\n")
lines = [{"delay": "CELL_IGNITION_DELAY sweep,", "egen": "Forest ember-load threshold, EMBER_GR_PER_MW_VEGE sweep,", "thr": "Forest ember threshold (embers/m2, variant build) sweep,"}[KL] + " domain extended 10.2 km north (seed means). MTBS %.0f ac, north of building line %.0f ac" % (
    per.sum() * AC, obs_n.sum() * AC),
    {"delay": "delay", "egen": " g/MW", "thr": "   thr"}[KL] + "   total   inside  outside  out%  Sor_MTBS  north   Sor_north  bldgs  top-edge  score_AAR (calibration, 0 = best)"]
for d, _, n, s, a, _ in runs:
    lines.append("%9g %7.0f %8.0f %8.0f %4.0f  %8.2f %7.0f   %8.2f %6.0f   %4.0f/%d   %.2f   (seeds total: %s)" % (
        d, s[0], s[1], s[2], 100 * s[2] / s[0], s[3], s[4], s[5], s[6], s[7] * n, n, s[8], ", ".join("%.0f" % v for v in a[:, 0])))
lines.append("")
lines.append("Burned area added since 11:00 vs AAR - 500 (acres):")
lines.append("time   AAR-500 " + " ".join("%9g" % d for d, *_ in runs))
for k, (hh, a) in enumerate(AAR):
    lines.append("%02d:00  %7d " % (hh % 24, a - 500) + " ".join("%9.0f" % r[3][9 + k] for r in runs))
best = min(runs, key=lambda r: r[3][8])
lines.append("")
lines.append("Closest to the AAR curve: " + K + " %g (score %.2f); its perimeter test: Sorensen %.2f, outside %.0f ac" % (
    best[0], best[3][8], best[3][3], best[3][2]))
txt = "\n".join(lines); print(txt); open(D + "/%s_sweep_summary.txt" % K, "w").write(txt + "\n")

# ---- figure: maps + area over time ----
runs = [r for r in runs if r[3][0] > 1000]  # map only runs that grew beyond the ignition area (all are in the table)
anyb = per.copy()
for r in runs:
    anyb |= r[1] > 0
rr, cc = np.where(anyb); pad = 33
r0, r1, c0, c1 = max(rr.min() - pad, 0), min(rr.max() + pad, ny), max(cc.min() - pad, 0), min(cc.max() + pad, nx)
ext = [(gt[0] + c0 * gt[1]) / 1000, (gt[0] + c1 * gt[1]) / 1000, (gt[3] + r1 * gt[5]) / 1000, (gt[3] + r0 * gt[5]) / 1000]
cmap = ListedColormap(["#fdd9b5", "#f08c3a", "#b33a06"])
n = len(runs); fig = plt.figure(figsize=(3.6 * n + 5.5, 8.4))
gs = fig.add_gridspec(1, n + 1, width_ratios=[1] * n + [1.55])
for k, (d, fr, ns, s, _, _) in enumerate(runs):
    a = fig.add_subplot(gs[0, k])
    a.imshow(per[r0:r1, c0:c1], extent=ext, cmap=ListedColormap(["#ffffff", "#eef0f2"]), interpolation="nearest")
    a.imshow(np.ma.masked_equal(fr[r0:r1, c0:c1], 0), extent=ext, cmap=cmap, vmin=0.5, vmax=3.5, interpolation="nearest")
    a.contour(np.flipud(per[r0:r1, c0:c1]).astype(float), levels=[0.5], colors="#1f2328", linewidths=0.9, extent=ext, origin="lower")
    a.axhline(Y0 / 1000, color="#1f2328", lw=0.9, ls="--"); a.axhline(gt[3] / 1000 - 0.03, color="#7a3b8f", lw=1.2)
    a.axhline(3965.617, color="#7a3b8f", lw=0.9, ls=":")
    a.set_title(("delay %d s%s" % (d, " (default)" if d == 100 else "")) if K == "delay" else ("threshold, %d g/MW" % d if K == "egen" else "%g embers/m2" % d), loc="left", fontsize=11, color="#1f2328",
                weight="bold" if d == best[0] else "normal")
    a.text(0.03, 0.985, "total %s ac\ninside %s / outside %s\noverlap MTBS %.2f\nbuildings %.0f%s" % (
        format(round(s[0]), ","), format(round(s[1]), ","), format(round(s[2]), ","), s[3], s[6],
        "\nreaches domain edge" if s[7] > 0 else ""), transform=a.transAxes, va="top", fontsize=8.3, color="#1f2328",
        bbox=dict(facecolor="white", edgecolor="#d0d7de", boxstyle="round,pad=0.35"))
    a.set_aspect("equal"); a.tick_params(colors="#57606a", labelsize=8); a.set_xlabel("easting (km)", color="#57606a", fontsize=9)
    if k == 0:
        a.set_ylabel("northing (km), UTM 17N", color="#57606a")
    else:
        a.set_yticklabels([])
a = fig.add_subplot(gs[0, n])
pal = ["#1f2328", "#2b7bba", "#2e9c5a", "#e07b24", "#9b2c2c", "#7a3b8f"]
for k, (d, _, ns, s, _, curves) in enumerate(runs):
    a.plot(hours, np.median(curves, 0), color=pal[k % len(pal)], lw=2, label={"delay": "delay %g s", "egen": "%g g/MW", "thr": "%g embers/m2"}[KL] % d)
    for cv in curves:
        a.plot(hours, cv, color=pal[k % len(pal)], lw=0.7, alpha=0.3)
ah = np.array([p[0] for p in AAR]); aa = np.array([p[1] - 500 for p in AAR])
a.plot(ah, aa, "o-", color="#c0392b", lw=2.4, ms=6, mec="white", mew=1.5, label="AAR acres - 500 (whole fire)")
a.set_xticks(range(11, 28, 2)); a.set_xticklabels(["%02d:00" % (h % 24) for h in range(11, 28, 2)], fontsize=8.5)
a.set_ylabel("acres burned since 11:00", color="#57606a"); a.set_xlabel("time (EST), 28-29 Nov 2016", color="#57606a")
a.spines[["top", "right"]].set_visible(False); a.grid(color="#eeeeee"); a.legend(frameon=False, fontsize=8.5, loc="upper left")
a.set_title("Burned area over time (thin = seeds)", loc="left", fontsize=11, color="#1f2328")
fig.legend(handles=[Patch(color=c, label="burned in %d of 3 seeds" % (i + 1)) for i, c in enumerate(cmap.colors)] +
           [Patch(facecolor="#eef0f2", edgecolor="#1f2328", label="MTBS perimeter"),
            Line2D([], [], color="#1f2328", ls="--", label="building line"),
            Line2D([], [], color="#7a3b8f", ls=":", label="old domain edge"),
            Line2D([], [], color="#7a3b8f", label="new domain edge")], loc="lower center", ncol=7, frameon=False, fontsize=9)
fig.suptitle({"delay": "ELMFIRE spot-fire development delay (CELL_IGNITION_DELAY) sweep,", "egen": "ELMFIRE forest ember-load threshold, ember generation (EMBER_GR_PER_MW_VEGE) sweep,", "thr": "ELMFIRE forest ember threshold sweep (variant build),"}[KL] + " domain extended 10 km north, 28 Nov 11:00 - 29 Nov 03:00",
             x=0.01, ha="left", fontsize=12.5, weight="bold", color="#1f2328")
fig.tight_layout(rect=(0, 0.05, 1, 0.96)); fig.savefig(D + "/%s_sweep_map.png" % K, dpi=140, facecolor="white")
print("wrote", D + "/%s_sweep_map.png" % K)
