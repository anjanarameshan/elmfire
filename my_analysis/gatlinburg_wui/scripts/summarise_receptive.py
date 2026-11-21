#!/usr/bin/env python3
"""Burned area inside / outside the MTBS perimeter for the receptive-fraction runs (step5).

Usage: python summarise_receptive.py PERIMETER.shp SEEDS...
Rows: baseline (ms_st09/spot2) and spread_reduction/step5_receptiveXX/spot2, XX = 100 80 60 40 20.
Only finished seeds (log line "finished") are used.
"""
import sys, glob, os
import numpy as np
from osgeo import gdal, ogr

gdal.UseExceptions(); ogr.UseExceptions()
shp = sys.argv[1]; seeds = [int(s) for s in sys.argv[2:]]


def rd(p, k=1):
    ds = gdal.Open(p); return ds.GetRasterBand(k).ReadAsArray()


L = gdal.Open("ms_st09/spot2/inputs/landscape.tif"); fuel = L.GetRasterBand(4).ReadAsArray()
cnt = rd("ms_st09/spot2/inputs/bldg_count.tif")
m = gdal.GetDriverByName("MEM").Create("", L.RasterXSize, L.RasterYSize, 1, gdal.GDT_Byte)
m.SetGeoTransform(L.GetGeoTransform()); m.SetProjection(L.GetProjection())
pds = ogr.Open(shp); gdal.RasterizeLayer(m, [1], pds.GetLayer(), burn_values=[1]); per = m.ReadAsArray() == 1
ac = L.GetGeoTransform()[1] ** 2 / 4046.86; bper = (fuel == 91) & per
print("MTBS perimeter on grid: %s ac, %d buildings\n" % (format(round(per.sum() * ac), ","), cnt[bper].sum()))
print("%-22s %5s %9s %9s %9s %8s %8s %6s" % ("case", "seeds", "total", "inside", "outside", "out %", "cover %", "bldg"))
cases = [("baseline (original)", "ms_st09/spot2")] + [("receptive %d %%" % p, "spread_reduction/step5_receptive%d/spot2" % p) for p in (100, 80, 60, 40, 30, 20)]
for lab, case in cases:
    r = []
    for s in seeds:
        log = "%s/seed_%d/elmfire.log" % (case, s)
        if not (os.path.exists(log) and "finished" in open(log).read()):
            continue
        t = rd(glob.glob("%s/seed_%d/outputs/time_of_arrival_*.tif" % (case, s))[0]); b = t > 0
        r.append(((b & per).sum() * ac, (b & ~per).sum() * ac, (b & per).sum() / per.sum(), cnt[bper & b].sum()))
    if not r:
        print("%-22s  (no finished seeds)" % lab); continue
    i, o, c, n = np.mean(r, 0)
    print("%-22s %5d %9s %9s %9s %7.0f%% %7.0f%% %6.0f" % (lab, len(r), format(round(i + o), ","), format(round(i), ","),
                                                         format(round(o), ","), 100 * o / (i + o), 100 * c, n))
