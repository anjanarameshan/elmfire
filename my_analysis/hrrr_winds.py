#!/usr/bin/env python3
"""
HRRR winds for an ELMFIRE run.

Downloads the hourly HRRR analysis (fxx=0) from the NOAA archive on AWS (via Herbie):
10 m wind (u, v) and surface gust. HRRR winds are relative to its Lambert grid, so they
are rotated to true north. Values are interpolated (bilinear, on the HRRR 3 km grid) onto
the run's existing weather grid (the CloudFire 600 m grid in inputs/ws.tif), so the
moisture rasters (m1, m10, m100, lh, lw) can stay as they are.
Wind speed is converted to the 20 ft height ELMFIRE expects with the same factor ELMFIRE
uses for WS_AT_10M (0.87).

Usage:
    python hrrr_winds.py RUN_INPUTS_DIR START_UTC OUT_DIR [--test]
        RUN_INPUTS_DIR: an ELMFIRE run's inputs/ (ws.tif gives the grid and number of hours)
        START_UTC:      time of band 1, e.g. "2016-11-27 18:00"
        OUT_DIR:        writes ws.tif (mph, 20 ft), wd.tif (deg, from), gust.tif (mph, 10 m),
                        and hrrr_vs_cloudfire.csv (values at Chimney Tops and Gatlinburg)
        --test:         only the first hour, printed at the two points
Downloads are cached in my_analysis/hrrr_data/.
"""
import argparse
import csv
import datetime as dt
import os
import sys

import numpy as np
from osgeo import gdal, osr

gdal.UseExceptions()
HERE = os.path.dirname(os.path.abspath(__file__))
SAVE_DIR = os.path.join(HERE, "hrrr_data")
MPS_TO_MPH = 2.23694
TEN_M_TO_20FT = 0.87                      # ELMFIRE's own WS_AT_10M factor (elmfire_io.f90)
# HRRR Lambert conformal grid (CONUS): standard parallel 38.5 N, central meridian 97.5 W
HRRR_PROJ = "+proj=lcc +lat_1=38.5 +lat_2=38.5 +lat_0=38.5 +lon_0=-97.5 +a=6371229 +b=6371229 +units=m +no_defs"
POINTS = {"ChimneyTops": (-83.47833, 35.62889), "Gatlinburg": (-83.5102, 35.7143)}


def find_run(t):
    """HRRR valid at UTC time t: the analysis (fxx=0) from the surface file (wrfsfc), else the
    analysis from the pressure-level file (wrfprs, which holds the same 10 m wind and gust fields;
    in 2016 wrfsfc is missing for whole days, e.g. 24 Nov 10Z - 27 Nov 12Z, while wrfprs is complete),
    else the 1- or 2-hour forecast from an earlier run."""
    from herbie import Herbie
    for back, product in ((0, "sfc"), (0, "prs"), (1, "sfc"), (1, "prs"), (2, "sfc"), (2, "prs")):
        H = Herbie((t - dt.timedelta(hours=back)).strftime("%Y-%m-%d %H:%M"), model="hrrr",
                   product=product, fxx=back, save_dir=SAVE_DIR, verbose=False, priority=["google", "aws"])
        if H.grib is not None:
            H.used_product = product
            return H, back
    raise RuntimeError(f"No HRRR data valid at {t:%Y-%m-%d %H:%M} UTC (analysis or 1-2 h forecast)")


