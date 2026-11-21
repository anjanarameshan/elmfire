#!/usr/bin/env python3
"""ILLUSTRATIVE (not fitted) slope-conditioned wildfire fragility curves, to show the idea for Objective 1.

All numbers are invented to show the shape of the result; the ordering of slope positions is a hypothesis to test.
Lognormal fragility (as in earthquake engineering): P(failure | IM) = Phi(ln(IM / theta) / beta).
(a) separate curves per slope position, IM = ember load;  (b) slope as a continuous extra term
    (theta falls with slope);  (c) two-IM surface P(failure | heat, embers): 50 % lines per slope position,
    combined as P = 1 - (1 - P_heat)(1 - P_ember).
Writes fragility_concept.png next to this script.
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from math import erf
Phi = np.vectorize(lambda z: 0.5 * (1 + erf(z / 2 ** 0.5)))

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fragility_concept.png")
INK, MUTED, GRID = "#1f2328", "#57606a", "#e6e6e6"
POS = [("flat ground", 60, "#2a78d6", "-"), ("hollow / valley", 40, "#1baf7a", "--"),
       ("mid-slope", 28, "#eda100", "-."), ("ridge", 16, "#eb6834", ":")]   # (name, median ember load g/m2, colour, dash)
BETA_E, HEAT_THETA, BETA_H = 0.6, 25.0, 0.35
frag = lambda x, th, b: Phi(np.log(x / th) / b)

plt.rcParams.update({"font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED})
fig, ax = plt.subplots(1, 3, figsize=(16, 5.4))
e = np.logspace(0, np.log10(400), 300)

# (a) separate curves per slope position
a = ax[0]
for name, th, c, ls in POS:
    a.plot(e, frag(e, th, BETA_E), color=c, lw=2, ls=ls)
    a.text(th * 1.08, 0.5, name, color=INK, fontsize=9, rotation=62, ha="left", va="center")
a.axhline(0.5, color=GRID, lw=1, zorder=0)
a.set_xscale("log"); a.set_xlabel("ember load at the house (g/m²)"); a.set_ylabel("P(failure | IM)")
a.set_title("(a) Separate curves per slope position", loc="left", color=INK)
a.text(0.02, 0.97, "same ember load → higher P(failure)\non a ridge than on flat ground", transform=a.transAxes, va="top", fontsize=8.8, color=MUTED)

# (b) slope as a continuous term: theta = theta0 * exp(-k * slope)
a = ax[1]
cols = ["#b7d3f6", "#6da7ec", "#2a78d6", "#184f95"]
for s, c in zip([0, 10, 20, 30], cols):
    th = 60 * np.exp(-0.045 * s)
    a.plot(e, frag(e, th, BETA_E), color=c, lw=2)
    a.text(th * 0.92, 0.5, "%d°" % s, color=INK, fontsize=9, ha="right", va="bottom")
a.axhline(0.5, color=GRID, lw=1, zorder=0)
a.set_xscale("log"); a.set_xlabel("ember load at the house (g/m²)")
a.set_title("(b) Slope as an extra term in the fit", loc="left", color=INK)
a.text(0.02, 0.97, "probit[P] = (ln IM − ln θ₀ + k·slope) / β\none fit, curve shifts left as slope increases", transform=a.transAxes, va="top", fontsize=8.8, color=MUTED)

# (c) two-IM surface: 50 % failure line per slope position
a = ax[2]
h = np.linspace(1, 60, 300); E, H = np.meshgrid(np.logspace(0, np.log10(400), 300), h)
for name, th, c, ls in POS:
    P = 1 - (1 - frag(H, HEAT_THETA, BETA_H)) * (1 - frag(E, th, BETA_E))
    cs = a.contour(E, H, P, levels=[0.5], colors=[c], linewidths=2, linestyles=[ls])
a.set_xscale("log"); a.set_xlabel("ember load at the house (g/m²)"); a.set_ylabel("heat flux at the house (kW/m²)")
a.set_title("(c) Two intensity measures: 50 % failure lines", loc="left", color=INK)
a.text(1.3, 50, "fails mainly by heat", fontsize=8.8, color=MUTED); a.text(60, 4, "fails mainly\nby embers", fontsize=8.8, color=MUTED)
a.text(1.3, 6, "survives\n(below the line)", fontsize=8.8, color=MUTED)

for a in ax:
    a.grid(color=GRID, lw=0.6); a.spines[["top", "right"]].set_visible(False)
    if a is not ax[2]: a.set_ylim(0, 1.02)
fig.legend(handles=[plt.Line2D([], [], color=c, lw=2, ls=ls, label=n) for n, _, c, ls in POS],
           loc="lower center", ncol=4, frameon=False, fontsize=9.5, bbox_to_anchor=(0.36, -0.01))
fig.suptitle("Slope-conditioned wildfire fragility — ILLUSTRATIVE shapes only (invented numbers, not fitted to data)",
             x=0.01, ha="left", fontsize=12.5, weight="bold", color=INK)
fig.tight_layout(rect=(0, 0.05, 1, 0.95)); fig.savefig(OUT, dpi=150, facecolor="white")
print("wrote", OUT)
