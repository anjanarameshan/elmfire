#!/usr/bin/env python3
"""Time of arrival or embers produced, one panel per ignition location, on the same base map as
plot_run_with_buildings.py (MTBS perimeter and burned area, urban/building cells (fuel 91), building
footprints, major OSM roads, ignition star).
Usage: python basemap_panels.py toa|ember PERIMETER.shp BUILDINGS.gpkg ROADS.json PARENT SEED LOC [LOC ...]
  toa    time of arrival (hours after ignition, 28 Nov 2016 11:00 EST)
  ember  embers produced per burning vegetation cell = 10 x FLIN (PER-MW, TAU_EMBERGEN 10 s), log scale
Writes PARENT/fire_spread_seed<SEED>.png or PARENT/ember_production_seed<SEED>.png.
"""
import sys, glob, json
import numpy as np
import pandas as pd
from osgeo import gdal, ogr, osr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm, LogNorm
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

sys.path.insert(0, __file__.rsplit("/", 3)[0])          # my_analysis/, for compare_perimeter
from compare_perimeter import perimeter_lines, rasterise, time_cmap

gdal.UseExceptions(); ogr.UseExceptions()
MODE, SHP, BFILE, ROADS, PARENT, SEED, LOCS = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5].rstrip("/"), sys.argv[6], sys.argv[7:]
NAMES = {"spot2": "reported location", "spot2_N1km": "1 km north", "spot2_S1km": "1 km south",
         "spot2_E1km": "1 km east", "spot2_W1km": "1 km west"}

L = gdal.Open(f"{PARENT}/{LOCS[0]}/inputs/landscape.tif"); gt = L.GetGeoTransform(); fuel = L.GetRasterBand(4).ReadAsArray()
ny, nx = fuel.shape; extent = [gt[0], gt[0] + nx * gt[1], gt[3] + ny * gt[5], gt[3]]
srs = osr.SpatialReference(); srs.ImportFromWkt(L.GetProjection()); srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
wgs = osr.SpatialReference(); wgs.ImportFromEPSG(4326); wgs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
obs = rasterise(SHP, L)
veg = fuel >= 100

bds = ogr.Open(BFILE); bl = bds.GetLayer(); bs = bl.GetSpatialRef(); bs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
btr = osr.CoordinateTransformation(bs, srs); bxy = []
for f in bl:
    c = f.GetGeometryRef().Centroid(); c.Transform(btr); bxy.append((c.GetX(), c.GetY()))
bxy = np.array(bxy)

rtr = osr.CoordinateTransformation(wgs, srs); major = []
for e in json.load(open(ROADS))["elements"]:
    if "geometry" in e and e["tags"].get("highway") in ("motorway", "trunk", "primary", "secondary", "tertiary"):
        major.append(np.array(rtr.TransformPoints([(p["lon"], p["lat"]) for p in e["geometry"]]))[:, :2])

# vegetation cells next to labelled buildings (8 neighbours), for the ember panel titles
fe = pd.read_csv("vulnerability/features.csv")
fc = ((fe.x - gt[0]) / gt[1]).astype(int).values; fr = ((fe.y - gt[3]) / gt[5]).astype(int).values
near = np.zeros_like(veg)
for dy in (-1, 0, 1):
    for dx in (-1, 0, 1):
        if dy or dx:
            near[fr + dy, fc + dx] = True
near &= veg

runs = []
for loc in LOCS:
    o = f"{PARENT}/{loc}/seed_{SEED}/outputs"
    toa = gdal.Open(glob.glob(o + "/time_of_arrival_*.tif")[0]).ReadAsArray().astype(float)
    fl = gdal.Open(glob.glob(o + "/flin_*.tif")[0]).ReadAsArray().astype(float)
    phi = gdal.Open(f"{PARENT}/{loc}/inputs/phi.tif").ReadAsArray(); ri, ci = np.where(phi < 0)
    runs.append(dict(loc=loc, toa=toa, burned=toa > 0, fl=fl,
                     ign=(gt[0] + (ci.mean() + .5) * gt[1], gt[3] + (ri.mean() + .5) * gt[5])))

