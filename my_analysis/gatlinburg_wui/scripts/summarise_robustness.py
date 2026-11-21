#!/usr/bin/env python3
"""Robustness runs vs the WU-E / ST09 baseline: buildings ignited inside the MTBS perimeter, by embers, burned acres.

Usage: python summarise_robustness.py PERIMETER.shp
Cases: ms_st09 (baseline: WU-E building model type 2, building fuel class ST09), robustness/hamada (type 1 Hamada,
5 locations x 10 seeds), robustness/bldg_ST10..12 (WU-E with building classes ST10-12, observed location x 10 seeds).
Mean, min-max over finished seeds. Writes robustness/robustness_summary.csv.
"""
import sys, glob, os
import numpy as np
from osgeo import gdal, ogr

gdal.UseExceptions(); ogr.UseExceptions()
shp = sys.argv[1]


def rd(p, k=1):
    ds = gdal.Open(p); return ds.GetRasterBand(k).ReadAsArray()


inp = "ms_st09/spot2/inputs/"
L = gdal.Open(inp + "landscape.tif"); fuel = rd(inp + "landscape.tif", 4); cnt = rd(inp + "bldg_count.tif")
m = gdal.GetDriverByName("MEM").Create("", L.RasterXSize, L.RasterYSize, 1, gdal.GDT_Byte)
m.SetGeoTransform(L.GetGeoTransform()); m.SetProjection(L.GetProjection())
pds = ogr.Open(shp); gdal.RasterizeLayer(m, [1], pds.GetLayer(), burn_values=[1]); per = m.ReadAsArray() == 1
bper = (fuel == 91) & per; ac = L.GetGeoTransform()[1] ** 2 / 4046.86
LOCS = ["spot2", "spot2_N1km", "spot2_S1km", "spot2_E1km", "spot2_W1km"]
cases = [("WU-E, ST09 (baseline)", "ms_st09", LOCS), ("Hamada (type 1), ST09", "robustness/hamada", LOCS)]
cases += [("WU-E, ST09 (baseline)", "ms_st09", ["spot2"])] + [("WU-E, ST%d" % k, "robustness/bldg_ST%d" % k, ["spot2"]) for k in (10, 11, 12)]
out = open("robustness/robustness_summary.csv", "w")
out.write("case,locations,runs,buildings_mean,buildings_min,buildings_max,by_embers_mean,acres_mean\n")
print("%-24s %-10s %4s %22s %10s %10s" % ("case", "locations", "runs", "buildings in perimeter", "by embers", "acres"))
for lab, root, locs in cases:
    r = []
    for loc in locs:
        for d in glob.glob("%s/%s/seed_*" % (root, loc)):
            if not (os.path.exists(d + "/elmfire.log") and "finished" in open(d + "/elmfire.log").read()):
                continue
            t = rd(glob.glob(d + "/outputs/time_of_arrival_*.tif")[0]); e = rd(glob.glob(d + "/outputs/ember_ignition_*.tif")[0]) > 0
            r.append((cnt[bper & (t > 0)].sum(), cnt[bper & (t > 0) & e].sum(), (t > 0).sum() * ac))
    r = np.array(r, float); ls = "all 5" if len(locs) > 1 else "observed"
    print("%-24s %-10s %4d %10.0f [%4.0f-%4.0f] %10.1f %10.0f" % (lab, ls, len(r), r[:, 0].mean(), r[:, 0].min(), r[:, 0].max(), r[:, 1].mean(), r[:, 2].mean()))
    out.write("%s,%s,%d,%.1f,%d,%d,%.2f,%.0f\n" % (lab, ls, len(r), r[:, 0].mean(), r[:, 0].min(), r[:, 0].max(), r[:, 1].mean(), r[:, 2].mean()))
out.close()
