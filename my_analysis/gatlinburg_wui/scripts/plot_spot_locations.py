#!/usr/bin/env python3
"""Location map of the spot-fire ignitions used in the Gatlinburg structure-ignition runs:
observed spot fire 2 (Jimenez et al. 2018, Fig. 1; ~11:30 EST 28 Nov 2016) and the same spot moved 1 km N, S, E, W.

Usage: python plot_spot_locations.py LANDSCAPE.tif PERIMETER.shp BUILDINGS.gpkg ROADS.json OUT.png
  LANDSCAPE.tif  any case landscape on the 30 m grid (band 4 = fuel: 91 urban, 98 water, 99 barren)
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
OBS = (35.690, -83.497)                        # observed spot fire 2
DLAT, DLON = 0.00899, 0.01107                  # 1 km at 35.69 N (same offsets as setup_cases.sh)
SPOTS = [("Observed spot fire 2", OBS[0], OBS[1]),
         ("1 km north", OBS[0] + DLAT, OBS[1]), ("1 km south", OBS[0] - DLAT, OBS[1]),
         ("1 km east", OBS[0], OBS[1] + DLON), ("1 km west", OBS[0], OBS[1] - DLON)]
ORIGIN = (35.62889, -83.47833)                 # Chimney Tops (fire origin, 23 Nov)
DOWNTOWN = (35.7143, -83.5102)
HALF = 4500                                    # half-width of the map (m) around the observed spot

L = gdal.Open(land); gt = L.GetGeoTransform(); fuel = L.GetRasterBand(4).ReadAsArray(); ny, nx = fuel.shape
srs = osr.SpatialReference(); srs.ImportFromWkt(L.GetProjection()); srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
wgs = osr.SpatialReference(); wgs.ImportFromEPSG(4326); wgs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
to_xy = osr.CoordinateTransformation(wgs, srs)
xy = lambda la, lo: to_xy.TransformPoint(lo, la)[:2]
ox, oy = xy(*OBS)
xmin, xmax, ymin, ymax = ox - HALF, ox + HALF, oy - HALF * 0.8, oy + HALF * 1.05
extent = [gt[0], gt[0] + nx * gt[1], gt[3] + ny * gt[5], gt[3]]

fig, ax = plt.subplots(figsize=(9, 9.6), constrained_layout=True)
# observed burned area (MTBS)
pds = ogr.Open(shp); pl = pds.GetLayer(); ps = pl.GetSpatialRef(); ps.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
ptr = osr.CoordinateTransformation(ps, srs)
for f in pl:
    g = f.GetGeometryRef().Clone(); g.Transform(ptr)
    for p in ([g.GetGeometryRef(i) for i in range(g.GetGeometryCount())] if "MULTI" in g.GetGeometryName() else [g]):
        r = p.GetGeometryRef(0); a = np.array([r.GetPoint_2D(i) for i in range(r.GetPointCount())])
        ax.fill(a[:, 0], a[:, 1], color="#d4e4f4", zorder=0); ax.plot(a[:, 0], a[:, 1], color="#1f5fbf", lw=1.6, zorder=6)
# non-burnable cells
nb = np.full(fuel.shape, np.nan); nb[fuel == 91] = 0; nb[fuel == 98] = 1; nb[fuel == 99] = 2
ax.imshow(nb, extent=extent, origin="upper", cmap=ListedColormap(["#9a9a9a", "#0a8fb8", "#c8c8c8"]), vmin=-0.5, vmax=2.5,
          interpolation="nearest", alpha=0.8, zorder=1)
# roads
major, minor = [], []
for e in json.load(open(roads))["elements"]:
    if "geometry" not in e:
        continue
    p = np.array(to_xy.TransformPoints([(q["lon"], q["lat"]) for q in e["geometry"]]))[:, :2]
    (major if e["tags"].get("highway") in ("motorway", "trunk", "primary", "secondary", "tertiary") else minor).append(p)
ax.add_collection(LineCollection(minor, colors="#6b4423", linewidths=0.4, alpha=0.8, zorder=2))
ax.add_collection(LineCollection(major, colors="#4a2a10", linewidths=1.3, zorder=3))
# buildings
bds = ogr.Open(bfile); bl = bds.GetLayer(); bs = bl.GetSpatialRef(); bs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
btr = osr.CoordinateTransformation(bs, srs); b = []
for f in bl:
    c = f.GetGeometryRef().Centroid(); c.Transform(btr); b.append((c.GetX(), c.GetY()))
b = np.array(b); k = (b[:, 0] > xmin) & (b[:, 0] < xmax) & (b[:, 1] > ymin) & (b[:, 1] < ymax)
ax.scatter(b[k, 0], b[k, 1], s=5, marker="s", c="#c44e00", lw=0, zorder=4)
# 1 km circle and offsets
th = np.linspace(0, 2 * np.pi, 200)
ax.plot(ox + 1000 * np.cos(th), oy + 1000 * np.sin(th), ls=":", color="#7a0177", lw=1.2, zorder=7)
cols = {"Observed spot fire 2": "#ffd400", "1 km north": "#e41a1c", "1 km south": "#377eb8", "1 km east": "#4daf4a", "1 km west": "#984ea3"}
for name, la, lo in SPOTS:
    x, y = xy(la, lo)
    if name.startswith("1 km"):
        ax.annotate("", xy=(x, y), xytext=(ox, oy), arrowprops=dict(arrowstyle="->", color="#333333", lw=1.2), zorder=8)
        ax.plot(x, y, marker="^", ms=13, mfc=cols[name], mec="black", mew=1.0, ls="", zorder=9)
        dx, dy = {"1 km north": (8, 6), "1 km south": (8, -14), "1 km east": (8, -4), "1 km west": (-150, 12)}[name]
        ax.annotate("%s\n%.4f N, %.4f W" % (name, la, -lo), (x, y), xytext=(dx, dy), textcoords="offset points", fontsize=8,
                    weight="bold", zorder=10, bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="0.5", alpha=0.85))
    else:
        ax.plot(x, y, marker="*", ms=22, mfc=cols[name], mec="black", mew=1.2, ls="", zorder=10)
        ax.annotate("Observed spot fire 2\n%.3f N, %.3f W\n~11:30 EST 28 Nov 2016" % (la, -lo), (x, y), xytext=(22, -62),
                    textcoords="offset points", fontsize=8.5, weight="bold", zorder=10,
                    bbox=dict(boxstyle="round,pad=0.25", fc="#fff8cc", ec="0.4", alpha=0.95))
gx, gy = xy(*DOWNTOWN)
ax.plot(gx, gy, marker="P", ms=13, mfc="black", mec="white", ls="", zorder=9)
ax.annotate("Downtown Gatlinburg", (gx, gy), xytext=(10, 6), textcoords="offset points", fontsize=9, weight="bold", zorder=10,
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="0.5", alpha=0.85))
cx, cy = xy(*ORIGIN)
if ymin < cy < ymax:
    ax.plot(cx, cy, marker="o", ms=9, mfc="#d7191c", mec="black", ls="", zorder=9)
else:                                          # origin is south of the map: arrow pointing to it
    ax.annotate("Chimney Tops (fire origin)\n%.1f km south-east" % (np.hypot(cx - ox, cy - oy) / 1000),
                xy=(min(max(cx, xmin + 300), xmax - 300), ymin + 150), xytext=(min(max(cx, xmin + 300), xmax - 300) - 2200, ymin + 900),
                fontsize=8.5, arrowprops=dict(arrowstyle="->", color="#d7191c", lw=1.5), zorder=10,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#d7191c", alpha=0.9))
# scale bar and north arrow
sx, sy = xmin + 300, ymin + 300
ax.plot([sx, sx + 1000], [sy, sy], color="black", lw=3, zorder=10); ax.text(sx + 500, sy + 120, "1 km", ha="center", fontsize=9, zorder=10)
ax.annotate("N", xy=(xmax - 350, ymax - 350), xytext=(xmax - 350, ymax - 1050), ha="center", fontsize=12, weight="bold",
            arrowprops=dict(arrowstyle="-|>", color="black", lw=1.5), zorder=10)
ax.set_xlim(xmin, xmax); ax.set_ylim(ymin, ymax); ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
ax.legend(handles=[Line2D([], [], ls="", marker="*", ms=15, mfc="#ffd400", mec="black", label="Observed spot fire 2 (ignition, 1 ac)"),
                   Line2D([], [], ls="", marker="^", ms=11, mfc="0.7", mec="black", label="Same spot moved 1 km N / S / E / W"),
                   Line2D([], [], ls=":", color="#7a0177", lw=1.2, label="1 km from the observed spot"),
                   Line2D([], [], color="#1f5fbf", lw=1.6, label="Observed perimeter (MTBS)"), Patch(color="#d4e4f4", label="Observed burned area"),
                   Line2D([], [], ls="", marker="s", ms=5, color="#c44e00", label="Building (Microsoft footprints)"),
                   Line2D([], [], color="#4a2a10", lw=1.3, label="Major road"), Line2D([], [], color="#6b4423", lw=0.5, label="Minor road / track"),
                   Patch(color="#9a9a9a", label="Urban / developed (non-burnable)"), Patch(color="#0a8fb8", label="Water")],
          loc="lower right", fontsize=7.8, framealpha=1.0).set_zorder(20)
ax.set_title("Spot-fire ignition locations for the Gatlinburg structure-ignition runs\n"
             "Observed spot fire 2 and the same spot moved 1 km N, S, E, W\n"
             "(1 ac each, 10 runs each, 11:00 EST 28 Nov to 03:00 EST 29 Nov 2016)", fontsize=10)
fig.savefig(out, dpi=150)
print("wrote", out, "| buildings shown", int(k.sum()))
