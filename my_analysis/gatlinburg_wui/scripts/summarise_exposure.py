#!/usr/bin/env python3
"""Ember vs heat building ignitions for the exposure-time series (perimeter-constrained, 100 % case).

Usage: python summarise_exposure.py PERIMETER.shp
Cases: perimeter_constrained/receptive100 (TAU_EMBERGEN 10 s) and exposure0100 ... exposure1000.
Per case (mean of finished seeds): burned acres, buildings ignited inside the MTBS perimeter, of which by
embers (DUMP_EMBER_IGNITION flag on a building cell), largest ember load on a building cell inside the
perimeter (g/cm2) and that load relative to the ST09 threshold at the strongest wind (0.00767 g/cm2).
"""
import sys, glob, os
import numpy as np
from osgeo import gdal, ogr

gdal.UseExceptions(); ogr.UseExceptions()
shp = sys.argv[1]


def rd(p, k=1):
    ds = gdal.Open(p); return ds.GetRasterBand(k).ReadAsArray()


base = "perimeter_constrained/inputs_spot2"
L = gdal.Open(base + "/landscape.tif"); fuel = L.GetRasterBand(4).ReadAsArray(); cnt = rd(base + "/bldg_count.tif")
m = gdal.GetDriverByName("MEM").Create("", L.RasterXSize, L.RasterYSize, 1, gdal.GDT_Byte)
m.SetGeoTransform(L.GetGeoTransform()); m.SetProjection(L.GetProjection())
pds = ogr.Open(shp); gdal.RasterizeLayer(m, [1], pds.GetLayer(), burn_values=[1]); per = m.ReadAsArray() == 1
bper = (fuel == 91) & per; ac = L.GetGeoTransform()[1] ** 2 / 4046.86
NEED = 0.211 / ((1.35 + 0.073) * (4.111 - 1.35)) / 7.0
print("%-14s %5s %8s %10s %10s %10s %10s" % ("exposure", "seeds", "acres", "bldg", "by embers", "max psi", "x needed"))
for lab, case in [("10 s", "receptive100")] + [("%d s" % v, "exposure%04d" % v) for v in (100, 300, 600, 900, 1000)]:
    r = []
    for s in (1, 2, 3):
        d = "perimeter_constrained/%s/spot2/seed_%d" % (case, s)
        if not (os.path.exists(d + "/elmfire.log") and "finished" in open(d + "/elmfire.log").read()):
            continue
        t = rd(glob.glob(d + "/outputs/time_of_arrival_*.tif")[0]); e = rd(glob.glob(d + "/outputs/ember_ignition_*.tif")[0]) > 0
        f = rd(d + "/outputs/ember_flux.tif"); psi = f[bper].max() / 900 * 0.2 / 1e4
        r.append(((t > 0).sum() * ac, cnt[bper & (t > 0)].sum(), cnt[bper & e].sum(), psi))
    if not r:
        print("%-14s  (not finished)" % lab); continue
    a = np.mean(r, 0)
    print("%-14s %5d %8.0f %10.0f %10.1f %10.5f %10.1f" % (lab, len(r), a[0], a[1], a[2], a[3], NEED / a[3]))