rows, cols = np.where(obs | np.any([r["burned"] for r in runs], axis=0))
pad = 800
xmin, xmax = gt[0] + cols.min() * gt[1] - pad, gt[0] + (cols.max() + 1) * gt[1] + pad
ymax, ymin = gt[3] + rows.min() * gt[5] + pad, gt[3] + (rows.max() + 1) * gt[5] - pad
inview = (bxy[:, 0] > xmin) & (bxy[:, 0] < xmax) & (bxy[:, 1] > ymin) & (bxy[:, 1] < ymax)

if MODE == "toa":
    bounds = np.arange(0, 18, 2); cmap = time_cmap("YlOrRd", len(bounds) - 1); norm = BoundaryNorm(bounds, cmap.N)
    cblabel = "Simulated time of arrival (hours after ignition, 0 = 28 Nov 2016 11:00 EST)"
else:
    cmap = ListedColormap(plt.get_cmap("Purples")(np.linspace(0.3, 1.0, 256))); norm = LogNorm(1, 1e5)
    cblabel = "Embers produced by the burning vegetation cell (≈ 10 × fireline intensity, per 30 m cell)"

w, h = xmax - xmin, ymax - ymin
fig, ax = plt.subplots(2, 3, figsize=(16, 2 * 16 / 3 * h / w + 1.6), constrained_layout=True); ax = ax.ravel()
for a, r in zip(ax, runs):
    a.imshow(np.where(obs, 1, np.nan), extent=extent, origin="upper", cmap=ListedColormap(["#d4e4f4"]), interpolation="nearest")
    a.imshow(np.where(fuel == 91, 1, np.nan), extent=extent, origin="upper", cmap=ListedColormap(["#8c8c8c"]),
             interpolation="nearest", alpha=0.85)
    if MODE == "toa":
        data = np.where(r["burned"], r["toa"] / 3600.0, np.nan)
        acres = r["burned"].sum() * gt[1] ** 2 / 4046.86
        a.set_title(f"Spot fire 2, {NAMES[r['loc']]} · {acres:,.0f} acres in 16 h", fontsize=10)
    else:
        b = veg & r["burned"]
        data = np.where(b, 10 * np.clip(r["fl"], 0, None), np.nan)
        a.set_title(f"Spot fire 2, {NAMES[r['loc']]}\nmedian {np.nanmedian(data[b & near]):.0f} embers per cell next to buildings",
                    fontsize=10)
    im = a.imshow(np.ma.masked_invalid(data), extent=extent, origin="upper", cmap=cmap, norm=norm, interpolation="nearest")
    a.add_collection(LineCollection(major, colors="#4a2a10", linewidths=0.9))
    a.scatter(bxy[inview, 0], bxy[inview, 1], s=2, marker="s", c="#c44e00", lw=0, zorder=5)
    for lx, ly in perimeter_lines(SHP):
        a.plot(lx, ly, color="#1f5fbf", lw=1.4, zorder=6)
    a.plot(*r["ign"], marker="*", ms=15, mfc="#ffff00", mec="black", mew=1.1, zorder=9, ls="")
    a.set_xlim(xmin, xmax); a.set_ylim(ymin, ymax); a.set_xticks([]); a.set_yticks([])

leg = ax[len(runs)]
for a in ax[len(runs) + 1:]:
    a.remove()
leg.axis("off")
handles = [Line2D([], [], ls="", marker="*", ms=13, mfc="#ffff00", mec="black", label="Ignition point"),
           Line2D([], [], color="#1f5fbf", lw=1.6, label="Observed perimeter (MTBS, 15,002 ac)"),
           Patch(color="#d4e4f4", label="Observed burned area"),
           Line2D([], [], ls="", marker="s", color="#c44e00", ms=4, label="Building (Microsoft footprints)"),
           Patch(color="#8c8c8c", label="Non-burnable: building cell (91)"),
           Line2D([], [], color="#4a2a10", lw=1.1, label="Major road (OpenStreetMap)")]
leg.legend(handles=handles, loc="center", fontsize=10, frameon=False)
cb = fig.colorbar(im, ax=ax[:len(runs)], orientation="horizontal", fraction=0.03, pad=0.01, shrink=0.6)
cb.set_label(cblabel)
out = f"{PARENT}/{'fire_spread' if MODE == 'toa' else 'ember_production'}_seed{SEED}.png"
fig.savefig(out, dpi=130, bbox_inches="tight", pad_inches=0.15); print(out)
