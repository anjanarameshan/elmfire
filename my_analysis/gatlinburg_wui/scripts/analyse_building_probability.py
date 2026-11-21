#!/usr/bin/env python3
"""Ignition probability of each building cell from the 50-run stochastic study, and the site factors behind it.

Usage: python analyse_building_probability.py PERIMETER.shp [CASE_ROOT=ms_st09]
Runs: CASE_ROOT/<location>/seed_1..10 for the 5 spot-fire locations (50 runs). Building cells inside the MTBS
perimeter only.
  P(ignite)            = runs in which the cell ignited / all runs
  P(ignite | exposed)  = runs in which it ignited / runs in which fire burned an adjacent cell (8 neighbours)
                         (fire within 150 m is too loose: cells that never ignite had fire within 150 m in ~40 of 50 runs)
  Only building cells holding at least one building centroid are used (roof-sliver cells are left out).
Site factors per building cell:
  distance to vegetation  distance to the nearest burnable vegetation cell (fuel model > 100), m, capped at 300 m
  neighbour bldg cells    other building cells within 150 m (+-5 cells)
  separation              bldg_separation input (mean gap between buildings in the cell), m
  plan dimension          bldg_area input (sqrt of mean footprint), m
  slope                   landscape band 2, degrees
Logistic regression (binomial, IRLS) of P(ignite | exposed) on the standardised factors: odds ratio per 1 SD.
Writes building_probability/{building_probability.csv, regression.csv, building_probability.png}.
"""
import sys, glob, os
import numpy as np
from osgeo import gdal, ogr, osr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

gdal.UseExceptions(); ogr.UseExceptions()
shp = sys.argv[1]; root = sys.argv[2] if len(sys.argv) > 2 else "ms_st09"
LOCS = ["spot2", "spot2_N1km", "spot2_S1km", "spot2_E1km", "spot2_W1km"]
OUT = "building_probability"; os.makedirs(OUT, exist_ok=True)


def rd(p, k=1):
    ds = gdal.Open(p); return ds.GetRasterBand(k).ReadAsArray()


inp = "ms_st09/spot2/inputs/"
L = gdal.Open(inp + "landscape.tif"); gt = L.GetGeoTransform(); dx = gt[1]
fuel = rd(inp + "landscape.tif", 4); slope = rd(inp + "landscape.tif", 2).astype(float)
cnt = rd(inp + "bldg_count.tif"); sep = rd(inp + "bldg_separation.tif"); area = rd(inp + "bldg_area.tif")
m = gdal.GetDriverByName("MEM").Create("", L.RasterXSize, L.RasterYSize, 1, gdal.GDT_Byte)
m.SetGeoTransform(gt); m.SetProjection(L.GetProjection())
pds = ogr.Open(shp); gdal.RasterizeLayer(m, [1], pds.GetLayer(), burn_values=[1]); per = m.ReadAsArray() == 1
bldg = fuel == 91; bper = bldg & per & (cnt > 0); veg = fuel > 100
ny, nx = fuel.shape


def window_any(a, r):
    """True where any cell of a lies within the (2r+1)^2 window."""
    p = np.pad(a, r); o = np.zeros_like(a, bool)
    for di in range(-r, r + 1):
        for dj in range(-r, r + 1):
            o |= p[r + di:r + di + ny, r + dj:r + dj + nx]
    return o


def window_sum(a, r):
    p = np.pad(a.astype(np.int32), r); o = np.zeros(a.shape, np.int32)
    for di in range(-r, r + 1):
        for dj in range(-r, r + 1):
            o += p[r + di:r + di + ny, r + dj:r + dj + nx]
    return o


# distance to nearest vegetation cell (Euclidean, up to 10 cells = 300 m)
R = 10; dveg = np.full(fuel.shape, R * dx); pv = np.pad(veg, R)
for di in range(-R, R + 1):
    for dj in range(-R, R + 1):
        d = np.hypot(di, dj) * dx
        if d <= R * dx:
            hit = pv[R + di:R + di + ny, R + dj:R + dj + nx]
            dveg = np.where(hit & (d < dveg), d, dveg)
