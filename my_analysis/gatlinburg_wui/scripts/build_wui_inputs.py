#!/usr/bin/env python3
"""Build ELMFIRE inputs for a Gatlinburg ember / structure-ignition scenario.

Usage:
  python build_wui_inputs.py BASE_INPUTS BUILDINGS.gpkg OUT_INPUTS LAT LON FIRST_BAND NBANDS [START_ACRES]

  BASE_INPUTS  inputs/ folder of an all-CloudFire run (landscape.tif, ws, wd, m1, m10, m100, lh, lw, adj,
               fuel_models.csv) on the 40 km Chimney Tops grid
  BUILDINGS    building footprints (polygons, any CRS) - Microsoft US Building Footprints
  LAT LON      centre of the spot-fire ignition (a circle of START_ACRES, default 1 acre)
  FIRST_BAND   1-based weather band of the scenario start; NBANDS hourly bands are kept

What it writes to OUT_INPUTS:
  landscape.tif   copy of BASE landscape with the fuel band (4) changed:
                    - cells with building footprint fraction >= FOOTPRINT_MIN -> 91 (building cell)
                    - LANDFIRE 91 cells without buildings (roads, parking) -> 99 (non-burnable)
  bldg_footprint_frac.tif   building footprint area / cell area (0-1)
  bldg_area.tif             mean building plan dimension in the cell, m (sqrt of mean footprint area)
  bldg_separation.tif       mean separation between buildings in the cell, m
                            (sqrt(cell area / n buildings) - plan dimension, at least 2 m)
  bldg_nonburnable_frac.tif 0 (all buildings combustible)
  bldg_fuel_model.tif       building fuel model number of ELMFIRE's building_fuel_models.csv, env BLDG_FM
                            (default 1 = ST01, which embers cannot ignite: hardening 0; 9 = ST09, hardening 7)
  bldg_count.tif            number of building centroids in the cell (for counting structures)
  ws, wd, m1, m10, m100, lh, lw .tif   bands FIRST_BAND .. FIRST_BAND+NBANDS-1 of BASE
  adj.tif, phi.tif          adj = 1; phi = -1 inside the spot-fire circle, +1 elsewhere
  fuel_models.csv, building_fuel_models.csv
"""
import sys, os, shutil
import numpy as np
from osgeo import gdal, ogr, osr

gdal.UseExceptions(); ogr.UseExceptions()
base, bfile, out = sys.argv[1:4]
lat, lon = float(sys.argv[4]), float(sys.argv[5])
b0, nb = int(sys.argv[6]), int(sys.argv[7])
acres = float(sys.argv[8]) if len(sys.argv) > 8 else 1.0
FOOTPRINT_MIN = 0.02
BLDG_FM = int(os.environ.get("BLDG_FM", "1"))
os.makedirs(out, exist_ok=True)

land = gdal.Open(os.path.join(base, "landscape.tif"))
gt, prj = land.GetGeoTransform(), land.GetProjection()
nx, ny = land.RasterXSize, land.RasterYSize
cell = gt[1]
drv = gdal.GetDriverByName("GTiff")


def new(name, dtype=gdal.GDT_Float32, bands=1):
    ds = drv.Create(os.path.join(out, name), nx, ny, bands, dtype, ["COMPRESS=DEFLATE"])
    ds.SetGeoTransform(gt); ds.SetProjection(prj)
    return ds


# ---- building footprints -> 30 m rasters ----
srs = osr.SpatialReference(); srs.ImportFromWkt(prj); srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
src = ogr.Open(bfile); lyr = src.GetLayer()
s_srs = lyr.GetSpatialRef(); s_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
tr = osr.CoordinateTransformation(s_srs, srs)
xmin, xmax, ymax = gt[0], gt[0] + nx * cell, gt[3]
ymin = ymax - ny * cell
mem = ogr.GetDriverByName("MEM").CreateDataSource("m")
ml = mem.CreateLayer("b", srs, ogr.wkbPolygon)
n_in = 0
cnt = np.zeros((ny, nx), np.int32); asum = np.zeros((ny, nx))
for f in lyr:
    g = f.GetGeometryRef().Clone(); g.Transform(tr)
    c = g.Centroid(); x, y = c.GetX(), c.GetY()
    if not (xmin <= x < xmax and ymin < y <= ymax):
        continue
    of = ogr.Feature(ml.GetLayerDefn()); of.SetGeometry(g); ml.CreateFeature(of)
    i, j = int((ymax - y) / cell), int((x - xmin) / cell)
    cnt[i, j] += 1; asum[i, j] += g.GetArea(); n_in += 1
