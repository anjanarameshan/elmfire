#!/usr/bin/env python3
"""HRRR domain-mean weather in the layout of Fig. 2 of Jimenez et al. (2018): 10 m wind speed and
direction (upper panel), 2 m temperature and relative humidity (lower panel), hourly, LST.
Only our HRRR data is plotted.

Usage: python plot_hrrr_fig2_style.py SERIES.csv OUT.png
SERIES.csv: from hrrr_vs_paper_fig2.py (columns time_lst, hrrr_ws, hrrr_wd, hrrr_t2, hrrr_rh, hrrr_cells)
"""
import sys, csv, datetime as dt
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

rows = list(csv.DictReader(open(sys.argv[1])))
t = [dt.datetime.strptime(r["time_lst"], "%Y-%m-%d %H:%M") for r in rows]
g = lambda k: np.array([float(r[k]) for r in rows])
ws, wd, t2, rh = g("hrrr_ws"), g("hrrr_wd"), g("hrrr_t2"), g("hrrr_rh")
x = np.arange(len(t))
B, R = "#352f87", "#a52a2a"

fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 7.4), sharex=True, gridspec_kw=dict(hspace=0.06))
b1, b2 = a1.twinx(), a2.twinx()
a1.plot(x, ws, color=B, lw=1.6); b1.plot(x, wd, color=R, lw=1.6)
a2.plot(x, t2, color=B, lw=1.6); b2.plot(x, rh, color=R, lw=1.6)
a1.set_ylim(0, 18); a1.set_yticks([0, 4.5, 9, 13.5, 18]); b1.set_ylim(0, 360); b1.set_yticks([0, 90, 180, 270, 360])
lo, hi = min(274, 2 * np.floor(t2.min() / 2)), max(290, 2 * np.ceil(t2.max() / 2))   # paper's 274-290 K, widened to fit
a2.set_ylim(lo, hi); a2.set_yticks(np.arange(lo, hi + 0.1, 4 if hi - lo <= 20 else 5)); b2.set_ylim(0, 100); b2.set_yticks([0, 25, 50, 75, 100])
a1.set_ylabel("10-m wind speed [m s$^{-1}$]", color=B); b1.set_ylabel("10-m wind direction [$^\\circ$]", color=R)
a2.set_ylabel("2-m temperature [K]", color=B); b2.set_ylabel("2-m relative humidity [%]", color=R)
for a, c in ((a1, B), (a2, B), (b1, R), (b2, R)):
    a.tick_params(axis="y", colors=c)
ticks = [k for k in x if t[k].hour % 8 == 0]
a2.set_xticks(ticks); a2.set_xticklabels([t[k].strftime("%d/%H") for k in ticks])
a2.set_xlim(0, len(t) - 1); a2.set_xlabel("Time [DD/HH], LST (EST = UTC - 5)")
i = int(np.argmax(ws))
a1.annotate("peak %.1f m s$^{-1}$\n%s LST" % (ws[i], t[i].strftime("%d Nov %H:%M")), xy=(i, ws[i]),
            xytext=(i - 16, ws[i] + 0.3), fontsize=9, color=B, arrowprops=dict(arrowstyle="->", color=B))
fig.suptitle("HRRR 3 km analyses, mean over the 13 x 13 km domain of Jimenez et al. (2018) (%s cells)\n"
             "26 Nov 14:00 - 29 Nov 14:00 LST 2016" % rows[0]["hrrr_cells"], fontsize=11, y=0.96)
fig.savefig(sys.argv[2], dpi=150, bbox_inches="tight")
print("wrote", sys.argv[2], "| peak wind %.1f m/s at %s LST, min RH %.0f %% at %s LST" %
      (ws[i], t[i].strftime("%d %H:%M"), rh.min(), t[int(np.argmin(rh))].strftime("%d %H:%M")))
