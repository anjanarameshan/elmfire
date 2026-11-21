#!/usr/bin/env python3
"""Map of the three reported ignition points of the Chimney Tops II fire: the origin at Chimney Tops
(23 Nov 2016), spot fire 1 (morning of 28 Nov) and spot fire 2 (~11:30 EST 28 Nov).
Spot-fire positions read from Fig. 1 of Jimenez et al. (2018) (blue and red squares), so approximate.

Usage: python plot_three_ignitions.py LANDSCAPE.tif PERIMETER.shp BUILDINGS.gpkg ROADS.json OUT.png
"""
import sys, json
import numpy as np
from osgeo import gdal, ogr, osr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

gdal.UseExceptions(); ogr.UseExceptions()
land, shp, bfile, roads, out = sys.argv[1:6]
PTS = [("Origin (Chimney Tops)", 35.62889, -83.47833, "first identified 23 Nov 2016, ~17:30 EST", "*", "#ffd400", 24),
       ("Spot fire 1", 35.648, -83.487, "found morning of 28 Nov, ~1.5 mi from the fire", "s", "#2f6690", 15),
       ("Spot fire 2", 35.690, -83.497, "found ~11:30 EST 28 Nov, ~1.5 mi from park boundary", "s", "#d7191c", 15)]
DOWNTOWN = (35.7143, -83.5102)

L = gdal.Open(land); gt = L.GetGeoTransform(); fuel = L.GetRasterBand(4).ReadAsArray(); ny, nx = fuel.shape
srs = osr.SpatialReference(); srs.ImportFromWkt(L.GetProjection()); srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
wgs = osr.SpatialReference(); wgs.ImportFromEPSG(4326); wgs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
to_xy = osr.CoordinateTransformation(wgs, srs)
xy = lambda la, lo: to_xy.TransformPoint(lo, la)[:2]
P = np.array([xy(la, lo) for _, la, lo, *_ in PTS] + [xy(*DOWNTOWN)])
xmin, xmax = P[:, 0].min() - 3000, P[:, 0].max() + 3000
ymin, ymax = P[:, 1].min() - 1500, P[:, 1].max() + 2500
extent = [gt[0], gt[0] + nx * gt[1], gt[3] + ny * gt[5], gt[3]]

fig, ax = plt.subplots(figsize=(9, 9 * (ymax - ymin) / (xmax - xmin) + 1.4), constrained_layout=True)
pds = ogr.Open(shp); pl = pds.GetLayer(); ps = pl.GetSpatialRef(); ps.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
ptr = osr.CoordinateTransformation(ps, srs)
for f in pl:
    g = f.GetGeometryRef().Clone(); g.Transform(ptr)
    for p in ([g.GetGeometryRef(i) for i in range(g.GetGeometryCount())] if "MULTI" in g.GetGeometryName() else [g]):
        r = p.GetGeometryRef(0); a = np.array([r.GetPoint_2D(i) for i in range(r.GetPointCount())])
        ax.fill(a[:, 0], a[:, 1], color="#d4e4f4", zorder=0); ax.plot(a[:, 0], a[:, 1], color="#1f5fbf", lw=1.6, zorder=6)
nb = np.full(fuel.shape, np.nan); nb[fuel == 91] = 0; nb[fuel == 98] = 1
ax.imshow(nb, extent=extent, origin="upper", cmap=ListedColormap(["#9a9a9a", "#0a8fb8"]), vmin=-0.5, vmax=1.5,
          interpolation="nearest", alpha=0.8, zorder=1)
major, minor, us = [], [], []
for e in json.load(open(roads))["elements"]:
    if "geometry" not in e:
        continue
    p = np.array(to_xy.TransformPoints([(q["lon"], q["lat"]) for q in e["geometry"]]))[:, :2]
    if "US 441" in e["tags"].get("ref", ""):
        us.append(p)
    (major if e["tags"].get("highway") in ("motorway", "trunk", "primary", "secondary", "tertiary") else minor).append(p)
