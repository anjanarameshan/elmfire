#!/usr/bin/env python3
"""
Landscape figure in the style of Park & Sim (2023, Fig. 1c-e) from ELMFIRE inputs, clipped to
the observed fire perimeter: fuel model (LANDFIRE FBFM40), optional second fuel map (e.g. the
NPS-based one), canopy height and elevation, with the ignition marked.

Usage:
    python plot_landscape_figure.py LANDSCAPE.tif PERIMETER.shp OUT.png [--fuel2 FBFM.tif "Title"]
        [--ign-lon -83.47833 --ign-lat 35.62889]
"""
import argparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from osgeo import gdal, osr

from compare_perimeter import perimeter_lines, rasterise

gdal.UseExceptions()

# Scott & Burgan (2005) fuel models: label, colour
FUELS = {
    91: ("NB1 urban", "#9e9e9e"), 92: ("NB2 snow/ice", "#d9e7f2"), 93: ("NB3 agriculture", "#c8b88a"),
    98: ("NB8 water", "#4a90c2"), 99: ("NB9 bare", "#e0e0e0"),
    101: ("GR1 short grass", "#f6ef9b"), 102: ("GR2 low-load grass", "#efe36a"),
    121: ("GS1 grass-shrub", "#d9c46a"), 122: ("GS2 grass-shrub", "#c9ad4a"),
    141: ("SH1 shrub", "#e0a77a"), 142: ("SH2 shrub", "#d48a5a"), 145: ("SH5 heavy shrub", "#9b4f9e"),
    161: ("TU1 timber-understory", "#c8d98a"), 162: ("TU2 timber-understory", "#a6c36b"),
    165: ("TU5 heavy timber-shrub", "#c0552b"),
    181: ("TL1 conifer litter", "#cfe8c0"), 182: ("TL2 light broadleaf litter", "#9ed39a"),
    183: ("TL3 conifer litter", "#6fae7a"), 186: ("TL6 moderate broadleaf litter", "#3f8f5a"),
    189: ("TL9 heavy broadleaf litter", "#1b5e3a"),
}


def fuel_panel(ax, fuel, inside, extent, title):
    codes = [c for c in sorted(FUELS) if (fuel[inside] == c).any()]
    idx = np.full(fuel.shape, np.nan)
    for k, c in enumerate(codes):
        idx[(fuel == c) & inside] = k
    ax.imshow(idx, extent=extent, origin="upper", interpolation="nearest",
              cmap=ListedColormap([FUELS[c][1] for c in codes]), vmin=-0.5, vmax=len(codes) - 0.5)
    tot = inside.sum()
    shares = sorted(((100 * ((fuel == c) & inside).sum() / tot, c) for c in codes), reverse=True)
    handles = [Patch(color=FUELS[c][1], label=f"{FUELS[c][0]} ({p:.1f}%)") for p, c in shares if p >= 0.3]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.0), fontsize=7.5, framealpha=0.9,
              title="Fuel model (share of burned area)", title_fontsize=8, ncol=1)
    ax.set_title(title, fontsize=10)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("landscape")
    ap.add_argument("perimeter")
    ap.add_argument("out")
    ap.add_argument("--fuel2", nargs=2, metavar=("FBFM_TIF", "TITLE"))
    ap.add_argument("--ign-lon", type=float, default=-83.47833)
    ap.add_argument("--ign-lat", type=float, default=35.62889)
    args = ap.parse_args()

    L = gdal.Open(args.landscape)
    gt = L.GetGeoTransform()
    band = lambda b: L.GetRasterBand(b).ReadAsArray()
    dem, fuel, ch = band(1).astype(float), band(4), band(6).astype(float) / 10.0   # CH stored as 10 x metres
    inside = rasterise(args.perimeter, L)
    ny, nx = inside.shape
    extent = [gt[0], gt[0] + nx * gt[1], gt[3] + ny * gt[5], gt[3]]
    r, c = np.where(inside)
    pad = 400
    xmin, xmax = gt[0] + c.min() * gt[1] - pad, gt[0] + (c.max() + 1) * gt[1] + pad
    ymin, ymax = gt[3] + (r.max() + 1) * gt[5] - pad, gt[3] + r.min() * gt[5] + pad

    ll = osr.SpatialReference()
    ll.ImportFromEPSG(4326)
    ll.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    xi, yi, _ = osr.CoordinateTransformation(ll, osr.SpatialReference(wkt=L.GetProjection())).TransformPoint(args.ign_lon, args.ign_lat)

    panels = ["fuel"] + (["fuel2"] if args.fuel2 else []) + ["ch", "dem"]
    fig, axs = plt.subplots(1, len(panels), figsize=(4.4 * len(panels), 9.0), constrained_layout=True)
    letters = "abcdefg"
    for k, (ax, p) in enumerate(zip(axs, panels)):
        if p == "fuel":
            fuel_panel(ax, fuel, inside, extent, f"({letters[k]}) Fuel model - LANDFIRE 1.4.0")
        elif p == "fuel2":
            f2 = gdal.Open(args.fuel2[0]).ReadAsArray()
            fuel_panel(ax, f2, inside, extent, f"({letters[k]}) Fuel model - {args.fuel2[1]}")
        elif p == "ch":
            im = ax.imshow(np.where(inside, ch, np.nan), extent=extent, origin="upper", cmap="viridis_r",
                           vmin=0, vmax=40, interpolation="nearest")
            cb = fig.colorbar(im, ax=ax, shrink=0.45, location="bottom", pad=0.02)
            cb.set_label("Canopy height (m)")
            ax.set_title(f"({letters[k]}) Canopy height - LANDFIRE\nmean {ch[inside].mean():.1f} m", fontsize=10)
        else:
            im = ax.imshow(np.where(inside, dem, np.nan), extent=extent, origin="upper", cmap="turbo",
                           vmin=400, vmax=1400, interpolation="nearest")
            cb = fig.colorbar(im, ax=ax, shrink=0.45, location="bottom", pad=0.02)
            cb.set_label("Elevation (m)")
            ax.set_title(f"({letters[k]}) Elevation\n{dem[inside].min():.0f}-{dem[inside].max():.0f} m", fontsize=10)
        for lx, ly in perimeter_lines(args.perimeter):
            ax.plot(lx, ly, color="black", lw=0.8)
        ax.plot(xi, yi, marker="*", color="red", ms=15, mec="white", mew=1.2, zorder=5)
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        ax.set_aspect("equal")
        ax.axis("off")
    axs[0].annotate("N", xy=(xmin + 0.12 * (xmax - xmin), ymax - 0.03 * (ymax - ymin)),
                    xytext=(xmin + 0.12 * (xmax - xmin), ymax - 0.09 * (ymax - ymin)), ha="center",
                    fontsize=12, fontweight="bold", arrowprops=dict(arrowstyle="-|>", color="black", lw=2))
    fig.suptitle("Chimney Tops 2 Fire (2016) - ELMFIRE landscape inside the MTBS perimeter   (red star: ignition)",
                 fontsize=12)
    fig.savefig(args.out, dpi=170, facecolor="white", bbox_inches="tight", pad_inches=0.2)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
