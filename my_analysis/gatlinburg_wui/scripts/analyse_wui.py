#!/usr/bin/env python3
"""Structure-ignition probability from an ensemble of Gatlinburg ember cases.

Usage: python analyse_wui.py TAG_DIR PERIMETER.shp OUT_PREFIX
  TAG_DIR   e.g. osm/ - holds one folder per case (spot2, spot2_N1km, ...) each with inputs/ and seed_*/
Writes OUT_PREFIX_summary.csv and OUT_PREFIX_map.png

Definitions (per case, over its seeds):
  building cell        fuel 91 in the case landscape (cell holding building footprints)
  ignited              time of arrival > 0 in a building cell (ELMFIRE building model: ignited by embers
                       through the PHYSICAL criterion or by heat from burning neighbours)
  ember-exposed        accumulated ember flux > 0 in the cell
  ignition probability fraction of seeds in which the cell ignited
  structures ignited   sum of bldg_count over ignited building cells (per seed: mean, min, max)
  in perimeter         building cells whose centre lies inside the MTBS burn perimeter
"""
import sys, glob, os, csv
import numpy as np
from osgeo import gdal, ogr, osr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, LinearSegmentedColormap
from matplotlib.lines import Line2D

gdal.UseExceptions()
tagdir, shp, outp = sys.argv[1:4]
DOWNTOWN = (35.7143, -83.5102)
EXT = (-83.575, -83.440, 35.650, 35.760)
SPOTS = {"spot2": (0, 0), "spot2_N1km": (0.00899, 0), "spot2_S1km": (-0.00899, 0),
         "spot2_E1km": (0, 0.01107), "spot2_W1km": (0, -0.01107)}
OBS = (35.690, -83.497)

cases = [c for c in SPOTS if os.path.isdir(os.path.join(tagdir, c))]
L = gdal.Open(os.path.join(tagdir, cases[0], "inputs", "landscape.tif"))
gt, prj = L.GetGeoTransform(), L.GetProjection()
ny, nx = L.RasterYSize, L.RasterXSize
srs = osr.SpatialReference(); srs.ImportFromWkt(prj); srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
wgs = osr.SpatialReference(); wgs.ImportFromEPSG(4326); wgs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
to_xy = osr.CoordinateTransformation(wgs, srs)
X, Y = np.meshgrid(gt[0] + (np.arange(nx) + 0.5) * gt[1], gt[3] + (np.arange(ny) + 0.5) * gt[5])
gx, gy, _ = to_xy.TransformPoint(DOWNTOWN[1], DOWNTOWN[0])
# MTBS burn perimeter on the case grid (cell centre inside)
_m = gdal.GetDriverByName("MEM").Create("", nx, ny, 1, gdal.GDT_Byte); _m.SetGeoTransform(gt); _m.SetProjection(prj)
_p = ogr.Open(shp); gdal.RasterizeLayer(_m, [1], _p.GetLayer(), burn_values=[1])
inper = _m.ReadAsArray() == 1; _m = _p = None


def band(path, k=1):
    ds = gdal.Open(path)
    return ds.GetRasterBand(k).ReadAsArray()


def ll2xy(lat, lon):
    return to_xy.TransformPoint(lon, lat)[:2]


