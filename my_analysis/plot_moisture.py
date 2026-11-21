#!/usr/bin/env python3
"""
Show the CloudFire dead fuel moisture used by an ELMFIRE run:
  top:    hourly 1-hr, 10-hr and 100-hr moisture at Chimney Tops (ignition) and Gatlinburg
  bottom: maps of 1-hr moisture at selected hours, with the observed perimeter

Usage:
    python plot_moisture.py RUN_DIR START_UTC [--perimeter SHP] [--hours 0 12 24 30]
        RUN_DIR:   run folder containing inputs/m1.tif, m10.tif, m100.tif
        START_UTC: time of band 1, e.g. "2016-11-27 18:00"
Writes RUN_DIR/analysis/moisture.png
"""
import argparse
import datetime as dt
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from osgeo import gdal, osr

from compare_perimeter import perimeter_lines

gdal.UseExceptions()
POINTS = {"Chimney Tops (ignition)": (-83.47833, 35.62889), "Gatlinburg": (-83.5102, 35.7143)}
EST = dt.timedelta(hours=-5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("start_utc")
    ap.add_argument("--perimeter", default=None)
    ap.add_argument("--hours", type=int, nargs="+", default=[0, 12, 24, 30],
                    help="hours after the start to map (default: 0 12 24 30)")
    args = ap.parse_args()
    inp = os.path.join(args.run_dir, "inputs")
    t0 = dt.datetime.strptime(args.start_utc, "%Y-%m-%d %H:%M")

    data, gt, srs = {}, None, None
    for n in ("m1", "m10", "m100"):
        ds = gdal.Open(os.path.join(inp, f"{n}.tif"))
        data[n] = ds.ReadAsArray().astype(float)
        nd = ds.GetRasterBand(1).GetNoDataValue()
        if nd is not None:
            data[n][data[n] == nd] = np.nan
        gt, srs = ds.GetGeoTransform(), osr.SpatialReference(wkt=ds.GetProjection())
    nb = data["m1"].shape[0]
    times = [t0 + dt.timedelta(hours=h) + EST for h in range(nb)]
    ll = osr.SpatialReference()
    ll.ImportFromEPSG(4326)
    ll.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    tr = osr.CoordinateTransformation(ll, srs)
    pts = {}
    for name, (lon, lat) in POINTS.items():
        x, y, _ = tr.TransformPoint(lon, lat)
        pts[name] = (x, y, int((y - gt[3]) / gt[5]), int((x - gt[0]) / gt[1]))

    hours = [h for h in args.hours if h < nb]
    fig = plt.figure(figsize=(15, 10.5), constrained_layout=True)
    gs = fig.add_gridspec(2, max(len(hours), 1), height_ratios=[1, 1.35])

    ax = fig.add_subplot(gs[0, :])
    styles = {"m1": "-", "m10": "--", "m100": ":"}
    colors = {"Chimney Tops (ignition)": "tab:red", "Gatlinburg": "tab:blue"}
    for name, (_, _, i, j) in pts.items():
        for n, ls in styles.items():
            ax.plot(times, data[n][:, i, j], ls, color=colors[name], lw=1.8,
                    label=f"{name} - {n[1:]}-hr")
    for h in hours:
        ax.axvline(times[h], color="0.5", lw=0.8)
    ax.set_ylabel("Dead fuel moisture (%)")
    ax.set_ylim(0, min(60, np.nanmax([data[n][:, i, j].max() for n in data for (_, _, i, j) in pts.values()]) + 3))
    ax.grid(alpha=0.3)
    ax.legend(ncol=2, fontsize=8.5, loc="upper left")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%a %d\n%H:%M"))
    ax.set_title("CloudFire fuel moisture (model estimate: NOAA RTMA + NFDRS4) - grey lines: hours mapped below")

    m1 = data["m1"]
    ext = [gt[0], gt[0] + m1.shape[2] * gt[1], gt[3] + m1.shape[1] * gt[5], gt[3]]
    xs = [p[0] for p in pts.values()]
    ys = [p[1] for p in pts.values()]
    xmin, xmax = min(xs) - 6000, max(xs) + 6000
    ymin, ymax = min(ys) - 4000, max(ys) + 4000
    for k, h in enumerate(hours):
        a = fig.add_subplot(gs[1, k])
        im = a.imshow(m1[h], extent=ext, origin="upper", cmap="YlGnBu", vmin=0, vmax=30,
                      interpolation="nearest")
        if args.perimeter:
            for lx, ly in perimeter_lines(args.perimeter):
                a.plot(lx, ly, color="black", lw=1.2)
        for name, (x, y, i, j) in pts.items():
            a.plot(x, y, "*" if "ignition" in name else "o", color=colors[name], ms=11, mec="white")
            a.annotate(f"{m1[h, i, j]:.1f}%", (x, y), xytext=(6, 4), textcoords="offset points",
                       fontsize=9, fontweight="bold", color=colors[name])
        a.set_xlim(xmin, xmax)
        a.set_ylim(ymin, ymax)
        a.set_aspect("equal")
        a.set_xticks([])
        a.set_yticks([])
        a.set_title(f"1-hr moisture, {times[h]:%a %d %H:%M} EST")
    cb = fig.colorbar(im, ax=fig.axes[1:], orientation="horizontal", shrink=0.5, pad=0.02)
    cb.set_label("1-hr dead fuel moisture (%) - 600 m cells; leaf litter stops spreading near 25 %")

    out = os.path.join(args.run_dir, "analysis")
    os.makedirs(out, exist_ok=True)
    fn = os.path.join(out, "moisture.png")
    fig.savefig(fn, dpi=130, facecolor="white")
    print("wrote", fn)


if __name__ == "__main__":
    main()
