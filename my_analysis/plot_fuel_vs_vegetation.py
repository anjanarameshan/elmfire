#!/usr/bin/env python3
"""
Two maps inside the fire perimeter: (a) the LANDFIRE fuel models delivered by CloudFire and
(b) the NPS recorded vegetation, grouped into the six classes of Park & Sim (2023, Fig. 1c):
SHF, COF, YPF, OHF, NHF/AHF, Others. Also prints/writes the cross-table: which LANDFIRE fuel
each vegetation class received.

Usage:
    python plot_fuel_vs_vegetation.py LANDSCAPE.tif PERIMETER.shp OVERSTORY.shp OUT.png
Writes OUT.png and OUT.csv (cross-table, % of each vegetation class).
"""
import csv
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from osgeo import gdal

from compare_perimeter import perimeter_lines, rasterise
from plot_landscape_figure import FUELS

gdal.UseExceptions()
# Paper classes (Park & Sim 2023) -> NPS ECOGROUP names; colours close to the paper's Fig. 1c
CLASSES = [
    ("SHF", "Successional hardwood forest", ["Successional hardwood forests"], "#56b4e9", 6.4),
    ("COF", "Chestnut oak forest", ["Chestnut oak forests"], "#6aa84f", 27.8),
    ("YPF", "Yellow pine forest", ["Yellow pine forests"], "#7b3fa0", 12.8),
    ("OHF", "Oak-hickory forest", ["Montane oak-hickory forests"], "#e6a817", 14.9),
    ("NHF/AHF", "Northern / acid hardwood forest", ["Northern hardwood/acid hardwood forests"], "#e0662a", 13.9),
    ("Others", "Other types (cove, boulderfield, floodplain, heath, ...)", None, "#2f6fb5", 24.2),
]
NON_VEG = ["Human influence", "Roads", "Water", "Sparse vegetation"]


