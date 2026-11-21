#!/usr/bin/env python3
"""
Where can a downslope wind effect be expected? Terrain (DEM) + wind direction.

Panels:
  (a) elevation with hillshade and the mean HRRR wind (arrows) for the chosen hours
  (b) slope (degrees)
  (c) downslope exposure = how directly the wind blows down the slope, times slope steepness
      (0 = flat or uphill/cross-slope, 1 = wind straight down a slope of >= SLOPE_FULL)
      This is the same index downslope_wind.py uses to boost the wind (factor up to F).
Slope and aspect are computed from the DEM smoothed to SMOOTH_M, so whole mountain sides
show up rather than small gullies.

Usage: python plot_downslope_map.py RUN_DIR PERIMETER.shp OUT.png [HOUR0 HOUR1] [SMOOTH_M]
    HOUR0..HOUR1: band indices of RUN_DIR/hrrr_wind/wd.tif averaged (default 13 21 =
                  28 Nov 13:00-21:00 EST for runs starting 28 Nov 00:00 EST)
"""
import glob
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LightSource
from osgeo import gdal, osr

from compare_perimeter import perimeter_lines
from plot_tutorial_figure import add_scalebar

gdal.UseExceptions()
SLOPE_FULL = 0.15
run, shp, out = sys.argv[1:4]
h0, h1 = (int(sys.argv[4]), int(sys.argv[5])) if len(sys.argv) > 5 else (13, 21)
smooth = float(sys.argv[6]) if len(sys.argv) > 6 else 300.0

L = gdal.Open(run + "/inputs/landscape.tif")
gt = L.GetGeoTransform()
dem30 = L.GetRasterBand(1).ReadAsArray().astype(float)
ny, nx = dem30.shape
bounds = (gt[0], gt[3] + ny * gt[5], gt[0] + nx * gt[1], gt[3])
dem_ds = gdal.Translate("", L, format="MEM", bandList=[1])
dem = gdal.Warp("", dem_ds, format="MEM",
                outputBounds=bounds, xRes=smooth, yRes=smooth, resampleAlg="average").ReadAsArray().astype(float)
dzdy, dzdx = np.gradient(dem, smooth, smooth)
dzdy = -dzdy
slope = np.hypot(dzdx, dzdy)
down_e, down_n = -dzdx / np.maximum(slope, 1e-9), -dzdy / np.maximum(slope, 1e-9)

# Mean wind over the chosen hours, interpolated to the smoothed grid
wds, wss = gdal.Open(run + "/hrrr_wind/wd.tif"), gdal.Open(run + "/hrrr_wind/ws.tif")
def to_grid(ds, b):
    return gdal.Warp("", gdal.Translate("", ds, format="MEM", bandList=[b]), format="MEM", outputBounds=bounds,
                     xRes=smooth, yRes=smooth, resampleAlg="bilinear").ReadAsArray().astype(float)
U = V = 0
for b in range(h0 + 1, h1 + 2):
    wd, ws = to_grid(wds, b), to_grid(wss, b)
    U = U + ws * -np.sin(np.radians(wd))
    V = V + ws * -np.cos(np.radians(wd))
n = h1 - h0 + 1
U, V = U / n, V / n                           # mean vector the wind blows towards
spd = np.hypot(U, V)
wfrom = (np.degrees(np.arctan2(-U, -V)) + 360) % 360
to_e, to_n = U / np.maximum(spd, 1e-9), V / np.maximum(spd, 1e-9)
align = np.clip(to_e * down_e + to_n * down_n, 0, 1)
expo = align * np.clip(slope / SLOPE_FULL, 0, 1)

ll = osr.SpatialReference()
ll.ImportFromEPSG(4326)
ll.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
tr = osr.CoordinateTransformation(ll, osr.SpatialReference(wkt=L.GetProjection()))
pts = [("Ignition (Chimney Tops)", -83.47833, 35.62889, "*", 15), ("Gatlinburg", -83.5102, 35.7143, "o", 9)]

px = np.array([tr.TransformPoint(lo, la)[0] for _, lo, la, _, _ in pts])
xmin, xmax, ymin, ymax = 263000, 288000, 3937000, 3962000      # ~25 x 25 km around the fire
ext = list(bounds[0:1]) + [bounds[2], bounds[1], bounds[3]]
ls = LightSource(azdeg=315, altdeg=45)
hill = ls.hillshade(dem30, vert_exag=1.5, dx=30, dy=30)

