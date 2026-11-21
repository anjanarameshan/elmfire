#!/usr/bin/env python3
"""Barrier-width raster for ELMFIRE (USE_BARRIERS, guide section 1.10) from OpenStreetMap roads and rivers.

Usage: python build_barriers.py LANDSCAPE.tif ROADS.json WATERWAYS.json OUT_BARRIER.tif

Each 30 m cell crossed by a road or waterway gets that feature's typical width (m); where several
cross a cell the widest is kept. ELMFIRE stops surface spread into a cell when
1.5 x flame length <= barrier width (elmfire_subs.f90, CHECK_BARRIER_BREACH); embers are not affected.
Widths are typical paved / channel widths, not measured:
"""
import sys, json
import numpy as np
from osgeo import gdal, osr

WIDTH = {"motorway": 20, "trunk": 15, "primary": 12, "secondary": 10, "tertiary": 8, "unclassified": 6,
         "residential": 6, "service": 4, "track": 3, "river": 20, "canal": 8, "stream": 3}
__doc__ += "  " + ", ".join("%s %d m" % kv for kv in WIDTH.items())

gdal.UseExceptions()
land, roads, water, out = sys.argv[1:5]
L = gdal.Open(land); gt = L.GetGeoTransform(); nx, ny = L.RasterXSize, L.RasterYSize
srs = osr.SpatialReference(); srs.ImportFromWkt(L.GetProjection()); srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
wgs = osr.SpatialReference(); wgs.ImportFromEPSG(4326); wgs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
tr = osr.CoordinateTransformation(wgs, srs)
bw = np.zeros((ny, nx), np.float32)
count = {}
for fn, key in ((roads, "highway"), (water, "waterway")):
    for e in json.load(open(fn))["elements"]:
        w = WIDTH.get(e.get("tags", {}).get(key))
        if not w or "geometry" not in e:
            continue
        count[e["tags"][key]] = count.get(e["tags"][key], 0) + 1
        p = np.array(tr.TransformPoints([(q["lon"], q["lat"]) for q in e["geometry"]]))[:, :2]
        for a, b in zip(p[:-1], p[1:]):                 # sample every 5 m along each segment
            n = int(np.hypot(*(b - a)) / 5) + 1
            xy = a + (b - a) * np.linspace(0, 1, n + 1)[:, None]
            j = ((xy[:, 0] - gt[0]) / gt[1]).astype(int); i = ((xy[:, 1] - gt[3]) / gt[5]).astype(int)
            k = (i >= 0) & (i < ny) & (j >= 0) & (j < nx)
            bw[i[k], j[k]] = np.maximum(bw[i[k], j[k]], w)
d = gdal.GetDriverByName("GTiff").Create(out, nx, ny, 1, gdal.GDT_Float32, ["COMPRESS=DEFLATE"])
d.SetGeoTransform(gt); d.SetProjection(L.GetProjection()); d.GetRasterBand(1).WriteArray(bw); d = None
print("wrote", out, "| features:", count, "| barrier cells:", int((bw > 0).sum()),
      "| by width:", {int(v): int((bw == v).sum()) for v in np.unique(bw[bw > 0])})
