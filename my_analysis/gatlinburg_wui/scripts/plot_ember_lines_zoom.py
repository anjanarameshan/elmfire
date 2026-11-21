#!/usr/bin/env python3
"""Zoom on one run to show how the low-probability ember 'lines' form and why they are curved / fan out.

Usage: python plot_ember_lines_zoom.py CASE_DIR SEED X0 X1 Y0 Y1 OUT.png
  CASE_DIR  e.g. ms_st09/spot2 (inputs/ws.tif, inputs/wd.tif, inputs/landscape.tif, seed_N/outputs)
  X0..Y1    zoom window in metres (projected CRS of the run)

Left:  cells ignited by embers (DUMP_EMBER_IGNITION) in the last hour, coloured by ignition time;
       arrows = ember-transport wind direction exactly as EMBER_TRAJECTORY_EULERIAN computes it
       (hourly bands 16 = 02:00 and 17 = 03:00 EST, direction blended linearly in 'to' degrees,
       no 360-degree wrap) at the time the middle group of lines ignited; thin lines = 600 m wind cells.
Right: that blended direction over 02:00-03:00 for one wind cell, against the shortest-turn blend.
"""
import sys, glob
import numpy as np
from osgeo import gdal
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

gdal.UseExceptions()
case, seed = sys.argv[1], int(sys.argv[2])
X0, X1, Y0, Y1 = map(float, sys.argv[3:7]); out = sys.argv[7]
T0 = 15.0                                            # 02:00 EST = 15 h after 11:00


def rd(p, k=1):
    ds = gdal.Open(p); return ds.GetRasterBand(k).ReadAsArray(), ds.GetGeoTransform()


o = "%s/seed_%d/outputs" % (case, seed)
t, gt = rd(glob.glob(o + "/time_of_arrival_*.tif")[0])
ei, _ = rd(glob.glob(o + "/ember_ignition_*.tif")[0])
fuel, _ = rd(case + "/inputs/landscape.tif", 4)
wd16, gw = rd(case + "/inputs/wd.tif", 16); wd17, _ = rd(case + "/inputs/wd.tif", 17)


def to_dir(a):
    a = a + 180.0; return np.where(a > 360, a - 360, a)


def code_blend(f):                                   # as in EMBER_TRAJECTORY_EULERIAN
    w = to_dir(wd16) + f * (to_dir(wd17) - to_dir(wd16))
    return np.where(w > 360, w - 360, np.where(w < 0, w + 360, w))


ny, nx = t.shape
xs = gt[0] + gt[1] * (np.arange(nx) + 0.5); ys = gt[3] + gt[5] * (np.arange(ny) + 0.5)
jj = np.where((xs >= X0) & (xs <= X1))[0]; ii = np.where((ys >= Y0) & (ys <= Y1))[0]
s = (slice(ii[0], ii[-1] + 1), slice(jj[0], jj[-1] + 1))
ext = [(xs[jj[0]] - 15 - X0) / 1e3, (xs[jj[-1]] + 15 - X0) / 1e3, (ys[ii[-1]] - 15 - Y0) / 1e3, (ys[ii[0]] + 15 - Y0) / 1e3]

hrs = t[s] / 3600.0
late = (ei[s] > 0) & (hrs > T0)
late = late & (hrs > T0 + 0.5)                                    # keep the last half hour: the line groups
mins = np.round((hrs[late] - T0) * 60, 1)
times, nc = np.unique(mins, return_counts=True)                   # ignition time steps, minutes after 02:00
kmid = int(np.argmax(nc)); tmid = times[kmid]
# embers that ignite at step k landed ~2 steps earlier (random draw, then CELL_IGNITION_DELAY 100 s, on ~5-7 min steps)
tfly = 0.5 * (times[max(kmid - 2, 0)] + times[max(kmid - 1, 0)])

