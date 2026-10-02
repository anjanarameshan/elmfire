#!/usr/bin/env python3
"""
Post-process ELMFIRE outputs for tutorial 01-constant-wind.

Reads the GeoTIFFs and hourly isochrone shapefile written by 01-run.sh and
produces summary statistics, a burned-area growth table, and figures.

Usage:
    python process_outputs.py [RUN_DIR]
RUN_DIR is a folder containing outputs/ (default: runs/01-constant-wind,
created by ./run_tutorial.sh 01-constant-wind). Results go to RUN_DIR/analysis/
"""
import argparse
import csv
import glob
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from osgeo import gdal, ogr

gdal.UseExceptions()
ogr.UseExceptions()

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RUN_DIR = os.path.join(HERE, "runs", "01-constant-wind")
X_IGN, Y_IGN = 0.0, 3000.0  # ignition point from elmfire.data.in (m)
FTMIN_TO_MS = 0.3048 / 60.0  # vs is written in ft/min (SPREAD_RATE_IN_M = .FALSE.)
M2_PER_HA, M2_PER_ACRE = 1.0e4, 4046.8564


def read_raster(outputs, prefix):
    """Return (array with NaN for no-data/unburned, extent [xmin,xmax,ymin,ymax], cellsize)."""
    fn = glob.glob(os.path.join(outputs, f"{prefix}_*.tif"))[0]
    ds = gdal.Open(fn)
    band = ds.GetRasterBand(1)
    a = band.ReadAsArray().astype(float)
    a[a == band.GetNoDataValue()] = np.nan
    gt = ds.GetGeoTransform()
    nx, ny = ds.RasterXSize, ds.RasterYSize
    extent = [gt[0], gt[0] + nx * gt[1], gt[3] + ny * gt[5], gt[3]]
    return a, extent, gt[1]


def read_isochrones(outputs, toa, extent, dx):
    """Return list of (hour, x array, y array) from hourly_isochrones.shp.

    01-run.sh calls gdal_contour without -a, so the shapefile has no contour
    value; the hour is recovered by sampling time of arrival along each line.
    """
    ds = ogr.Open(os.path.join(outputs, "hourly_isochrones.shp"))
    layer = ds.GetLayer()
    ny, nx = toa.shape
    lines = []
    for feat in layer:
        geom = feat.GetGeometryRef()
        parts = [geom.GetGeometryRef(i) for i in range(geom.GetGeometryCount())] or [geom]
        for g in parts:
            pts = np.array(g.GetPoints())
            if not len(pts):
                continue
            ix = np.clip(((pts[:, 0] - extent[0]) / dx).astype(int), 0, nx - 1)
            iy = np.clip(((extent[3] - pts[:, 1]) / dx).astype(int), 0, ny - 1)
            vals = toa[iy, ix]
            if np.all(np.isnan(vals)):
                continue  # 0-level contour around the ignition cell
            hour = int(round(np.nanmedian(vals) / 3600))
            if hour < 1:
                continue
            lines.append((hour, pts[:, 0], pts[:, 1]))
    return sorted(lines, key=lambda l: l[0])


def parse_run_dir(description, extra_args=None):
    """Parse RUN_DIR (plus any extra options); return (outputs, analysis[, args])."""
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("run_dir", nargs="?", default=DEFAULT_RUN_DIR,
                    help="folder containing outputs/ (default: %(default)s)")
    if extra_args:
        extra_args(ap)
    args = ap.parse_args()
    run_dir = args.run_dir
    outputs = os.path.join(run_dir, "outputs")
    if not os.path.isdir(outputs):
        ap.error(f"{outputs} not found - run the tutorial first (./run_tutorial.sh)")
    analysis = os.path.join(run_dir, "analysis")
    os.makedirs(analysis, exist_ok=True)
    return (outputs, analysis, args) if extra_args else (outputs, analysis)


