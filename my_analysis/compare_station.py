#!/usr/bin/env python3
"""
Compare a weather station (Synoptic / MesoWest CSV export) with the gridded CloudFire weather
used by ELMFIRE, at the station location.

Station 1-hr fuel moisture is estimated from air temperature and relative humidity with the
NFDRS equilibrium moisture content equations (Simard 1968); the station itself does not
measure 1-hr moisture.

Usage:
    python compare_station.py STATION.csv WEATHER_DIR [--out OUT_DIR]
WEATHER_DIR holds ws.tif, wd.tif, m1.tif (one band per hour) and metadata.out (WX_BEGIN).
Writes OUT_DIR/<station>_vs_cloudfire.csv and .png (default OUT_DIR = folder of STATION.csv).
"""
import argparse
import csv
import datetime as dt
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from osgeo import gdal, osr

gdal.UseExceptions()
MS_TO_MPH = 2.23694


def read_station(fn):
    """Return station metadata dict and list of hourly records (time rounded to the hour, UTC)."""
    meta, rows, header = {}, [], None
    with open(fn) as f:
        for line in f:
            if line.startswith("#"):
                if ":" in line:
                    k, v = line[1:].split(":", 1)
                    meta[k.strip()] = v.strip()
                continue
            parts = line.rstrip("\n").split(",")
            if header is None:
                header = parts
                continue
            if not parts[0]:          # units row
                units = dict(zip(header, parts))
                continue
            rows.append(dict(zip(header, parts)))
    assert units.get("wind_speed_set_1") == "m/s" and units.get("air_temp_set_1") == "Celsius", \
        "expected metric units (m/s, Celsius)"

    def num(r, k):
        try:
            return float(r.get(k, ""))
        except ValueError:
            return np.nan

    recs = []
    for r in rows:
        t = dt.datetime.strptime(r["Date_Time"], "%Y-%m-%dT%H:%M:%SZ")
        t = (t + dt.timedelta(minutes=30)).replace(minute=0, second=0)  # nearest hour
        recs.append({
            "time": t,
            "temp_c": num(r, "air_temp_set_1"),
            "rh": num(r, "relative_humidity_set_1"),
            "ws_mph": num(r, "wind_speed_set_1") * MS_TO_MPH,
            "gust_mph": num(r, "wind_gust_set_1") * MS_TO_MPH,
            "wd": num(r, "wind_direction_set_1"),
        })
    return meta, recs


def emc_simard(temp_c, rh):
    """Equilibrium moisture content (%) from temperature and RH (NFDRS, Simard 1968)."""
    tf = temp_c * 9 / 5 + 32
    if np.isnan(tf) or np.isnan(rh):
        return np.nan
    if rh < 10:
        return 0.03229 + 0.281073 * rh - 0.000578 * rh * tf
    if rh < 50:
        return 2.22749 + 0.160107 * rh - 0.01478 * tf
    return 21.0606 + 0.005565 * rh ** 2 - 0.00035 * rh * tf - 0.483199 * rh


def read_grid_series(wx_dir, lon, lat):
    """CloudFire hourly ws/wd/m1 at the grid cell containing (lon, lat)."""
    begin = None
    for line in open(os.path.join(wx_dir, "metadata.out")):
        if line.startswith("WX_BEGIN"):
            begin = dt.datetime.strptime(line.split("=", 1)[1].strip(), "%Y-%m-%d %H:%M")
    ds = gdal.Open(os.path.join(wx_dir, "ws.tif"))
    srs = osr.SpatialReference(wkt=ds.GetProjection())
    ll = osr.SpatialReference()
    ll.ImportFromEPSG(4326)
    ll.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    x, y, _ = osr.CoordinateTransformation(ll, srs).TransformPoint(lon, lat)
    gt = ds.GetGeoTransform()
    j, i = int((x - gt[0]) / gt[1]), int((y - gt[3]) / gt[5])
    if not (0 <= i < ds.RasterYSize and 0 <= j < ds.RasterXSize):
        raise SystemExit("Station is outside the weather grid")
    series = {}
    for n in ("ws", "wd", "m1"):
        a = gdal.Open(os.path.join(wx_dir, f"{n}.tif")).ReadAsArray()
        series[n] = a[:, i, j].astype(float)
    times = [begin + dt.timedelta(hours=h) for h in range(len(series["ws"]))]
    return times, series


