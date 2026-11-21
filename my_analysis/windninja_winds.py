#!/usr/bin/env python3
"""
Replace the CloudFire wind of an ELMFIRE run with WindNinja winds over the terrain.

For each hourly band of the CloudFire wind (ws.tif / wd.tif):
  1. take the average CloudFire wind over the fire domain (mean speed, vector-mean direction)
  2. run WindNinja (domain-average initialization) on the run's DEM with that wind
  3. collect the 20-ft speed and direction grids
The hourly WindNinja grids are stacked into ws.tif / wd.tif; the other weather rasters
(m1, m10, m100, lh, lw) are resampled to the same grid, since ELMFIRE expects one weather grid.

WindNinja for Windows is called from WSL (default path below). Identical hourly winds are only
computed once (cache in the Windows work folder).

Usage:
    python windninja_winds.py RUN_INPUTS_DIR OUT_DIR [--res 100] [--threads 16] [--parallel 2]
        RUN_INPUTS_DIR: an ELMFIRE run's inputs/ (landscape.tif, ws.tif, wd.tif, m1.tif, ...)
        OUT_DIR:        where the new weather rasters and windninja_hourly.csv are written
"""
import argparse
import csv
import glob
import hashlib
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from osgeo import gdal

gdal.UseExceptions()
WN_EXE = "/mnt/c/WindNinja/WindNinja-4.0.0/bin/WindNinja_cli.exe"
WORK = "/mnt/c/temp/windninja_chimney"     # WindNinja (a Windows program) works in a Windows folder
OTHER_WX = ("m1", "m10", "m100", "lh", "lw")


def winpath(p):
    return subprocess.check_output(["wslpath", "-w", p], text=True).strip()


def domain_average_wind(ws, wd, gt_wx, dom):
    """Mean speed and vector-mean 'from' direction of each band over the domain extent."""
    xmin, ymin, xmax, ymax = dom
    j0, j1 = int((xmin - gt_wx[0]) / gt_wx[1]), int(np.ceil((xmax - gt_wx[0]) / gt_wx[1]))
    i0, i1 = int((ymax - gt_wx[3]) / gt_wx[5]), int(np.ceil((ymin - gt_wx[3]) / gt_wx[5]))
    s, d = ws[:, i0:i1, j0:j1], np.radians(wd[:, i0:i1, j0:j1])
    u, v = -s * np.sin(d), -s * np.cos(d)          # vector the wind blows toward
    speed = s.mean(axis=(1, 2))
    direction = (np.degrees(np.arctan2(-u.mean(axis=(1, 2)), -v.mean(axis=(1, 2)))) + 360) % 360
    return speed, direction