def scan_10m_wind(H):
    """Some 2016 HRRR wrfprs files have a truncated .idx (600 of 684 entries) that omits the
    10 m wind although the GRIB file holds it. Read it directly: fetch the bytes after the last
    indexed message and decode them with ecCodes. Returns (u10, v10, lat, lon, relative_to_grid)."""
    import urllib.request, eccodes
    url = H.grib
    idx = urllib.request.urlopen(url + ".idx", timeout=120).read().decode().strip().split("\n")
    start = int(idx[-1].split(":")[1])
    req = urllib.request.Request(url, headers={"Range": "bytes=%d-%d" % (start, start + 12_500_000)})
    for attempt in range(8):
        try:
            data = urllib.request.urlopen(req, timeout=900).read()
            break
        except Exception:
            if attempt == 7:
                raise
            import time; time.sleep(30)
    found, pos = {}, 0
    while not ("10u" in found and "10v" in found):
        pos = data.find(b"GRIB", pos)
        if pos < 0:
            break
        h = eccodes.codes_new_from_message(data[pos:])
        if h is None:
            break
        name, lev, tl = eccodes.codes_get(h, "shortName"), eccodes.codes_get(h, "level"), eccodes.codes_get(h, "typeOfLevel")
        if tl == "heightAboveGround" and lev == 10 and name in ("10u", "10v"):
            ni, nj = eccodes.codes_get(h, "Ni"), eccodes.codes_get(h, "Nj")
            found[name] = eccodes.codes_get_values(h).reshape(nj, ni)
            if "lat" not in found:
                found["lat"] = eccodes.codes_get_array(h, "latitudes").reshape(nj, ni)
                found["lon"] = eccodes.codes_get_array(h, "longitudes").reshape(nj, ni)
                found["rel"] = eccodes.codes_get(h, "uvRelativeToGrid")
        pos += eccodes.codes_get(h, "totalLength")
        eccodes.codes_release(h)
    if "10u" not in found or "10v" not in found:
        raise RuntimeError("10 m wind not found after the indexed part of " + url)
    lon = found["lon"]
    return found["10u"], found["10v"], found["lat"], np.where(lon > 180, lon - 360, lon), int(found["rel"])


LOCAL_RAW = os.path.join(HERE, "chimney_tops_wrf", "data", "hrrr_raw")   # verified full wrfprs f00 files


def local_hour(t):
    """10 m wind and gust from a full wrfprs analysis already on disk (checksummed download), or None."""
    import eccodes
    f = os.path.join(LOCAL_RAW, "hrrr.%s" % t.strftime("%Y%m%d"), "hrrr.t%02dz.wrfprsf00.grib2" % t.hour)
    if not os.path.exists(f):
        return None
    got = {}
    with open(f, "rb") as fh:
        while True:
            h = eccodes.codes_grib_new_from_file(fh)
            if h is None:
                break
            name, tl, lev = eccodes.codes_get(h, "shortName"), eccodes.codes_get(h, "typeOfLevel"), eccodes.codes_get(h, "level")
            if (name in ("10u", "10v") and tl == "heightAboveGround" and lev == 10) or (name == "gust" and tl == "surface"):
                ni, nj = eccodes.codes_get(h, "Ni"), eccodes.codes_get(h, "Nj")
                got[name] = eccodes.codes_get_values(h).reshape(nj, ni)
                if "lat" not in got:
                    got["lat"] = eccodes.codes_get_array(h, "latitudes").reshape(nj, ni)
                    lo = eccodes.codes_get_array(h, "longitudes").reshape(nj, ni)
                    got["lon"] = np.where(lo > 180, lo - 360, lo)
                    got["rel"] = eccodes.codes_get(h, "uvRelativeToGrid")
            eccodes.codes_release(h)
            if all(k in got for k in ("10u", "10v", "gust")):
                break
    if not all(k in got for k in ("10u", "10v", "gust")):
        return None
    u, v = got["10u"], got["10v"]
    if int(got["rel"]) == 1:
        alpha = np.radians(np.sin(np.radians(38.5)) * (got["lon"] - (-97.5)))
        u, v = u * np.cos(alpha) + v * np.sin(alpha), -u * np.sin(alpha) + v * np.cos(alpha)
    return u, v, got["gust"], got["lat"], got["lon"], "analysis (local wrfprs file)"


