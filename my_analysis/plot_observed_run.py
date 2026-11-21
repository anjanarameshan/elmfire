#!/usr/bin/env python3
"""
Annotated map of an observation-based Chimney Tops 2 run: simulated time of arrival, MTBS
perimeter, initial fire, the two reported spot fires, and a panel listing the set-up and
where each value comes from.

Usage: python plot_observed_run.py RUN_DIR PERIMETER.shp OUT.png "Fuel description" ADJ
"""
import glob
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import BoundaryNorm
from matplotlib.lines import Line2D
from osgeo import gdal, osr

from compare_perimeter import perimeter_lines, rasterise, time_cmap
from plot_tutorial_figure import add_scalebar

gdal.UseExceptions()
run, shp, out, fuel_txt, adj = sys.argv[1:6]
SHOW_URBAN = not (len(sys.argv) > 6 and sys.argv[6] == "no-urban")   # 6th argument "no-urban": plain map
POINTS = [("Start: 35 acres, 00:00", -83.47833, 35.62889, "*", "#1f5fbf", 16),
          ("Spot fire 1, 06:00", -83.487, 35.648, "^", "#111111", 10),
          ("Spot fire 2, 11:30", -83.497, 35.690, "s", "#111111", 9),
          ("Gatlinburg", -83.5102, 35.7143, "o", "#6a3d9a", 8)]

ds = gdal.Open(sorted(glob.glob(run + "/outputs/time_of_arrival_*.tif"))[-1])
toa = ds.ReadAsArray().astype(float)
gt = ds.GetGeoTransform()
sim = toa >= 0
obs = rasterise(shp, ds)
ac = gt[1] ** 2 / 4046.8564
a_sim, a_obs, a_both = sim.sum() * ac, obs.sum() * ac, (sim & obs).sum() * ac
sor = 2 * a_both / (a_sim + a_obs)
# Non-burnable cells (urban NB1 = 91; water, bare, ...) from this run's own fuel map
_land = gdal.Open(run + "/inputs/landscape.tif")
fuel = _land.GetRasterBand(4).ReadAsArray()
urban = fuel == 91
a_urban = (urban & obs).sum() * ac
a_nb = ((fuel < 100) & obs).sum() * ac
burnable = obs & (fuel > 100)
a_burnable = burnable.sum() * ac
a_both_b = (sim & burnable).sum() * ac

ny, nx = toa.shape
extent = [gt[0], gt[0] + nx * gt[1], gt[3] + ny * gt[5], gt[3]]
r, c = np.where(sim | obs)
pad = 700
xmin, xmax = gt[0] + c.min() * gt[1] - pad, gt[0] + (c.max() + 1) * gt[1] + pad
ymin, ymax = gt[3] + (r.max() + 1) * gt[5] - pad, gt[3] + r.min() * gt[5] + pad
w, h = xmax - xmin, ymax - ymin

ll = osr.SpatialReference()
ll.ImportFromEPSG(4326)
ll.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
tr = osr.CoordinateTransformation(ll, osr.SpatialReference(wkt=ds.GetProjection()))

bounds = np.arange(0, 28, 3)
cmap = time_cmap("yellow-red", len(bounds) - 1)
fig, (ax, tx) = plt.subplots(1, 2, figsize=(14, 10.5), gridspec_kw={"width_ratios": [1.0, 0.95]},
                             constrained_layout=True)
ax.imshow(np.where(obs, 1, np.nan), extent=extent, origin="upper",
          cmap=matplotlib.colors.ListedColormap(["#cfe3f5"]), interpolation="nearest")
im = ax.imshow(np.where(sim, toa / 3600, np.nan), extent=extent, origin="upper", cmap=cmap,
               norm=BoundaryNorm(bounds, cmap.N), interpolation="nearest")
if SHOW_URBAN:
  ax.imshow(np.where(urban & obs, 1, np.nan), extent=extent, origin="upper",
          cmap=matplotlib.colors.ListedColormap(["#5a5a5a"]), interpolation="nearest", alpha=0.85, zorder=3)
for lx, ly in perimeter_lines(shp):
    ax.plot(lx, ly, color="#1f5fbf", lw=1.6, zorder=4)
handles = [Line2D([], [], color="#1f5fbf", lw=1.6, label="Observed perimeter (MTBS)"),
           plt.Rectangle((0, 0), 1, 1, color="#cfe3f5", label="Observed burned area"),
           ] + ([plt.Rectangle((0, 0), 1, 1, color="#5a5a5a", label=f"Urban, cannot burn in ELMFIRE ({a_urban:,.0f} ac inside)")]
                if SHOW_URBAN else [])
for name, lon, lat, mk, col, ms in POINTS:
    x, y, _ = tr.TransformPoint(lon, lat)
    ax.plot(x, y, mk, color=col, ms=ms, mec="white", mew=1.2, zorder=6)
    handles.append(Line2D([], [], marker=mk, color=col, ls="", ms=ms * 0.8, mec="white", label=name))
ax.set_xlim(xmin, xmax)
ax.set_ylim(ymin, ymax)
ax.set_aspect("equal")
ax.set_xticks([])
ax.set_yticks([])
LEGEND_HANDLES = handles
add_scalebar(ax, xmax - 2000 - 0.05 * w, ymin + 0.025 * h, 2000, 2, 0.006 * h)
ax.annotate("N", xy=(xmin + 0.07 * w, ymax - 0.03 * h), xytext=(xmin + 0.07 * w, ymax - 0.09 * h),
            ha="center", fontsize=13, fontweight="bold", arrowprops=dict(arrowstyle="-|>", color="black", lw=2))