rows, panels = [], []
for c in cases:
    d = os.path.join(tagdir, c)
    fuel = band(d + "/inputs/landscape.tif", 4)
    cnt = gdal.Open(d + "/inputs/bldg_count.tif").ReadAsArray()
    b = fuel == 91
    seeds = sorted(glob.glob(d + "/seed_*"))
    burn = np.zeros((ny, nx)); ign = np.zeros((ny, nx)); emb = np.zeros((ny, nx))
    n_str, n_str_per, n_exp, acres, n_emb, veg_emb_frac = [], [], [], [], [], []
    for s in seeds:
        toa = gdal.Open(sorted(glob.glob(s + "/outputs/time_of_arrival_*.tif"))[-1]).ReadAsArray()
        ef = gdal.Open(s + "/outputs/ember_flux.tif").ReadAsArray()
        bu = toa > 0; ig = b & bu
        burn += bu; ign += ig; emb += ef
        n_str.append(cnt[ig].sum()); n_str_per.append(cnt[ig & inper].sum()); n_exp.append(cnt[b & (ef > 0)].sum())
        # cells ignited by the spotting algorithm (DUMP_EMBER_IGNITION), if written
        eg = glob.glob(s + "/outputs/ember_ignition_*.tif")
        if eg:
            ei = gdal.Open(eg[0]).ReadAsArray() > 0
            n_emb.append(cnt[ei & b & inper].sum()); veg_emb_frac.append((ei & ~b & bu).sum() / max((~b & bu).sum(), 1))
        acres.append(bu.sum() * gt[1] ** 2 / 4046.86)
    n = len(seeds); burn /= n; ign /= n; emb /= n
    sx, sy = ll2xy(OBS[0] + SPOTS[c][0], OBS[1] + SPOTS[c][1])
    # direction of spread: bearing from the spot to the centroid of the burn-probability field
    w = burn.sum(); cx, cy = (burn * X).sum() / w, (burn * Y).sum() / w
    brg = np.degrees(np.arctan2(cx - sx, cy - sy)) % 360
    brg_g = np.degrees(np.arctan2(gx - sx, gy - sy)) % 360
    rows.append(dict(case=c, seeds=n, bldg_total=int(cnt[b].sum()), bldg_in_perimeter=int(cnt[b & inper].sum()),
                     acres_mean=round(np.mean(acres)), str_ign_mean=round(np.mean(n_str)), str_ign_min=int(min(n_str)),
                     str_ign_max=int(max(n_str)), str_ign_in_perimeter_mean=round(np.mean(n_str_per)),
                     str_ign_in_perimeter_min=int(min(n_str_per)), str_ign_in_perimeter_max=int(max(n_str_per)),
                     str_ember_exposed_mean=round(np.mean(n_exp)),
                     str_ember_ignited_in_perimeter_mean=round(np.mean(n_emb)) if n_emb else "",
                     pct_veg_burn_by_embers=round(100 * np.mean(veg_emb_frac), 1) if veg_emb_frac else "",
                     pct_bldg_ignited=round(100 * np.mean(n_str) / max(cnt[b].sum(), 1), 1),
                     spread_bearing_deg=round(brg), bearing_to_downtown_deg=round(brg_g)))
    panels.append((c, burn, np.where(b, ign, np.nan), (sx, sy), rows[-1]))
    print(rows[-1])

with open(outp + "_summary.csv", "w", newline="") as f:
    wr = csv.DictWriter(f, list(rows[0])); wr.writeheader(); wr.writerows(rows)

# ---------------- map ----------------
to_ll = osr.CoordinateTransformation(srs, wgs)
p = np.array(to_ll.TransformPoints(np.column_stack([X.ravel(), Y.ravel()]).tolist()))
LON, LAT = p[:, 0].reshape(ny, nx), p[:, 1].reshape(ny, nx)
fuel0 = band(os.path.join(tagdir, cases[0], "inputs", "landscape.tif"), 4)
roads = np.where(fuel0 == 99, 1.0, np.nan); water = np.where(fuel0 == 98, 1.0, np.nan)
perim = []
ds = ogr.Open(shp); lyr = ds.GetLayer(); tr = osr.CoordinateTransformation(lyr.GetSpatialRef(), wgs)
for ft in lyr:
    g = ft.GetGeometryRef().Clone(); g.Transform(tr)
    for pg in ([g.GetGeometryRef(i) for i in range(g.GetGeometryCount())] if "MULTI" in g.GetGeometryName() else [g]):
        r = pg.GetGeometryRef(0); perim.append(np.array([r.GetPoint_2D(i) for i in range(r.GetPointCount())]))

