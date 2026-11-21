#!/usr/bin/env python3
"""
Side-by-side maps of several runs against the observed perimeter, on the same extent and
the same time-of-arrival colour scale.

Usage:
    python compare_runs_maps.py OUT.png PERIMETER.shp RUN_DIR:"Label" [RUN_DIR:"Label" ...]
"""
import glob
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import BoundaryNorm
from matplotlib.lines import Line2D
from osgeo import gdal

from compare_perimeter import perimeter_lines, rasterise, time_cmap
from plot_tutorial_figure import add_scalebar

gdal.UseExceptions()


def main():
    out, shp, runs = sys.argv[1], sys.argv[2], [r.split(":", 1) for r in sys.argv[3:]]
    data = []
    # OFFSETS_H="23,0": hours added to each run's arrival times so runs that start at different
    # times are coloured on one common clock (TIME_START = the earliest start)
    offs = [float(x) for x in os.environ.get("OFFSETS_H", "").split(",") if x.strip()] or [0.0] * len(runs)
    for (d, label), off in zip(runs, offs):
        ds = gdal.Open(sorted(glob.glob(d + "/outputs/time_of_arrival_*.tif"))[-1])
        toa = ds.ReadAsArray().astype(float)
        sim = toa >= 0
        obs = rasterise(shp, ds)
        both = (sim & obs).sum()
        score = 2 * both / (sim.sum() + obs.sum())
        # optional: urban cells (fuel model 91, NB1) of the run's own fuel map, inside the MTBS perimeter
        # optional fuel-map barriers from the run's own LANDFIRE fuel (landscape band 4):
        #   SHOW_URBAN=1    urban/developed cells (91) inside the MTBS perimeter only
        #   SHOW_BARRIERS=1 urban/developed incl. roads (91) and open water / rivers (98) everywhere
        urban = water = None
        if os.environ.get("SHOW_URBAN") or os.environ.get("SHOW_BARRIERS"):
            lf = d + "/inputs/landscape.tif"
            if not os.path.exists(lf):                       # e.g. a results_* folder inside the run folder
                lf = os.path.dirname(d.rstrip("/")) + "/inputs/landscape.tif"
            land = gdal.Open(lf)   # band 4 = FBFM40 fuel model
            fuel = land.GetRasterBand(4).ReadAsArray()
            urban = fuel == 91
            if os.environ.get("SHOW_BARRIERS"):
                water = fuel == 98
            else:
                urban &= obs
        data.append((label, np.where(sim, toa / 3600 + off, np.nan), ds.GetGeoTransform(), sim, obs, score, urban, water))

    gt = data[0][2]
    ny, nx = data[0][1].shape
    extent = [gt[0], gt[0] + nx * gt[1], gt[3] + ny * gt[5], gt[3]]
    union = np.any([d[3] | d[4] for d in data], axis=0)
    r, c = np.where(union)
    pad = 800
    xmin, xmax = gt[0] + c.min() * gt[1] - pad, gt[0] + (c.max() + 1) * gt[1] + pad
    ymin, ymax = gt[3] + (r.max() + 1) * gt[5] - pad, gt[3] + r.min() * gt[5] + pad
    w, h = xmax - xmin, ymax - ymin

    step = int(os.environ.get("TIME_STEP_H", 6))
    bounds = np.arange(0, int(os.environ.get("TIME_MAX_H", 36)) + step, step)
    cmap = time_cmap("yellow-red", len(bounds) - 1)
    norm = BoundaryNorm(bounds, cmap.N)
    n = len(data)
    fig, axs = plt.subplots(1, n, figsize=(5.2 * n, 5.2 * h / w + 1.6), constrained_layout=True)
    axs = np.atleast_1d(axs)
    URBAN = "#5c3317"   # dark brown
    WATER = "#0a8fb8"   # teal blue
    for ax, (label, toa_h, _, sim, obs, score, urban, water) in zip(axs, data):
        ax.imshow(np.where(obs, 1, np.nan), extent=extent, origin="upper",
                  cmap=matplotlib.colors.ListedColormap(["#cfe3f5"]), interpolation="nearest")
        if urban is not None:
            ax.imshow(np.where(urban, 1, np.nan), extent=extent, origin="upper",
                      cmap=matplotlib.colors.ListedColormap([URBAN]), interpolation="nearest")
        if water is not None:
            ax.imshow(np.where(water, 1, np.nan), extent=extent, origin="upper",
                      cmap=matplotlib.colors.ListedColormap([WATER]), interpolation="nearest")
        im = ax.imshow(toa_h, extent=extent, origin="upper", cmap=cmap, norm=norm, interpolation="nearest")
        for lx, ly in perimeter_lines(shp):
            ax.plot(lx, ly, color="#1f5fbf", lw=1.6)
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        acres = sim.sum() * gt[1] ** 2 / 4046.86
        ax.set_title(f"{label}\n{acres:,.0f} ac  |  Sorensen {score:.3f}", fontsize=11)
    bar = 5000 if w > 15000 else 2000
    add_scalebar(axs[-1], xmax - bar - 0.05 * w, ymin + 0.03 * h, bar, 2, 0.008 * h)
    axs[0].annotate("N", xy=(xmin + 0.07 * w, ymax - 0.04 * h), xytext=(xmin + 0.07 * w, ymax - 0.10 * h),
                    ha="center", fontsize=13, fontweight="bold",
                    arrowprops=dict(arrowstyle="-|>", color="black", lw=2))
    axs[0].legend(handles=[Line2D([], [], color="#1f5fbf", lw=1.6, label="Observed perimeter (MTBS, 15,002 ac)"),
                           plt.Rectangle((0, 0), 1, 1, color="#cfe3f5", label="Observed burned area")]
                  + ([plt.Rectangle((0, 0), 1, 1, color=URBAN, label=("Urban / roads (LANDFIRE fuel 91)" if data[0][7] is not None
                                                                     else "Urban cells (fuel 91) inside perimeter"))]
                     if data[0][6] is not None else [])
                  + ([plt.Rectangle((0, 0), 1, 1, color=WATER, label="Water / rivers (LANDFIRE fuel 98)")]
                     if data[0][7] is not None else []),
                  loc="lower left", fontsize=8.5, framealpha=0.95)
    cb = fig.colorbar(im, ax=list(axs), orientation="horizontal", shrink=0.6, pad=0.02, ticks=bounds)
    cb.set_label("Simulated time of arrival (hours after " + os.environ.get("TIME_START", "Sun 27 Nov 13:00 EST") + ")")
    fig.savefig(out, dpi=150, facecolor="white")
    print("wrote", out)


if __name__ == "__main__":
    main()