cb = fig.colorbar(im, ax=ax, orientation="horizontal", shrink=0.85, pad=0.02, ticks=bounds)
cb.ax.set_xticklabels(["00:00", "03:00", "06:00", "09:00", "12:00", "15:00", "18:00", "21:00", "00:00", "03:00"])
cb.set_label("Simulated time of arrival, EST (Mon 28 Nov 00:00 to Tue 29 Nov 03:00)")
ax.set_title(f"Simulated {a_sim:,.0f} ac  vs  observed {a_obs:,.0f} ac", fontsize=12)

tx.axis("off")
lines = [
    ("RESULT", None),
    (f"Simulated burned area: {a_sim:,.0f} acres", None),
    (f"Observed (MTBS): {a_obs:,.0f} acres", None),
    (f"Overlap: {a_both:,.0f} acres ({100 * a_both / a_sim:.0f} % of the simulated area is inside the perimeter)", None),
    (f"Sorensen score: {sor:.3f}     Share of observed area burned: {100 * a_both / a_obs:.0f} %", None),
] + ([
    ("", None),
    ("URBAN AREA (CANNOT BURN IN THE MODEL)", None),
    (f"Urban cells (fuel NB1) inside the perimeter: {a_urban:,.0f} acres", "Dark grey on the map. Mostly Gatlinburg. Plus water/bare ground: " + f"{a_nb - a_urban:,.0f} acres"),
    (f"Observed area the model could burn: {a_obs:,.0f} - {a_nb:,.0f} = {a_burnable:,.0f} acres", None),
    (f"Model burned {a_both_b:,.0f} acres of it = {100 * a_both_b / a_burnable:.0f} %;  Sorensen vs this area: {2 * a_both_b / (a_sim + a_burnable):.3f}", None),
] if SHOW_URBAN else []) + [
    ("", None),
    ("SET-UP AND WHERE EACH VALUE COMES FROM", None),
    ("Start: Mon 28 Nov 00:00 EST from a 35-acre fire at Chimney Tops", "Jimenez et al. 2018 (incident report): 35 acres at the end of 27 Nov; wind rose that night"),
    ("Spot fire 1: lit 06:00 EST, about 1.5 mile from the fire", "Jimenez et al. 2018: spot fires found on the morning of 28 Nov. Location read off their Fig. 1 (approximate)"),
    ("Spot fire 2: lit 11:30 EST, towards Gatlinburg", "Jimenez et al. 2018: found at about 11:30, 1.5 mile from the park boundary. Location approximate"),
    ("End: Tue 29 Nov 03:00 EST (27 hours)", "Jimenez et al. 2018: fire activity subsided after 02:00 with steady rain"),
    ("Wind: HRRR hourly average (3 km), no gust factor", "HRRR mean over the Jimenez 13 km area peaks at 35.6 mph at 18:00; their 111 m WRF-Fire gives 35.8 mph"),
    ("Fuel moisture: 1-hr capped at 4 % until 28 Nov 19:00 EST", "Shadbolt et al. 2019: relative humidity < 10 % descending the lee slope; dry layer gone by 29 Nov 00:00 UTC. 4 % is the assumed equilibrium value (dry end)"),
    (f"Fuel: {fuel_txt}", "Vegetation classes as in Park & Sim 2023; the conversion to fuel models is an assumption"),
    (f"Spread-rate adjustment factor adj = {adj}", "Calibration factor, not an observed value"),
    ("Spotting: on (ELMFIRE tutorial settings)", "Not calibrated for this fire"),
    ("", None),
    ("NOT IN THE MODEL", None),
    ("Fires started by fallen power lines in Gatlinburg after 17:00", "Jimenez et al. 2018"),
    ("Burning of buildings (urban cells cannot burn)", None),
    ("Downslope mountain-wave winds on individual slopes", "Shadbolt et al. 2019: descent up to 3 m/s on the lee side; winds >= 30 m/s at 850 hPa"),
]
y = 0.985
for main, src in lines:
    if src is None and main.isupper():
        tx.text(0, y, main, fontsize=11.5, fontweight="bold", color="#b3470f", va="top", transform=tx.transAxes)
        y -= 0.030
    elif main == "":
        y -= 0.008
    else:
        t = tx.text(0, y, main, fontsize=9.5, va="top", wrap=True, transform=tx.transAxes)
        y -= 0.024
        if src:
            import textwrap
            wrapped = textwrap.fill(src, 92)
            tx.text(0.02, y, wrapped, fontsize=8, color="0.35", va="top", transform=tx.transAxes, style="italic")
            y -= 0.019 * (wrapped.count("\n") + 1) + 0.006
tx.legend(handles=LEGEND_HANDLES, loc="upper left", bbox_to_anchor=(0, y - 0.01), fontsize=8.5, framealpha=0.95, ncol=2,
          title="Map legend", title_fontsize=9)
fig.suptitle("Chimney Tops 2 Fire, 28 November 2016 - ELMFIRE run with observation-based inputs", fontsize=13.5, fontweight="bold")
fig.savefig(out, dpi=160, facecolor="white")
print("wrote", out)
