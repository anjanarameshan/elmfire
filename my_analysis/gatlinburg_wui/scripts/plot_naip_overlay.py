#!/usr/bin/env python3
"""Building footprints over NAIP aerial photos before (Apr 2016) and after (Oct 2018) the fire.

Usage: python plot_naip_overlay.py NAIP_DIR MS.gpkg OSM.gpkg PERIMETER.shp OUT_PREFIX
  NAIP_DIR  from data/naip/fetch.sh: overview_2016.tif (6 m) and zoom_<year>_<area>.tif (1 m)
Writes OUT_PREFIX_overview.png (whole burned town, 2016) and OUT_PREFIX_<area>.png (zooms, 2016 | 2018)

Footprints: yellow = Microsoft (traced from 2019-2020 imagery), cyan = OpenStreetMap (today).
A house visible in the 2016 photo with no yellow outline is missing from the Microsoft data
(typically destroyed in 2016 and not rebuilt by 2019).
"""
import sys
import numpy as np
from osgeo import gdal, ogr, osr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.lines import Line2D

gdal.UseExceptions(); ogr.UseExceptions()
nd, ms, osm, shp, outp = sys.argv[1:6]
ZOOMS = {                                   # name: (lat, lon, half-width m)
    "downtown": (35.7110, -83.5180, 450),
    "north_hillside": (35.7250, -83.5080, 450),
    "west_hillside_chalet_village": (35.7090, -83.5330, 450),
    "east_ski_mountain_rd": (35.7180, -83.4950, 450),
}
ds16 = gdal.Open(nd + "/overview_2016.tif"); utm = osr.SpatialReference(); utm.ImportFromWkt(ds16.GetProjection())
utm.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
wgs = osr.SpatialReference(); wgs.ImportFromEPSG(4326); wgs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
to_utm = osr.CoordinateTransformation(wgs, utm)


def polys(fn, flt=None):
    d = ogr.Open(fn); l = d.GetLayer()
    s = l.GetSpatialRef(); s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    tr = osr.CoordinateTransformation(s, utm); out = []
    for f in l:
        g = f.GetGeometryRef().Clone(); g.Transform(tr)
        for p in ([g.GetGeometryRef(i) for i in range(g.GetGeometryCount())] if "MULTI" in g.GetGeometryName() else [g]):
            r = p.GetGeometryRef(0); out.append(np.array([r.GetPoint_2D(i) for i in range(r.GetPointCount())]))
    return out


P_MS, P_OSM, PER = polys(ms), polys(osm), polys(shp)


def read(ds, x0, x1, y0, y1, step=1.0):
    gt = ds.GetGeoTransform()
    c0, r0 = int((x0 - gt[0]) / gt[1]), int((y1 - gt[3]) / gt[5])
    w, h = int((x1 - x0) / gt[1]), int((y0 - y1) / gt[5])
    c0, r0 = max(c0, 0), max(r0, 0); w = min(w, ds.RasterXSize - c0); h = min(h, ds.RasterYSize - r0)
    a = ds.ReadAsArray(c0, r0, w, h, buf_xsize=int(w / step), buf_ysize=int(h / step))
    ext = (gt[0] + c0 * gt[1], gt[0] + (c0 + w) * gt[1], gt[3] + (r0 + h) * gt[5], gt[3] + r0 * gt[5])
    return np.transpose(a, (1, 2, 0)), ext


def draw(ax, img, ext, lw=0.9, show_per=False):
    ax.imshow(img, extent=ext)
    if show_per:
        for r in PER:
            ax.plot(r[:, 0], r[:, 1], color="#ff3030", lw=1.8)
    ax.add_collection(PolyCollection(P_OSM, facecolors="none", edgecolors="#00e5ff", linewidths=lw))
    ax.add_collection(PolyCollection(P_MS, facecolors="none", edgecolors="#ffe600", linewidths=lw))
    ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3]); ax.set_xticks([]); ax.set_yticks([])


LEG = [Line2D([], [], color="#ffe600", lw=1.6, label="Microsoft footprint (traced from 2019-20 imagery)"),
       Line2D([], [], color="#00e5ff", lw=1.6, label="OpenStreetMap footprint (2026)")]

# overview: whole window, 2016
gt = ds16.GetGeoTransform()
X0, X1 = gt[0], gt[0] + ds16.RasterXSize * gt[1]; Y1, Y0 = gt[3], gt[3] + ds16.RasterYSize * gt[5]
img, ext = read(ds16, X0, X1, Y0, Y1)
fig, ax = plt.subplots(figsize=(10, 10))
draw(ax, img, ext, lw=0.4, show_per=True)
for k, (la, lo, hw) in ZOOMS.items():
    x, y, _ = to_utm.TransformPoint(lo, la)
    ax.add_patch(plt.Rectangle((x - hw, y - hw), 2 * hw, 2 * hw, fill=False, ec="white", lw=1.5))
    ax.text(x - hw, y + hw + 40, k.replace("_", " "), color="white", fontsize=8, weight="bold")
ax.legend(handles=LEG + [Line2D([], [], color="#ff3030", lw=1.8, label="MTBS burn perimeter")], loc="lower left", fontsize=8)
ax.set_title("NAIP aerial photo, 17-18 April 2016 (7 months before the fire), shown at 6 m\nwhite boxes: zoom areas", fontsize=11)
fig.savefig(outp + "_overview.png", dpi=130, bbox_inches="tight"); plt.close(fig)

for k, (la, lo, hw) in ZOOMS.items():
    x, y, _ = to_utm.TransformPoint(lo, la)
    fig, axs = plt.subplots(1, 2, figsize=(14, 7.3))
    for ax, yr, t in ((axs[0], 2016, "April 2016 (before the fire)"), (axs[1], 2018, "October 2018 (2 years after)")):
        ds = gdal.Open("%s/zoom_%d_%s.tif" % (nd, yr, k))
        img, ext = read(ds, x - hw, x + hw, y - hw, y + hw)
        draw(ax, img, ext); ax.set_title(t, fontsize=11)
    n_ms = sum(1 for p in P_MS if abs(p[:, 0].mean() - x) < hw and abs(p[:, 1].mean() - y) < hw)
    n_osm = sum(1 for p in P_OSM if abs(p[:, 0].mean() - x) < hw and abs(p[:, 1].mean() - y) < hw)
    fig.suptitle("%s (%.4f N, %.4f W), %d x %d m: Microsoft %d buildings, OpenStreetMap %d"
                 % (k.replace("_", " "), la, -lo, 2 * hw, 2 * hw, n_ms, n_osm), fontsize=12, y=0.97)
    fig.legend(handles=LEG, loc="lower center", ncol=2, fontsize=9)
    fig.savefig("%s_%s.png" % (outp, k), dpi=120, bbox_inches="tight"); plt.close(fig)
    print("wrote %s_%s.png | MS %d, OSM %d" % (outp, k, n_ms, n_osm))
print("wrote", outp + "_overview.png")
