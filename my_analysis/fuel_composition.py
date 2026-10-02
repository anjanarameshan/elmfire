#!/usr/bin/env python3
"""
Which fuel models dominate? Counts the fuel model codes (landscape.tif band 4, LANDFIRE FBFM40)
inside the observed perimeter, within 1 km of the ignition, and in the whole domain,
and draws a fuel map with the perimeter.

Usage:
    python fuel_composition.py RUN_DIR PERIMETER.shp [--ign-lat 35.62889 --ign-lon -83.47833] [--code 182]
Writes RUN_DIR/analysis/fuel_composition.csv and fuel_map.png
(with --code N also fuel_code_N.png: where that one fuel model is)
"""
import argparse
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from osgeo import gdal, osr

from compare_perimeter import perimeter_lines, rasterise

gdal.UseExceptions()

# Scott & Burgan (2005) fuel model groups
GROUPS = [(91, 99, "Non-burnable", "#9e9e9e"), (101, 109, "Grass (GR)", "#e6d36a"),
          (121, 124, "Grass-shrub (GS)", "#c9b458"), (141, 149, "Shrub (SH)", "#b5651d"),
          (161, 165, "Timber-understory (TU)", "#5a8f3e"), (181, 189, "Timber litter (TL)", "#2e6b3c"),
          (201, 204, "Slash-blowdown (SB)", "#7a4fa0")]
DESCRIPTION = {182: "low load broadleaf litter", 186: "moderate load broadleaf litter",
               189: "very high load broadleaf litter", 183: "moderate load conifer litter",
               165: "very high load, dry climate timber-shrub", 162: "moderate load, humid climate timber-shrub",
               91: "urban / developed", 98: "open water", 99: "bare ground", 93: "agricultural",
               121: "low load, dry climate grass-shrub", 101: "short, sparse dry climate grass",
               102: "low load, dry climate grass", 161: "low load dry climate timber-grass-shrub",
               181: "low load compact conifer litter", 184: "small downed logs", 185: "high load conifer litter",
               187: "large downed logs", 188: "long-needle litter"}