def get_hour(t):
    """HRRR valid at UTC time t: earth-relative u10, v10 (m/s), gust (m/s), lat, lon, source."""
    loc = local_hour(t)
    if loc is not None:
        return loc
    H, back = find_run(t)
    out = H.xarray(":(UGRD|VGRD):10 m above|:GUST:surface", remove_grib=False)
    dss = out if isinstance(out, list) else [out]
    if not [d for d in dss if "u10" in d]:
        g = [d for d in dss if "gust" in d][0]
        u, v, lat, lon, rel = scan_10m_wind(H)
        if rel == 1:
            alpha = np.radians(np.sin(np.radians(38.5)) * (lon - (-97.5)))
            u, v = u * np.cos(alpha) + v * np.sin(alpha), -u * np.sin(alpha) + v * np.cos(alpha)
        source = ("analysis" if back == 0 else f"{back} h forecast from {back} h earlier run") + \
            f" (wrf{H.used_product}, 10 m wind read past truncated .idx)"
        return u, v, g.gust.values.astype(float), lat, lon, source
    w = [d for d in dss if "u10" in d][0]
    g = [d for d in dss if "gust" in d][0]
    lat, lon = w.latitude.values, w.longitude.values - 360.0
    u, v = w.u10.values.astype(float), w.v10.values.astype(float)
    if int(w.u10.attrs.get("GRIB_uvRelativeToGrid", 1)) == 1:
        alpha = np.radians(np.sin(np.radians(38.5)) * (lon - (-97.5)))
        u, v = u * np.cos(alpha) + v * np.sin(alpha), -u * np.sin(alpha) + v * np.cos(alpha)
    source = ("analysis" if back == 0 else f"{back} h forecast from {back} h earlier run") + f" (wrf{H.used_product})"
    return u, v, g.gust.values.astype(float), lat, lon, source


def bilinear(field, fi, fj):
    """Bilinear interpolation of a 2-D array at fractional (row, col) indices."""
    i0 = np.clip(np.floor(fi).astype(int), 0, field.shape[0] - 2)
    j0 = np.clip(np.floor(fj).astype(int), 0, field.shape[1] - 2)
    di, dj = fi - i0, fj - j0
    return (field[i0, j0] * (1 - di) * (1 - dj) + field[i0 + 1, j0] * di * (1 - dj)
            + field[i0, j0 + 1] * (1 - di) * dj + field[i0 + 1, j0 + 1] * di * dj)