def main():
    ap = argparse.ArgumentParser(description="Compare station observations with CloudFire weather")
    ap.add_argument("station_csv")
    ap.add_argument("wx_dir")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    out_dir = args.out or os.path.dirname(os.path.abspath(args.station_csv))

    meta, recs = read_station(args.station_csv)
    sid = meta.get("STATION", "station")
    lat, lon = float(meta["LATITUDE"]), float(meta["LONGITUDE"])
    times, grid = read_grid_series(args.wx_dir, lon, lat)
    gidx = {t: h for h, t in enumerate(times)}

    matched = []
    for r in recs:
        h = gidx.get(r["time"])
        if h is None:
            continue
        matched.append({**r, "emc": emc_simard(r["temp_c"], r["rh"]),
                        "cf_ws": grid["ws"][h], "cf_wd": grid["wd"][h], "cf_m1": grid["m1"][h]})

    fn = os.path.join(out_dir, f"{sid}_vs_cloudfire.csv")
    with open(fn, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time_UTC", "time_EST", "station_temp_C", "station_RH_pct", "station_ws_mph",
                    "station_gust_mph", "station_wd_deg", "station_1hr_emc_pct",
                    "cloudfire_ws_mph", "cloudfire_wd_deg", "cloudfire_m1_pct"])
        for m in matched:
            w.writerow([m["time"].strftime("%Y-%m-%d %H:%M"),
                        (m["time"] - dt.timedelta(hours=5)).strftime("%a %d %H:%M"),
                        m["temp_c"], m["rh"], round(m["ws_mph"], 1), round(m["gust_mph"], 1), m["wd"],
                        round(m["emc"], 1), round(m["cf_ws"], 1), round(m["cf_wd"]), round(m["cf_m1"], 1)])

    t = [m["time"] - dt.timedelta(hours=5) for m in matched]   # plot in EST
    g = lambda k: np.array([m[k] for m in matched])
    fig, axs = plt.subplots(4, 1, figsize=(12, 12), sharex=True, constrained_layout=True)
    axs[0].plot(t, g("ws_mph"), color="k", label=f"{sid} (20 ft)")
    axs[0].plot(t, g("cf_ws"), color="tab:red", label="CloudFire (20 ft)")
    axs[0].set_ylabel("Wind speed (mph)")
    axs[1].scatter(t, g("wd"), s=8, color="k", label=sid)
    axs[1].scatter(t, g("cf_wd"), s=8, color="tab:red", label="CloudFire")
    axs[1].set_ylabel("Wind from (deg)")
    axs[1].set_yticks([0, 90, 180, 270, 360])
    axs[2].plot(t, g("emc"), color="k", label=f"{sid} (from T, RH)")
    axs[2].plot(t, g("cf_m1"), color="tab:red", label="CloudFire m1")
    axs[2].set_ylabel("1-hr fuel moisture (%)")
    axs[3].plot(t, g("rh"), color="tab:blue", label="RH (%)")
    ax3b = axs[3].twinx()
    ax3b.plot(t, g("temp_c"), color="tab:orange", label="Temperature (C)")
    axs[3].set_ylabel("RH (%)", color="tab:blue")
    ax3b.set_ylabel("Temperature (C)", color="tab:orange")
    event = [dt.datetime(2016, 11, 28, 12), dt.datetime(2016, 11, 29, 0)]
    for ax in axs:
        ax.axvspan(*event, color="gold", alpha=0.25, lw=0)
        ax.grid(alpha=0.3)
        ax.legend(loc="upper left", fontsize=8)
    axs[3].xaxis.set_major_formatter(mdates.DateFormatter("%a %d\n%H:%M"))
    axs[3].set_xlabel("Local time (EST)   -   shaded: Nov 28 afternoon/evening wind event")
    fig.suptitle(f"{meta.get('STATION NAME', sid)} ({sid}, {meta.get('ELEVATION [ft]', '?')} ft) "
                 f"vs CloudFire weather at the same location")
    png = fn.replace(".csv", ".png")
    fig.savefig(png, dpi=140)

    ev = [m for m in matched if event[0] <= m["time"] - dt.timedelta(hours=5) < event[1]]
    def stats(rows, label):
        a = lambda k: np.nanmean([r[k] for r in rows])
        mx = lambda k: np.nanmax([r[k] for r in rows])
        print(f"{label:28s} station ws {a('ws_mph'):5.1f} (max {mx('ws_mph'):4.1f}, gust max {mx('gust_mph'):4.1f}) | "
              f"CloudFire ws {a('cf_ws'):5.1f} (max {mx('cf_ws'):4.1f}) | 1-hr: station {a('emc'):5.1f}  CloudFire {a('cf_m1'):5.1f}")
    stats(matched, "Whole period (mean)")
    stats(ev, "Nov 28 12:00-24:00 EST")
    print("wrote", fn)
    print("wrote", png)


if __name__ == "__main__":
    main()
