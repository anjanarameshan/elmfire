#!/usr/bin/env python3
"""Simulated time of arrival with non-burnable cells, roads and building footprints.

Usage: python plot_run_with_buildings.py RUN_DIR PERIMETER.shp BUILDINGS.gpkg ROADS.json OUT.png [LABEL]
  RUN_DIR     ELMFIRE run folder (outputs/time_of_arrival_*.tif, inputs/landscape.tif band 4 = fuel)
  BUILDINGS   building footprints (any CRS); drawn as small dark-orange squares at their centroids
  ROADS.json  OpenStreetMap Overpass JSON ("out geom") of highway ways
  env IGN="lat,lon,text"  ignition point to mark with a star (optional)
  env COMPARE_RUN=DIR      outline that run's final burned area (black dashed) for comparison (optional)
  env SHOW_EMBER_IGN=1     mark cells ignited by embers (outputs/ember_ignition_*.tif) (optional)
  env US_ROADS=1           draw and label US routes (OSM "ref" tag starting with "US")
  env CROSS_ROAD="US 441"  find where the fire first burned across that route: the map is split along the route,
                           cells burned outside the part holding the ignition point are "across the road"; each
                           separate across-road patch is marked at its first-ignited cell, flagged as an ember
                           spot fire if that cell is in the ember-ignition raster EMBER_IGN_TIF (0/1 map); crossings
                           earlier than EMBER_VALID_FROM_H hours (no ember output for that period) are left unflagged.
                           TIME0_LABEL="YYYY-MM-DD HH:MM" converts hours after ignition to a clock time.

Spot fires = burned patches not connected (8-neighbour) to the patch holding the ignition point.
"""
import sys, os, glob, json
import numpy as np
from osgeo import gdal, ogr, osr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from compare_perimeter import perimeter_lines, rasterise, time_cmap

gdal.UseExceptions(); ogr.UseExceptions()
run, shp, bfile, roads, out = sys.argv[1:6]
label = sys.argv[6] if len(sys.argv) > 6 else run.rstrip("/").split("/")[-1]

tds = gdal.Open(sorted(glob.glob(run + "/outputs/time_of_arrival_*.tif"))[-1])
toa = tds.ReadAsArray().astype(float)
gt = tds.GetGeoTransform(); ny, nx = toa.shape
srs = osr.SpatialReference(); srs.ImportFromWkt(tds.GetProjection()); srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
lds = gdal.Open(run + "/inputs/landscape.tif"); fuel = lds.GetRasterBand(4).ReadAsArray()
burned = toa > 0
toa_h = np.where(burned, toa / 3600.0, np.nan)
extent = [gt[0], gt[0] + nx * gt[1], gt[3] + ny * gt[5], gt[3]]
obs = rasterise(shp, tds)

# ---- spot fires: burned patches not connected to the main (largest) patch ----
mem = gdal.GetDriverByName("MEM").Create("", nx, ny, 1, gdal.GDT_Byte)
mem.SetGeoTransform(gt); mem.SetProjection(tds.GetProjection()); mem.GetRasterBand(1).WriteArray(burned.astype(np.uint8))
vds = ogr.GetDriverByName("Memory").CreateDataSource("p"); vl = vds.CreateLayer("p", srs)
vl.CreateField(ogr.FieldDefn("v", ogr.OFTInteger))
gdal.Polygonize(mem.GetRasterBand(1), mem.GetRasterBand(1), vl, 0, ["8CONNECTED=8"])
patches = sorted([(f.GetGeometryRef().GetArea() / 4046.86, f.GetGeometryRef().Centroid()) for f in vl], key=lambda p: -p[0])
main_ac, spots = patches[0][0], patches[1:]

# ---- buildings (centroids) ----
bds = ogr.Open(bfile); bl = bds.GetLayer(); bs = bl.GetSpatialRef(); bs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
btr = osr.CoordinateTransformation(bs, srs)
bxy = []
for f in bl:
    c = f.GetGeometryRef().Centroid(); c.Transform(btr); bxy.append((c.GetX(), c.GetY()))