nbr = window_sum(bldg, 5) - bldg

# ignition and exposure counts over the 50 runs
ign = np.zeros(fuel.shape, np.int32); exp_ = np.zeros(fuel.shape, np.int32); nrun = 0; per_loc = {}
for loc in LOCS:
    il = np.zeros(fuel.shape, np.int32)
    for s in range(1, 11):
        f = glob.glob("%s/%s/seed_%d/outputs/time_of_arrival_*.tif" % (root, loc, s))
        if not f:
            continue
        b = rd(f[0]) > 0
        ign += b & bldg; il += b & bldg; nrun += 1
        burned_other = window_sum(b, 1) - b          # burned adjacent cells, not counting the cell itself
        exp_ += (burned_other > 0) & bldg
    per_loc[loc] = il
print("runs used:", nrun)

idx = np.where(bper)
P = ign[idx] / nrun; E = exp_[idx]; K = ign[idx]; W = cnt[idx]
Pc = np.where(E > 0, K / np.maximum(E, 1), np.nan)
X = {"distance to vegetation (m)": dveg[idx], "neighbour building cells within 150 m": nbr[idx].astype(float),
     "separation between buildings (m)": sep[idx].astype(float), "building plan dimension (m)": area[idx].astype(float),
     "slope (deg)": slope[idx]}

with open(OUT + "/building_probability.csv", "w") as f:
    f.write("row,col,buildings,p_ignite,runs_exposed,p_ignite_given_exposed," + ",".join(k.split(" (")[0].replace(" ", "_") for k in X) + "\n")
    for n in range(len(P)):
        f.write("%d,%d,%d,%.3f,%d,%s," % (idx[0][n], idx[1][n], W[n], P[n], E[n], "" if np.isnan(Pc[n]) else "%.3f" % Pc[n])
                + ",".join("%.2f" % X[k][n] for k in X) + "\n")

# summary
print("building cells (with >= 1 building) in perimeter: %d (%d buildings)" % (len(P), W.sum()))
print("expected buildings ignited (sum of p x buildings): %.0f" % (P * W).sum())
for lo, hi in [(0, 0.001), (0.001, 0.2), (0.2, 0.5), (0.5, 0.8), (0.8, 0.999), (0.999, 1.01)]:
    s = (P >= lo) & (P < hi); print("  p in [%.2f, %.2f): %4d cells, %4d buildings" % (lo, min(hi, 1), s.sum(), W[s].sum()))
print("never exposed in any run: %d cells (%d buildings)" % ((E == 0).sum(), W[E == 0].sum()))
se_max = 0.5 / np.sqrt(nrun)
print("per-cell probability: 1 SE at most +-%.3f, 95%% CI at most +-%.2f with %d runs" % (se_max, 1.96 * se_max, nrun))
half = [loc for loc in LOCS]
# run-count check for the per-cell probability: first 5 seeds vs all 10 seeds of each location
ign5 = np.zeros(fuel.shape, np.int32); n5 = 0
for loc in LOCS:
    for s in range(1, 6):
        f = glob.glob("%s/%s/seed_%d/outputs/time_of_arrival_*.tif" % (root, loc, s))
        if f:
            ign5 += (rd(f[0]) > 0) & bldg; n5 += 1
d = np.abs(ign5[idx] / n5 - P)
print("per-cell p, %d runs vs %d runs: mean |difference| %.3f, 95th pct %.3f, max %.3f" % (n5, nrun, d.mean(), np.percentile(d, 95), d.max()))

# logistic regression on exposed cells: K successes of E trials
ok = E > 0
Z = np.column_stack([X[k][ok] for k in X]); mu, sd = Z.mean(0), Z.std(0); Zs = (Z - mu) / sd
A = np.column_stack([np.ones(ok.sum()), Zs]); y, n = K[ok].astype(float), E[ok].astype(float)
beta = np.zeros(A.shape[1])
for _ in range(50):
    eta = A @ beta; p = 1 / (1 + np.exp(-eta)); w = n * p * (1 - p)
    H = A.T @ (A * w[:, None]); g = A.T @ (y - n * p); step = np.linalg.solve(H, g); beta += step
    if np.abs(step).max() < 1e-8:
        break
