#!/usr/bin/env python3
"""Which test run comes closest to the observed burned area north of the building line (6,420 ac)?

Usage: python compare_runs_north_zone.py PERIMETER.shp
Observed: MTBS perimeter north of northing 3,953,384 m (southern edge of the continuous built-up area, see
vulnerability/town_zone.txt) = 6,420 ac.
For every run folder with time_of_arrival_*.tif (seeds averaged), on the run's own 30 m grid:
  total      all burned cells (time of arrival > 0)
  north      burned cells north of the line (inside or outside MTBS)
  hit        share of the observed 6,420 ac that the run burned
  Sorensen   2 x overlap / (model north + observed north), 1 = same area in the same place
Writes vulnerability/runs_north_zone.csv and prints the table sorted by |north - 6,420|.
"""
import sys, glob, os
import numpy as np
from osgeo import gdal, ogr

gdal.UseExceptions(); ogr.UseExceptions()
Y0 = 3953384.0; AC = 4046.856
pds = ogr.Open(sys.argv[1])
runs = sorted({os.path.dirname(os.path.dirname(f)).rsplit("/seed_", 1)[0] for f in glob.glob("**/outputs/time_of_arrival_*.tif", recursive=True)})
cache = {}; rows = []
for r in runs:
    fs = sorted(glob.glob(r + "/seed_*/outputs/time_of_arrival_*.tif") + glob.glob(r + "/outputs/time_of_arrival_*.tif"))
    v = []
    for f in fs:
        ds = gdal.Open(f); gt = ds.GetGeoTransform(); key = (gt, ds.RasterXSize, ds.RasterYSize)
        if key not in cache:
            m = gdal.GetDriverByName("MEM").Create("", ds.RasterXSize, ds.RasterYSize, 1, gdal.GDT_Byte)
            m.SetGeoTransform(gt); m.SetProjection(ds.GetProjection())
            gdal.RasterizeLayer(m, [1], pds.GetLayer(), burn_values=[1])
            yc = gt[3] + (np.arange(ds.RasterYSize) + 0.5) * gt[5]
            north = np.repeat((yc >= Y0)[:, None], ds.RasterXSize, 1)
            cache[key] = (m.ReadAsArray() == 1, north, abs(gt[1] * gt[5]) / AC)
        per, north, ca = cache[key]
        b = ds.GetRasterBand(1).ReadAsArray() > 0; del ds
        obs = per & north; mod = b & north; ov = (obs & mod).sum()
        v.append((b.sum() * ca, mod.sum() * ca, ov / obs.sum(), 2 * ov / (mod.sum() + obs.sum()), obs.sum() * ca))
    v = np.array(v).mean(0); rows.append((r, len(fs), *v))
rows.sort(key=lambda x: abs(x[3] - 6420))
with open("vulnerability/runs_north_zone.csv", "w") as f:
    f.write("run,seeds,total_ac,north_ac,hit_share,sorensen,observed_north_ac\n")
    for r in rows:
        f.write("%s,%d,%.0f,%.0f,%.3f,%.3f,%.0f\n" % r)
print("observed (MTBS north of the line on the 30 m grid): %.0f ac" % rows[0][6])
print("%-46s %5s %9s %9s %6s %8s" % ("run", "seeds", "total ac", "north ac", "hit", "Sorensen"))
for r in rows:
    print("%-46s %5d %9.0f %9.0f %6.2f %8.2f" % (r[0], r[1], r[2], r[3], r[4], r[5]))
