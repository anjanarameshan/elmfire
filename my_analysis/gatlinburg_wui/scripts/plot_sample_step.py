#!/usr/bin/env python3
"""Schematic of the sample time-step calculation: burning forest cell F upwind throws embers onto
building B; burning building A, 30 m from B, heats B by radiation. 30 m ELMFIRE grid, wind from the SSE.
Usage: python plot_sample_step.py OUT.png
"""
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch

out = sys.argv[1]
C = 30.0                                   # cell size (m)
fig, ax = plt.subplots(figsize=(9, 9.6), constrained_layout=True)
nx, ny = 7, 9
for i in range(nx):                        # grid: forest everywhere except the town cells
    for j in range(ny):
        town = j >= 5
        ax.add_patch(Rectangle((i * C, j * C), C, C, fc="#e8efe0" if not town else "#f1ece4", ec="#b9b2a5", lw=0.8))
F = (3, 1); A = (1, 7); B = (2, 7)        # cells (column, row)
cen = lambda c: ((c[0] + 0.5) * C, (c[1] + 0.5) * C)
ax.add_patch(Rectangle((F[0] * C, F[1] * C), C, C, fc="#e4572e", ec="black", lw=2))
for c, col in ((A, "#e4572e"), (B, "#c44e00")):
    ax.add_patch(Rectangle((c[0] * C, c[1] * C), C, C, fc="#f7d9c4" if c == B else "#f3b8a2", ec="black", lw=2))
    x0, y0 = c[0] * C + 7, c[1] * C + 7                     # house footprint inside the cell
    ax.add_patch(Rectangle((x0, y0), 16, 13, fc=col, ec="black", lw=1.2))
    ax.fill([x0 - 1, x0 + 8, x0 + 17], [y0 + 13, y0 + 20, y0 + 13], color=col, ec="black", lw=1.2)
fx, fy = cen(F); ax_, ay = cen(A); bx, by = cen(B)
ax.text(fx, fy, "F", ha="center", va="center", fontsize=22, weight="bold", color="white")
ax.text(ax_ + 11, ay + 11, "A", ha="center", va="center", fontsize=20, weight="bold")
ax.text(bx + 11, by + 11, "B", ha="center", va="center", fontsize=20, weight="bold")
# embers F -> B
for k, dx in enumerate((-8, 0, 8)):
    ax.add_patch(FancyArrowPatch((fx + dx, fy + 10), (bx + dx * 0.6, by - 6), connectionstyle="arc3,rad=%.2f" % (-0.25 + 0.2 * k),
                                 arrowstyle="-|>", mutation_scale=14, color="#f0a202", lw=1.6, ls="--"))
# radiation A -> B
ax.add_patch(FancyArrowPatch((ax_ + 4, ay - 2), (bx - 6, by - 2), arrowstyle="-|>", mutation_scale=18, color="#d7191c", lw=3))
# wind arrow (from SSE, blowing towards NNW)
ax.add_patch(FancyArrowPatch((6.4 * C, 0.6 * C), (5.3 * C, 3.6 * C), arrowstyle="simple", mutation_scale=34, color="#2f6690"))
ax.text(6.55 * C, 0.4 * C, "wind from SSE\nU20 = 30 mph", fontsize=10, color="#2f6690", weight="bold", ha="right", va="top")
ax.annotate("F: burning forest cell\nfireline intensity 2,000 kW/m\nHRR = 2,000 x 30 m = 60 MW\n~20,000 embers in 10 s",
            (fx - 15, fy), xytext=(-0.2 * C, 2.6 * C), fontsize=9.5, ha="left", va="center",
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#e4572e"), arrowprops=dict(arrowstyle="-", color="#e4572e"))
ax.annotate("Embers: ~1% land in B's cell\n= 200 embers -> psi = 4.4e-6 g/cm2\nneeded at v = 0.85 m/s: 0.010 g/cm2\n-> no ember ignition",
            (bx - 2, by - 25), xytext=(4.3 * C, 4.6 * C), fontsize=9.5, ha="left", va="center",
            bbox=dict(boxstyle="round,pad=0.3", fc="#fff6dd", ec="#f0a202"), arrowprops=dict(arrowstyle="-", color="#f0a202"))
ax.annotate("A: burning building (ST09)\nburning 600 s -> fully developed\nHRRPUA 25 kW/m2 x 900 m2 = 22.5 MW",
            (ax_ - 12, ay), xytext=(-0.2 * C, 8.55 * C), fontsize=9.5, ha="left", va="center",
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#e4572e"), arrowprops=dict(arrowstyle="-", color="#e4572e"))
ax.annotate("Radiation A -> B, R = 30 m\n0.3 x 22,500 / (4 pi 30^2) = 0.60 kW/m2\nabsorbed 0.24 kW/m2 (< 13 kW/m2)\nadded to B's heat total (FTP)",
            ((ax_ + bx) / 2, (ay + by) / 2), xytext=(4.3 * C, 6.4 * C), fontsize=9.5, ha="left", va="center",
            bbox=dict(boxstyle="round,pad=0.3", fc="#fde3e3", ec="#d7191c"), arrowprops=dict(arrowstyle="-", color="#d7191c"))
ax.text(3.5 * C, 9.25 * C, "B: target building (ST09) — ignites when its accumulated heat reaches FTP, or if its ember pile passes the threshold",
        fontsize=9.5, ha="center", weight="bold", wrap=True)
ax.text(0.1 * C, 5.05 * C, "town (building cells, fuel 91)", fontsize=9, color="#6a5d4d", style="italic")
ax.text(0.1 * C, 0.08 * C, "forest (vegetation fuel)", fontsize=9, color="#4d6a3d", style="italic")
ax.plot([0.2 * C, 1.2 * C], [-0.5 * C, -0.5 * C], color="black", lw=3); ax.text(0.7 * C, -0.85 * C, "30 m = one cell", ha="center", fontsize=9)
ax.set_xlim(-0.3 * C, nx * C + 0.3 * C); ax.set_ylim(-1.1 * C, ny * C + 0.6 * C); ax.set_aspect("equal"); ax.axis("off")
ax.set_title("Sample 30 s time step (illustrative numbers): positions of F, A and B on the 30 m grid", fontsize=11)
fig.savefig(out, dpi=150)
print("wrote", out)