def main():
    ap = argparse.ArgumentParser(description="HRRR winds for ELMFIRE")
    ap.add_argument("inputs")
    ap.add_argument("start_utc")
    ap.add_argument("out_dir")
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()
    t0 = dt.datetime.strptime(args.start_utc, "%Y-%m-%d %H:%M")

    ref = gdal.Open(os.path.join(args.inputs, "ws.tif"))
    gt, nb = ref.GetGeoTransform(), ref.RasterCount
    ny, nx = ref.RasterYSize, ref.RasterXSize
    utm = osr.SpatialReference(wkt=ref.GetProjection())
    ll = osr.SpatialReference()
    ll.ImportFromEPSG(4326)
    ll.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    lcc = osr.SpatialReference()
    lcc.ImportFromProj4(HRRR_PROJ)
    lcc.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    utm.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    to_lcc = osr.CoordinateTransformation(utm, lcc)
    ll_to_lcc = osr.CoordinateTransformation(ll, lcc)
    ll_to_utm = osr.CoordinateTransformation(ll, utm)

    # Target cell centres (run weather grid) in HRRR projection coordinates
    xs = gt[0] + (np.arange(nx) + 0.5) * gt[1]
    ys = gt[3] + (np.arange(ny) + 0.5) * gt[5]
    X, Y = np.meshgrid(xs, ys)
    pts = np.array(to_lcc.TransformPoints(np.column_stack([X.ravel(), Y.ravel()])))[:, :2]

    hours = 1 if args.test else nb
    ws, wd, gust = [], [], []
    point_rows = []
    x0 = y0 = None
    for h in range(hours):
        t = t0 + dt.timedelta(hours=h)
        for attempt in range(1, 21):          # slow/unstable network: retry, discarding partial subsets
            try:
                u, v, g, lat, lon, source = get_hour(t)
                break
            except Exception as e:
                import glob, time
                for f in glob.glob(os.path.join(SAVE_DIR, "hrrr", t.strftime("%Y%m%d"), "subset_*t%02dz*" % t.hour)):
                    os.remove(f)
                if attempt == 20:
                    raise
                print(f"  {t:%Y-%m-%d %H} UTC: attempt {attempt} failed ({type(e).__name__}), retrying in 60 s", flush=True)
                time.sleep(60)
        if x0 is None:   # HRRR grid origin (first grid point) in projection metres; 3 km spacing
            x0, y0 = ll_to_lcc.TransformPoint(float(lon[0, 0]), float(lat[0, 0]))[:2]
        fj = (pts[:, 0] - x0) / 3000.0
        fi = (pts[:, 1] - y0) / 3000.0
        uu, vv, gg = (bilinear(a, fi, fj).reshape(ny, nx) for a in (u, v, g))
        spd = np.hypot(uu, vv) * MPS_TO_MPH * TEN_M_TO_20FT
        dirn = (np.degrees(np.arctan2(-uu, -vv)) + 360) % 360
        ws.append(spd)
        wd.append(dirn)
        gust.append(gg * MPS_TO_MPH)
        row = [h, t.strftime("%Y-%m-%d %H:%M"), (t - dt.timedelta(hours=5)).strftime("%a %d %H:%M"), source]
        for name, (lo, la) in POINTS.items():
            px, py = ll_to_utm.TransformPoint(lo, la)[:2]
            i, j = int((py - gt[3]) / gt[5]), int((px - gt[0]) / gt[1])
            row += [round(float(spd[i, j]), 1), round(float(dirn[i, j])), round(float(gg[i, j] * MPS_TO_MPH), 1)]
        point_rows.append(row)
        print(f"hour {h:2d} {row[2]} EST | Chimney Tops {row[4]:5.1f} mph from {row[5]:3d} deg, gust {row[6]:5.1f} mph"
              f" | Gatlinburg {row[7]:5.1f} mph from {row[8]:3d} deg, gust {row[9]:5.1f} mph"
              + ("" if source == "analysis" else f"   [{source}]"), flush=True)

    if args.test:
        return
    os.makedirs(args.out_dir, exist_ok=True)
    drv = gdal.GetDriverByName("GTiff")
    for name, stack in (("ws", ws), ("wd", wd), ("gust", gust)):
        d = drv.Create(os.path.join(args.out_dir, f"{name}.tif"), nx, ny, nb, gdal.GDT_Float32, ["COMPRESS=DEFLATE"])
        d.SetGeoTransform(gt)
        d.SetProjection(ref.GetProjection())
        for b, a in enumerate(stack):
            d.GetRasterBand(b + 1).SetNoDataValue(-9999)
            d.GetRasterBand(b + 1).WriteArray(a.astype(np.float32))
        d = None

    cf_ws = gdal.Open(os.path.join(args.inputs, "ws.tif")).ReadAsArray()
    cf_wd = gdal.Open(os.path.join(args.inputs, "wd.tif")).ReadAsArray()
    with open(os.path.join(args.out_dir, "hrrr_vs_cloudfire.csv"), "w", newline="") as f:
        w = csv.writer(f)
        hdr = ["hour", "time_UTC", "time_EST", "hrrr_source"]
        for name in POINTS:
            hdr += [f"{name}_hrrr_ws_mph_20ft", f"{name}_hrrr_wd_deg", f"{name}_hrrr_gust_mph",
                    f"{name}_cloudfire_ws_mph", f"{name}_cloudfire_wd_deg"]
        w.writerow(hdr)
        for h, row in enumerate(point_rows):
            out = row[:4]
            for k, (lo, la) in enumerate(POINTS.values()):
                px, py = ll_to_utm.TransformPoint(lo, la)[:2]
                i, j = int((py - gt[3]) / gt[5]), int((px - gt[0]) / gt[1])
                out += row[4 + 3 * k: 7 + 3 * k] + [round(float(cf_ws[h, i, j]), 1), round(float(cf_wd[h, i, j]))]
            w.writerow(out)
    print(f"wrote ws.tif, wd.tif, gust.tif and hrrr_vs_cloudfire.csv to {args.out_dir}")


if __name__ == "__main__":
    main()
    sys.stdout.flush()
    os._exit(0)   # skip interpreter teardown: ecCodes + GDAL can crash there ("double free"), after the files are written