fig, (ax, bx) = plt.subplots(1, 2, figsize=(17, 8.2), gridspec_kw=dict(width_ratios=[1.15, 1]))
ax.imshow(np.where((t[s] > 0) & ~late, 1.0, np.nan), extent=ext, cmap=ListedColormap(["#dcdcdc"]), interpolation="nearest")
ax.imshow(np.where(fuel[s] == 91, 1.0, np.nan), extent=ext, cmap=ListedColormap(["#9a9a9a"]), interpolation="nearest")
pal = ["#1b9e77", "#d95f02", "#7570b3", "#e7298a", "#e6ab02"]
for k, m in enumerate(times):
    cell = late & (np.abs((hrs - T0) * 60 - m) < 0.05)
    ax.imshow(np.where(cell, 1.0, np.nan), extent=ext, cmap=ListedColormap([pal[k % 5]]), interpolation="nearest")
    ax.plot([], [], "s", color=pal[k % 5], ms=9, label="ignited by embers at 02:%02d" % round(m))

cx = gw[0] + 600 * (np.arange(wd16.shape[1]) + 0.5); cy = gw[3] - 600 * (np.arange(wd16.shape[0]) + 0.5)
for x in gw[0] + 600 * np.arange(wd16.shape[1] + 1):
    if X0 <= x <= X1: ax.axvline((x - X0) / 1e3, color="#4a90c2", lw=0.6, alpha=0.5)
for y in gw[3] - 600 * np.arange(wd16.shape[0] + 1):
    if Y0 <= y <= Y1: ax.axhline((y - Y0) / 1e3, color="#4a90c2", lw=0.6, alpha=0.5)
CJ = np.where((cx > X0) & (cx < X1))[0]; CI = np.where((cy > Y0) & (cy < Y1))[0]
CXX, CYY = np.meshgrid(cx[CJ], cy[CI])
tt = np.radians(code_blend(tfly / 60.0)[np.ix_(CI, CJ)])
ax.quiver((CXX - X0) / 1e3, (CYY - Y0) / 1e3, np.sin(tt), np.cos(tt), color="#1f5fbf", scale=22, width=0.005,
          zorder=5, label="ember wind in the model at 02:%02d\n(when the 02:%02d embers were flying)" % (round(tfly), round(tmid)))
ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
ax.set_xlabel("km (east)"); ax.set_ylabel("km (north)")
ax.legend(loc="upper right", fontsize=11, framealpha=0.95)
ax.set_title("A. One run (seed %d): each thin line = the path of one ember tracer\n"
             "light grey = burned earlier; dark grey = building cells; blue squares = 600 m wind cells" % seed, fontsize=12)

# right panel: direction over the hour for the wind cell in the middle of the window
ci, cj = CI[len(CI) // 2], CJ[len(CJ) // 2]
f = np.linspace(0, 1, 121)
a, b = to_dir(wd16[ci, cj]), to_dir(wd17[ci, cj])
code = np.array([code_blend(v)[ci, cj] for v in f])
d = (b - a + 180) % 360 - 180; short = (a + f * d) % 360
short[1:][np.abs(np.diff(short)) > 180] = np.nan
bx.plot(f * 60, code, color="#c8551b", lw=3, label="as the ember code blends it")
bx.plot(f * 60, short, color="#1f5fbf", lw=3, ls="--", label="shortest turn (physical)")
for k, m in enumerate(times):
    bx.axvline(m, color=pal[k % 5], lw=2, alpha=0.8)
    bx.text(m + 0.5, 345, "02:%02d" % round(m), color=pal[k % 5], fontsize=11, rotation=90, va="top")
bx.set_yticks([0, 90, 180, 270, 360]); bx.set_yticklabels(["N 0°", "E 90°", "S 180°", "W 270°", "N 360°"])
bx.set_ylim(0, 360); bx.set_xlim(0, 60)
bx.set_xticks(range(0, 61, 10)); bx.set_xticklabels(["02:%02d" % m if m < 60 else "03:00" for m in range(0, 61, 10)])
bx.set_ylabel("direction the wind blows TOWARD"); bx.set_xlabel("time (EST)")
bx.legend(loc="lower left", fontsize=11)
bx.set_title("B. Wind direction used for embers in one 600 m cell\n02:00 input: from %d° (blows to %d°);  03:00 input: from %d° (blows to %d°)"
             % (wd16[ci, cj], a, wd17[ci, cj], b), fontsize=12)
for sp in ("top", "right"): bx.spines[sp].set_visible(False)
fig.tight_layout(); fig.savefig(out, dpi=150, facecolor="white")
print("ignition steps (min after 02:00):", times, " wind cell", ci, cj, "to-dirs", a, b)
