#!/usr/bin/env python3
"""Model fire arrival at named places vs the observed timeline of 28 Nov 2016.

Usage: python compare_timeline.py
Observed times: Guthrie, Finucane, Keith and Stinnett (2017), After Action Review of the November 28, 2016,
Firestorm (ABS Group, for the City of Gatlinburg and Sevier County), pp. 21-24 and 83; cross-checked with
Walpole et al. (2020), NIST TN 2103, section 1.1. Places are traced from OpenStreetMap roads (data/osm_roads/roads_domain.json) onto the 30 m grid
(points every 5 m along each way). Runs: ms_st09/<location>/seed_1..10 (50 runs); simulation starts 28 Nov 11:00 EST.
Per run and place: arrival = time when 10 % of the road cells have burned (a single ember-ignited cell does not count),
the earliest arrival on any road cell, and the share of road cells burned by the end of the run (03:00).
Places where under 10 % of the road burns are 'not reached'.
Writes timeline/timeline_comparison.csv and timeline/timeline_comparison.png.
"""
import json, glob, os
import numpy as np
from osgeo import gdal, osr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

gdal.UseExceptions()
OUT = "timeline"; os.makedirs(OUT, exist_ok=True)
T0 = 11.0
LOCS = [("spot2", "observed"), ("spot2_N1km", "N 1 km"), ("spot2_S1km", "S 1 km"), ("spot2_E1km", "E 1 km"), ("spot2_W1km", "W 1 km")]
LCOL = ["#222222", "#2b7bba", "#e07b24", "#7a3b8f", "#2e9c5a"]
# place, OSM road names, observed clock time (h), what was observed
PLACES = [
    ("Twin Creeks", lambda n: n.startswith("Twin Creeks"), 11.5, "AAR p.21: about 11:30 fire had spotted to Twin Creeks"),
    ("Park Vista", lambda n: n in ("Park Vista Road", "Park Vista Way"), 18 + 8 / 60, "AAR p.23: 18:08 fire crossed the park boundary towards the Park Vista Hotel"),
    ("Gatlinburg Spur", lambda n: n.startswith("Gatlinburg Spur Road") and "Parking" not in n, 19.0, "AAR p.24: fire observed at the Spur at about 19:00"),
    ("Ski Mountain Rd", lambda n: n == "Ski Mountain Road", 19.0, "AAR p.83: about 19:00 fire reported on Ski Mountain, a quarter mile from the bottom"),
]


def rd(p, k=1):
    ds = gdal.Open(p); return ds.GetRasterBand(k).ReadAsArray()


L = gdal.Open("ms_st09/spot2/inputs/landscape.tif"); gt = L.GetGeoTransform(); ny, nx = L.RasterYSize, L.RasterXSize
srs = osr.SpatialReference(wkt=L.GetProjection()); srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
wgs = osr.SpatialReference(); wgs.ImportFromEPSG(4326); wgs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
tr = osr.CoordinateTransformation(wgs, srs)
els = json.load(open("data/osm_roads/roads_domain.json"))["elements"]

cells, lines = {}, {}
for name, sel, _, _ in PLACES:
    s, pl = set(), []
    for e in els:
        if e.get("type") != "way" or not sel(e.get("tags", {}).get("name", "")):
            continue
        xy = np.array([tr.TransformPoint(p["lon"], p["lat"])[:2] for p in e["geometry"]])
        pl.append(xy)
        for a, b in zip(xy[:-1], xy[1:]):
            k = max(int(np.hypot(*(b - a)) / 5), 1)
            for f in np.linspace(0, 1, k + 1):
                x, y = a + f * (b - a)
                c, r = int((x - gt[0]) / gt[1]), int((gt[3] - y) / gt[1])
                if 0 <= r < ny and 0 <= c < nx:
                    s.add((r, c))
    cells[name] = tuple(np.array(sorted(s)).T); lines[name] = pl
    print("%-16s %4d road cells, %.1f km of road" % (name, len(s), sum(np.hypot(*np.diff(q, axis=0).T).sum() for q in pl) / 1e3))