def main():
    OUTPUTS, ANALYSIS = parse_run_dir("Summarise ELMFIRE tutorial 01 outputs")

    toa, extent, dx = read_raster(OUTPUTS, "time_of_arrival")
    vs, _, _ = read_raster(OUTPUTS, "vs")
    flin, _, _ = read_raster(OUTPUTS, "flin")

    toa[toa < 0] = np.nan          # -1 = never burned
    burned = ~np.isnan(toa)
    vs_ms = vs * FTMIN_TO_MS
    vs_ms[~burned] = np.nan
    flin[~burned] = np.nan

    # Cell-centre coordinates
    ny, nx = toa.shape
    xc = extent[0] + (np.arange(nx) + 0.5) * dx
    yc = extent[3] - (np.arange(ny) + 0.5) * dx
    X, Y = np.meshgrid(xc, yc)

    # ---- Summary statistics ----
    cell_area = dx * dx
    area_m2 = burned.sum() * cell_area
    xb, yb = X[burned], Y[burned]
    length = yb.max() - yb.min() + dx   # along wind (N-S)
    width = xb.max() - xb.min() + dx    # across wind (E-W)
    head_dist = Y_IGN - (yb.min() - dx / 2)   # downwind (south) run from ignition
    back_dist = (yb.max() + dx / 2) - Y_IGN   # upwind (north) run
    t_end = np.nanmax(toa)

    summary = {
        "burned_cells": int(burned.sum()),
        "burned_area_ha": area_m2 / M2_PER_HA,
        "burned_area_acres": area_m2 / M2_PER_ACRE,
        "last_arrival_time_h": t_end / 3600,
        "fire_length_m": length,
        "fire_width_m": width,
        "length_to_width_ratio": length / width,
        "head_run_m": head_dist,
        "back_run_m": back_dist,
        "avg_head_spread_m_per_min": head_dist / (t_end / 60),
        "max_spread_rate_m_per_s": np.nanmax(vs_ms),
        "mean_spread_rate_m_per_s": np.nanmean(vs_ms),
        "max_fireline_intensity_kW_per_m": np.nanmax(flin),
        "mean_fireline_intensity_kW_per_m": np.nanmean(flin),
    }
    with open(os.path.join(ANALYSIS, "summary.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["quantity", "value"])
        for k, v in summary.items():
            w.writerow([k, f"{v:.4g}" if isinstance(v, float) else v])

    # ---- Burned area vs time ----
    hours = np.arange(0, np.ceil(t_end / 3600) + 1)
    growth = []
    for h in hours:
        a = np.sum(toa <= h * 3600) * cell_area / M2_PER_HA
        growth.append((h, a))
    with open(os.path.join(ANALYSIS, "area_growth.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["hour", "burned_area_ha", "growth_since_previous_ha"])
        prev = 0.0
        for h, a in growth:
            w.writerow([int(h), f"{a:.1f}", f"{a - prev:.1f}"])
            prev = a

    # ---- Figures ----
    km = [e / 1000 for e in extent]
    iso = read_isochrones(OUTPUTS, toa, extent, dx)

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2), constrained_layout=True)
    panels = [
        (toa / 3600, "Time of arrival (h)", "viridis"),
        (vs_ms, "Spread rate (m/s)", "plasma"),
        (flin, "Fireline intensity (kW/m)", "inferno"),
    ]
    for ax, (data, title, cmap) in zip(axes, panels):
        im = ax.imshow(data, extent=km, origin="upper", cmap=cmap)
        for _, lx, ly in iso:
            ax.plot(lx / 1000, ly / 1000, color="white", lw=0.7, alpha=0.8)
        ax.plot(X_IGN / 1000, Y_IGN / 1000, "r*", ms=12, mec="k", label="Ignition")
        ax.set_title(title)
        ax.set_xlabel("Easting (km)")
        ax.set_ylabel("Northing (km)")
        ax.set_aspect("equal")
        fig.colorbar(im, ax=ax, shrink=0.85)
    axes[0].legend(loc="upper right")
    fig.suptitle("ELMFIRE tutorial 01 — constant 15 mph north wind, GR2 grass")
    fig.savefig(os.path.join(ANALYSIS, "maps.png"), dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 7))
    for h, lx, ly in iso:
        ax.plot(lx / 1000, ly / 1000, lw=1.2, label=f"{h} h")
    ax.plot(X_IGN / 1000, Y_IGN / 1000, "r*", ms=14, mec="k", label="Ignition")
    ax.set_aspect("equal")
    ax.set_xlabel("Easting (km)")
    ax.set_ylabel("Northing (km)")
    ax.set_title("Hourly fire perimeters")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.savefig(os.path.join(ANALYSIS, "perimeters.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.5), constrained_layout=True)
    g = np.array(growth)
    a1.plot(g[:, 0], g[:, 1], "o-")
    a1.set_xlabel("Time since ignition (h)")
    a1.set_ylabel("Burned area (ha)")
    a1.set_title("Burned area growth")
    a1.grid(alpha=0.3)
    a2.hist(flin[burned], bins=40, color="tab:orange", edgecolor="k", lw=0.3)
    a2.set_xlabel("Fireline intensity (kW/m)")
    a2.set_ylabel("Number of cells")
    a2.set_title("Distribution of fireline intensity")
    fig.savefig(os.path.join(ANALYSIS, "growth_and_intensity.png"), dpi=150)
    plt.close(fig)

    print("Summary")
    for k, v in summary.items():
        print(f"  {k:36s} {v:.4g}" if isinstance(v, float) else f"  {k:36s} {v}")
    print("\nBurned area by hour (ha):")
    for h, a in growth:
        print(f"  {int(h):2d} h  {a:8.1f}")
    print(f"\nWrote summary.csv, area_growth.csv, maps.png, perimeters.png, "
          f"growth_and_intensity.png to {ANALYSIS}/")


if __name__ == "__main__":
    main()
