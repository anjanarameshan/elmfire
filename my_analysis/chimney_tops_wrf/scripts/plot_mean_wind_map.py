#!/usr/bin/env python3
"""Map of the period-mean 10 m wind from our HRRR inputs, in the style of Fig. 1 (right) of
Jimenez et al. (2018): mean wind speed (shaded, m/s), mean wind vectors (arrows), observed MTBS
perimeter (purple), urban / no-fuel cells (orange) and, optionally, a simulated ELMFIRE perimeter
(black).

Usage: python plot_mean_wind_map.py RUN_DIR PERIMETER.shp OUT.png [SIM_RUN_DIR]
  RUN_DIR      ELMFIRE run folder holding hrrr_wind/ws.tif, wd.tif (hourly bands, 20 ft wind in mph
               as given to ELMFIRE) and inputs/landscape.tif (band 4 = fuel model)
  SIM_RUN_DIR  optional run whose final burned area is outlined in black

ws.tif holds 20 ft wind (10 m wind x 0.87, mph); it is converted back to 10 m m/s here so the
colour scale matches the paper (0-20 m/s). Mean speed = mean of hourly speeds; arrows = mean of
hourly (u, v), shown every few cells.
"""
import sys, glob
import numpy as np
from osgeo import gdal, ogr, osr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

gdal.UseExceptions()
run, shp, out = sys.argv[1:4]
sim = sys.argv[4] if len(sys.argv) > 4 else None
TO_MS_10M = 1 / 2.2369363 / 0.87
EXT = (-83.545, -83.385, 35.602, 35.765)          # lon/lat window of the paper's figure

ws_ds = gdal.Open(run + "/hrrr_wind/ws.tif"); wd_ds = gdal.Open(run + "/hrrr_wind/wd.tif")
ws = ws_ds.ReadAsArray().astype(float) * TO_MS_10M
wd = np.radians(wd_ds.ReadAsArray().astype(float))
u, v = -ws * np.sin(wd), -ws * np.cos(wd)          # wd = direction the wind blows FROM
mean_speed, mu, mv = ws.mean(0), u.mean(0), v.mean(0)
nb = ws.shape[0]


def lonlat(ds, shape):
    gt = ds.GetGeoTransform()
    ny, nx = shape
    X, Y = np.meshgrid(gt[0] + (np.arange(nx) + 0.5) * gt[1], gt[3] + (np.arange(ny) + 0.5) * gt[5])
    src = osr.SpatialReference(); src.ImportFromWkt(ds.GetProjection()); src.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    wgs = osr.SpatialReference(); wgs.ImportFromEPSG(4326); wgs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    p = np.array(osr.CoordinateTransformation(src, wgs).TransformPoints(np.column_stack([X.ravel(), Y.ravel()]).tolist()))
    return p[:, 0].reshape(ny, nx), p[:, 1].reshape(ny, nx)


LON, LAT = lonlat(ws_ds, mean_speed.shape)
# HRRR winds are relative to true north already (hrrr_winds.py rotates them); the map is lon/lat, so
# arrow components are plotted as east/north directly.

land = gdal.Open(run + "/inputs/landscape.tif")
fuel = land.GetRasterBand(4).ReadAsArray()
FLON, FLAT = lonlat(land, fuel.shape)
nofuel = np.isin(fuel, [91, 92, 93, 98, 99])        # urban, snow/ice, agriculture, water, barren

fig, ax = plt.subplots(figsize=(8, 8.6))
pm = ax.pcolormesh(LON, LAT, mean_speed, cmap="viridis", vmin=0, vmax=20, shading="auto")
step = 2
sl = (slice(None, None, step), slice(None, None, step))
ax.quiver(LON[sl], LAT[sl], mu[sl], mv[sl], color="#2b2b2b", scale=80, width=0.0035, headwidth=4)
ax.contourf(FLON, FLAT, nofuel.astype(float), levels=[0.5, 1.5], colors=["#ff7f50"], alpha=0.9)

sr = osr.SpatialReference(); sr.ImportFromEPSG(4326); sr.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
ds = ogr.Open(shp); lyr = ds.GetLayer(); tr = osr.CoordinateTransformation(lyr.GetSpatialRef(), sr)
for feat in lyr:
    g = feat.GetGeometryRef().Clone(); g.Transform(tr)
    polys = [g.GetGeometryRef(i) for i in range(g.GetGeometryCount())] if g.GetGeometryCount() > 1 or "MULTI" in g.GetGeometryName() else [g]
    for pg in polys:
        r = pg.GetGeometryRef(0)
        pts = np.array([r.GetPoint_2D(i) for i in range(r.GetPointCount())])
        ax.plot(pts[:, 0], pts[:, 1], color="#c000ff", lw=1.6)

label_sim = ""
if sim:
    toa = gdal.Open(sorted(glob.glob(sim + "/outputs/time_of_arrival_*.tif"))[-1])
    burned = (toa.ReadAsArray() >= 0).astype(float)
    SLON, SLAT = lonlat(toa, burned.shape)
    ax.contour(SLON, SLAT, burned, levels=[0.5], colors="black", linewidths=1.4)
    label_sim = "; black: ELMFIRE final burned area"

ax.set_xlim(EXT[0], EXT[1]); ax.set_ylim(EXT[2], EXT[3])
ax.set_aspect(1 / np.cos(np.radians(35.68)))
ax.set_xlabel("longitude [$^\\circ$]"); ax.set_ylabel("latitude [$^\\circ$]")
cb = fig.colorbar(pm, ax=ax, orientation="horizontal", location="top", shrink=0.85, pad=0.03)
cb.set_label("10-m wind speed [m s$^{-1}$], HRRR, mean of %d hourly analyses" % nb)
ax.set_title("26 Nov 14:00 - 29 Nov 14:00 LST 2016.  Purple: MTBS perimeter; orange: urban / no fuel%s" % label_sim,
             fontsize=9, pad=4)
fig.savefig(out, dpi=150, bbox_inches="tight")
i = np.unravel_index(np.argmax(np.where((LON > EXT[0]) & (LON < EXT[1]) & (LAT > EXT[2]) & (LAT < EXT[3]), mean_speed, -1)), mean_speed.shape)
print("wrote %s | %d hours | mean speed in window: %.1f m/s, max %.1f m/s at %.3f N %.3f W" % (
    out, nb, mean_speed[(LON > EXT[0]) & (LON < EXT[1]) & (LAT > EXT[2]) & (LAT < EXT[3])].mean(),
    mean_speed[i], LAT[i], -LON[i]))