rows = []
for (loc, lab) in LOCS:
    for s in range(1, 11):
        f = glob.glob("ms_st09/%s/seed_%d/outputs/time_of_arrival_*.tif" % (loc, s))
        if not f:
            continue
        t = rd(f[0])
        for name, _, obs, _ in PLACES:
            v = t[cells[name]]; b = v > 0
            first = T0 + v[b].min() / 3600 if b.any() else np.nan
            k10 = max(int(np.ceil(0.1 * len(v))), 1)
            arr = T0 + np.sort(v[b])[k10 - 1] / 3600 if b.sum() >= k10 else np.nan
            rows.append((lab, s, name, arr, first, b.mean(), obs))

with open(OUT + "/timeline_comparison.csv", "w") as f:
    f.write("location,seed,place,model_arrival_10pct_road_h,model_first_cell_h,share_road_burned,observed_h\n")
    for r in rows:
        f.write("%s,%d,%s,%.3f,%.3f,%.3f,%.3f\n" % r)


def hm(h):
    return "--:--" if np.isnan(h) else "%02d:%02d" % (int(h) % 24, int(round((h % 1) * 60)) % 60)


print("\n%-16s %-9s %-26s %-18s %s" % ("place", "observed", "model arrival, 10% of road", "model - observed", "runs reaching it"))
print("%-16s %-9s %-26s %-18s" % ("", "", "median [min - max]", "median"))
summ = {}
for name, _, obs, _ in PLACES:
    a = np.array([r[3] for r in rows if r[2] == name]); ok = ~np.isnan(a)
    med = np.median(a[ok]) if ok.any() else np.nan; summ[name] = a
    sh = np.mean([r[5] for r in rows if r[2] == name])
    print("%-16s %-9s %-26s %s            %d/%d   (mean share of road burned %.0f%%)" % (name, hm(obs), "%s [%s - %s]" % (hm(med), hm(np.nanmin(a)), hm(np.nanmax(a))) if ok.any() else "not reached",
                                                       "%+6.1f h" % (med - obs) if ok.any() else "   --   ", ok.sum(), len(a), 100 * sh))
for lab in [l for _, l in LOCS]:
    print("  %-8s " % lab + "  ".join("%s %s" % (n.split()[0], hm(np.nanmedian([r[3] for r in rows if r[0] == lab and r[2] == n]))) for n, _, _, _ in PLACES))

# ---------------- figure ----------------
fig = plt.figure(figsize=(16, 7.4), facecolor="white")
gs = fig.add_gridspec(1, 2, width_ratios=[1, 1.25], wspace=0.42)
ax = fig.add_subplot(gs[0])
T = np.stack([rd(glob.glob("ms_st09/%s/seed_%d/outputs/time_of_arrival_*.tif" % (loc, s))[0]) for loc, _ in LOCS for s in range(1, 11)])
burned = (T > 0).mean(0); med = np.where(burned >= 0.5, T0 + np.nanmedian(np.where(T > 0, T, np.nan), 0) / 3600, np.nan)
allpts = np.vstack([q for name in lines for q in lines[name]])
x0, x1 = allpts[:, 0].min() - 3000, allpts[:, 0].max() + 3000; y0, y1 = allpts[:, 1].min() - 3000, allpts[:, 1].max() + 3000
c0, c1 = int((x0 - gt[0]) / gt[1]), int((x1 - gt[0]) / gt[1]); r0, r1 = int((gt[3] - y1) / gt[1]), int((gt[3] - y0) / gt[1])
c0, r0 = max(c0, 0), max(r0, 0); c1, r1 = min(c1, nx - 1), min(r1, ny - 1)
ext = [(gt[0] + c0 * gt[1] - gt[0]) / 1e3, (gt[0] + (c1 + 1) * gt[1] - gt[0]) / 1e3, -(r1 + 1) * gt[1] / 1e3, -r0 * gt[1] / 1e3]
im = ax.imshow(med[r0:r1 + 1, c0:c1 + 1], extent=ext, cmap="YlOrRd_r", vmin=11, vmax=27, interpolation="nearest")
cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02, ticks=range(11, 28, 2)); cb.ax.set_yticklabels(["%02d:00" % (h % 24) for h in range(11, 28, 2)])
cb.set_label("model median arrival time (cells burned in >= half of 50 runs)", fontsize=8.5)
pcol = ["#1f5fbf", "#0b7a3b", "#8e44ad", "#111111"]
for (name, _, obs, _), c in zip(PLACES, pcol):
    for q in lines[name]:
        ax.plot((q[:, 0] - gt[0]) / 1e3, (q[:, 1] - gt[3]) / 1e3, color=c, lw=2.6)
    q = np.vstack(lines[name]); m_ = q.mean(0)
    ax.annotate("%s\nobserved %s" % (name, hm(obs)), ((m_[0] - gt[0]) / 1e3, (m_[1] - gt[3]) / 1e3), xytext=(8, 8), textcoords="offset points",
                fontsize=8.5, color=c, weight="bold", bbox=dict(fc="white", ec=c, alpha=0.85, pad=2))
ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3]); ax.set_xlabel("km"); ax.tick_params(labelsize=8)
ax.set_title("A. Model arrival time and the observed places", fontsize=11, loc="left")

