#!/usr/bin/env python3
"""
Compare the LANDFIRE fuel models (CloudFire) with fuel models derived from the NPS recorded
vegetation, both as FBFM40 codes with the same colours, inside the fire perimeter.

Crosswalk NPS vegetation -> FBFM40 (assumptions, guided by Park & Sim 2023):
  Yellow pine forests -> TU5 (165); any forest with medium/heavy mountain laurel or mixed
  rhododendron-laurel understory -> TU5; Chestnut oak -> TL9 (189); montane oak-hickory and
  high-elevation red/white oak -> TL6 (186); northern hardwood (acid, boulderfield), cove,
  successional hardwood, floodplain, successional/modified -> TL2 (182); hemlock, spruce-fir,
  white pine -> TL3 (183); ericaceous shrubs (heath balds) -> SH5 (145); human influence, roads
  -> NB1 (91); water -> NB8 (98); sparse vegetation -> NB9 (99). Outside the park: not mapped.

Usage:
    python plot_fuel_vs_vegetation_fbfm.py LANDSCAPE.tif PERIMETER.shp NPS_DIR OUT.png
Writes OUT.png, OUT.tif (vegetation-derived FBFM40, 0 = not mapped) and OUT.csv (cross-table).
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
from plot_fuel_vs_vegetation import _ignition
from plot_landscape_figure import FUELS

gdal.UseExceptions()
CROSSWALK = [   # (fbfm code, list of NPS ECOGROUP names); later entries overwrite earlier ones
    (182, ["Northern hardwood/acid hardwood forests", "Northern hardwood/boulderfield forests",
           "Montane cove forests", "Successional hardwood forests", "Floodplain forests",
           "Successional or modified vegetation"]),
    (186, ["Montane oak-hickory forests", "High elevation red oak/white oak forests"]),
    (189, ["Chestnut oak forests"]),
    (165, ["Yellow pine forests"]),
    (183, ["Hemlock forests", "Spruce-fir forests", "White pine forests", "White pine-hemlock forests"]),
    (145, ["Ericaceous shrubs (heath bald type)", "Ericaceous shrubs (non-heath bald type)"]),
    (91, ["Human influence", "Roads"]),
    (98, ["Water"]),
    (99, ["Sparse vegetation"]),
]
LAUREL = ["Mountain Laurel, Medium", "Mountain Laurel, Heavy",
          "Mixed Rhodo - Mtn. Laurel, Medium", "Mixed Rhodo - Mtn. Laurel, Heavy"]
FOREST = [182, 186, 189, 183]


def main():
    land, per, nps_dir, out = sys.argv[1:5]
    over = os.path.join(nps_dir, "GRSM_VEGETATION_OVERSTORY_2004.shp")
    under = os.path.join(nps_dir, "GRSM_VEGETATION_UNDERSTORY.shp")
    L = gdal.Open(land)
    gt = L.GetGeoTransform()
    lf = L.GetRasterBand(4).ReadAsArray()
    inside = rasterise(per, L)
    ny, nx = inside.shape
    extent = [gt[0], gt[0] + nx * gt[1], gt[3] + ny * gt[5], gt[3]]

    mem = gdal.GetDriverByName("MEM")

    def blank():
        d = mem.Create("", nx, ny, 1, gdal.GDT_Int16)
        d.SetGeoTransform(gt)
        d.SetProjection(L.GetProjection())
        return d

    veg = blank()
    gdal.Rasterize(veg, over, burnValues=[182])              # unlisted mapped types: light litter
    for code, names in CROSSWALK:
        gdal.Rasterize(veg, over, burnValues=[code], where=" OR ".join("ECOGROUP = '%s'" % n for n in names))
    laurel = blank()
    gdal.Rasterize(laurel, under, burnValues=[1], where=" OR ".join("DENS_CLASS = '%s'" % c for c in LAUREL))
    vf = veg.ReadAsArray()
    vf[np.isin(vf, FOREST) & (laurel.ReadAsArray() > 0)] = 165
    t = gdal.GetDriverByName("GTiff").Create(os.path.splitext(out)[0] + ".tif", nx, ny, 1, gdal.GDT_Int16, ["COMPRESS=DEFLATE"])
    t.SetGeoTransform(gt)
    t.SetProjection(L.GetProjection())
    t.GetRasterBand(1).WriteArray(vf)
    t = None

    mapped = inside & (vf > 0)
    codes = [k for k in sorted(FUELS) if (lf[inside] == k).any() or (vf[mapped] == k).any()]
    cmap = ListedColormap([FUELS[k][1] for k in codes])

    # Show only the study area of Park & Sim (2023): the perimeter inside the park (NPS map)
    r, c = np.where(mapped)
    pad = 250
    xmin, xmax = gt[0] + c.min() * gt[1] - pad, gt[0] + (c.max() + 1) * gt[1] + pad
    ymin, ymax = gt[3] + (r.max() + 1) * gt[5] - pad, gt[3] + r.min() * gt[5] + pad
    fig, axs = plt.subplots(1, 2, figsize=(12, 8.2), constrained_layout=True)
    for ax, fuel, mask, title in ((axs[0], lf, mapped, "(a) LANDFIRE 1.4.0 fuel (via CloudFire)\nused by ELMFIRE"),
                                  (axs[1], vf, mapped, "(b) Fuel from recorded vegetation\n(NPS GSMNP map, crosswalk to FBFM40)")):
        idx = np.full(fuel.shape, np.nan)
        for k, code in enumerate(codes):
            idx[(fuel == code) & mask] = k
        ax.imshow(idx, extent=extent, origin="upper", interpolation="nearest", cmap=cmap,
                  vmin=-0.5, vmax=len(codes) - 0.5)
        ax.plot(*_ignition(L), marker="*", color="red", ms=15, mec="white", mew=1.2, zorder=5)
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.set_title(title, fontsize=11)
    tot = mapped.sum()
    handles = []
    for code in codes:
        a, b = 100 * (lf[mapped] == code).sum() / tot, 100 * (vf[mapped] == code).sum() / tot
        if max(a, b) >= 0.2:
            handles.append(Patch(color=FUELS[code][1], label=f"{code} {FUELS[code][0]}:  {a:4.1f}%  |  {b:4.1f}%"))
    fig.legend(handles=handles, loc="lower center", ncol=2, fontsize=8.5, frameon=True,
               title=f"Fuel model:   (a) LANDFIRE  |  (b) recorded vegetation   (share of the study area, {mapped.sum() * gt[1] ** 2 / 1e4:,.0f} ha inside the park)",
               title_fontsize=9, bbox_to_anchor=(0.5, -0.12))
    agree = 100 * (lf[mapped] == vf[mapped]).mean()
    fig.suptitle(f"Chimney Tops 2 Fire, study area inside the park: LANDFIRE fuel vs fuel from recorded vegetation\n"
                 f"same fuel model in {agree:.0f}% of the area  (red star: ignition)", fontsize=11.5)
    fig.savefig(out, dpi=170, facecolor="white", bbox_inches="tight", pad_inches=0.25)

    # Cross-table: rows = vegetation-derived fuel, columns = LANDFIRE fuel (% of row)
    rows_codes = [k for k in codes if (vf[mapped] == k).any()]
    cols_codes = [k for k in codes if (lf[mapped] == k).any()]
    with open(os.path.splitext(out)[0] + ".csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["vegetation_fuel", "share_pct"] + [f"landfire_{k}_{FUELS[k][0].split()[0]}_pct" for k in cols_codes])
        print(f"same fuel model in {agree:.1f}% of the mapped area\n")
        print(f"{'from vegetation':22s} {'share':>6s}   LANDFIRE fuel in the same cells")
        for k in rows_codes:
            m = mapped & (vf == k)
            row = [100 * (lf[m] == j).mean() for j in cols_codes]
            w.writerow([f"{k} {FUELS[k][0]}", round(100 * m.sum() / tot, 1)] + [round(x, 1) for x in row])
            top = ", ".join(f"{FUELS[cols_codes[i]][0].split()[0]} {row[i]:.0f}%" for i in np.argsort(row)[::-1][:3] if row[i] >= 1)
            print(f"{k} {FUELS[k][0][:17]:17s} {100 * m.sum() / tot:6.1f}%   {top}")
    print("\nwrote", out)


if __name__ == "__main__":
    main()