def run_windninja(dem_win, speed, direction, res, threads):
    """Run (or reuse) one WindNinja simulation; return (vel.asc, ang.asc) paths."""
    key = hashlib.md5(f"{dem_win}|{speed:.1f}|{direction:.0f}|{res}".encode()).hexdigest()[:12]
    out = os.path.join(WORK, "cache", key)
    found = glob.glob(os.path.join(out, "*_vel.asc"))
    if found:
        return found[0], found[0].replace("_vel.asc", "_ang.asc")
    os.makedirs(out, exist_ok=True)
    cmd = [WN_EXE, "--num_threads", str(threads), "--elevation_file", dem_win,
           "--initialization_method", "domainAverageInitialization",
           "--input_speed", f"{max(speed, 0.1):.1f}", "--input_speed_units", "mph",
           "--input_direction", f"{direction:.0f}",
           "--input_wind_height", "20", "--units_input_wind_height", "ft",
           "--output_wind_height", "20", "--units_output_wind_height", "ft",
           "--vegetation", "trees", "--mesh_resolution", str(res), "--units_mesh_resolution", "m",
           "--output_speed_units", "mph", "--write_ascii_output", "true",
           "--ascii_out_resolution", str(res), "--units_ascii_out_resolution", "m",
           "--output_path", winpath(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    found = glob.glob(os.path.join(out, "*_vel.asc"))
    if not found:
        shutil.rmtree(out, ignore_errors=True)
        raise RuntimeError(f"WindNinja failed ({speed:.1f} mph, {direction:.0f} deg):\n{r.stdout[-2000:]}{r.stderr[-2000:]}")
    return found[0], found[0].replace("_vel.asc", "_ang.asc")


def write_stack(fn, bands, gt, wkt):
    nb, ny, nx = len(bands), bands[0].shape[0], bands[0].shape[1]
    ds = gdal.GetDriverByName("GTiff").Create(fn, nx, ny, nb, gdal.GDT_Float32, ["COMPRESS=DEFLATE"])
    ds.SetGeoTransform(gt)
    ds.SetProjection(wkt)
    for b, a in enumerate(bands):
        band = ds.GetRasterBand(b + 1)
        band.SetNoDataValue(-9999)
        band.WriteArray(a.astype(np.float32))
    ds = None


def main():
    ap = argparse.ArgumentParser(description="WindNinja winds for an ELMFIRE run")
    ap.add_argument("inputs")
    ap.add_argument("out_dir")
    ap.add_argument("--res", type=int, default=100, help="WindNinja mesh/output resolution, m")
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--parallel", type=int, default=2, help="WindNinja runs at the same time")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    os.makedirs(WORK, exist_ok=True)

    # DEM (landscape band 1) in the Windows work folder
    land = gdal.Open(os.path.join(args.inputs, "landscape.tif"))
    lg = land.GetGeoTransform()
    dom = (lg[0], lg[3] + land.RasterYSize * lg[5], lg[0] + land.RasterXSize * lg[1], lg[3])
    dem = os.path.join(WORK, "dem.tif")
    gdal.Translate(dem, land, bandList=[1], outputType=gdal.GDT_Float32, noData=-9999)

    wsd, wdd = gdal.Open(os.path.join(args.inputs, "ws.tif")), gdal.Open(os.path.join(args.inputs, "wd.tif"))
    ws, wd = wsd.ReadAsArray().astype(float), wdd.ReadAsArray().astype(float)
    speed, direction = domain_average_wind(ws, wd, wsd.GetGeoTransform(), dom)
    nb = len(speed)
    print(f"{nb} hourly WindNinja runs on a {args.res} m mesh (cache: {WORK}/cache)", flush=True)

    dem_win = winpath(dem)
    with ThreadPoolExecutor(max_workers=args.parallel) as ex:
        res = list(ex.map(lambda h: run_windninja(dem_win, speed[h], direction[h], args.res, args.threads), range(nb)))

    vel = [gdal.Open(v).ReadAsArray().astype(float) for v, _ in res]
    ang = [gdal.Open(a).ReadAsArray().astype(float) for _, a in res]
    ref = gdal.Open(res[0][0])
    gt, wkt = ref.GetGeoTransform(), wsd.GetProjection()
    write_stack(os.path.join(args.out_dir, "ws.tif"), vel, gt, wkt)
    write_stack(os.path.join(args.out_dir, "wd.tif"), ang, gt, wkt)

    # Other weather rasters onto the WindNinja grid (bilinear)
    ny, nx = vel[0].shape
    bounds = (gt[0], gt[3] + ny * gt[5], gt[0] + nx * gt[1], gt[3])
    for n in OTHER_WX:
        src = os.path.join(args.inputs, f"{n}.tif")
        if os.path.exists(src):
            gdal.Warp(os.path.join(args.out_dir, f"{n}.tif"), src, outputBounds=bounds, xRes=gt[1], yRes=-gt[5],
                      resampleAlg="bilinear", dstNodata=-9999, creationOptions=["COMPRESS=DEFLATE"])

    with open(os.path.join(args.out_dir, "windninja_hourly.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["band", "cloudfire_domain_mean_speed_mph", "cloudfire_domain_direction_deg",
                    "windninja_min_mph", "windninja_mean_mph", "windninja_max_mph"])
        for h in range(nb):
            a = vel[h][vel[h] >= 0]
            w.writerow([h + 1, round(speed[h], 1), round(direction[h]), round(a.min(), 1), round(a.mean(), 1), round(a.max(), 1)])
    print(f"wrote ws.tif, wd.tif, {', '.join(OTHER_WX)} and windninja_hourly.csv to {args.out_dir}")


if __name__ == "__main__":
    main()
