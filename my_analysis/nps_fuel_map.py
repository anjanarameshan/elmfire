#!/usr/bin/env python3
"""
Build an FBFM40 fuel model raster from the NPS Great Smoky Mountains vegetation maps
(overstory ECOGROUP + understory shrub class/density), on the grid of an ELMFIRE run.

Assignment (assumptions, following the burn-severity ranking of Park & Sim 2023:
yellow pine > chestnut oak > oak-hickory > northern/successional hardwood):
  Yellow pine forests                                  -> TU5 (165)
  Any forest with medium/heavy mountain laurel or
  mixed rhododendron-mountain laurel understory        -> TU5 (165)
  Ericaceous shrubs (heath bald types)                 -> SH5 (145)
  Chestnut oak forests                                 -> TL9 (189)
  Montane oak-hickory, high-elevation red/white oak    -> TL6 (186)
  Montane cove, northern hardwood (+boulderfield),
  successional hardwood, floodplain forests            -> TL2 (182)
  Everything else, and areas outside the park          -> LANDFIRE (unchanged)
LANDFIRE non-burnable cells (codes 91-99) always stay non-burnable.

Usage:
    python nps_fuel_map.py LANDFIRE_FBFM40.tif OUT.tif [--veg-dir nps_vegetation]
Writes OUT.tif (Int16, same grid as the input) and OUT.csv (share of each fuel code
before/after, over the area the NPS map covers).
"""
import argparse
import csv
import os

import numpy as np
from osgeo import gdal

gdal.UseExceptions()

OVERSTORY = {
    "Yellow pine forests": 165,
    "Ericaceous shrubs (heath bald type)": 145,
    "Ericaceous shrubs (non-heath bald type)": 145,
    "Chestnut oak forests": 189,
    "Montane oak-hickory forests": 186,
    "High elevation red oak/white oak forests": 186,
    "Montane cove forests": 182,
    "Northern hardwood/acid hardwood forests": 182,
    "Northern hardwood/boulderfield forests": 182,
    "Successional hardwood forests": 182,
    "Floodplain forests": 182,
}
# Understory shrub classes (DENS_CLASS) that make any burnable forest cell TU5
LAUREL_SHRUB = ["Mountain Laurel, Medium", "Mountain Laurel, Heavy",
                "Mixed Rhodo - Mtn. Laurel, Medium", "Mixed Rhodo - Mtn. Laurel, Heavy"]
TU5 = 165


def rasterize(shp, like, where, value, out):
    """Burn value into 'out' (in-memory copy of like's grid) for features matching 'where'."""
    gdal.Rasterize(out, shp, burnValues=[value], where=where)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("landfire")
    ap.add_argument("out")
    ap.add_argument("--veg-dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "nps_vegetation"))
    args = ap.parse_args()
    over = os.path.join(args.veg_dir, "GRSM_VEGETATION_OVERSTORY_2004.shp")
    under = os.path.join(args.veg_dir, "GRSM_VEGETATION_UNDERSTORY.shp")

    lf_ds = gdal.Open(args.landfire)
    lf = lf_ds.ReadAsArray().astype(np.int16)
    mem = gdal.GetDriverByName("MEM")

    def blank():
        d = mem.Create("", lf_ds.RasterXSize, lf_ds.RasterYSize, 1, gdal.GDT_Int16)
        d.SetGeoTransform(lf_ds.GetGeoTransform())
        d.SetProjection(lf_ds.GetProjection())
        d.GetRasterBand(1).Fill(0)
        return d

    # NAD83 and WGS84 UTM 17N differ by about 1 m here; the shapefiles are burned directly.
    nps = blank()
    for eco, code in OVERSTORY.items():
        rasterize(over, lf_ds, "ECOGROUP = '%s'" % eco.replace("'", "''"), code, nps)
    covered = blank()
    rasterize(over, lf_ds, None, 1, covered)
    laurel = blank()
    rasterize(under, lf_ds, " OR ".join("DENS_CLASS = '%s'" % c for c in LAUREL_SHRUB), 1, laurel)
    nps, covered, laurel = (d.ReadAsArray() for d in (nps, covered, laurel))

    burnable = (lf > 100)                       # LANDFIRE 91-99 = non-burnable, keep as is
    new = lf.copy()
    sel = burnable & (nps > 0)
    new[sel] = nps[sel]
    forest = burnable & (covered > 0) & np.isin(new, [182, 186, 189, 165, 161, 162, 163, 181, 183, 184, 185, 187, 188])
    new[forest & (laurel > 0)] = TU5

    drv = gdal.GetDriverByName("GTiff")
    out = drv.CreateCopy(args.out, lf_ds, options=["COMPRESS=DEFLATE"])
    out.GetRasterBand(1).WriteArray(new)
    out = None

    area = covered > 0
    codes = sorted(set(np.unique(lf[area])) | set(np.unique(new[area])))
    with open(os.path.splitext(args.out)[0] + ".csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["fuel_code", "landfire_pct_of_nps_area", "nps_based_pct_of_nps_area"])
        for c in codes:
            w.writerow([int(c), round(100 * (lf[area] == c).mean(), 1), round(100 * (new[area] == c).mean(), 1)])
    changed = (new != lf)
    print(f"NPS map covers {100 * area.mean():.0f}% of the grid; {changed.sum():,} cells changed "
          f"({100 * changed.sum() / area.sum():.0f}% of the mapped area). Wrote {args.out}")


if __name__ == "__main__":
    main()
