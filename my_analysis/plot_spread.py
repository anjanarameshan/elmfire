#!/usr/bin/env python3
"""
Time-of-arrival map: colour shows the hour after ignition at which each cell burned.
Works for any run (ignition is taken from the earliest-burning cell).

Usage:
    python plot_spread.py [RUN_DIR] [--step HOURS] [--cmap yellow-red]
Writes RUN_DIR/analysis/spread.png
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import BoundaryNorm

from compare_perimeter import time_cmap
from plot_tutorial_figure import add_scalebar
from process_outputs import parse_run_dir, read_raster

PAD = 500.0  # margin around the burned area, m


def add_options(ap):
    ap.add_argument("--step", type=int, default=6,
                    help="hours per colour band (default: %(default)s)")
    ap.add_argument("--title", default=None, help="figure title")
    ap.add_argument("--cmap", default="inferno_r",
                    help="colours: inferno_r (default) or yellow-red, or any matplotlib name")


def main():
    OUTPUTS, ANALYSIS, args = parse_run_dir("Map of fire time of arrival", add_options)

    toa, extent, dx = read_raster(OUTPUTS, "time_of_arrival")
    toa[toa < 0] = np.nan
    toa_h = toa / 3600.0
    burned = ~np.isnan(toa_h)

    rows, cols = np.where(burned)
    xmin = extent[0] + cols.min() * dx - PAD
    xmax = extent[0] + (cols.max() + 1) * dx + PAD
    ymin = extent[3] - (rows.max() + 1) * dx - PAD
    ymax = extent[3] - rows.min() * dx + PAD
    iy, ix = np.unravel_index(np.nanargmin(toa_h), toa_h.shape)
    x_ign = extent[0] + (ix + 0.5) * dx
    y_ign = extent[3] - (iy + 0.5) * dx

    t_end = np.nanmax(toa_h)
    bounds = np.arange(0, np.ceil(t_end / args.step) * args.step + args.step, args.step)
    cmap = time_cmap(args.cmap, len(bounds) - 1)
    norm = BoundaryNorm(bounds, cmap.N)

    w, h = xmax - xmin, ymax - ymin
    fig, ax = plt.subplots(figsize=(10, 10 * h / w + 1.2), constrained_layout=True)
    im = ax.imshow(toa_h, extent=extent, origin="upper", cmap=cmap, norm=norm,
                   interpolation="nearest")
    ax.plot(x_ign, y_ign, marker="*", color="#1f78ff", ms=18, mec="white", mew=1.2,
            label="Ignition", zorder=6)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])

    bar = 10 ** np.floor(np.log10(w / 3))
    bar = bar * 2 if w / bar > 6 else bar
    add_scalebar(ax, xmax - bar - 0.04 * w, ymin + 0.03 * h, bar, 2, 0.01 * h)
    ax.annotate("N", xy=(xmin + 0.05 * w, ymax - 0.05 * h),
                xytext=(xmin + 0.05 * w, ymax - 0.14 * h), ha="center", fontsize=14,
                fontweight="bold", arrowprops=dict(arrowstyle="-|>", color="black", lw=2))
    ax.legend(loc="upper right", frameon=True)

    cb = fig.colorbar(im, ax=ax, orientation="horizontal", shrink=0.7, pad=0.02,
                      ticks=bounds)
    cb.set_label("Time of arrival (hours after ignition)")

    area_ac = burned.sum() * dx * dx / 4046.8564
    ax.set_title(args.title or f"Simulated fire spread: {area_ac:,.0f} acres after {t_end:.0f} h")

    out = os.path.join(ANALYSIS, "spread.png")
    fig.savefig(out, dpi=180, facecolor="white")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