def main():
    land, per, over, out = sys.argv[1:5]
    L = gdal.Open(land)
    gt = L.GetGeoTransform()
    fuel = L.GetRasterBand(4).ReadAsArray()
    inside = rasterise(per, L)
    ny, nx = inside.shape
    extent = [gt[0], gt[0] + nx * gt[1], gt[3] + ny * gt[5], gt[3]]

    mem = gdal.GetDriverByName("MEM")
    veg_ds = mem.Create("", nx, ny, 1, gdal.GDT_Byte)
    veg_ds.SetGeoTransform(gt)
    veg_ds.SetProjection(L.GetProjection())
    gdal.Rasterize(veg_ds, over, burnValues=[6])                       # any mapped polygon -> Others
    gdal.Rasterize(veg_ds, over, burnValues=[9],
                   where=" OR ".join("ECOGROUP = '%s'" % n for n in NON_VEG))   # non-vegetated
    for k, (_, _, names, _, _) in enumerate(CLASSES[:-1]):
        gdal.Rasterize(veg_ds, over, burnValues=[k + 1], where=" OR ".join("ECOGROUP = '%s'" % n for n in names))
    veg = veg_ds.ReadAsArray()
    mapped = inside & (veg >= 1) & (veg <= 6)

    r, c = np.where(inside)
    pad = 400
    xmin, xmax = gt[0] + c.min() * gt[1] - pad, gt[0] + (c.max() + 1) * gt[1] + pad
    ymin, ymax = gt[3] + (r.max() + 1) * gt[5] - pad, gt[3] + r.min() * gt[5] + pad
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 9.5), constrained_layout=True)

    # (a) LANDFIRE fuel
    codes = [k for k in sorted(FUELS) if (fuel[inside] == k).any()]
    idx = np.full(fuel.shape, np.nan)
    for k, code in enumerate(codes):
        idx[(fuel == code) & inside] = k
    a1.imshow(idx, extent=extent, origin="upper", interpolation="nearest",
              cmap=ListedColormap([FUELS[k][1] for k in codes]), vmin=-0.5, vmax=len(codes) - 0.5)
    shares = sorted(((100 * ((fuel == k) & inside).sum() / inside.sum(), k) for k in codes), reverse=True)
    a1.legend(handles=[Patch(color=FUELS[k][1], label=f"{k} {FUELS[k][0]} ({p:.1f}%)") for p, k in shares if p >= 0.3],
              loc="upper center", bbox_to_anchor=(0.5, 0.0), fontsize=8, title="Share of the burned area",
              title_fontsize=8.5)
    a1.set_title("(a) Fuel model used by ELMFIRE\nLANDFIRE 1.4.0 via CloudFire", fontsize=11)

    # (b) NPS vegetation, paper classes
    vshow = np.where(mapped, veg - 1, np.nan)
    a2.imshow(np.where(inside & ~mapped, 1, np.nan), extent=extent, origin="upper",
              cmap=ListedColormap(["#d9d9d9"]), interpolation="nearest")
    a2.imshow(vshow, extent=extent, origin="upper", interpolation="nearest",
              cmap=ListedColormap([cl[3] for cl in CLASSES]), vmin=-0.5, vmax=len(CLASSES) - 0.5)
    tot = mapped.sum()
    handles = [Patch(color=cl[3], label=f"{cl[0]}: {100 * ((veg == k + 1) & mapped).sum() / tot:.1f}%  (paper {cl[4]}%)")
               for k, cl in enumerate(CLASSES)]
    handles.append(Patch(color="#d9d9d9", label="not mapped (outside the park) or non-vegetated"))
    a2.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.0), fontsize=8,
              title="Share of mapped vegetated area (this map vs paper)", title_fontsize=8.5)
    a2.set_title("(b) Recorded vegetation - NPS GSMNP vegetation map\n(classes of Park & Sim 2023, Fig. 1c)", fontsize=11)

    for ax in (a1, a2):
        for lx, ly in perimeter_lines(per):
            ax.plot(lx, ly, color="black", lw=0.8)
        ax.plot(*_ignition(L), marker="*", color="red", ms=15, mec="white", mew=1.2, zorder=5)
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        ax.set_aspect("equal")
        ax.axis("off")
    a1.annotate("N", xy=(xmin + 0.1 * (xmax - xmin), ymax - 0.03 * (ymax - ymin)),
                xytext=(xmin + 0.1 * (xmax - xmin), ymax - 0.09 * (ymax - ymin)), ha="center",
                fontsize=12, fontweight="bold", arrowprops=dict(arrowstyle="-|>", color="black", lw=2))
    fig.suptitle("Chimney Tops 2 Fire: CloudFire fuel vs recorded vegetation (red star: ignition)", fontsize=12)
    fig.savefig(out, dpi=170, facecolor="white", bbox_inches="tight", pad_inches=0.2)

    # Cross-table: LANDFIRE fuel within each vegetation class
    with open(os.path.splitext(out)[0] + ".csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["vegetation_class", "share_of_mapped_pct", "paper_pct"] + [f"{k}_{FUELS[k][0].split()[0]}_pct" for k in codes])
        print(f"{'class':9s} {'map %':>6s} {'paper %':>8s}   LANDFIRE fuel inside this class")
        for k, cl in enumerate(CLASSES):
            m = (veg == k + 1) & mapped
            row = [100 * (fuel[m] == code).mean() for code in codes]
            w.writerow([cl[0], round(100 * m.sum() / tot, 1), cl[4]] + [round(x, 1) for x in row])
            top = ", ".join(f"{FUELS[codes[i]][0].split()[0]} {row[i]:.0f}%" for i in np.argsort(row)[::-1][:3] if row[i] >= 1)
            print(f"{cl[0]:9s} {100 * m.sum() / tot:6.1f} {cl[4]:8.1f}   {top}")
    print("wrote", out)


def _ignition(L, lon=-83.47833, lat=35.62889):
    from osgeo import osr
    ll = osr.SpatialReference()
    ll.ImportFromEPSG(4326)
    ll.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    x, y, _ = osr.CoordinateTransformation(ll, osr.SpatialReference(wkt=L.GetProjection())).TransformPoint(lon, lat)
    return x, y


if __name__ == "__main__":
    main()
