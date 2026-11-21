#!/usr/bin/env python3
"""Leaf-off canopy for deciduous (broadleaf-litter) cells, for the 28 Nov 2016 runs.

Usage: python make_leafoff_landscape.py IN_landscape.tif OUT_landscape.tif [CC_PERCENT=10]
LANDFIRE canopy cover (band 5, %) is leaf-on. ELMFIRE derives the wind adjustment factor (20-ft -> midflame) from canopy
cover and height (elmfire_init.f90, CALC_WIND_ADJUSTMENT_FACTOR_EVERYWHERE); leaf-on cover (median 85 %) gives WAF 0.08.
Andrews (2012, USDA RMRS-GTR-266, Table 12, NFMAS): hardwood litter WAF 0.25 in winter (leaf-off), 0.08 in summer.
Setting cover to 10 % in fuel models 182 TL2, 186 TL6, 189 TL9 (broadleaf litter) gives ELMFIRE's WAF median 0.249
(10-90 %: 0.22-0.26). Cells with lower cover keep their value. All other bands and cells are copied unchanged.
Side effect: these cells fall below CRITICAL_CANOPY_COVER (0.39), so no crown fire there (leafless hardwoods).
"""
import sys
import numpy as np
from osgeo import gdal

gdal.UseExceptions()
src = gdal.Open(sys.argv[1]); cc_new = int(sys.argv[3]) if len(sys.argv) > 3 else 10
out = gdal.GetDriverByName("GTiff").CreateCopy(sys.argv[2], src)
fuel = src.GetRasterBand(4).ReadAsArray(); cc = src.GetRasterBand(5).ReadAsArray()
dec = np.isin(fuel, [182, 186, 189]) & (cc > cc_new)
cc[dec] = cc_new; out.GetRasterBand(5).WriteArray(cc); out.FlushCache()
print("changed canopy cover to %d %% in %d cells" % (cc_new, dec.sum()))
