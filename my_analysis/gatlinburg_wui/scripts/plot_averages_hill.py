#!/usr/bin/env python3
"""Real-number illustration of the SEM for the observed spot fire (buildings ignited inside the MTBS perimeter).
Left: the 10 actual runs. Right: 10,000 bootstrap averages (10 values drawn with replacement from the 10 runs).
Usage: python plot_averages_hill.py OUT.png
"""
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

runs = np.array([1039, 1049, 1060, 1010, 1024, 1055, 1044, 1056, 1051, 1043])   # seeds 1..10, ms_st09/spot2
m, sd = runs.mean(), runs.std(ddof=1); sem = sd / np.sqrt(len(runs)); half = 2.262 * sem
rng = np.random.default_rng(1)
boot = rng.choice(runs, size=(10000, 10), replace=True).mean(1)
plt.rcParams.update({"font.size": 13, "axes.spines.top": False, "axes.spines.right": False})
fig, (a, b) = plt.subplots(1, 2, figsize=(15, 5.8), sharex=True)
a.scatter(runs, np.zeros_like(runs) + rng.uniform(-0.15, 0.15, 10), s=140, color="#c8551b", edgecolor="white", zorder=3)
a.axvline(m, color="#14213d", lw=2.5); a.axvspan(m - sd, m + sd, color="#c8551b", alpha=0.12)
a.set_yticks([]); a.set_ylim(-1, 1)
a.set_title("A. Our 10 real runs (one dot each)\nspread of single runs: SD = %.1f (shaded = mean ± 1 SD)" % sd)
a.text(m, 0.75, "mean %.0f" % m, ha="center", fontsize=13, color="#14213d", weight="bold")
b.hist(boot, bins=np.arange(1015, 1066, 1), color="#2f6690", alpha=0.85)
b.axvline(m, color="#14213d", lw=2.5)
b.axvspan(m - half, m + half, color="#2f6690", alpha=0.12)
inside = np.mean(np.abs(boot - m) <= half) * 100
b.set_title("B. 10,000 imitated 10-run averages (resampled from A)\nthe hill: SEM = %.1f; shaded = mean ± %.0f holds %.0f%% of them" % (sem, half, inside))
b.set_ylabel("how many averages")
for ax in (a, b):
    ax.set_xlabel("buildings ignited inside the perimeter")
fig.tight_layout(); fig.savefig(sys.argv[1], dpi=150, facecolor="white")
print("mean %.1f sd %.1f sem %.2f 95%% half %.1f | bootstrap sd of averages %.2f, inside %.1f%%" % (m, sd, sem, half, boot.std(), inside))
