#!/usr/bin/env python3
"""Slide flow chart of the work done so far (Objective 1) and how it leads to Objectives 2-4.
Usage: python plot_workflow.py OUT.png
"""
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

NAVY, GREY, BG = "#14213d", "#5f6b7a", "white"
C1, C1L = "#2f6690", "#e3edf5"        # done (objective 1)
C2, C2L = "#c8551b", "#fbe9df"        # findings
C3, C3L = "#4d7a3d", "#e6f0e1"        # next objectives

fig, ax = plt.subplots(figsize=(16, 9))
fig.patch.set_facecolor(BG); ax.set_xlim(0, 160); ax.set_ylim(0, 90); ax.axis("off")


def box(x, y, w, h, title, lines, ec, fc, step=None):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2", fc=fc, ec=ec, lw=2))
    tx = x + 1.2
    if step:
        ax.add_patch(plt.Circle((x + 2.6, y + h - 2.6), 1.9, color=ec, zorder=3))
        ax.text(x + 2.6, y + h - 2.6, step, ha="center", va="center", color="white", fontsize=12, weight="bold", zorder=4)
        tx = x + 5.4
    ax.text(tx, y + h - 2.6, title, ha="left", va="center", fontsize=12, weight="bold", color=ec)
    ax.text(x + 1.2, y + h - 5.6, "\n".join(lines), ha="left", va="top", fontsize=9.8, color=NAVY, linespacing=1.4)


def arrow(x0, y0, x1, y1, col=GREY):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=20, color=col, lw=2.2))


ax.text(2, 86.5, "Research workflow: Chimney Tops II fire, Gatlinburg, 28 Nov 2016", fontsize=19, weight="bold", color=NAVY)
ax.text(2, 82.6, "Objective 1 completed with ELMFIRE (stochastic wildfire–WUI model); its findings motivate Objectives 2–4",
        fontsize=12.5, color=GREY)

# row 1: done steps
W, H, Y1 = 36.5, 27, 50
box(2, Y1, W, H, "Data and model set-up", [
    "• Fuel, terrain, hourly wind, moisture",
    "  (CloudFire, LANDFIRE; 30 m grid)",
    "• Burn perimeter: MTBS",
    "• Buildings: Microsoft footprints,",
    "  NAIP-checked; building cell if",
    "  ≥ 2 % of it is roof",
    "  → 1,609 buildings in the perimeter",
    "• Roads and rivers: OpenStreetMap"], C1, C1L, "1")
box(41.5, Y1, W, H, "Fire-spread evaluation", [
    "• Compared with MTBS perimeter and",
    "  reported timeline (Jiménez et al.)",
    "• Tested fuels, spotting models,",
    "  road/river barriers, suppression",
    "  (26–29 Nov)",
    "• No tuning to fit the perimeter",
    "  (spread adjustment = 1)"], C1, C1L, "2")
box(81, Y1, W, H, "Stochastic ignition study", [
    "• Observed spot fire + 4 points 1 km",
    "  N, S, E, W  ×  10 random seeds",
    "  = 50 runs (16 h, 11:00 → 03:00)",
    "• Buildings: ST09, WU-E model",
    "• Embers: Eulerian transport,",
    "  physical ignition criterion"], C1, C1L, "3")
box(120.5, Y1, W + 1, H, "Ignition probability", [
    "• 981–1,270 of 1,609 buildings",
    "  ignited inside the perimeter",
    "  (observed spot: 1,043; 1,010–1,060)",
    "• Mean converges after ~5 runs;",
    "  standard error 0.3–1.0 %",
    "• Spot location matters far more",
    "  than chance (up to 290 buildings)"], C1, C1L, "4")
for x in (38.5, 78, 117.5):
    arrow(x + 0.4, Y1 + H / 2, x + 3.1, Y1 + H / 2, C1)

# row 2: diagnosis
Y2, H2 = 21, 22
box(2, Y2, 115.5, H2, "Ignition mechanism diagnosis: how did buildings and forest ignite?", [], C2, C2L, "5")
cols = [("Buildings", ["0 ignited by embers (all 50 runs)", "max ember load 6.4× below need", "→ ignited by heat only"]),
        ("Forest", ["≈ 96 % ignited by embers", "strict ember rule: fire 1,075× smaller", "→ ember rule controls fire size"]),
        ("Model limitations", ["burning buildings emit no embers", "no heat–ember interaction", "one fitted threshold, 0.2 g ember"])]
for k, (t, ls) in enumerate(cols):
    x = 4 + k * 38
    ax.text(x, Y2 + H2 - 7.2, t, fontsize=12, weight="bold", color=C2)
    ax.text(x, Y2 + H2 - 10.2, "\n".join("• " + s for s in ls), fontsize=9.8, color=NAVY, va="top", linespacing=1.45)
arrow(139, Y1 - 0.6, 108, Y2 + H2 + 0.6, C1)

# gap -> next objectives
box(120.5, Y2, W + 1, H2, "Research gap", [
    "In 2016 embers ignited many",
    "houses; the model cannot",
    "reproduce ember ignition of",
    "buildings → needs ember",
    "physics and building data"], C2, C2L)
arrow(117.8, Y2 + H2 / 2, 120.2, Y2 + H2 / 2, C2)

Y3, H3 = 2, 14
nxt = [("Objective 2", "Building topology and", "ember ignition"),
       ("Objective 3", "Lab: firebrand accumulation", "and ignition of materials"),
       ("Objective 4", "Fragility: ignition under", "combined heat + firebrands")]
for k, (t, a, b) in enumerate(nxt):
    x = 2 + k * 53
    box(x, Y3, 49.5, H3, t + " (next)", [a, b], C3, C3L)
    if k < 2:
        arrow(x + 49.9, Y3 + H3 / 2, x + 52.6, Y3 + H3 / 2, C3)
arrow(139, Y2 - 0.6, 132, Y3 + H3 + 0.6, C2)

fig.savefig(sys.argv[1], dpi=150, facecolor=BG)
print("wrote", sys.argv[1])
