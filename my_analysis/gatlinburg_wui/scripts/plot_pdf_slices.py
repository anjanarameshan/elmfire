#!/usr/bin/env python3
"""Slide figure: how the Eulerian ember model turns the Sardoy lognormal pdf into embers per cell.
Example source cell F (fireline intensity 2,000 kW/m, U10 = 15.4 m/s -> mu_x = 2.12, sigma_x = 1.17),
N = 20,000 embers, 30 m cells, cut-off at P_EPS = 0.001.
Usage: python plot_pdf_slices.py OUT.png
"""
import sys, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch

out = sys.argv[1]
MU, SIG, N, DX = 2.12, 1.17, 20000, 30.0
pdf = lambda x: np.exp(-(np.log(x) - MU) ** 2 / (2 * SIG ** 2)) / (x * SIG * math.sqrt(2 * math.pi))
cdf = lambda x: 0.5 * (1 + math.erf((math.log(x) - MU) / (SIG * math.sqrt(2)))) if x > 0 else 0.0
xcut = math.exp(MU + 3.090 * SIG)
K = 5
pr = [cdf(DX * k) - cdf(DX * (k - 1)) for k in range(1, K + 1)]
tail = cdf(xcut) - cdf(DX * K)
cols = ["#d9622b", "#e8894f", "#f0a97a", "#f6c7a4", "#fbe3d0"]

fig = plt.figure(figsize=(16, 9))
ax = fig.add_axes([0.07, 0.40, 0.88, 0.50])
x = np.linspace(0.3, 160, 2000)
y = pdf(x)
for k in range(K):
    xs = np.linspace(max(DX * k, 0.3), DX * (k + 1), 300)
    ax.fill_between(xs, pdf(xs), color=cols[k], alpha=0.95, lw=0)
    ax.axvline(DX * (k + 1), color="#1b2430", lw=1, ls=":", alpha=0.6)
    ytxt = 0.032 if k == 0 else 0.011
    ax.text(DX * k + DX / 2 + (11 if k == 0 else 0), ytxt, "slice %d\n%d–%d m\nPr = %.1f %%" % (k + 1, DX * k, DX * (k + 1), 100 * pr[k]),
            ha="center", va="bottom", fontsize=14, weight="bold", color="#1b2430")
ax.plot(x, y, color="#1b2430", lw=2.5)
ax.set_xlim(0, 160); ax.set_ylim(0, 0.045)
ax.set_xlabel("downwind distance X from the burning cell (m)", fontsize=15)
ax.set_ylabel("pdf(X)  [fraction of embers per metre]", fontsize=15)
ax.tick_params(labelsize=13)
ax.spines[["top", "right"]].set_visible(False)
ax.set_title("Same 30 m width, different height → different area.  Area of each slice = Pr_k = share of the parcel for that cell",
             fontsize=16, pad=12)
ax.annotate("tail beyond 150 m: %.1f %%\ncut-off X*M ≈ %.0f m (only 0.1 %% fly farther)" % (100 * tail, xcut),
            xy=(150, pdf(150)), xytext=(112, 0.026), fontsize=13, arrowprops=dict(arrowstyle="->", color="#1b2430"))

# strip of cells along the wind path
ax2 = fig.add_axes([0.07, 0.05, 0.88, 0.22])
ax2.set_xlim(-35, 160); ax2.set_ylim(0, 1); ax2.axis("off")
ax2.add_patch(Rectangle((-32, 0.2), 28, 0.6, fc="#c0392b", ec="black", lw=1.5))
ax2.text(-18, 0.5, "F\nburning", ha="center", va="center", fontsize=13, color="white", weight="bold")
for k in range(K):
    ax2.add_patch(Rectangle((DX * k + 1, 0.2), DX - 2, 0.6, fc=cols[k], ec="black", lw=1.5))
    ax2.text(DX * k + DX / 2, 0.5, "cell %d\n%s embers" % (k + 1, format(int(round(N * pr[k], -1)), ",")),
             ha="center", va="center", fontsize=13, weight="bold", color="#1b2430")
ax2.add_patch(FancyArrowPatch((-30, 0.95), (155, 0.95), arrowstyle="-|>", mutation_scale=22, color="#2f6690", lw=2.5))
ax2.text(62, 1.02, "tracer moves 30 m per step along the wind  →  deposits N × Pr_k in the cell it reaches   (N = 20,000)",
         ha="center", va="bottom", fontsize=14, color="#2f6690", weight="bold")
ax2.text(62, 0.02, "within each cell the embers are treated as spread evenly over 900 m²", ha="center", fontsize=13, style="italic",
         color="#3e4a5b")
fig.savefig(out, dpi=150, facecolor="#F6F3EE")
print("wrote", out, "| Pr_k:", [round(p, 4) for p in pr], "tail", round(tail, 4), "cutoff", round(xcut))