bxy = np.array(bxy)

# ---- roads ----
wgs = osr.SpatialReference(); wgs.ImportFromEPSG(4326); wgs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
rtr = osr.CoordinateTransformation(wgs, srs)
major, minor, usr = [], [], {}
for e in json.load(open(roads))["elements"]:
    if "geometry" not in e:
        continue
    pts = np.array(rtr.TransformPoints([(p["lon"], p["lat"]) for p in e["geometry"]]))[:, :2]
    ref = e["tags"].get("ref", "")
    for r_ in ref.split(";"):
        if r_.strip().startswith("US "):
            usr.setdefault(r_.strip(), []).append(pts)
    (major if e["tags"].get("highway") in ("motorway", "trunk", "primary", "secondary", "tertiary") else minor).append(pts)

# ---- extent: perimeter + simulated fire, with margin ----
rows, cols = np.where(obs | burned)
xmin, xmax = gt[0] + cols.min() * gt[1], gt[0] + (cols.max() + 1) * gt[1]
ymax, ymin = gt[3] + rows.min() * gt[5], gt[3] + (rows.max() + 1) * gt[5]
pad = 800; xmin -= pad; xmax += pad; ymin -= pad; ymax += pad
inview = (bxy[:, 0] > xmin) & (bxy[:, 0] < xmax) & (bxy[:, 1] > ymin) & (bxy[:, 1] < ymax)

w, h = xmax - xmin, ymax - ymin
fig, ax = plt.subplots(figsize=(9, 9 * h / w + 1.6), constrained_layout=True)
# non-burnable cells by type
nb = np.full(fuel.shape, np.nan)
for k, code in enumerate((91, 92, 93, 98, 99)):
    nb[fuel == code] = k
nb_cols = ["#8c8c8c", "#e0f3ff", "#c9b37e", "#0a8fb8", "#bdbdbd"]
nb_names = ["urban / developed (91)", "snow / ice (92)", "agriculture (93)", "water (98)", "barren (99)"]
present = [k for k in range(5) if np.any(nb == k)]
ax.imshow(np.where(obs, 1, np.nan), extent=extent, origin="upper", cmap=ListedColormap(["#d4e4f4"]), interpolation="nearest")
ax.imshow(nb, extent=extent, origin="upper", cmap=ListedColormap(nb_cols), norm=BoundaryNorm(np.arange(-0.5, 5.5), 5),
          interpolation="nearest", alpha=0.85)
