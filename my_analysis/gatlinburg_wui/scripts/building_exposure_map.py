#!/usr/bin/env python3
"""Building exposure ("disaster") map from one ELMFIRE run set, compared with the observed damage.

Usage: python building_exposure_map.py PERIMETER.shp RUNDIR   (e.g. domain_north30/thr0p0005/spot2, seeds 1-3)
Buildings: vulnerability/features.csv (1,614 Microsoft footprints with centroid inside MTBS; reviewer label y_A:
1 destroyed/damaged, 0 survived, -1 new/unsure = left out of the statistics, drawn grey).
Per building, from the 30 m model cell under its centroid:
  P(lost)     share of seeds in which the cell burned
  ember load  total embers landed on the cell during the run, per m2 (ember_flux, seed mean; model ember units)
  arrival     earliest seed arrival time (EST)
Statistics: AUC of P(lost) and of ember load for observed burned vs survived; hit rate / false alarms at P >= 2/3.
Writes <RUNDIR>/../building_exposure_map.png, building_exposure.csv, building_exposure_summary.txt.
"""
import sys, glob, csv, os
import numpy as np
from osgeo import gdal, ogr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm, LogNorm
from matplotlib.lines import Line2D

gdal.UseExceptions(); ogr.UseExceptions()
RUN = sys.argv[2].rstrip("/"); OUT = os.path.dirname(RUN); T0 = 11.0; Y0 = 3953384.0
seeds = sorted(glob.glob(RUN + "/seed_*/outputs"))
T = [gdal.Open(glob.glob(s + "/time_of_arrival_*.tif")[0]) for s in seeds]
gt = T[0].GetGeoTransform(); T = [t.ReadAsArray() for t in T]
F = np.mean([gdal.Open(s + "/ember_flux.tif").ReadAsArray() for s in seeds], 0) / 900.
P = np.mean([t > 0 for t in T], 0)
A = np.min([np.where(t > 0, T0 + t / 3600, np.inf) for t in T], 0)
ny, nx = P.shape
m = gdal.GetDriverByName("MEM").Create("", nx, ny, 1, gdal.GDT_Byte); m.SetGeoTransform(gt)
m.SetProjection(gdal.Open(glob.glob(seeds[0] + "/time_of_arrival_*.tif")[0]).GetProjection())
pds = ogr.Open(sys.argv[1]); gdal.RasterizeLayer(m, [1], pds.GetLayer(), burn_values=[1]); per = m.ReadAsArray() == 1

B = list(csv.DictReader(open("vulnerability/features.csv")))
x = np.array([float(b["x"]) for b in B]); y = np.array([float(b["y"]) for b in B]); obs = np.array([int(b["y_A"]) for b in B])
c = ((x - gt[0]) / gt[1]).astype(int); r = ((y - gt[3]) / gt[5]).astype(int)
p, ember, arr = P[r, c], F[r, c], A[r, c]
with open(OUT + "/building_exposure.csv", "w") as f:
    f.write("id,x,y,observed_A,p_lost,ember_per_m2,arrival_h\n")
    for b, *v in zip(B, p, ember, arr):
        f.write("%s,%s,%s,%s,%.3f,%.4g,%s\n" % (b["id"], b["x"], b["y"], b["y_A"], v[0], v[1], "%.2f" % v[2] if np.isfinite(v[2]) else ""))


def auc(s, yy):
    s1, s0 = s[yy == 1], s[yy == 0]
    return (np.sum(s1[:, None] > s0[None, :]) + 0.5 * np.sum(s1[:, None] == s0[None, :])) / (len(s1) * len(s0))


k = obs >= 0; yk = obs[k]
hit = np.mean(p[k][yk == 1] >= 2 / 3); fa = np.mean(p[k][yk == 0] >= 2 / 3); miss0 = np.mean(p[k][yk == 1] == 0)
L = ["Building exposure, %s (%d seeds); buildings with centroid in MTBS: %d, labelled %d (burned %d, survived %d)" % (
        RUN, len(seeds), len(B), k.sum(), (yk == 1).sum(), (yk == 0).sum()),
     "Model-lost (P >= 2/3): %d buildings of %d labelled" % ((p[k] >= 2 / 3).sum(), k.sum()),
     "Observed burned that the model loses (P >= 2/3): %.0f %%; never reached (P = 0): %.0f %%" % (100 * hit, 100 * miss0),
     "Observed survived that the model loses (false alarm): %.0f %%" % (100 * fa),
     "AUC P(lost) %.2f; AUC ember load %.2f (0.5 = no skill)" % (auc(p[k], yk), auc(ember[k], yk)),
     "Median ember load (embers/m2): burned %.3g, survived %.3g" % (np.median(ember[k][yk == 1]), np.median(ember[k][yk == 0])),
     "Observed burned share by model P(lost): " + ", ".join("P=%.2f: %.2f (n=%d)" % (q, yk[np.round(p[k], 2) == q].mean(), (np.round(p[k], 2) == q).sum())
                                                            for q in sorted(set(np.round(p[k], 2))))]
txt = "\n".join(L); print(txt); open(OUT + "/building_exposure_summary.txt", "w").write(txt + "\n")

# ---- map ----
pad = 400; x0, x1, y0, y1 = x.min() - pad, x.max() + pad, y.min() - pad, y.max() + pad
c0, c1 = int((x0 - gt[0]) / gt[1]), int((x1 - gt[0]) / gt[1]); r0, r1 = int((y1 - gt[3]) / gt[5]), int((y0 - gt[3]) / gt[5])
ext = [(gt[0] + c0 * gt[1]) / 1e3, (gt[0] + c1 * gt[1]) / 1e3, (gt[3] + r1 * gt[5]) / 1e3, (gt[3] + r0 * gt[5]) / 1e3]
X, Y = x / 1e3, y / 1e3
fig, ax = plt.subplots(1, 4, figsize=(19, 8.4), sharey=True)
panels = [
    ("Observed (your damage review)", None),
    ("Model: chance the building is lost", None),
    ("Model: embers landed (per m²)", None),
    ("Model: when the fire arrived", None)]
