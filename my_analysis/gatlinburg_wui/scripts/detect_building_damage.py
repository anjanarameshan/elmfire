#!/usr/bin/env python3
"""Automatic first pass of building damage from NAIP 2016 (pre-fire) vs 2018 (post-fire) imagery.

Usage: python detect_building_damage.py PERIMETER.shp
Footprints: data/ms_buildings.gpkg (Microsoft, captured 9/2019-12/2019, i.e. after the fire), buildings whose
centroid is inside the MTBS perimeter. Imagery: data/naip/bldg4_2016.tif (17-18 Apr 2016, leaf-off) and
bldg4_2018.tif (30 Oct 2018), 1 m, bands R G B NIR (data/naip/fetch_buildings_4band.sh).
Per footprint (shrunk by 1 m to avoid edges and shadows), both years: mean NDVI, mean RGB, and the pixel
correlation of the grey image between years.
First-pass label (thresholds are a starting point, to be checked by eye on the uncertain and a random sample):
  new_construction  2016 footprint area looks like vegetation (NDVI16 > 0.30): building not there at the fire
  survived          same roof: correlation > 0.5 and RGB change < 35
  destroyed         changed: correlation < 0.2 or RGB change > 70 (empty lot, ash, or rebuilt roof)
  uncertain         anything else, or footprint < 20 pixels
Writes damage/damage_auto.csv (one row per building: id, lon, lat, features, label).
"""
import sys, os
import numpy as np
from osgeo import gdal, ogr, osr

gdal.UseExceptions(); ogr.UseExceptions()
shp = sys.argv[1]; OUT = "damage"; os.makedirs(OUT, exist_ok=True)
A = gdal.Open("data/naip/bldg4_2016.tif"); B = gdal.Open("data/naip/bldg4_2018.tif")
gt = A.GetGeoTransform(); nx, ny = A.RasterXSize, A.RasterYSize
utm = osr.SpatialReference(); utm.ImportFromEPSG(32617); utm.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
wgs = osr.SpatialReference(); wgs.ImportFromEPSG(4326); wgs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
to_utm = osr.CoordinateTransformation(wgs, utm)

# perimeter in UTM
pds = ogr.Open(shp); pl = pds.GetLayer(); perim = None
for f in pl:
    g = f.GetGeometryRef().Clone(); g.TransformTo(utm); perim = g if perim is None else perim.Union(g)

# footprints with centroid inside the perimeter, shrunk 1 m, in a memory layer with an integer id
sds = ogr.Open("data/ms_buildings.gpkg"); src = sds.GetLayer()
src.SetSpatialFilterRect(-83.58, 35.66, -83.44, 35.78)
mem = ogr.GetDriverByName("Memory").CreateDataSource(""); ml = mem.CreateLayer("b", utm, ogr.wkbPolygon)
ml.CreateField(ogr.FieldDefn("id", ogr.OFTInteger))
info = []
for f in src:
    g = f.GetGeometryRef().Clone(); g.Transform(to_utm)
    c = g.Centroid()
    if not perim.Contains(c):
        continue
    k = len(info) + 1
    gs = g.Buffer(-1.0)
    if gs.IsEmpty():
        gs = g
    nf = ogr.Feature(ml.GetLayerDefn()); nf.SetField("id", k); nf.SetGeometry(gs); ml.CreateFeature(nf)
    lonlat = c.Clone(); lonlat.Transform(osr.CoordinateTransformation(utm, wgs))
    info.append((k, lonlat.GetX(), lonlat.GetY(), g.GetArea()))
n = len(info); print("footprints with centroid inside the MTBS perimeter:", n)
ids = gdal.GetDriverByName("MEM").Create("", nx, ny, 1, gdal.GDT_Int32)
ids.SetGeoTransform(gt); ids.SetProjection(utm.ExportToWkt())
gdal.RasterizeLayer(ids, [1], ml, options=["ATTRIBUTE=id", "ALL_TOUCHED=FALSE"])
I = ids.ReadAsArray().ravel(); sel = I > 0; I = I[sel]


def bands(ds):
    return [ds.GetRasterBand(k).ReadAsArray().ravel()[sel].astype(float) for k in range(1, 5)]


def bsum(v):
    return np.bincount(I, weights=v, minlength=n + 1)[1:]


r1, g1, b1, n1 = bands(A); r2, g2, b2, n2 = bands(B)
npx = np.bincount(I, minlength=n + 1)[1:].astype(float); npx_ = np.maximum(npx, 1)
ndvi1 = bsum((n1 - r1) / np.maximum(n1 + r1, 1)) / npx_; ndvi2 = bsum((n2 - r2) / np.maximum(n2 + r2, 1)) / npx_
m1 = np.array([bsum(x) / npx_ for x in (r1, g1, b1)]); m2 = np.array([bsum(x) / npx_ for x in (r2, g2, b2)])
drgb = np.sqrt(((m1 - m2) ** 2).sum(0))
y1 = (r1 + g1 + b1) / 3; y2 = (r2 + g2 + b2) / 3
sx, sy = bsum(y1), bsum(y2); sxx, syy, sxy = bsum(y1 * y1), bsum(y2 * y2), bsum(y1 * y2)
cov = sxy / npx_ - sx * sy / npx_ ** 2; vx = sxx / npx_ - (sx / npx_) ** 2; vy = syy / npx_ - (sy / npx_) ** 2
corr = cov / np.sqrt(np.maximum(vx * vy, 1e-9))

lab = np.full(n, "uncertain", object)
lab[(corr > 0.5) & (drgb < 35)] = "survived"
lab[(corr < 0.2) | (drgb > 70)] = "destroyed"
lab[ndvi1 > 0.30] = "new_construction"
lab[npx < 20] = "uncertain"
with open(OUT + "/damage_auto.csv", "w") as f:
    f.write("id,lon,lat,area_m2,pixels,ndvi2016,ndvi2018,rgb_change,corr,label_auto\n")
    for (k, lo, la, ar), p, a, b, d, c, l in zip(info, npx, ndvi1, ndvi2, drgb, corr, lab):
        f.write("%d,%.6f,%.6f,%.1f,%d,%.3f,%.3f,%.1f,%.3f,%s\n" % (k, lo, la, ar, p, a, b, d, c, l))
for l in ("survived", "destroyed", "new_construction", "uncertain"):
    print("  %-17s %5d" % (l, (lab == l).sum()))
print("wrote damage/damage_auto.csv")
