#!/usr/bin/env python3
"""
Compare a simulated fire with an observed perimeter (e.g. MTBS burn boundary).

The observed polygon is rasterised onto the simulation grid, then:
  - areas (acres) of observed, simulated and overlap
  - Sorensen (Dice) coefficient = 2|A n B| / (|A| + |B|)   (1 = perfect match)
  - Jaccard index              = |A n B| / |A u B|
  - fraction of the observed area that the simulation burned (hit rate)
A map is written to RUN_DIR/analysis/compare_perimeter.png.

Usage:
    python compare_perimeter.py RUN_DIR PERIMETER.shp [--label TEXT] [--cmap yellow-red]
Several runs at once (one row per run in the printed table, one map each):
    python compare_perimeter.py DIR1 DIR2 ... --perimeter PERIMETER.shp
"""
import argparse
import glob
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import BoundaryNorm
from matplotlib.lines import Line2D
from osgeo import gdal, ogr

from plot_tutorial_figure import add_scalebar

gdal.UseExceptions()
ogr.UseExceptions()
M2_PER_ACRE = 4046.8564


def time_cmap(name, n):
    """Discrete colour map for time-of-arrival bands. 'yellow-red' = light yellow (early) to dark red (late)."""
    if name == "yellow-red":
        return matplotlib.colors.ListedColormap(plt.get_cmap("YlOrRd")(np.linspace(0.15, 1.0, n)))
    return plt.get_cmap(name, n)


def rasterise(shp, like_ds):
    """Burn the perimeter polygon(s) into a grid matching like_ds (1 inside, 0 outside)."""
    drv = gdal.GetDriverByName("MEM")
    ds = drv.Create("", like_ds.RasterXSize, like_ds.RasterYSize, 1, gdal.GDT_Byte)
    ds.SetGeoTransform(like_ds.GetGeoTransform())
    ds.SetProjection(like_ds.GetProjection())
    vec = ogr.Open(shp)
    gdal.RasterizeLayer(ds, [1], vec.GetLayer(), burn_values=[1])
    return ds.ReadAsArray().astype(bool)


def perimeter_lines(shp):
    """Yield (x, y) arrays of every ring in the shapefile."""
    vec = ogr.Open(shp)
    for feat in vec.GetLayer():
        geom = feat.GetGeometryRef()
        polys = [geom.GetGeometryRef(i) for i in range(geom.GetGeometryCount())] \
            if geom.GetGeometryName() == "MULTIPOLYGON" else [geom]
        for poly in polys:
            for i in range(poly.GetGeometryCount()):
                pts = np.array(poly.GetGeometryRef(i).GetPoints())
                yield pts[:, 0], pts[:, 1]


