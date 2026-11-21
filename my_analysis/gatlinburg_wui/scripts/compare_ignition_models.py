#!/usr/bin/env python3
"""Building ignitions under two ember ignition models, per seed: PHYSICAL (De Beer threshold) vs SIMPLE (probabilistic).

Usage: python compare_ignition_models.py PERIMETER.shp NAME=RUNDIR [NAME=RUNDIR ...]
       (e.g. PHYSICAL=simple_ignition/physical_ref/spot2 SIMPLE=simple_ignition/spot2; seeds = RUNDIR/seed_*)
Building cell = fuel 91 with >= 1 building centroid (bldg_count, from ms_st09/spot2/inputs). Per seed:
  burned area (ac), buildings ignited inside / outside the MTBS perimeter, building cells ignited by embers
  (ember_ignition map = 1) and the share of ignited buildings that were ember-ignited.
Writes OUT (env, default simple_ignition/compare_summary.txt).
"""
import sys, glob
import numpy as np
from osgeo import gdal, ogr

gdal.UseExceptions(); ogr.UseExceptions()


def rd(p, k=1):
    d = gdal.Open(p); return d.GetRasterBand(k).ReadAsArray()


inp = "ms_st09/spot2/inputs/"
L = gdal.Open(inp + "landscape.tif"); fuel = rd(inp + "landscape.tif", 4); cnt = rd(inp + "bldg_count.tif")
m = gdal.GetDriverByName("MEM").Create("", L.RasterXSize, L.RasterYSize, 1, gdal.GDT_Byte)
m.SetGeoTransform(L.GetGeoTransform()); m.SetProjection(L.GetProjection())
pds = ogr.Open(sys.argv[1]); gdal.RasterizeLayer(m, [1], pds.GetLayer(), burn_values=[1]); per = m.ReadAsArray() == 1
bc = (fuel == 91) & (cnt > 0)
AC = 900 / 4046.86
out = ["Ember ignition model comparison, observed spot point, 16 h (buildings counted from bldg_count of ignited cells)",
       "%-9s %-5s %8s %10s %10s %14s %14s %14s" % ("model", "seed", "acres", "bldg in", "bldg out", "ember-ign in", "ember share", "ember-ign out")]
for arg in sys.argv[2:]:
    name, run = arg.split("=", 1); rows = []
    for sd in sorted(glob.glob(run + "/seed_*/outputs"), key=lambda s: int(s.split("seed_")[1].split("/")[0])):
        toa = rd(glob.glob(sd + "/time_of_arrival_*.tif")[0]); ei = rd(glob.glob(sd + "/ember_ignition_*.tif")[0])
        ig = bc & (toa > 0); e = ig & (ei == 1)
        v = [(toa > 0).sum() * AC, cnt[ig & per].sum(), cnt[ig & ~per].sum(), cnt[e & per].sum()]
        v.append(v[3] / max(v[1], 1)); v.append(cnt[e & ~per].sum()); rows.append(v)
        out.append("%-9s %-5s %8.0f %10d %10d %14d %13.0f%% %14d" % (name, sd.split("seed_")[1].split("/")[0], v[0], v[1], v[2], v[3], 100 * v[4], v[5]))
    mu = np.mean(rows, 0)
    out.append("%-9s %-5s %8.0f %10.0f %10.0f %14.0f %13.0f%% %14.0f" % (name, "mean", mu[0], mu[1], mu[2], mu[3], 100 * mu[4], mu[5]))
txt = "\n".join(out); print(txt); open(__import__("os").environ.get("OUT", "simple_ignition/compare_summary.txt"), "w").write(txt + "\n")
