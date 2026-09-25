#!/usr/bin/env python3
"""
Map-style figure of tutorial 01 results: fireline intensity with hourly
isochrones, a scale bar and a legend (same layout as the tutorial figure).

Usage:
    python plot_tutorial_figure.py [RUN_DIR]
RUN_DIR is a folder containing outputs/ (default: runs/01-constant-wind).
Writes RUN_DIR/analysis/flin_isochrones.png
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

from process_outputs import parse_run_dir, read_isochrones, read_raster

VMIN, VMAX = 0, 1200        # colour range, kW/m
# QGIS "Spectral" ramp, inverted: blue (low) -> yellow -> red (high)
CMAP = LinearSegmentedColormap.from_list(
    "qgis_spectral_r", ["#2b83ba", "#abdda4", "#ffffbf", "#fdae61", "#d7191c"])
LEGEND_W = 2600.0           # space to the right of the fire for legend/scale bar, m
PAD = 300.0                 # margin around the burned area, m
SCALEBAR_M = 2000           # scale bar length, m
SCALEBAR_DIV = 4            # number of alternating segments


def add_scalebar(ax, x0, y0, length, ndiv, height):
    seg = length / ndiv
    for i in range(ndiv):
        ax.add_patch(plt.Rectangle((x0 + i * seg, y0), seg, height,
                                   facecolor="black" if i % 2 == 0 else "white",
                                   edgecolor="black", lw=0.8, zorder=5))
    for i in range(ndiv + 1):
        label = f"{int(i * seg):,}" + (" m" if i == ndiv else "")
        ax.text(x0 + i * seg, y0 + 1.6 * height, label, ha="center", va="bottom",
                fontsize=9, zorder=5)


def main():
    OUTPUTS, ANALYSIS = parse_run_dir("Map of fireline intensity with hourly isochrones")

    toa, extent, dx = read_raster(OUTPUTS, "time_of_arrival")
    flin, _, _ = read_raster(OUTPUTS, "flin")
    toa[toa < 0] = np.nan
    flin[np.isnan(toa)] = np.nan
    iso = read_isochrones(OUTPUTS, toa, extent, dx)

    # Crop the view to the burned area (+ margin), with room on the right for the legend
    rows, cols = np.where(~np.isnan(flin))
    xmin = extent[0] + cols.min() * dx - PAD
    xmax = extent[0] + (cols.max() + 1) * dx + PAD
    ymin = extent[3] - (rows.max() + 1) * dx - PAD
    ymax = extent[3] - rows.min() * dx + PAD
    xview = (xmin, xmax + LEGEND_W)

    h = ymax - ymin
    w = xview[1] - xview[0]
    fig = plt.figure(figsize=(10 * w / h, 10))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.imshow(flin, extent=extent, origin="upper", cmap=CMAP, vmin=VMIN, vmax=VMAX,
              interpolation="nearest")
    for _, lx, ly in iso:
        ax.plot(lx, ly, color="black", lw=1.4)
    ax.set_xlim(*xview)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")
    ax.axis("off")

    # Legend block (bottom right): isochrone line, colour bar, scale bar
    lx0 = xview[1] - LEGEND_W + 0.1 * LEGEND_W
    ax.plot([lx0, lx0 + 0.12 * LEGEND_W], [ymin + 0.20 * h] * 2, color="black", lw=1.4)
    ax.text(lx0 + 0.16 * LEGEND_W, ymin + 0.20 * h, "Hourly isochrones", va="center",
            fontsize=11)
    ax.text(lx0, ymin + 0.165 * h, "Fireline intensity (kW/m)", va="center", fontsize=11)
    cax = fig.add_axes([(lx0 - xview[0]) / w, 0.105, 0.035 * h / w * 0.9, 0.04])
    sm = plt.cm.ScalarMappable(cmap=CMAP, norm=plt.Normalize(VMIN, VMAX))
    cb = fig.colorbar(sm, cax=cax, ticks=[VMIN, VMAX])
    cb.ax.set_yticklabels([f"{VMIN:,}", f"{VMAX:,}"], fontsize=11)
    cb.ax.tick_params(length=0)
    cb.outline.set_linewidth(0.6)

    bar_x0 = xview[1] - SCALEBAR_M - 0.25 * LEGEND_W
    add_scalebar(ax, bar_x0, ymin + 0.03 * h, SCALEBAR_M, SCALEBAR_DIV, 0.009 * h)

    out = os.path.join(ANALYSIS, "flin_isochrones.png")
    fig.savefig(out, dpi=200, bbox_inches="tight", pad_inches=0.2, facecolor="white")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