def compare(run_dir, shp, label, cmap_name="inferno_r"):
    toa_fn = glob.glob(os.path.join(run_dir, "outputs", "time_of_arrival_*.tif"))
    if not toa_fn:
        raise SystemExit(f"No time_of_arrival raster in {run_dir}/outputs")
    ds = gdal.Open(sorted(toa_fn)[-1])
    toa = ds.ReadAsArray().astype(float)
    gt = ds.GetGeoTransform()
    dx = gt[1]
    sim = toa >= 0
    obs = rasterise(shp, ds)

    cell_ac = dx * dx / M2_PER_ACRE
    a_obs, a_sim, a_both = obs.sum(), sim.sum(), (obs & sim).sum()
    stats = {
        "run": label,
        "observed_ac": a_obs * cell_ac,
        "simulated_ac": a_sim * cell_ac,
        "overlap_ac": a_both * cell_ac,
        "sorensen": 2 * a_both / (a_obs + a_sim) if a_obs + a_sim else 0.0,
        "jaccard": a_both / (obs | sim).sum() if (obs | sim).any() else 0.0,
        "hit_rate": a_both / a_obs if a_obs else 0.0,
    }

    # Map: simulated time of arrival + observed perimeter
    ny, nx = toa.shape
    extent = [gt[0], gt[0] + nx * dx, gt[3] + ny * gt[5], gt[3]]
    rows, cols = np.where(obs | sim)
    pad = 800.0
    xmin = gt[0] + cols.min() * dx - pad
    xmax = gt[0] + (cols.max() + 1) * dx + pad
    ymin = gt[3] - (rows.max() + 1) * dx - pad
    ymax = gt[3] - rows.min() * dx + pad
    w, h = xmax - xmin, ymax - ymin

    toa_h = np.where(sim, toa / 3600.0, np.nan)
    t_end = np.nanmax(toa_h) if sim.any() else 1
    step = 6 if t_end > 24 else 3
    bounds = np.arange(0, np.ceil(t_end / step) * step + step, step)
    cmap = time_cmap(cmap_name, len(bounds) - 1)

    fig, ax = plt.subplots(figsize=(8, 8 * h / w + 1.5), constrained_layout=True)
    ax.imshow(np.where(obs, 1, np.nan), extent=extent, origin="upper",
              cmap=matplotlib.colors.ListedColormap(["#cfe3f5"]), interpolation="nearest")
    im = ax.imshow(toa_h, extent=extent, origin="upper", cmap=cmap,
                   norm=BoundaryNorm(bounds, cmap.N), interpolation="nearest")
    for lx, ly in perimeter_lines(shp):
        ax.plot(lx, ly, color="#1f5fbf", lw=1.8)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    bar = 1000 if w < 12000 else 2000
    add_scalebar(ax, xmax - bar - 0.05 * w, ymin + 0.03 * h, bar, 2, 0.008 * h)
    ax.annotate("N", xy=(xmin + 0.06 * w, ymax - 0.04 * h), xytext=(xmin + 0.06 * w, ymax - 0.11 * h),
                ha="center", fontsize=13, fontweight="bold",
                arrowprops=dict(arrowstyle="-|>", color="black", lw=2))
    ax.legend(handles=[Line2D([], [], color="#1f5fbf", lw=1.8, label="Observed perimeter (MTBS)"),
                       plt.Rectangle((0, 0), 1, 1, color="#cfe3f5", label="Observed burned area")],
              loc="upper right")
    cb = fig.colorbar(im, ax=ax, orientation="horizontal", shrink=0.7, pad=0.02, ticks=bounds)
    cb.set_label("Simulated time of arrival (hours after ignition)")
    ax.set_title(f"{label}\nSimulated {stats['simulated_ac']:,.0f} ac vs observed "
                 f"{stats['observed_ac']:,.0f} ac  |  Sorensen {stats['sorensen']:.3f}")

    os.makedirs(os.path.join(run_dir, "analysis"), exist_ok=True)
    out = os.path.join(run_dir, "analysis", "compare_perimeter.png")
    fig.savefig(out, dpi=160, facecolor="white")
    plt.close(fig)
    stats["map"] = out
    return stats


def main():
    ap = argparse.ArgumentParser(description="Compare simulated fire(s) with an observed perimeter")
    ap.add_argument("run_dirs", nargs="+", help="run folder(s) containing outputs/ "
                    "(if --perimeter is not given, the last argument is the shapefile)")
    ap.add_argument("--perimeter", help="observed perimeter shapefile")
    ap.add_argument("--label", help="title for a single run")
    ap.add_argument("--cmap", default="inferno_r",
                    help="colours for time of arrival: inferno_r (default) or yellow-red, or any matplotlib name")
    args = ap.parse_args()
    runs, shp = args.run_dirs, args.perimeter
    if shp is None:
        runs, shp = runs[:-1], runs[-1]

    rows = [compare(r, shp, args.label if args.label and len(runs) == 1 else r, args.cmap) for r in runs]
    print(f"{'run':40s} {'observed ac':>12s} {'simulated ac':>13s} {'overlap ac':>11s} "
          f"{'Sorensen':>9s} {'Jaccard':>8s} {'hit rate':>9s}")
    for s in rows:
        print(f"{s['run']:40s} {s['observed_ac']:12,.0f} {s['simulated_ac']:13,.0f} {s['overlap_ac']:11,.0f} "
              f"{s['sorensen']:9.3f} {s['jaccard']:8.3f} {s['hit_rate']:9.3f}")
    for s in rows:
        print("map:", s["map"])


if __name__ == "__main__":
    main()