for i, a in enumerate(ax):
    a.imshow(per[r0:r1, c0:c1], extent=ext, cmap=ListedColormap(["#ffffff", "#f3f4f6"]), interpolation="nearest")
    a.imshow(np.ma.masked_equal(P[r0:r1, c0:c1], 0), extent=ext, cmap=ListedColormap(["#fde7d3"]), vmin=0, vmax=1, alpha=0.8,
             interpolation="nearest")
    a.contour(np.flipud(per[r0:r1, c0:c1]).astype(float), levels=[0.5], colors="#1f2328", linewidths=0.9, extent=ext, origin="lower")
    a.axhline(Y0 / 1e3, color="#1f2328", lw=0.9, ls="--")
    a.scatter(X[~k], Y[~k], s=5, color="#c9ccd1", lw=0)
    if i == 0:
        a.scatter(X[obs == 0], Y[obs == 0], s=7, color="#2b7bba", lw=0, label="survived (%d)" % (obs == 0).sum())
        a.scatter(X[obs == 1], Y[obs == 1], s=8, color="#b31b1b", lw=0, label="destroyed / damaged (%d)" % (obs == 1).sum())
        a.legend(loc="upper left", fontsize=8.5, frameon=True, markerscale=2.2)
    elif i == 1:
        cm = ListedColormap(["#2b7bba", "#f6c48f", "#e46b2b", "#b31b1b"])
        sc = a.scatter(X[k], Y[k], c=p[k], s=8, cmap=cm, norm=BoundaryNorm([-0.01, 0.2, 0.5, 0.8, 1.01], 4), lw=0)
        cb = fig.colorbar(sc, ax=a, fraction=0.04, pad=0.02, ticks=[0.1, 0.35, 0.65, 0.9]); cb.ax.set_yticklabels(["0 of 3", "1 of 3", "2 of 3", "3 of 3"], fontsize=8)
        cb.set_label("seeds in which the building cell burned", color="#57606a", fontsize=8.5)
    elif i == 2:
        e = np.where(ember > 0, ember, np.nan)
        sc = a.scatter(X[k], Y[k], c=e[k], s=8, cmap="magma_r", norm=LogNorm(1e-4, max(np.nanmax(e), 1e-3)), lw=0)
        a.scatter(X[k & ~(ember > 0)], Y[k & ~(ember > 0)], s=6, facecolor="none", edgecolor="#9aa0a6", lw=0.4)
        cb = fig.colorbar(sc, ax=a, fraction=0.04, pad=0.02); cb.set_label("embers per m² (model units, log); open = none", color="#57606a", fontsize=8.5)
    else:
        bounds = [11, 15, 17, 19, 21, 23, 27.01]; cm = ListedColormap(["#fde725", "#7ad151", "#22a884", "#2a788e", "#414487", "#440154"])
        ok = k & np.isfinite(arr)
        sc = a.scatter(X[ok], Y[ok], c=arr[ok], s=8, cmap=cm, norm=BoundaryNorm(bounds, cm.N), lw=0)
        a.scatter(X[k & ~np.isfinite(arr)], Y[k & ~np.isfinite(arr)], s=6, facecolor="none", edgecolor="#9aa0a6", lw=0.4)
        cb = fig.colorbar(sc, ax=a, fraction=0.04, pad=0.02, ticks=bounds[:-1] + [27])
        cb.ax.set_yticklabels(["%02d:00" % (b_ % 24) for b_ in bounds[:-1]] + ["03:00"], fontsize=8)
        cb.set_label("earliest arrival (EST); open = not reached", color="#57606a", fontsize=8.5)
    a.set_title(panels[i][0], loc="left", fontsize=11, color="#1f2328")
    a.set_aspect("equal"); a.set_xlim(ext[0], ext[1]); a.set_ylim(ext[2], ext[3])
    a.tick_params(colors="#57606a", labelsize=8); a.set_xlabel("UTM 17N easting (km)", color="#57606a", fontsize=9)
ax[0].set_ylabel("northing (km)", color="#57606a")
ax[1].text(0.02, 0.985, "observed burned lost by model: %.0f %%\nobserved survived lost by model: %.0f %%\nAUC %.2f (0.5 = no skill)" % (
    100 * hit, 100 * fa, auc(p[k], yk)), transform=ax[1].transAxes, va="top", fontsize=8.5,
    bbox=dict(facecolor="white", edgecolor="#d0d7de", boxstyle="round,pad=0.35"))
fig.legend(handles=[Line2D([], [], color="#1f2328", lw=1, label="MTBS perimeter"), Line2D([], [], color="#1f2328", ls="--", label="building line"),
                    Line2D([], [], marker="s", ls="", color="#fde7d3", ms=8, label="model burned area (any seed)"),
                    Line2D([], [], marker="o", ls="", color="#c9ccd1", ms=4, label="new / unsure (not used)")],
           loc="lower center", ncol=4, frameon=False, fontsize=9)
fig.suptitle("Building exposure inside the MTBS perimeter: ELMFIRE (%s) vs observed damage" % RUN.split("/")[1], x=0.01, ha="left",
             fontsize=12.5, weight="bold", color="#1f2328")
fig.tight_layout(rect=(0, 0.04, 1, 0.96)); fig.savefig(OUT + "/building_exposure_map.png", dpi=140, facecolor="white")
print("wrote", OUT + "/building_exposure_map.png")