burn_cm = LinearSegmentedColormap.from_list("yr", ["#fff7bc", "#fec44f", "#ec7014", "#cc1f1f"])
ign_cm = LinearSegmentedColormap.from_list("ig", ["#6a51a3", "#3f007d", "#000000"])
nc = len(panels)
fig, axs = plt.subplots(1, nc, figsize=(4.6 * nc, 5.6), squeeze=False)
for ax, (c, burn, ign, (sx, sy), r) in zip(axs[0], panels):
    sl = (LON > EXT[0] - .01) & (LON < EXT[1] + .01) & (LAT > EXT[2] - .01) & (LAT < EXT[3] + .01)
    jj = np.where(sl.any(0))[0]; ii = np.where(sl.any(1))[0]
    s = (slice(ii[0], ii[-1] + 1), slice(jj[0], jj[-1] + 1))
    pm = ax.pcolormesh(LON[s], LAT[s], np.where(burn[s] > 0, burn[s], np.nan), cmap=burn_cm, vmin=0, vmax=1, shading="auto")
    ax.pcolormesh(LON[s], LAT[s], roads[s], cmap=ListedColormap(["#5c3317"]), shading="auto")
    ax.pcolormesh(LON[s], LAT[s], water[s], cmap=ListedColormap(["#0a8fb8"]), shading="auto")
    gi = np.where(np.isnan(ign[s]), np.nan, ign[s])
    bm = ax.pcolormesh(LON[s], LAT[s], np.where(gi > 0, gi, np.nan), cmap=ign_cm, vmin=0, vmax=1, shading="auto")
    ax.pcolormesh(LON[s], LAT[s], np.where(gi == 0, 1, np.nan), cmap=ListedColormap(["#39a845"]), shading="auto")
    for q in perim:
        ax.plot(q[:, 0], q[:, 1], color="#1f5fbf", lw=1.2)
    ax.plot(DOWNTOWN[1], DOWNTOWN[0], "k*", ms=11)
    lo, la = OBS[1] + SPOTS[c][1], OBS[0] + SPOTS[c][0]
    ax.plot(OBS[1], OBS[0], "o", mfc="none", mec="k", ms=9)
    ax.plot(lo, la, "^", color="#00e5ff", mec="k", ms=10)
    ax.set_xlim(EXT[0], EXT[1]); ax.set_ylim(EXT[2], EXT[3]); ax.set_aspect(1 / np.cos(np.radians(35.7)))
    ax.tick_params(labelsize=7)
    ax.set_title("%s (%d runs)\ninside burn perimeter: %d of %d buildings ignited\n(range %d-%d; by embers: %s)"
                 % (c.replace("spot2", "spot fire 2").replace("_", " ") if c != "spot2" else "spot fire 2 (observed)",
                    r["seeds"], r["str_ign_in_perimeter_mean"], r["bldg_in_perimeter"], r["str_ign_in_perimeter_min"],
                    r["str_ign_in_perimeter_max"], r["str_ember_ignited_in_perimeter_mean"]), fontsize=9)
cb = fig.colorbar(pm, ax=axs[0].tolist(), orientation="horizontal", fraction=0.04, pad=0.08, shrink=0.4, anchor=(0.5, 0))
cb.set_label("burn probability (share of runs)", fontsize=8)
fig.legend(handles=[Line2D([], [], color="#1f5fbf", lw=1.4, label="MTBS perimeter"),
                    Line2D([], [], ls="", marker="*", color="k", ms=10, label="downtown Gatlinburg"),
                    Line2D([], [], ls="", marker="o", mfc="none", mec="k", ms=8, label="observed spot fire 2"),
                    Line2D([], [], ls="", marker="^", color="#00e5ff", mec="k", ms=9, label="ignition used"),
                    Line2D([], [], ls="", marker="s", color="#000000", ms=8, label="building cell ignited"),
                    Line2D([], [], ls="", marker="s", color="#39a845", ms=8, label="building cell not ignited"),
                    Line2D([], [], ls="", marker="s", color="#5c3317", ms=8, label="roads / paved"),
                    Line2D([], [], ls="", marker="s", color="#0a8fb8", ms=8, label="water")],
           loc="upper center", ncol=8, fontsize=8, bbox_to_anchor=(0.5, 1.02))
fig.savefig(outp + "_map.png", dpi=140, bbox_inches="tight")
print("wrote", outp + "_summary.csv", outp + "_map.png")