cov = np.linalg.inv(H); se = np.sqrt(np.diag(cov))
ll = np.sum(y * np.log(np.clip(p, 1e-12, 1)) + (n - y) * np.log(np.clip(1 - p, 1e-12, 1)))
p0 = y.sum() / n.sum(); ll0 = np.sum(y * np.log(p0) + (n - y) * np.log(1 - p0))
print("\nlogistic regression, P(ignite | exposed), %d exposed building cells; McFadden pseudo-R2 = %.2f" % (ok.sum(), 1 - ll / ll0))
print("%-40s %8s %8s %16s %8s" % ("factor", "mean", "SD", "odds ratio/SD", "z"))
with open(OUT + "/regression.csv", "w") as f:
    f.write("factor,mean,sd,coef_per_sd,se,odds_ratio_per_sd,or_low95,or_high95,z\n")
    for k, b_, s_, m_, d_ in zip(X, beta[1:], se[1:], mu, sd):
        print("%-40s %8.1f %8.1f %6.2f (%.2f-%.2f) %8.1f" % (k, m_, d_, np.exp(b_), np.exp(b_ - 1.96 * s_), np.exp(b_ + 1.96 * s_), b_ / s_))
        f.write("%s,%.3f,%.3f,%.4f,%.4f,%.3f,%.3f,%.3f,%.2f\n" % (k, m_, d_, b_, s_, np.exp(b_), np.exp(b_ - 1.96 * s_), np.exp(b_ + 1.96 * s_), b_ / s_))
    f.write("intercept,,,%.4f,%.4f,,,,\n" % (beta[0], se[0]))
    f.write("pseudo_R2_McFadden,%.3f,,,,,,,\n" % (1 - ll / ll0))

# ---------------- figure ----------------
fig = plt.figure(figsize=(17, 8.2), facecolor="white")
gs = fig.add_gridspec(2, 3, width_ratios=[1.25, 1, 1], wspace=0.28, hspace=0.42)
ax = fig.add_subplot(gs[:, 0])
ii, jj = idx; r0, r1 = max(ii.min() - 15, 0), min(ii.max() + 15, ny - 1); c0, c1 = max(jj.min() - 15, 0), min(jj.max() + 15, nx - 1)
sl = (slice(r0, r1 + 1), slice(c0, c1 + 1)); ext = [c0 * dx / 1e3, (c1 + 1) * dx / 1e3, -(r1 + 1) * dx / 1e3, -r0 * dx / 1e3]
pm = np.full(fuel.shape, np.nan); pm[idx] = P
ax.imshow(np.where(veg[sl], 1.0, np.nan), extent=ext, cmap=ListedColormap(["#eef3ea"]), interpolation="nearest")
im = ax.imshow(pm[sl], extent=ext, cmap="magma_r", vmin=0, vmax=1, interpolation="nearest")
lyr = pds.GetLayer(); lyr.ResetReading()
for ft in lyr:
    g = ft.GetGeometryRef().Clone(); g.TransformTo(osr.SpatialReference(wkt=L.GetProjection()))
    for pg in ([g.GetGeometryRef(i) for i in range(g.GetGeometryCount())] if "MULTI" in g.GetGeometryName() else [g]):
        q = np.array(pg.GetGeometryRef(0).GetPoints())[:, :2]
        ax.plot((q[:, 0] - gt[0]) / 1e3, (q[:, 1] - gt[3]) / 1e3, color="#1f5fbf", lw=1.2)
ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3]); ax.set_xlabel("km"); ax.tick_params(labelsize=8)
cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02); cb.set_label("ignition probability (share of %d runs)" % nrun, fontsize=9)
ax.set_title("A. Ignition probability of each building cell\n(inside MTBS perimeter, blue line; light green = vegetation)", fontsize=10.5, loc="left")


