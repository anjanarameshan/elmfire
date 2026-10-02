#!/usr/bin/env python3
"""
Correct CloudFire dead fuel moisture (m1, m10) with a weather station.

For every hour, the station's 1-hr moisture (NFDRS equilibrium moisture from its temperature
and relative humidity) is divided by the CloudFire m1 at the station location. That ratio is
applied to the m1 and m10 grids of an ELMFIRE run (whole domain, same factor everywhere);
m100 is left unchanged.

Safeguards:
  - hours without station data: ratio interpolated in time
  - ratio limited to [RATIO_MIN, RATIO_MAX]
  - rain: where CloudFire m1 > WET_LIMIT (rain-wetted fuel, which a T/RH estimate cannot see),
    that cell is left unchanged

Usage:
    python correct_moisture.py RUN_INPUTS_DIR RUN_START_UTC STATION.csv STATION_WX_DIR
        RUN_INPUTS_DIR: folder with m1.tif, m10.tif (one band per hour) - modified in place
        RUN_START_UTC:  time of band 1, e.g. "2016-11-27 18:00"
        STATION_WX_DIR: CloudFire weather downloaded around the station (m1.tif, metadata.out)
Writes RUN_INPUTS_DIR/moisture_correction.csv with the hourly factors.
"""
import csv
import datetime as dt
import os
import sys

import numpy as np
from osgeo import gdal

from compare_station import emc_simard, read_grid_series, read_station

gdal.UseExceptions()
RATIO_MIN, RATIO_MAX = 0.3, 1.2
WET_LIMIT = 30.0   # % - CloudFire m1 above this is treated as rain-wetted and not changed


def main():
    inputs, start, station_csv, station_wx = sys.argv[1:5]
    t0 = dt.datetime.strptime(start, "%Y-%m-%d %H:%M")

    meta, recs = read_station(station_csv)
    lat, lon = float(meta["LATITUDE"]), float(meta["LONGITUDE"])
    st_times, st_grid = read_grid_series(station_wx, lon, lat)
    cf_at_station = dict(zip(st_times, st_grid["m1"]))
    emc = {r["time"]: emc_simard(r["temp_c"], r["rh"]) for r in recs}

    m1_ds = gdal.Open(os.path.join(inputs, "m1.tif"))
    nb = m1_ds.RasterCount
    times = [t0 + dt.timedelta(hours=h) for h in range(nb)]

    # Hourly ratio station / CloudFire at the station; NaN where either is missing or it is raining
    raw = np.full(nb, np.nan)
    for h, t in enumerate(times):
        s, c = emc.get(t, np.nan), cf_at_station.get(t, np.nan)
        if np.isfinite(s) and np.isfinite(c) and c > 0 and c <= WET_LIMIT:
            raw[h] = s / c
    ok = np.isfinite(raw)
    if not ok.any():
        raise SystemExit("No overlapping station data for this run period")
    ratio = np.interp(np.arange(nb), np.flatnonzero(ok), raw[ok])     # fill gaps, hold ends
    ratio = np.clip(ratio, RATIO_MIN, RATIO_MAX)

    for name in ("m1", "m10"):
        fn = os.path.join(inputs, f"{name}.tif")
        src = gdal.Open(fn)
        a = src.ReadAsArray().astype(np.float32)
        nodata = src.GetRasterBand(1).GetNoDataValue()
        valid = a != nodata if nodata is not None else np.ones_like(a, bool)
        dry = valid & (a <= WET_LIMIT)
        a = np.where(dry, a * ratio[:, None, None], a).astype(np.float32)
        tmp = fn + ".tmp.tif"
        out = gdal.GetDriverByName("GTiff").Create(tmp, src.RasterXSize, src.RasterYSize, nb,
                                                  gdal.GDT_Float32, ["COMPRESS=DEFLATE"])
        out.SetGeoTransform(src.GetGeoTransform())
        out.SetProjection(src.GetProjection())
        for b in range(nb):
            band = out.GetRasterBand(b + 1)
            if nodata is not None:
                band.SetNoDataValue(nodata)
            band.WriteArray(a[b])
        out = src = None
        os.replace(tmp, fn)

    with open(os.path.join(inputs, "moisture_correction.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["band", "time_UTC", "time_EST", "station_1hr_pct", "cloudfire_m1_at_station_pct",
                    "ratio_used", "from_station"])
        for h, t in enumerate(times):
            w.writerow([h + 1, t.strftime("%Y-%m-%d %H:%M"), (t - dt.timedelta(hours=5)).strftime("%a %d %H:%M"),
                        round(emc.get(t, np.nan), 1), round(float(cf_at_station.get(t, np.nan)), 1),
                        round(float(ratio[h]), 3), bool(ok[h])])
    print(f"Moisture correction ({meta['STATION']}): {ok.sum()}/{nb} hours from station data, "
          f"factor {ratio.min():.2f}-{ratio.max():.2f} (mean {ratio.mean():.2f}) applied to m1, m10")


if __name__ == "__main__":
    main()