# footprint fraction: rasterise at 3 m and aggregate to the 30 m cell
SUB = 10
fine = gdal.GetDriverByName("MEM").Create("", nx * SUB, ny * SUB, 1, gdal.GDT_Byte)
fine.SetGeoTransform((gt[0], cell / SUB, 0, gt[3], 0, -cell / SUB)); fine.SetProjection(prj)
gdal.RasterizeLayer(fine, [1], ml, burn_values=[1])
fp = fine.ReadAsArray().reshape(ny, SUB, nx, SUB).mean(axis=(1, 3)).astype(np.float32)
fine = None
plan = np.where(cnt > 0, np.sqrt(asum / np.maximum(cnt, 1)), 0).astype(np.float32)
sep = np.where(cnt > 0, np.maximum(np.sqrt(cell * cell / np.maximum(cnt, 1)) - plan, 2.0), 30.0).astype(np.float32)

fuel = land.GetRasterBand(4).ReadAsArray()
bcell = fp >= FOOTPRINT_MIN
new_fuel = fuel.copy()
new_fuel[(fuel == 91) & ~bcell] = 99
new_fuel[bcell] = 91
L = drv.CreateCopy(os.path.join(out, "landscape.tif"), land, options=["COMPRESS=DEFLATE"])
L.GetRasterBand(4).WriteArray(new_fuel); L = None

for name, arr in (("bldg_footprint_frac.tif", np.where(bcell, fp, 0)), ("bldg_area.tif", np.where(bcell, np.maximum(plan, 3), 10)),
                  ("bldg_separation.tif", np.where(bcell, sep, 30)), ("bldg_nonburnable_frac.tif", np.zeros_like(fp)),
                  ("bldg_count.tif", cnt.astype(np.float32))):
    d = new(name); d.GetRasterBand(1).WriteArray(arr.astype(np.float32)); d = None
d = new("bldg_fuel_model.tif", gdal.GDT_Int16); d.GetRasterBand(1).WriteArray(np.full((ny, nx), BLDG_FM, np.int16)); d = None

# ---- weather: slice the scenario's hours ----
for w in ("ws", "wd", "m1", "m10", "m100", "lh", "lw"):
    gdal.Translate(os.path.join(out, w + ".tif"), os.path.join(base, w + ".tif"),
                   bandList=list(range(b0, b0 + nb)), creationOptions=["COMPRESS=DEFLATE"])

# ---- adj and phi (spot-fire circle) ----
a = new("adj.tif"); a.GetRasterBand(1).WriteArray(np.ones((ny, nx), np.float32)); a = None
wgs = osr.SpatialReference(); wgs.ImportFromEPSG(4326); wgs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
x0, y0, _ = osr.CoordinateTransformation(wgs, srs).TransformPoint(lon, lat)
r = np.sqrt(acres * 4046.86 / np.pi)
X, Y = np.meshgrid(gt[0] + (np.arange(nx) + 0.5) * cell, gt[3] - (np.arange(ny) + 0.5) * cell)
inside = (X - x0) ** 2 + (Y - y0) ** 2 <= max(r, cell * 0.75) ** 2
p = new("phi.tif"); p.GetRasterBand(1).WriteArray(np.where(inside, -1.0, 1.0).astype(np.float32)); p = None

shutil.copy(os.path.join(base, "fuel_models.csv"), out)
shutil.copy(os.path.join(os.path.dirname(__file__), "..", "..", "..", "build", "source", "building_fuel_models.csv"), out)

print("building fuel model ST%02d | buildings in domain: %d | building cells (footprint >= %.2f): %d, holding %d buildings | road/parking 91 -> 99: %d cells"
      % (BLDG_FM, n_in, FOOTPRINT_MIN, bcell.sum(), cnt[bcell].sum(), ((fuel == 91) & ~bcell).sum()))
print("spot fire at %.4f N %.4f W: x=%.0f y=%.0f, %d cells (%.1f ac), fuel %s" %
      (lat, -lon, x0, y0, inside.sum(), inside.sum() * cell * cell / 4046.86, sorted(set(new_fuel[inside].tolist()))))