fig, axs = plt.subplots(1, 3, figsize=(19, 7.6), constrained_layout=True)
a = axs[0]
a.imshow(hill, extent=ext, origin="upper", cmap="gray", alpha=1.0)
im = a.imshow(dem30, extent=ext, origin="upper", cmap="terrain", alpha=0.55, vmin=300, vmax=2000)
fig.colorbar(im, ax=a, shrink=0.7, label="Elevation (m)")
step = max(1, int(2400 / smooth))
xs = bounds[0] + (np.arange(dem.shape[1]) + 0.5) * smooth
ys = bounds[3] - (np.arange(dem.shape[0]) + 0.5) * smooth
XX, YY = np.meshgrid(xs, ys)
a.quiver(XX[::step, ::step], YY[::step, ::step], U[::step, ::step], V[::step, ::step], color="#b30000",
         scale=600, width=0.004)
mf = (np.degrees(np.arctan2(-U.mean(), -V.mean())) + 360) % 360
a.set_title(f"(a) Elevation + HRRR wind, 28 Nov {h0:02d}:00-{h1:02d}:00 EST\nmean wind from {mf:.0f} deg, {spd.mean():.0f} mph (20 ft)", fontsize=11)

a = axs[1]
im = a.imshow(np.degrees(np.arctan(slope)), extent=ext, origin="upper", cmap="YlOrBr", vmin=0, vmax=35)
a.imshow(hill, extent=ext, origin="upper", cmap="gray", alpha=0.25)
fig.colorbar(im, ax=a, shrink=0.7, label="Slope (degrees)")
a.set_title(f"(b) Slope, terrain smoothed to {smooth:.0f} m", fontsize=11)

a = axs[2]
a.imshow(hill, extent=ext, origin="upper", cmap="gray", alpha=0.6)
im = a.imshow(np.where(expo > 0.02, expo, np.nan), extent=ext, origin="upper", cmap="Reds", vmin=0, vmax=1, alpha=0.85)
cb = fig.colorbar(im, ax=a, shrink=0.7)
cb.set_label("Downslope exposure (0-1)")
a.set_title("(c) Where the wind blows down the slope\n(lee slopes facing away from the wind)", fontsize=11)

for a in axs:
    for lx, ly in perimeter_lines(shp):
        a.plot(lx, ly, color="#1f5fbf", lw=1.4)
    for name, lo, la, mk, ms in pts:
        x, y, _ = tr.TransformPoint(lo, la)
        a.plot(x, y, mk, color="black" if mk == "o" else "#ffd400", ms=ms, mec="black", mew=1, zorder=6, label=name)
    a.set_xlim(xmin, xmax)
    a.set_ylim(ymin, ymax)
    a.set_aspect("equal")
    a.set_xticks([])
    a.set_yticks([])
axs[0].legend(loc="lower left", fontsize=8.5, framealpha=0.95)
add_scalebar(axs[2], xmax - 5000 - 1200, ymin + 900, 5000, 2, 250)
axs[0].annotate("N", xy=(xmin + 1800, ymax - 900), xytext=(xmin + 1800, ymax - 3000), ha="center",
                fontsize=13, fontweight="bold", arrowprops=dict(arrowstyle="-|>", color="black", lw=2))
fig.suptitle("Chimney Tops 2 Fire: where a downslope wind effect can be expected (blue: observed MTBS perimeter)",
             fontsize=13)
fig.savefig(out, dpi=150, facecolor="white")

# Share of the perimeter area with strong exposure
from compare_perimeter import rasterise
m = gdal.GetDriverByName("MEM").Create("", dem.shape[1], dem.shape[0], 1, gdal.GDT_Byte)
m.SetGeoTransform((bounds[0], smooth, 0, bounds[3], 0, -smooth))
m.SetProjection(L.GetProjection())
obs = rasterise(shp, m)
print(f"mean wind from {mf:.0f} deg; inside MTBS perimeter: {100*(expo[obs] > 0.5).mean():.0f}% strongly exposed (>0.5), "
      f"{100*(expo[obs] > 0.02).mean():.0f}% some exposure; whole map: {100*(expo > 0.5).mean():.0f}% strongly exposed")
print("wrote", out)
