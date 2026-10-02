#!/usr/bin/env python3
"""
Wind speed and wind gust at weather stations vs the CloudFire wind at the ignition point.

Two panels in one figure:
  1. wind speed: each station + CloudFire at the ignition point
  2. wind gust:  each station (CloudFire provides no gust)
Legend entries give each station's distance and direction from the ignition point.

Usage:
    python compare_wind_stations.py WEATHER_DIR STATION1.csv [STATION2.csv ...]
        [--ign-lat 35.62889 --ign-lon -83.47833 --out FIGURE.png]
WEATHER_DIR holds CloudFire ws.tif (one band per hour) and metadata.out (WX_BEGIN).
Station files are Synoptic / MesoWest CSV exports (metric units).
"""
import argparse
import datetime as dt
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from osgeo import gdal, osr

gdal.UseExceptions()
MS_TO_MPH = 2.23694
UTC_TO_EST = dt.timedelta(hours=-5)


def read_synoptic(fn):
    """Station metadata and observations (times UTC, speeds in mph) from a Synoptic CSV."""
    meta, header, units, obs = {}, None, None, []
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
            elif units is None:
                units = dict(zip(header, parts))
                assert units["wind_speed_set_1"] == "m/s", f"{fn}: expected wind in m/s"
            else:
                r = dict(zip(header, parts))
                num = lambda k: float(r[k]) * MS_TO_MPH if r.get(k, "") != "" else np.nan
                obs.append((dt.datetime.strptime(r["Date_Time"], "%Y-%m-%dT%H:%M:%SZ"),
                            num("wind_speed_set_1"), num("wind_gust_set_1")))
    return meta, obs


def distance_bearing(lat1, lon1, lat2, lon2):
    """Great-circle distance (km) and compass direction from point 1 to point 2."""
    p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    d = 2 * 6371.0 * math.asin(math.sqrt(a))
    b = (math.degrees(math.atan2(math.sin(dl) * math.cos(p2),
                                 math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl))) + 360) % 360
    compass = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return d, compass[int((b + 11.25) // 22.5) % 16]


def cloudfire_series(wx_dir, lat, lon):
    begin = None
    for line in open(os.path.join(wx_dir, "metadata.out")):
        if line.startswith("WX_BEGIN"):
            begin = dt.datetime.strptime(line.split("=", 1)[1].strip(), "%Y-%m-%d %H:%M")
    ds = gdal.Open(os.path.join(wx_dir, "ws.tif"))
    ll = osr.SpatialReference()
    ll.ImportFromEPSG(4326)
    ll.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    x, y, _ = osr.CoordinateTransformation(ll, osr.SpatialReference(wkt=ds.GetProjection())).TransformPoint(lon, lat)
    gt = ds.GetGeoTransform()
    j, i = int((x - gt[0]) / gt[1]), int((y - gt[3]) / gt[5])
    ws = ds.ReadAsArray()[:, i, j].astype(float)
    return [begin + dt.timedelta(hours=h) for h in range(len(ws))], ws


def main():
    ap = argparse.ArgumentParser(description="Compare station wind speed/gust with CloudFire")
    ap.add_argument("wx_dir")
    ap.add_argument("stations", nargs="+")
    ap.add_argument("--ign-lat", type=float, default=35.62889)
    ap.add_argument("--ign-lon", type=float, default=-83.47833)
    ap.add_argument("--ign-name", default="Chimney Tops (ignition)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    colors = ["black", "tab:blue", "tab:green", "tab:purple"]
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 8.5), sharex=True, constrained_layout=True)
    tmin, tmax = None, None
    for fn, col in zip(args.stations, colors):
        meta, obs = read_synoptic(fn)
        lat, lon = float(meta["LATITUDE"]), float(meta["LONGITUDE"])
        d, comp = distance_bearing(args.ign_lat, args.ign_lon, lat, lon)
        name = (f"{meta['STATION']} - {meta['STATION NAME'].title()}\n"
                f"   {d:.0f} km {comp} of ignition, elev. {float(meta['ELEVATION [ft]']) * 0.3048:.0f} m")
        t = [o[0] + UTC_TO_EST for o in obs]
        ws = np.array([o[1] for o in obs])
        gust = np.array([o[2] for o in obs])
        ax1.plot(t, ws, color=col, lw=1.2, label=name)
        ax2.plot(t, gust, "o", color=col, ms=3.5, label=name)
        tmin = min(t[0], tmin or t[0])
        tmax = max(t[-1], tmax or t[-1])
        print(f"{meta['STATION']:6s} {d:5.1f} km {comp:3s}  max wind {np.nanmax(ws):5.1f} mph, "
              f"max gust {np.nanmax(gust):5.1f} mph")

    tc, wc = cloudfire_series(args.wx_dir, args.ign_lat, args.ign_lon)
    tc = [x + UTC_TO_EST for x in tc]
    ax1.plot(tc, wc, color="tab:red", lw=1.8, label=f"CloudFire (model input) at {args.ign_name}\n   0 km, 600 m grid cell")
    print(f"CloudFire at ignition: max wind {wc.max():5.1f} mph")

    event = (dt.datetime(2016, 11, 28, 12), dt.datetime(2016, 11, 29, 0))
    for ax in (ax1, ax2):
        ax.axvspan(*event, color="gold", alpha=0.25, lw=0, label="_nolegend_")
        ax.grid(alpha=0.3)
        ax.set_xlim(tmin, tmax)
        ax.legend(loc="upper left", fontsize=8.5, framealpha=0.95)
    ax1.set_ylabel("Wind speed (mph)")
    ax1.set_title("Wind speed (sustained / hourly average at 20 ft)")
    ax2.set_ylabel("Wind gust (mph)")
    ax2.set_title("Wind gust (stations only - CloudFire weather has no gust)")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%a %d\n%H:%M"))
    ax2.set_xlabel("Local time (EST)   -   shaded: Nov 28 afternoon/evening wind event")
    fig.suptitle("Chimney Tops 2 Fire, Nov 2016 - observed vs CloudFire wind", fontsize=13)

    out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.stations[0])), "wind_stations_vs_cloudfire.png")
    fig.savefig(out, dpi=140, facecolor="white")
    print("wrote", out)


if __name__ == "__main__":
    main()