ax.add_collection(LineCollection(minor, colors="#6b4423", linewidths=0.4, alpha=0.7, zorder=2))
ax.add_collection(LineCollection(major, colors="#4a2a10", linewidths=1.2, zorder=3))
ax.add_collection(LineCollection(us, colors="#000080", linewidths=2.6, zorder=4))
bds = ogr.Open(bfile); bl = bds.GetLayer(); bs = bl.GetSpatialRef(); bs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
btr = osr.CoordinateTransformation(bs, srs); b = []
for f in bl:
    c = f.GetGeometryRef().Centroid(); c.Transform(btr); b.append((c.GetX(), c.GetY()))
b = np.array(b); k = (b[:, 0] > xmin) & (b[:, 0] < xmax) & (b[:, 1] > ymin) & (b[:, 1] < ymax)
ax.scatter(b[k, 0], b[k, 1], s=4, marker="s", c="#c44e00", lw=0, zorder=5)
offs = [(16, -6), (16, -6), (16, 4)]
for (name, la, lo, txt, mk, col, ms), (dx, dy) in zip(PTS, offs):
    x, y = xy(la, lo)
    ax.plot(x, y, marker=mk, ms=ms, mfc=col, mec="black", mew=1.4, ls="", zorder=10)
    ax.annotate("%s\n%.3f N, %.3f W\n%s" % (name, la, -lo, txt), (x, y), xytext=(dx, dy), textcoords="offset points",
                fontsize=8.5, weight="bold", zorder=11, bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=col, lw=1.5, alpha=0.95))
o = [xy(la, lo) for _, la, lo, *_ in PTS]
for a, c in ((o[0], o[1]), (o[1], o[2])):
    ax.annotate("", xy=c, xytext=a, arrowprops=dict(arrowstyle="->", color="#333333", lw=1.4, ls="--"), zorder=9)
    ax.text((a[0] + c[0]) / 2 + 150, (a[1] + c[1]) / 2, "%.1f km" % (np.hypot(c[0] - a[0], c[1] - a[1]) / 1000),
            fontsize=9, weight="bold", zorder=11, bbox=dict(boxstyle="round,pad=0.15", fc="#fff8cc", ec="0.5"))
gx, gy = xy(*DOWNTOWN)
ax.plot(gx, gy, marker="P", ms=13, mfc="black", mec="white", ls="", zorder=10)
ax.annotate("Downtown Gatlinburg", (gx, gy), xytext=(10, 6), textcoords="offset points", fontsize=9, weight="bold", zorder=11,
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="0.5", alpha=0.9))
sx, sy = xmax - 1600, ymin + 400
ax.plot([sx, sx + 1000], [sy, sy], color="black", lw=3, zorder=10); ax.text(sx + 500, sy + 150, "1 km", ha="center", fontsize=9)
ax.annotate("N", xy=(xmax - 400, ymax - 400), xytext=(xmax - 400, ymax - 1200), ha="center", fontsize=12, weight="bold",
            arrowprops=dict(arrowstyle="-|>", color="black", lw=1.5), zorder=10)
ax.set_xlim(xmin, xmax); ax.set_ylim(ymin, ymax); ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
ax.legend(handles=[Line2D([], [], ls="", marker="*", ms=15, mfc="#ffd400", mec="black", label="Origin, 23 Nov"),
                   Line2D([], [], ls="", marker="s", ms=10, mfc="#2f6690", mec="black", label="Spot fire 1, morning 28 Nov"),
                   Line2D([], [], ls="", marker="s", ms=10, mfc="#d7191c", mec="black", label="Spot fire 2, ~11:30 EST 28 Nov"),
                   Line2D([], [], color="#1f5fbf", lw=1.6, label="Final perimeter (MTBS)"), Patch(color="#d4e4f4", label="Burned area"),
                   Line2D([], [], color="#000080", lw=2.6, label="US 441 (Newfound Gap Rd / Parkway)"),
                   Line2D([], [], color="#4a2a10", lw=1.2, label="Other major road"),
                   Line2D([], [], ls="", marker="s", ms=5, color="#c44e00", label="Building (Microsoft footprints)"),
                   Patch(color="#9a9a9a", label="Urban / developed")],
          loc="lower left", fontsize=7.8, framealpha=0.95)
ax.set_title("Chimney Tops II: origin and the two spot fires of 28 Nov 2016\n"
             "(spot-fire positions read from Fig. 1 of Jimenez et al. 2018, approximate)", fontsize=10.5)
fig.savefig(out, dpi=150)
print("wrote", out)
