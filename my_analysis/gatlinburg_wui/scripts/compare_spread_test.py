#!/usr/bin/env python3
"""Compare a spread-reduction test against the baseline (same spot fire, same seeds).

Usage: python compare_spread_test.py BASE_CASE TEST_CASE PERIMETER.shp SEEDS...
  e.g. compare_spread_test.py ms_st09/spot2 spread_reduction/step1_dtmax60/spot2 mtbs.shp 1 2 3
Per seed: burned acres at 03:00, acres before/after 22:00 EST, buildings ignited inside the MTBS
perimeter, share of burned forest ignited by embers, building ember ignitions, run time.
"""
import sys, glob, re
import numpy as np
from osgeo import gdal, ogr

gdal.UseExceptions(); ogr.UseExceptions()
base, test, shp = sys.argv[1:4]; seeds = [int(s) for s in sys.argv[4:]]


def rd(p, k=1):
    ds = gdal.Open(p); return ds.GetRasterBand(k).ReadAsArray()


L = gdal.Open(base + "/inputs/landscape.tif")
fuel = L.GetRasterBand(4).ReadAsArray(); cnt = rd(base + "/inputs/bldg_count.tif")
m = gdal.GetDriverByName("MEM").Create("", L.RasterXSize, L.RasterYSize, 1, gdal.GDT_Byte)
m.SetGeoTransform(L.GetGeoTransform()); m.SetProjection(L.GetProjection())
pds = ogr.Open(shp); gdal.RasterizeLayer(m, [1], pds.GetLayer(), burn_values=[1]); per = m.ReadAsArray() == 1
bper = (fuel == 91) & per; ac = L.GetGeoTransform()[1] ** 2 / 4046.86; veg = fuel != 91


def stats(case, s):
    o = "%s/seed_%d/outputs" % (case, s)
    t = rd(glob.glob(o + "/time_of_arrival_*.tif")[0]); e = rd(glob.glob(o + "/ember_ignition_*.tif")[0]) > 0
    b = t > 0
    log = open("%s/seed_%d/elmfire.log" % (case, s)).read()
    mm = re.search(r"finished in (\d+) min", log)
    return dict(acres=b.sum() * ac, before22=(b & (t <= 11 * 3600)).sum() * ac, after22=(b & (t > 11 * 3600)).sum() * ac,
                bldg=cnt[bper & b].sum(), bldg_emb=cnt[bper & b & e].sum(),
                veg_emb=100 * (b & e & veg).sum() / max((b & veg).sum(), 1), minutes=int(mm.group(1)) if mm else -1)


print("%-6s %-5s %9s %9s %9s %6s %8s %8s %5s" % ("case", "seed", "acres", "<=22:00", ">22:00", "bldg", "bldg_emb", "veg_emb%", "min"))
res = {}
for name, case in (("base", base), ("test", test)):
    res[name] = []
    for s in seeds:
        r = stats(case, s); res[name].append(r)
        print("%-6s %-5d %9.0f %9.0f %9.0f %6d %8d %8.1f %5d" % (name, s, r["acres"], r["before22"], r["after22"], r["bldg"], r["bldg_emb"], r["veg_emb"], r["minutes"]))
for k in ("acres", "bldg", "veg_emb"):
    a = np.mean([r[k] for r in res["base"]]); b = np.mean([r[k] for r in res["test"]])
    print("mean %-8s base %9.1f  test %9.1f  change %+6.1f%%" % (k, a, b, 100 * (b - a) / a))
