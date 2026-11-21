#!/usr/bin/env python3
"""Exposure of buildings at ignition (for the laboratory test matrix): heat flux, wind and ember load.

Usage: python analyse_ignition_exposure.py PERIMETER.shp
Runs: ignition_pathway/<location>/seed_1..10 (50 runs, pathway build). Building cells with >= 1 building
centroid inside the MTBS perimeter; every ignited cell of every run is one sample.
  heat flux     path_q: WU-E heat flux (flame contact + radiation) on the cell at its last unignited step, kW/m2
  flame contact path_frac_dfc share of that heat
  wind          20-ft wind speed (ws input, mph) at the cell, interpolated in time to the ignition time
                (ELMFIRE blends hourly bands linearly); also given in m/s
  ember load    accumulated ember flux on the cell over the whole run (ember_flux.tif, embers per cell)
                -> g/cm2 with 0.2 g per ember, as in the ember ignition criterion
Not-ignited cells: path_q is the heat on the last step it received any (not the peak).
Writes ignition_exposure/{exposure_summary.csv, ignition_exposure.png}.
"""
import sys, glob, os
import numpy as np
from osgeo import gdal, ogr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

gdal.UseExceptions(); ogr.UseExceptions()
shp = sys.argv[1]
LOCS = ["spot2", "spot2_N1km", "spot2_S1km", "spot2_E1km", "spot2_W1km"]
OUT = "ignition_exposure"; os.makedirs(OUT, exist_ok=True)
T0 = 11.0


def rd(p, k=None):
    ds = gdal.Open(p); return ds.ReadAsArray() if k is None else ds.GetRasterBand(k).ReadAsArray()


inp = "ms_st09/spot2/inputs/"
L = gdal.Open(inp + "landscape.tif"); gt = L.GetGeoTransform(); fuel = rd(inp + "landscape.tif", 4); cnt = rd(inp + "bldg_count.tif")
m = gdal.GetDriverByName("MEM").Create("", L.RasterXSize, L.RasterYSize, 1, gdal.GDT_Byte)
m.SetGeoTransform(gt); m.SetProjection(L.GetProjection())
pds = ogr.Open(shp); gdal.RasterizeLayer(m, [1], pds.GetLayer(), burn_values=[1]); per = m.ReadAsArray() == 1
bsel = (fuel == 91) & per & (cnt > 0)

# wind: 600 m grid, hourly bands -> value at each fine cell (nearest coarse cell)
W = gdal.Open(inp + "ws.tif"); wgt = W.GetGeoTransform(); ws = W.ReadAsArray().astype(float)   # (bands, y, x) mph
ii, jj = np.where(bsel)
xc = gt[0] + (jj + 0.5) * gt[1]; yc = gt[3] - (ii + 0.5) * gt[1]
wj = ((xc - wgt[0]) / wgt[1]).astype(int); wi = ((wgt[3] - yc) / -wgt[5]).astype(int)

Q, D, U, PSI, T, Qn = [], [], [], [], [], []
for loc in LOCS:
    for s in range(1, 11):
        o = "ignition_pathway/%s/seed_%d/outputs/" % (loc, s)
        if not glob.glob(o + "path_q_*.tif"):
            continue
        t = rd(glob.glob(o + "time_of_arrival_*.tif")[0])[ii, jj]; q = rd(glob.glob(o + "path_q_*.tif")[0])[ii, jj]
        fd = rd(glob.glob(o + "path_frac_dfc_*.tif")[0])[ii, jj]; ef = rd(o + "ember_flux.tif")[ii, jj]
        ig = t > 0
        h = t[ig] / 3600.0; b0 = np.clip(np.floor(h).astype(int), 0, ws.shape[0] - 1); b1 = np.clip(b0 + 1, 0, ws.shape[0] - 1); f = h - np.floor(h)
        u = ws[b0, wi[ig], wj[ig]] * (1 - f) + ws[b1, wi[ig], wj[ig]] * f
        Q.append(q[ig]); D.append(fd[ig]); U.append(u); PSI.append(ef[ig] / 900.0 * 0.2 / 1e4); T.append(h)
        Qn.append(q[~ig & (q > 0)])
Q, D, U, PSI, T, Qn = [np.concatenate(a) for a in (Q, D, U, PSI, T, Qn)]
print("samples (ignited building cells, all runs): %d" % len(Q))
rows = [("heat flux at ignition (kW/m2)", Q), ("flame-contact share of heat", D), ("20-ft wind at ignition (mph)", U),
        ("20-ft wind at ignition (m/s)", U * 0.447), ("accumulated ember load on cell (g/cm2)", PSI),
        ("heat flux, cells never ignited, last value (kW/m2)", Qn)]