def group_of(code):
    for lo, hi, name, col in GROUPS:
        if lo <= code <= hi:
            return name, col
    return "Other", "#000000"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("perimeter")
    ap.add_argument("--ign-lat", type=float, default=35.62889)
    ap.add_argument("--ign-lon", type=float, default=-83.47833)
    ap.add_argument("--code", type=int, action="append", default=[],
                    help="also map where this fuel code is (can be repeated)")
    args = ap.parse_args()

    ds = gdal.Open(os.path.join(args.run_dir, "inputs", "landscape.tif"))
    fuel = ds.GetRasterBand(4).ReadAsArray()
    gt = ds.GetGeoTransform()
    names = {91: "NB1", 92: "NB2", 93: "NB3", 98: "NB8", 99: "NB9"}   # non-burnable (not in ELMFIRE's table)
    fm = os.path.join(args.run_dir, "inputs", "fuel_models.csv")
    if os.path.exists(fm):
        for row in csv.reader(open(fm)):
            if row and row[0].strip().isdigit():
                names[int(row[0])] = row[1].strip()

    obs = rasterise(args.perimeter, ds)
    ll = osr.SpatialReference()
    ll.ImportFromEPSG(4326)
    ll.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    xi, yi, _ = osr.CoordinateTransformation(ll, osr.SpatialReference(wkt=ds.GetProjection())).TransformPoint(args.ign_lon, args.ign_lat)
    ny, nx = fuel.shape
    X = gt[0] + (np.arange(nx) + 0.5) * gt[1]
    Y = gt[3] + (np.arange(ny) + 0.5) * gt[5]
    near = np.hypot(X[None, :] - xi, Y[:, None] - yi) <= 1000
    areas = {"inside_observed_perimeter": obs, "within_1km_of_ignition": near,
             "whole_domain": fuel > -9999}

    codes = sorted(set(np.unique(fuel[obs])) | set(np.unique(fuel[near])))
    out = os.path.join(args.run_dir, "analysis")
    os.makedirs(out, exist_ok=True)
    rows = []
    for c in codes:
        r = {"code": int(c), "name": names.get(int(c), "?"), "description": DESCRIPTION.get(int(c), ""),
             "group": group_of(int(c))[0]}
        for k, m in areas.items():
            r[k + "_pct"] = round(100 * (fuel[m] == c).mean(), 1)
        rows.append(r)
    rows.sort(key=lambda r: -r["inside_observed_perimeter_pct"])
    with open(os.path.join(out, "fuel_composition.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"{'code':>4s} {'name':5s} {'inside MTBS':>11s} {'<1 km ign.':>10s} {'domain':>7s}  description")
    for r in rows:
        if max(r["inside_observed_perimeter_pct"], r["within_1km_of_ignition_pct"]) >= 0.5:
            print(f"{r['code']:4d} {r['name']:5s} {r['inside_observed_perimeter_pct']:10.1f}% "
                  f"{r['within_1km_of_ignition_pct']:9.1f}% {r['whole_domain_pct']:6.1f}%  {r['description']}")

    # Map: fuel groups, observed perimeter, ignition
    grp = np.full(fuel.shape, np.nan)
    for i, (lo, hi, name, col) in enumerate(GROUPS):
        grp[(fuel >= lo) & (fuel <= hi)] = i
    r_, c_ = np.where(obs)
    pad = 1500
    xmin, xmax = X[c_.min()] - pad, X[c_.max()] + pad
    ymin, ymax = Y[r_.max()] - pad, Y[r_.min()] + pad
    fig, ax = plt.subplots(figsize=(8, 8 * (ymax - ymin) / (xmax - xmin)), constrained_layout=True)
    extent = [gt[0], gt[0] + nx * gt[1], gt[3] + ny * gt[5], gt[3]]
    ax.imshow(grp, extent=extent, origin="upper", interpolation="nearest",
              cmap=ListedColormap([g[3] for g in GROUPS]), vmin=-0.5, vmax=len(GROUPS) - 0.5)
    for lx, ly in perimeter_lines(args.perimeter):
        ax.plot(lx, ly, color="#1f5fbf", lw=2)
    ax.plot(xi, yi, "*", color="red", ms=16, mec="white", mew=1.2)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    present = {group_of(int(c))[0] for c in np.unique(fuel[(fuel > 0)])}
    handles = [Patch(color=g[3], label=g[2]) for g in GROUPS if g[2] in present]
    handles += [plt.Line2D([], [], color="#1f5fbf", lw=2, label="Observed perimeter (MTBS)"),
                plt.Line2D([], [], marker="*", color="red", ls="", ms=12, label="Ignition")]
    ax.legend(handles=handles, loc="lower left", fontsize=8.5, framealpha=0.95)
    top = rows[:3]
    ax.set_title("LANDFIRE fuel models (FBFM40)\nInside perimeter: " +
                 ", ".join(f"{r['name']} {r['inside_observed_perimeter_pct']:.0f}%" for r in top))
    fig.savefig(os.path.join(out, "fuel_map.png"), dpi=140, facecolor="white")
    print("wrote", os.path.join(out, "fuel_composition.csv"), "and fuel_map.png")

    # Optional: where is one particular fuel code?
    for code in args.code:
        m = fuel == code
        fig, ax = plt.subplots(figsize=(8, 8 * (ymax - ymin) / (xmax - xmin)), constrained_layout=True)
        ax.imshow(np.where(fuel > 0, 0, np.nan), extent=extent, origin="upper", cmap=ListedColormap(["#e4e6e1"]))
        ax.imshow(np.where(m, 1, np.nan), extent=extent, origin="upper", interpolation="nearest",
                  cmap=ListedColormap([group_of(code)[1]]))
        for lx, ly in perimeter_lines(args.perimeter):
            ax.plot(lx, ly, color="#1f5fbf", lw=2)
        ax.plot(xi, yi, "*", color="red", ms=16, mec="white", mew=1.2)
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        nm = names.get(code, "?")
        ax.set_title(f"Fuel code {code} ({nm}, {DESCRIPTION.get(code, '')})\n"
                     f"{100 * m[obs].mean():.1f}% of the area inside the MTBS perimeter, "
                     f"{100 * m[near].mean():.1f}% within 1 km of the ignition")
        ax.legend(handles=[Patch(color=group_of(code)[1], label=f"{code} {nm}"),
                           Patch(color="#e4e6e1", label="other fuels"),
                           plt.Line2D([], [], color="#1f5fbf", lw=2, label="Observed perimeter (MTBS)"),
                           plt.Line2D([], [], marker="*", color="red", ls="", ms=12, label="Ignition")],
                  loc="lower left", fontsize=8.5, framealpha=0.95)
        fn = os.path.join(out, f"fuel_code_{code}.png")
        fig.savefig(fn, dpi=140, facecolor="white")
        print("wrote", fn)


if __name__ == "__main__":
    main()
