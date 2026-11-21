#!/usr/bin/env python3
"""Map of building footprints inside / outside the MTBS burn perimeter, with roads and water.

Usage: python plot_buildings_in_perimeter.py BUILDINGS.gpkg PERIMETER.shp LANDSCAPE.tif OUT.png [LABEL]
  LANDSCAPE.tif  a case landscape (band 4 fuel: 99 roads/paved, 98 water) for the background
"""
import sys
import numpy as np
from osgeo import gdal, ogr, osr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.collections import PolyCollection
from matplotlib.lines import Line2D

gdal.UseExceptions(); ogr.UseExceptions()
bfile, shp, land, out = sys.argv[1:5]
label = sys.argv[5] if len(sys.argv) > 5 else "OpenStreetMap"
DOWNTOWN = (35.7143, -83.5102); SPOT2 = (35.690, -83.497)
wgs = osr.SpatialReference(); wgs.ImportFromEPSG(4326); wgs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)


def rings(g):
    gs = [g.GetGeometryRef(i) for i in range(g.GetGeometryCount())] if "MULTI" in g.GetGeometryName() else [g]
    return [np.array([p.GetGeometryRef(0).GetPoint_2D(i) for i in range(p.GetGeometryRef(0).GetPointCount())]) for p in gs]


pds = ogr.Open(shp); pl = pds.GetLayer(); per = None
for f in pl:
    g = f.GetGeometryRef().Clone(); g.Transform(osr.CoordinateTransformation(pl.GetSpatialRef(), wgs))
    per = g if per is None else per.Union(g)

bds = ogr.Open(bfile); bl = bds.GetLayer(); bs = bl.GetSpatialRef(); bs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
tr = osr.CoordinateTransformation(bs, wgs)
inside, outside = [], []
for f in bl:
    g = f.GetGeometryRef().Clone(); g.Transform(tr)
    (inside if per.Contains(g.Centroid()) else outside).extend(rings(g))

ds = gdal.Open(land); fuel = ds.GetRasterBand(4).ReadAsArray(); gt = ds.GetGeoTransform()
srs = osr.SpatialReference(); srs.ImportFromWkt(ds.GetProjection()); srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
ny, nx = fuel.shape
X, Y = np.meshgrid(gt[0] + (np.arange(nx) + 0.5) * gt[1], gt[3] + (np.arange(ny) + 0.5) * gt[5])
p = np.array(osr.CoordinateTransformation(srs, wgs).TransformPoints(np.column_stack([X.ravel(), Y.ravel()]).tolist()))
LON, LAT = p[:, 0].reshape(ny, nx), p[:, 1].reshape(ny, nx)

ex = per.GetEnvelope()                                     # minx, maxx, miny, maxy
EXT = (ex[0] - 0.02, ex[1] + 0.02, ex[2] - 0.01, ex[3] + 0.01)
sl = (LON > EXT[0] - .01) & (LON < EXT[1] + .01) & (LAT > EXT[2] - .01) & (LAT < EXT[3] + .01)
jj = np.where(sl.any(0))[0]; ii = np.where(sl.any(1))[0]; s = (slice(ii[0], ii[-1] + 1), slice(jj[0], jj[-1] + 1))

fig, ax = plt.subplots(figsize=(9, 9.5))
ax.pcolormesh(LON[s], LAT[s], np.where(fuel[s] == 99, 1.0, np.nan), cmap=ListedColormap(["#c9b39b"]), shading="auto")
ax.pcolormesh(LON[s], LAT[s], np.where(fuel[s] == 98, 1.0, np.nan), cmap=ListedColormap(["#0a8fb8"]), shading="auto")
ax.add_collection(PolyCollection(outside, facecolors="#7a7a7a", edgecolors="#7a7a7a", linewidths=0.6))
ax.add_collection(PolyCollection(inside, facecolors="#d7191c", edgecolors="#d7191c", linewidths=0.6))
for r in rings(per):
    ax.plot(r[:, 0], r[:, 1], color="#1f5fbf", lw=1.6)
ax.plot(DOWNTOWN[1], DOWNTOWN[0], "k*", ms=13)
ax.annotate("downtown\nGatlinburg", (DOWNTOWN[1], DOWNTOWN[0]), xytext=(8, 6), textcoords="offset points", fontsize=9)
ax.plot(SPOT2[1], SPOT2[0], "o", mfc="#00e5ff", mec="k", ms=9)
ax.annotate("observed spot fire 2", (SPOT2[1], SPOT2[0]), xytext=(8, -4), textcoords="offset points", fontsize=9)
ax.set_xlim(EXT[0], EXT[1]); ax.set_ylim(EXT[2], EXT[3]); ax.set_aspect(1 / np.cos(np.radians(35.68)))
ax.set_xlabel("longitude [$^\\circ$]"); ax.set_ylabel("latitude [$^\\circ$]")
ax.set_title("%s buildings: %d inside the MTBS perimeter, %d outside\n"
             "Reported destroyed in the fire: 2,013 homes + 53 commercial (Jimenez et al. 2018)"
             % (label, len(inside), len(outside)), fontsize=10.5)
ax.legend(handles=[Line2D([], [], color="#1f5fbf", lw=1.6, label="MTBS burn perimeter (15,002 ac)"),
                   Line2D([], [], ls="", marker="s", color="#d7191c", ms=8, label="building inside perimeter (%d)" % len(inside)),
                   Line2D([], [], ls="", marker="s", color="#7a7a7a", ms=8, label="building outside perimeter"),
                   Line2D([], [], ls="", marker="s", color="#c9b39b", ms=8, label="roads / paved (no buildings)"),
                   Line2D([], [], ls="", marker="s", color="#0a8fb8", ms=8, label="water")],
          loc="lower left", fontsize=8.5, framealpha=0.95)
fig.savefig(out, dpi=150, bbox_inches="tight")
print("wrote %s | inside %d, outside %d" % (out, len(inside), len(outside)))