ax = fig.add_subplot(gs[1])
for i, (name, _, obs, txt) in enumerate(PLACES):
    y = len(PLACES) - 1 - i
    for (loc, lab), c in zip(LOCS, LCOL):
        a = np.array([r[3] for r in rows if r[2] == name and r[0] == lab])
        jit = (np.arange(len(a)) - len(a) / 2) * 0.025 + (LOCS.index((loc, lab)) - 2) * 0.09
        nr = np.isnan(a)
        ax.scatter(a[~nr], (y + jit)[~nr], s=26, color=c, alpha=0.85, edgecolors="white", linewidths=0.5, zorder=3)
        ax.scatter(np.full(nr.sum(), 27.6), (y + jit)[nr], s=26, marker="x", color=c, alpha=0.85, zorder=3)
    ax.plot([obs, obs], [y - 0.38, y + 0.38], color="#c0392b", lw=3, zorder=4)
    a = summ[name]; nreach = (~np.isnan(a)).sum()
    if nreach * 2 >= len(a):
        d = np.nanmedian(a) - obs
        ax.text(28.3, y, "%+.1f h" % d, va="center", fontsize=10, weight="bold", color="#c0392b" if abs(d) > 1 else "#333333")
    else:
        ax.text(28.3, y, "not reached\nin %d/%d runs" % (len(a) - nreach, len(a)), va="center", fontsize=9, weight="bold", color="#c0392b")
ax.set_yticks(range(len(PLACES))); ax.set_yticklabels([p[0] for p in PLACES][::-1], fontsize=10)
ax.axvline(27.25, color="#bbbbbb", lw=1); ax.text(27.6, -0.75, "not\nreached", ha="center", fontsize=8, color="#555555")
ax.set_xlim(10.5, 28.1); ax.set_ylim(-0.95, len(PLACES) - 0.4); ax.set_xticks(range(11, 28, 2)); ax.set_xticklabels(["%02d:00" % (h % 24) for h in range(11, 28, 2)], fontsize=8.5)
ax.set_xlabel("time (EST), 28-29 Nov 2016", fontsize=9); ax.grid(axis="x", color="#eeeeee"); ax.set_axisbelow(True)
ax.spines[["top", "right"]].set_visible(False)
ax.text(28.3, len(PLACES) - 0.55, "model − observed\n(median)", fontsize=8, va="bottom")
ax.set_title("B. Model arrival (10% of the road burned; x = not reached) vs observed (red bar)", fontsize=11, loc="left")
ax.legend(handles=[Line2D([], [], ls="", marker="o", color=c, ms=7, label="spot fire " + l) for (_, l), c in zip(LOCS, LCOL)] +
          [Line2D([], [], color="#c0392b", lw=3, label="observed (After Action Review 2017)")],
          loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=3, fontsize=8.5, frameon=False)
fig.suptitle("When did the fire arrive? Model (ELMFIRE, 50 runs) vs the observed timeline of 28 Nov 2016", fontsize=13, weight="bold", x=0.02, ha="left")
fig.savefig(OUT + "/timeline_comparison.png", dpi=150, facecolor="white", bbox_inches="tight")
print("wrote %s/timeline_comparison.png, timeline_comparison.csv" % OUT)
