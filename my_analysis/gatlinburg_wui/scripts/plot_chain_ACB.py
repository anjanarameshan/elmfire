#!/usr/bin/env python3
"""Slide figure: the ignition chain forest cell A -> (embers) -> building C -> (heat) -> building B -> next house,
as implemented in ELMFIRE (Eulerian embers, PHYSICAL ignition, WU-E building model type 2).
Usage: python plot_chain_ACB.py OUT.png
"""
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle

out = sys.argv[1]
DARK, ORANGE, BLUE, GREY, LIGHT = "#1b2430", "#d9622b", "#2f6690", "#6b7585", "#f6f3ee"
fig, ax = plt.subplots(figsize=(16, 9))
fig.patch.set_facecolor(LIGHT); ax.set_facecolor(LIGHT)
ax.set_xlim(0, 160); ax.set_ylim(0, 90); ax.axis("off")


def cell(x, y, label, sub, fc):
    ax.add_patch(Rectangle((x, y), 22, 22, fc=fc, ec=DARK, lw=2.5))
    ax.text(x + 11, y + 14, label, ha="center", va="center", fontsize=30, weight="bold", color="white")
    ax.text(x + 11, y + 6, sub, ha="center", va="center", fontsize=12, color="white", weight="bold")


def box(x, y, w, h, title, text, ec):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.6,rounding_size=1.5", fc="white", ec=ec, lw=2))
    ax.text(x + 0.8, y + h - 1.2, title, ha="left", va="top", fontsize=13.5, weight="bold", color=ec)
    ax.text(x + 0.8, y + h - 5.0, text, ha="left", va="top", fontsize=12, color=DARK, linespacing=1.35)


# cells along the wind
cell(6, 34, "A", "forest", "#4d7a3d")
cell(69, 34, "C", "building", ORANGE)
cell(117, 34, "B", "building", "#a0522d")
ax.add_patch(FancyArrowPatch((6, 66), (60, 66), arrowstyle="simple", mutation_scale=30, color=BLUE))
ax.text(33, 68.5, "wind", ha="center", fontsize=14, color=BLUE, weight="bold")

# A -> C : embers (dashed arcs)
for r in (-0.25, -0.15, -0.05):
    ax.add_patch(FancyArrowPatch((28, 50), (69, 50), connectionstyle="arc3,rad=%.2f" % r, arrowstyle="-|>",
                                 mutation_scale=16, color="#f0a202", lw=2, ls="--"))
ax.text(48.5, 60, "EMBERS", ha="center", fontsize=15, weight="bold", color="#c98a00")
# C -> B : heat
ax.add_patch(FancyArrowPatch((91, 45), (117, 45), arrowstyle="simple", mutation_scale=34, color="#d7191c"))
ax.text(104, 51, "HEAT", ha="center", fontsize=15, weight="bold", color="#d7191c")
ax.text(104, 39.5, "DFC + radiation", ha="center", fontsize=11.5, color="#d7191c")
# B -> next
ax.add_patch(FancyArrowPatch((139, 45), (157, 45), arrowstyle="simple", mutation_scale=28, color="#d7191c", alpha=0.6))
ax.text(150, 51, "next\nhouse", ha="center", fontsize=12, color=GREY)

# step boxes
box(1, 2, 37, 28, "1 · A burns, sends embers",
    "HRR = fireline intensity × 30 m\nN = HRR × 33.3 /MW/s × 10 s\ntracer drops N × Pr_k along\nthe wind → C’s ember pile ψ", "#4d7a3d")
box(41, 2, 37, 28, "2 · C ignites by EMBERS",
    "H·ψ ≥ ψcrit(roof wind)?\n→ P = 0.9 → random draw\n→ + 300 s (t_1MW)\n→ φ_C JUMPS to −1 (no U)\n   time of arrival + ember flag", ORANGE)
box(81, 2, 37, 28, "3 · C burns → heats B",
    "HRR_C from ST09 curve\n(burning time = now − TOA_C)\nheat to B = DFC + radiation\n+ all burning cells ≤ 150 m\n→ summed total Q_B", "#d7191c")
box(121, 2, 37, 28, "4 · B ignites by HEAT",
    "U_B = f(Q_B)   (no 13 kW/m²\nor FTP test in code)\nφ_B falls at speed U_B\nφ_B ≤ 0 → B burning (no flag)\n→ heats the next house", "#a0522d")

ax.text(80, 86, "From one forest cell to house-to-house spread: how a cell ignites decides how its φ changes",
        ha="center", fontsize=17, weight="bold", color=DARK)
ax.text(80, 81, "embers → a random jump of φ  ·  heat → a spread speed that lowers φ  ·  once burning, every building follows its ST09 heat curve",
        ha="center", fontsize=13, color=GREY)
fig.savefig(out, dpi=150, facecolor=LIGHT)
print("wrote", out)
