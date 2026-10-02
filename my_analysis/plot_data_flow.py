#!/usr/bin/env python3
"""
Diagram of where the weather used in the Chimney Tops 2 ELMFIRE runs comes from,
and how the station data used for checking it relates.

Source for the CloudFire weather: PyroStack paper (CloudFire Inc. co-authored, arXiv 2609.36315):
RTMA wind and NFDRS4 fuel moisture, resampled from 2.5 km to 600 m, winds at 20 ft.

Usage: python plot_data_flow.py [OUT.png]
"""
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = sys.argv[1] if len(sys.argv) > 1 else "weather_stations/cloudfire_data_flow.png"

fig, ax = plt.subplots(figsize=(13, 8.2))
ax.set_xlim(0, 13)
ax.set_ylim(0, 8.2)
ax.axis("off")

STYLE = {
    "noaa": ("#dbe9f6", "#2f5e86"),
    "cloudfire": ("#fde6d6", "#b3470f"),
    "elmfire": ("#fbe0e0", "#a4161a"),
    "obs": ("#e1efe3", "#2e6b3c"),
}


def box(x, y, w, h, title, lines, kind):
    face, edge = STYLE[kind]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.06,rounding_size=0.12",
                                fc=face, ec=edge, lw=1.8))
    ax.text(x + w / 2, y + h - 0.28, title, ha="center", va="top", fontsize=11.5,
            fontweight="bold", color=edge)
    ax.text(x + 0.2, y + h - 0.72, "\n".join(lines), ha="left", va="top", fontsize=9.2,
            linespacing=1.45)


def arrow(x1, y1, x2, y2, label="", color="0.25", style="-|>", ls="-"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=16,
                                 lw=1.6, color=color, ls=ls))
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.14, label, ha="center", va="bottom",
                fontsize=8.8, color=color, style="italic")


# Row 1: operational chain
box(0.2, 4.3, 3.6, 3.3, "1. NOAA inputs",
    ["Weather stations (ASOS, RAWS, ...)",
     "Weather model first guess:",
     "  HRRR (3 km) / NAM (4 km)",
     "  (RAP-based before 2015)",
     "Terrain"], "noaa")
box(4.7, 4.3, 3.6, 3.3, "2. NOAA RTMA",
    ["Real-Time Mesoscale Analysis",
     "Hourly, 2.5 km grid, USA",
     "Wind speed & direction,",
     "temperature, humidity, ...",
     "Blend of model + observations"], "noaa")
box(9.2, 4.3, 3.6, 3.3, "3. CloudFire Worldgen",
    ["Server: worldgen.cloudfire.io",
     "Wind: RTMA, resampled",
     "  2.5 km -> 600 m, at 20 ft",
     "Dead fuel moisture m1, m10, m100:",
     "  computed with NFDRS4 models",
     "Live lh / lw: constant 30 / 60 %"], "cloudfire")

arrow(3.9, 5.95, 4.6, 5.95, "analysed")
arrow(8.4, 5.95, 9.1, 5.95, "downloaded")

# Row 2: our use
box(9.2, 0.35, 3.6, 3.2, "4. ELMFIRE run",
    ["fuel_wx_ign.py -> .tar",
     "inputs/ws.tif, wd.tif",
     "inputs/m1, m10, m100.tif",
     "inputs/lh.tif, lw.tif",
     "1 band per hour, 600 m cells",
     "(fuels & terrain: LANDFIRE, 30 m)"], "elmfire")
arrow(11.0, 4.2, 11.0, 3.65, "")
ax.text(11.12, 3.92, "hourly rasters", fontsize=8.8, color="0.25", style="italic", va="center")

box(0.2, 0.35, 7.6, 3.2, "Independent checks (station observations, point values)",
    ["IGGT1  Indian Grave RAWS - 30 km W of ignition, 823 m:",
     "     wind, gust, temperature, humidity (-> 1-hr moisture via NFDRS EMC)",
     "KGKT  Sevierville-Gatlinburg-Pigeon Forge Airport ASOS - 26 km N, 305 m:",
     "     wind, gust",
     "Note: these networks also feed RTMA, so they are not fully independent,",
     "but they are raw measurements (incl. gusts) at single points."], "obs")
arrow(7.9, 1.95, 9.1, 1.95, "compared with", color=STYLE["obs"][1], ls="--")
arrow(2.0, 3.6, 2.0, 4.2, "", color=STYLE["obs"][1], ls="--")

ax.set_title("Where the ELMFIRE weather for the Chimney Tops 2 runs comes from",
             fontsize=14, fontweight="bold", pad=6)
fig.text(0.5, 0.01, "Source for CloudFire processing: PyroStack dataset paper (CloudFire Inc. co-author), "
         "arXiv 2609.36315. RTMA = NOAA/NCEP Real-Time Mesoscale Analysis.",
         ha="center", fontsize=8.5, color="0.35")
fig.savefig(OUT, dpi=150, bbox_inches="tight", facecolor="white")
print("wrote", OUT)