def binned(ax, x, edges, title, xlabel, letter):
    c = 0.5 * (edges[:-1] + edges[1:]); pm_, pc_, nn = [], [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        s = (x >= lo) & (x < hi)
        nn.append(s.sum())
        pm_.append(P[s].mean() if s.any() else np.nan)
        e = s & ok
        pc_.append(K[e].sum() / E[e].sum() if e.any() else np.nan)
    ax.plot(c, pm_, "-o", color="#7a3b8f", lw=2, ms=6, label="P(ignite)")
    ax.plot(c, pc_, "-s", color="#e07b24", lw=2, ms=6, label="P(ignite | adjacent cell burned)")
    for ci, ni, yi in zip(c, nn, pc_):
        if ni and not np.isnan(yi):
            ax.text(ci, 0.03, "%d" % ni, ha="center", fontsize=7, color="#666666")
    ax.text(0.99, 0.09, "numbers: building cells per bin", transform=ax.transAxes, ha="right", fontsize=7, color="#666666")
    ax.set_ylim(0, 1.08); ax.set_xlabel(xlabel, fontsize=9); ax.set_ylabel("probability", fontsize=9)
    ax.set_title("%s. %s" % (letter, title), fontsize=10.5, loc="left"); ax.tick_params(labelsize=8)
    ax.spines[["top", "right"]].set_visible(False); ax.grid(color="#eeeeee"); ax.set_axisbelow(True)


axB = fig.add_subplot(gs[0, 1])
binned(axB, dveg[idx], np.array([0, 15, 45, 75, 105, 150, 210, 301]), "Distance to vegetation", "distance to nearest vegetation cell (m)", "B")
binned(fig.add_subplot(gs[0, 2]), nbr[idx], np.array([0, 5, 10, 20, 30, 45, 60, 80, 121]), "Building density", "other building cells within 150 m", "C")
binned(fig.add_subplot(gs[1, 1]), sep[idx], np.array([2, 5, 10, 15, 20, 30, 40, 60, 200]), "Separation between buildings", "mean gap between buildings in the cell (m)", "D")
ax = fig.add_subplot(gs[1, 2])
names = ["distance to vegetation", "neighbour building cells", "separation", "plan dimension", "slope"]
orv = np.exp(beta[1:]); lo_, hi_ = np.exp(beta[1:] - 1.96 * se[1:]), np.exp(beta[1:] + 1.96 * se[1:])
yy = np.arange(len(names))[::-1]
ax.axvline(1, color="#999999", lw=1)
ax.errorbar(orv, yy, xerr=[orv - lo_, hi_ - orv], fmt="o", color="#333333", ms=7, capsize=3)
for yi, o in zip(yy, orv):
    ax.text(o, yi + 0.22, "%.2f" % o, ha="center", fontsize=8)
ax.set_yticks(yy); ax.set_yticklabels(names, fontsize=9); ax.set_xscale("log")
ax.set_xticks([0.8, 1, 1.25, 1.6]); ax.set_xticklabels(["0.8", "1", "1.25", "1.6"]); ax.minorticks_off(); ax.set_xlim(0.75, 1.7); ax.set_ylim(-0.5, len(names) - 0.3)
ax.set_xlabel("odds ratio per 1 SD (95% CI)  <1 lowers, >1 raises", fontsize=9)
ax.set_title("E. Logistic regression, P(ignite | adjacent cell burned)\npseudo-R² = %.2f" % (1 - ll / ll0), fontsize=10.5, loc="left")
ax.spines[["top", "right"]].set_visible(False); ax.tick_params(labelsize=8)
axB.legend(fontsize=8.5, loc="lower left", bbox_to_anchor=(0, 0.12), frameon=False)
fig.suptitle("Which buildings ignite? Ignition probability from %d ELMFIRE runs (5 spot-fire locations x 10 seeds)" % nrun,
             fontsize=13, weight="bold", x=0.02, ha="left")
fig.savefig(OUT + "/building_probability.png", dpi=150, facecolor="white", bbox_inches="tight")
print("wrote %s/building_probability.png, building_probability.csv, regression.csv" % OUT)
