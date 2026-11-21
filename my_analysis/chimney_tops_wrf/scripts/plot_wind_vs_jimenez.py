#!/usr/bin/env python3
"""Domain-mean wind over the 13 x 13 km box of Jimenez et al. (2018): their WRF-Fire SIM1 (Fig. 2, digitised),
our HRRR 3 km analyses, and the CloudFire wind used by ELMFIRE (20 ft, converted to m/s).
Usage: python plot_wind_vs_jimenez.py SERIES.csv CLOUDFIRE_INPUTS_DIR OUT.png
SERIES.csv from hrrr_vs_paper_fig2.py; CloudFire ws/wd band 1 = 27 Nov 2016 13:00 LST.
"""
import sys
import numpy as np, pandas as pd
from osgeo import gdal, osr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

gdal.UseExceptions()
BOX = (-83.545, 35.602, -83.405, 35.720)
p = pd.read_csv(sys.argv[1]); p["t"] = pd.to_datetime(p.time_lst)
ws = gdal.Open(sys.argv[2] + "/ws.tif"); wd = gdal.Open(sys.argv[2] + "/wd.tif"); gt = ws.GetGeoTransform()
s = osr.SpatialReference(); s.ImportFromEPSG(4326); s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
t = osr.SpatialReference(); t.ImportFromWkt(ws.GetProjection()); ct = osr.CoordinateTransformation(s, t)
(x0, y0, _), (x1, y1, _) = ct.TransformPoint(BOX[0], BOX[1]), ct.TransformPoint(BOX[2], BOX[3])
c0, c1 = int((x0 - gt[0]) / gt[1]), int((x1 - gt[0]) / gt[1]); r0, r1 = int((y1 - gt[3]) / gt[5]), int((y0 - gt[3]) / gt[5])
W, D = [], []
for b in range(1, ws.RasterCount + 1):
    W.append(ws.GetRasterBand(b).ReadAsArray()[r0:r1 + 1, c0:c1 + 1].mean() * 0.44704)        # mph -> m/s
    a = np.radians(wd.GetRasterBand(b).ReadAsArray()[r0:r1 + 1, c0:c1 + 1])
    D.append(np.degrees(np.arctan2(np.sin(a).mean(), np.cos(a).mean())) % 360)
cf = pd.DataFrame({"t": pd.date_range("2016-11-27 13:00", periods=len(W), freq="h"), "cf_ws": W, "cf_wd": D})
d = cf.merge(p, on="t")

fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 6.4), sharex=True, gridspec_kw=dict(hspace=0.08))
for a, k, lab in [(a1, "ws", "10-m wind speed [m s$^{-1}$]"), (a2, "wd", "wind direction [$^\\circ$]")]:
    a.plot(d.t, d["paper_" + k], color="#1f2328", lw=2, label="Jiménez et al. (2018), WRF-Fire 111 m (Fig. 2)")
    a.plot(d.t, d["cf_" + k], color="#c2412d", lw=1.6, ls="--", label="CloudFire, used by ELMFIRE (20 ft)")
    a.plot(d.t, d["hrrr_" + k], color="#2e6b9a", lw=1.2, ls=":", label="HRRR 3 km analyses")
    a.set_ylabel(lab); a.grid(alpha=0.3)
a1.set_ylim(0, 18); a2.set_ylim(0, 360); a2.set_yticks([0, 90, 180, 270, 360])
a1.legend(loc="upper left", fontsize=9, frameon=False)
a2.set_xlabel("time, LST (EST = UTC − 5), 27–29 Nov 2016")
fig.suptitle("Mean wind over the 13 × 13 km domain of Jiménez et al. (2018)", fontsize=12)
fig.savefig(sys.argv[3], dpi=150, bbox_inches="tight")
r = lambda k: np.corrcoef(d[k + "_ws"], d.paper_ws)[0, 1]
dd = lambda k: ((d[k + "_wd"] - d.paper_wd + 180) % 360 - 180).abs().median()
for k in ("cf", "hrrr"):
    i = d[k + "_ws"].idxmax()
    print(f"{k}: r(speed)={r(k):.2f}, median |dir diff|={dd(k):.0f} deg, peak {d[k+'_ws'][i]:.1f} m/s at {d.t[i]:%d %H:%M}")
i = d.paper_ws.idxmax(); print(f"paper peak {d.paper_ws[i]:.1f} at {d.t[i]:%d %H:%M}; {len(d)} hours"); print(sys.argv[3])