pc = [5, 25, 50, 75, 95]
with open(OUT + "/exposure_summary.csv", "w") as f:
    f.write("quantity,n," + ",".join("p%d" % p for p in pc) + ",max\n")
    print("%-52s %7s " % ("quantity", "n") + " ".join("%9s" % ("p%d" % p) for p in pc) + " %9s" % "max")
    for k, a in rows:
        v = np.percentile(a, pc)
        f.write("%s,%d," % (k, len(a)) + ",".join("%.5g" % x for x in v) + ",%.5g\n" % a.max())
        print("%-52s %7d " % (k, len(a)) + " ".join("%9.4g" % x for x in v) + " %9.4g" % a.max())
NEED = 0.211 / ((1.35 + 0.073) * (4.111 - 1.35)) / 7.0
print("ember ignition threshold at 1.35 m/s roof wind: %.5f g/cm2; largest load on an ignited building cell: %.5f (%.1fx short)"
      % (NEED, PSI.max(), NEED / PSI.max()))

fig, axs = plt.subplots(1, 3, figsize=(16, 4.8), facecolor="white")
ax = axs[0]
ax.hist(np.clip(Q, 0.1, 500), bins=np.logspace(-1, np.log10(500), 50), color="#7a3b8f", edgecolor="white", linewidth=0.5)
ax.text(0.98, 0.6, "%d cells (%.2f%%) above 500\nkW/m² shown in last bin" % ((Q > 500).sum(), 100 * (Q > 500).mean()), transform=ax.transAxes, ha="right", fontsize=7.5, color="#555555")
ax.set_xscale("log"); ax.set_xlabel("heat flux on the building cell at ignition (kW/m²)", fontsize=9); ax.set_ylabel("ignited building cells (all 50 runs)", fontsize=9)
for (p_, ls), yf in zip([(25, ":"), (50, "-"), (75, ":")], (0.97, 0.89, 0.81)):
    v = np.percentile(Q, p_); ax.axvline(v, color="#333333", ls=ls, lw=1.2); ax.text(v, ax.get_ylim()[1] * yf, " p%d = %.0f" % (p_, v), fontsize=8, va="top",
                                                                                  bbox=dict(fc="white", ec="none", pad=0.5))
ax.set_title("A. Heat flux at ignition (%.0f%% by flame contact)" % (100 * np.median(D)), fontsize=10.5, loc="left")
ax = axs[1]
ax.hist(U * 0.447, bins=40, color="#2b7bba", edgecolor="white", linewidth=0.5)
ax.set_xlabel("20-ft wind speed at ignition (m/s)", fontsize=9); ax.set_ylabel("ignited building cells", fontsize=9)
for p_, ls in [(5, ":"), (50, "-"), (95, ":")]:
    v = np.percentile(U * 0.447, p_); ax.axvline(v, color="#333333", ls=ls, lw=1.2); ax.text(v, ax.get_ylim()[1] * 0.95, " p%d = %.1f" % (p_, v), fontsize=8, va="top")
ax.set_title("B. Wind at the time of ignition", fontsize=10.5, loc="left")
ax = axs[2]
pos = PSI[PSI > 0]
ax.hist(pos, bins=np.logspace(np.log10(pos.min()), np.log10(max(NEED * 1.5, pos.max())), 50), color="#c0392b", edgecolor="white", linewidth=0.5)
ax.set_xscale("log"); ax.axvline(NEED, color="#e07b24", lw=2); ax.text(NEED, ax.get_ylim()[1] * 0.9, " ignition\n threshold\n %.4f" % NEED, fontsize=8, color="#b35900", va="top")
ax.set_xlabel("accumulated ember load on the building cell (g/cm²)", fontsize=9); ax.set_ylabel("ignited building cells", fontsize=9)
ax.set_title("C. Ember load (%.0f%% of cells received embers)" % (100 * (PSI > 0).mean()), fontsize=10.5, loc="left")
for a in axs:
    a.spines[["top", "right"]].set_visible(False); a.tick_params(labelsize=8)
fig.suptitle("Exposure of buildings at ignition, 50 ELMFIRE runs (inside MTBS perimeter): ranges for the laboratory tests",
             fontsize=12.5, weight="bold", x=0.01, ha="left")
fig.tight_layout(rect=(0, 0, 1, 0.94)); fig.savefig(OUT + "/ignition_exposure.png", dpi=150, facecolor="white")
print("wrote %s/ignition_exposure.png, exposure_summary.csv" % OUT)