bounds = np.arange(0, np.nanmax(toa_h) // 6 * 6 + 7, 6)
cmap = time_cmap("YlOrRd", len(bounds) - 1)
im = ax.imshow(toa_h, extent=extent, origin="upper", cmap=cmap, norm=BoundaryNorm(bounds, cmap.N), interpolation="nearest")
ax.add_collection(LineCollection(minor, colors="#6b4423", linewidths=0.35, alpha=0.8))
ax.add_collection(LineCollection(major, colors="#4a2a10", linewidths=1.1))
ax.scatter(bxy[inview, 0], bxy[inview, 1], s=3.5, marker="s", c="#c44e00", lw=0, zorder=5)
for lx, ly in perimeter_lines(shp):
    ax.plot(lx, ly, color="#1f5fbf", lw=1.6, zorder=6)
cmp_run = os.environ.get("COMPARE_RUN")
if cmp_run:
    cds = gdal.Open(sorted(glob.glob(cmp_run + "/outputs/time_of_arrival_*.tif"))[-1])
    cb_ = (cds.ReadAsArray() > 0).astype(float)
    X = gt[0] + (np.arange(nx) + 0.5) * gt[1]; Y = gt[3] + (np.arange(ny) + 0.5) * gt[5]
    ax.contour(X, Y, cb_, levels=[0.5], colors="black", linewidths=1.0, linestyles="--", zorder=8)
emb = None
if os.environ.get("SHOW_EMBER_IGN") and glob.glob(run + "/outputs/ember_ignition_*.tif"):
    eds = gdal.Open(glob.glob(run + "/outputs/ember_ignition_*.tif")[0]); emb = (eds.ReadAsArray() > 0) & burned
    ii, jj = np.where(emb)
    ax.scatter(gt[0] + (jj + 0.5) * gt[1], gt[3] + (ii + 0.5) * gt[5], s=2, c="#00bcd4", marker="s", lw=0, zorder=7)
US_COL = {"US 441": "#000080", "US 321": "#8b008b"}
if os.environ.get("US_ROADS"):
    for r_, segs in usr.items():
        if r_ not in US_COL:
            continue
        col = US_COL[r_]
        ax.add_collection(LineCollection(segs, colors=col, linewidths=2.6, alpha=0.9, zorder=6))
        allp = np.vstack(segs); inv = allp[(allp[:, 0] > xmin) & (allp[:, 0] < xmax) & (allp[:, 1] > ymin) & (allp[:, 1] < ymax)]
        if len(inv):
            for q in inv[[len(inv) // 4, 3 * len(inv) // 4]]:
                ax.text(q[0], q[1], r_, fontsize=8, weight="bold", color="white", zorder=11, ha="center", va="center",
                        bbox=dict(boxstyle="round,pad=0.15", fc=col, ec="white"))
cross = []
cr = os.environ.get("CROSS_ROAD")
ign_xy = None
if os.environ.get("IGN"):
    _la, _lo, _ = os.environ["IGN"].split(",", 2)
    ign_xy = osr.CoordinateTransformation(wgs, srs).TransformPoint(float(_lo), float(_la))[:2]
if cr and cr in usr and ign_xy:
    # rasterise the route (cells it passes through, sampled every 5 m), split the grid, label 4-connected parts
    road = np.zeros((ny, nx), bool)
    for pts in usr[cr]:
        for a_, b_ in zip(pts[:-1], pts[1:]):
            n_ = int(np.hypot(*(b_ - a_)) / 5) + 1
            q = a_ + (b_ - a_) * np.linspace(0, 1, n_ + 1)[:, None]
            jj_ = ((q[:, 0] - gt[0]) / gt[1]).astype(int); ii_ = ((q[:, 1] - gt[3]) / gt[5]).astype(int)
            k_ = (ii_ >= 0) & (ii_ < ny) & (jj_ >= 0) & (jj_ < nx); road[ii_[k_], jj_[k_]] = True
    m_ = gdal.GetDriverByName("MEM").Create("", nx, ny, 1, gdal.GDT_Byte); m_.SetGeoTransform(gt); m_.SetProjection(tds.GetProjection())
    m_.GetRasterBand(1).WriteArray((~road).astype(np.uint8))
    lab = gdal.GetDriverByName("MEM").Create("", nx, ny, 1, gdal.GDT_Int32); lab.SetGeoTransform(gt); lab.SetProjection(tds.GetProjection())
    pv = ogr.GetDriverByName("Memory").CreateDataSource("s"); pl_ = pv.CreateLayer("s", srs); pl_.CreateField(ogr.FieldDefn("v", ogr.OFTInteger))
    gdal.Polygonize(m_.GetRasterBand(1), m_.GetRasterBand(1), pl_, 0, [])
    side = np.zeros((ny, nx), bool)
    pt = ogr.Geometry(ogr.wkbPoint); pt.AddPoint(*ign_xy)
    for f_ in pl_:
        if f_.GetGeometryRef().Contains(pt):
            tmp = ogr.GetDriverByName("Memory").CreateDataSource("t"); tl = tmp.CreateLayer("t", srs); tl.CreateFeature(f_.Clone())
            gdal.RasterizeLayer(lab, [1], tl, burn_values=[1]); side = lab.ReadAsArray() == 1
    across = burned & ~side & ~road
    ebm = None
    if os.environ.get("EMBER_IGN_TIF"):
        e_ = gdal.Open(os.environ["EMBER_IGN_TIF"]); ebm = e_.ReadAsArray() > 0
    am = gdal.GetDriverByName("MEM").Create("", nx, ny, 1, gdal.GDT_Byte); am.SetGeoTransform(gt); am.SetProjection(tds.GetProjection())
    am.GetRasterBand(1).WriteArray(across.astype(np.uint8))
    av = ogr.GetDriverByName("Memory").CreateDataSource("a"); al = av.CreateLayer("a", srs); al.CreateField(ogr.FieldDefn("v", ogr.OFTInteger))
    gdal.Polygonize(am.GetRasterBand(1), am.GetRasterBand(1), al, 0, ["8CONNECTED=8"])
    for f_ in al:
        pm = gdal.GetDriverByName("MEM").Create("", nx, ny, 1, gdal.GDT_Byte); pm.SetGeoTransform(gt); pm.SetProjection(tds.GetProjection())
        tmp = ogr.GetDriverByName("Memory").CreateDataSource("t"); tl = tmp.CreateLayer("t", srs); tl.CreateFeature(f_.Clone())
        gdal.RasterizeLayer(pm, [1], tl, burn_values=[1]); msk = (pm.ReadAsArray() == 1) & across
        if not msk.any():
            continue
        t_ = np.where(msk, toa, np.inf); i0, j0 = np.unravel_index(np.argmin(t_), t_.shape)
        cross.append(dict(x=gt[0] + (j0 + .5) * gt[1], y=gt[3] + (i0 + .5) * gt[5], t=toa[i0, j0] / 3600,
                          ac=msk.sum() * gt[1] ** 2 / 4046.86,
                          ember=(bool(ebm[i0, j0]) if ebm is not None and toa[i0, j0] / 3600 >= float(os.environ.get("EMBER_VALID_FROM_H", "0")) else None)))
    cross.sort(key=lambda c_: c_["t"])
    t0h = float(os.environ.get("TIME0_H", "0")); lab0 = os.environ.get("TIME0_LABEL", "")
    import datetime as _dt
    for k_, c_ in enumerate(cross):
        if c_["ac"] < 1:
            continue
        mk = "D" if c_["ember"] else ("s" if c_["ember"] is False else "o")
        ax.plot(c_["x"], c_["y"], marker=mk, ms=13, mfc="#00e5ff" if c_["ember"] else ("white" if c_["ember"] is False else "#cccccc"), mec="black", mew=1.5, zorder=12, ls="")
        when = ""
        if lab0:
            when = (_dt.datetime.strptime(lab0, "%Y-%m-%d %H:%M") + _dt.timedelta(hours=c_["t"])).strftime("%d Nov %H:%M EST")
        ax.annotate("%s crossed %s\n%s (%.0f h), patch %.0f ac" % ({True: "Ember spot fire", False: "Fire front", None: "Fire (cause not recorded)"}[c_["ember"]], cr, when, c_["t"], c_["ac"]),
                    (c_["x"], c_["y"]), xytext=(14, 10 - 34 * (k_ % 3)), textcoords="offset points", fontsize=8, weight="bold", zorder=12,
                    arrowprops=dict(arrowstyle="-", color="black", lw=0.8),
                    bbox=dict(boxstyle="round,pad=0.25", fc="#e0fbff" if c_["ember"] else "white", ec="black"))
    print("crossings of", cr, ":", [("%.1f h" % c_["t"], "%.0f ac" % c_["ac"], {True: "ember", False: "front", None: "unknown"}[c_["ember"]]) for c_ in cross if c_["ac"] >= 1])
ign = os.environ.get("IGN")
if ign:
    ila, ilo, itxt = ign.split(",", 2)
    ix, iy, _ = osr.CoordinateTransformation(wgs, srs).TransformPoint(float(ilo), float(ila))
    ax.plot(ix, iy, marker="*", ms=17, mfc="#ffff00", mec="black", mew=1.2, zorder=9, ls="")
    ax.annotate(itxt, (ix, iy), xytext=(12, -4), textcoords="offset points", fontsize=8, weight="bold", zorder=9,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="0.4", alpha=0.85))
for a, c in spots:
    ax.add_patch(plt.Circle((c.GetX(), c.GetY()), 120 + 40 * np.sqrt(a), fill=False, ec="#7a0177", lw=1.2, zorder=7))
ax.set_xlim(xmin, xmax); ax.set_ylim(ymin, ymax); ax.set_xticks([]); ax.set_yticks([])
cb = fig.colorbar(im, ax=ax, orientation="horizontal", fraction=0.03, pad=0.01, shrink=0.7)
cb.set_label("Simulated time of arrival (hours after ignition)")
handles = [Line2D([], [], color="#1f5fbf", lw=1.6, label="Observed perimeter (MTBS, 15,002 ac)"),
           Patch(color="#d4e4f4", label="Observed burned area"),
           Line2D([], [], ls="", marker="s", color="#c44e00", ms=4, label="Building (Microsoft footprints, %d shown)" % inview.sum()),
           Line2D([], [], color="#4a2a10", lw=1.1, label="Major road (OpenStreetMap)"),
           Line2D([], [], color="#6b4423", lw=0.5, label="Minor road / track"),
           Line2D([], [], ls="", marker="o", mfc="none", mec="#7a0177", ms=9, label="Ember spot fire (%d patches, %.0f ac)" % (len(spots), sum(a for a, _ in spots)))]
if cmp_run:
    handles.append(Line2D([], [], color="black", ls="--", lw=1.0, label="Burned area of " + os.environ.get("COMPARE_LABEL", "comparison run")))
if emb is not None:
    handles.append(Line2D([], [], ls="", marker="s", color="#00bcd4", ms=4, label="Cell ignited by embers (%d cells, %.0f ac)" % (emb.sum(), emb.sum() * gt[1] ** 2 / 4046.86)))
if ign:
    handles.insert(0, Line2D([], [], ls="", marker="*", ms=13, mfc="#ffff00", mec="black", label="Ignition point (" + itxt.split("\n")[0] + ")"))
if os.environ.get("US_ROADS"):
    handles += [Line2D([], [], color=US_COL.get(r_, "#000000"), lw=2.6, label=r_ + " (OpenStreetMap)") for r_ in sorted(usr) if r_ in US_COL]
if cross:
    handles += [Line2D([], [], ls="", marker="D", ms=10, mfc="#00e5ff", mec="black", label="First cell across " + cr + ": ember spot fire"),
                Line2D([], [], ls="", marker="s", ms=10, mfc="white", mec="black", label="First cell across " + cr + ": fire front")]
handles += [Patch(color=nb_cols[k], label="Non-burnable: " + nb_names[k]) for k in present]
ax.legend(handles=handles, loc="upper right", fontsize=7.5, framealpha=0.92)
ax.set_title("%s\nSimulated %s ac (main fire %s ac + %d spot fires)  |  observed 15,002 ac"
             % (label, format(round(burned.sum() * gt[1] ** 2 / 4046.86), ","), format(round(main_ac), ","), len(spots)), fontsize=10)
fig.savefig(out, dpi=150)
print("wrote %s | burned %.0f ac, main patch %.0f ac, %d spot patches (%.1f ac); buildings shown %d; roads %d major, %d minor"
      % (out, burned.sum() * gt[1] ** 2 / 4046.86, main_ac, len(spots), sum(a for a, _ in spots), inview.sum(), len(major), len(minor)))
