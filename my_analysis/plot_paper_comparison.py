#!/usr/bin/env python3
"""
Compare Park & Sim (2023) Fig. 1c with our data on the same study area (MTBS perimeter
inside the national park, i.e. where the NPS vegetation map exists):
  (a) the paper's figure (cropped image), (b) the NPS vegetation in the paper's six classes,
  (c) the LANDFIRE FBFM40 fuel models (via CloudFire) used by ELMFIRE.

Usage:
    python plot_paper_comparison.py LANDSCAPE.tif PERIMETER.shp OVERSTORY.shp PAPER_FIG.png OUT.png
"""
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from osgeo import gdal

from compare_perimeter import rasterise
from plot_fuel_vs_vegetation import CLASSES, NON_VEG
from plot_landscape_figure import FUELS

gdal.UseExceptions()


def main():
    land, per, over, paper_png, out = sys.argv[1:6]
    L = gdal.Open(land)
    gt = L.GetGeoTransform()
    fuel = L.GetRasterBand(4).ReadAsArray()
    inside = rasterise(per, L)
    ny, nx = inside.shape

    ds = gdal.GetDriverByName("MEM").Create("", nx, ny, 1, gdal.GDT_Byte)
    ds.SetGeoTransform(gt)
    ds.SetProjection(L.GetProjection())
    gdal.Rasterize(ds, over, burnValues=[6])
    gdal.Rasterize(ds, over, burnValues=[9], where=" OR ".join("ECOGROUP = '%s'" % n for n in NON_VEG))
    for k, (_, _, names, _, _) in enumerate(CLASSES[:-1]):
        gdal.Rasterize(ds, over, burnValues=[k + 1], where=" OR ".join("ECOGROUP = '%s'" % n for n in names))
    veg = ds.ReadAsArray()
    study = inside & (veg > 0)                      # MTBS perimeter inside the park = paper's study area
    vegd = study & (veg <= 6)

    r, c = np.where(study)
    r0, r1, c0, c1 = r.min() - 8, r.max() + 9, c.min() - 8, c.max() + 9
    ext = [gt[0] + c0 * gt[1], gt[0] + c1 * gt[1], gt[3] + r1 * gt[5], gt[3] + r0 * gt[5]]
    crop = lambda a: a[r0:r1, c0:c1]
    ha = study.sum() * gt[1] ** 2 / 1e4

    fig, axs = plt.subplots(1, 3, figsize=(17, 7.6), constrained_layout=True)
    axs[0].imshow(plt.imread(paper_png))
    axs[0].set_title("(a) Park & Sim (2023), Fig. 1c\nvegetation type (study area 3,994 ha)", fontsize=11)

    v = np.where(crop(vegd), crop(veg) - 1, np.nan)
    axs[1].imshow(v, extent=ext, origin="upper", interpolation="nearest",
                  cmap=ListedColormap([cl[3] for cl in CLASSES]), vmin=-0.5, vmax=5.5)
    tot = vegd.sum()
    axs[1].legend(handles=[Patch(color=cl[3], label=f"{cl[0]} {100 * ((veg == k + 1) & vegd).sum() / tot:.1f}%  (paper {cl[4]}%)")
                           for k, cl in enumerate(CLASSES)],
                  loc="upper left", bbox_to_anchor=(1.0, 0.45), fontsize=8.5, title="VegType", title_fontsize=9)
    axs[1].set_title(f"(b) Same NPS vegetation data, our reproduction\nstudy area {ha:,.0f} ha", fontsize=11)

    codes = [k for k in sorted(FUELS) if (fuel[study] == k).any()]
    idx = np.full(fuel.shape, np.nan)
    for k, code in enumerate(codes):
        idx[(fuel == code) & study] = k
    axs[2].imshow(crop(idx), extent=ext, origin="upper", interpolation="nearest",
                  cmap=ListedColormap([FUELS[k][1] for k in codes]), vmin=-0.5, vmax=len(codes) - 0.5)
    shares = sorted(((100 * ((fuel == k) & study).sum() / study.sum(), k) for k in codes), reverse=True)
    axs[2].legend(handles=[Patch(color=FUELS[k][1], label=f"{k} {FUELS[k][0]} {p:.1f}%") for p, k in shares if p >= 0.2],
                  loc="upper left", bbox_to_anchor=(1.0, 0.45), fontsize=8.5, title="FBFM40", title_fontsize=9)
    axs[2].set_title("(c) FBFM40 fuel model, same area\nLANDFIRE 1.4.0 via CloudFire (used by ELMFIRE)", fontsize=11)

    for ax in axs:
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_visible(False)
    for ax in axs[1:]:
        ax.set_aspect("equal")
    fig.suptitle("Chimney Tops 2 Fire study area (MTBS perimeter inside Great Smoky Mountains NP): "
                 "recorded vegetation vs LANDFIRE fuel model", fontsize=12)
    fig.savefig(out, dpi=170, facecolor="white", bbox_inches="tight", pad_inches=0.2)
    print("wrote", out)


if __name__ == "__main__":
    main()
