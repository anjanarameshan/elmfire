#!/usr/bin/env python3
"""Reproduce Figure 2 of Jimenez et al. (2018, Atmosphere 9, 197) with our HRRR analyses and overlay
the paper's own curves (extracted from the vector graphics in the PDF).

Paper Fig. 2: hourly series 26 Nov 14:00 - 29 Nov 14:00 LST (EST = UTC-5), averaged over the
13 x 13 km inner domain (Domain 2, 111 m, WRF-Fire SIM1): 10 m wind speed and direction (upper),
2 m temperature and relative humidity (lower).

Ours: HRRR 3 km analyses (f00, wrfprs) averaged over the same box. Box limits read from the axes of
the paper's Fig. 3 (lon -83.545..-83.405, lat 35.602..35.720). Wind speed = mean of the cell speeds;
direction = direction of the mean (u, v) vector; T and RH = cell means.

Usage: python hrrr_vs_paper_fig2.py PAPER.pdf HRRR_RAW_DIR OUT_PREFIX
Writes OUT_PREFIX.csv and OUT_PREFIX.png
"""
import sys, os, csv, datetime as dt, urllib.request
import numpy as np
import eccodes, pymupdf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

pdf, raw, outp = sys.argv[1:4]
T0_LST = dt.datetime(2016, 11, 26, 14)
NH = 73
BOX = (-83.545, 35.602, -83.405, 35.720)
S3 = "https://storage.googleapis.com/high-resolution-rapid-refresh/"   # Google mirror of the NOAA archive

# ---------------- 1. paper curves from the PDF vector graphics ----------------
page = pymupdf.open(pdf)[4]                      # page 5 holds Figure 2
BLUE, RED = (0.2056, 0.1882, 0.5289), (0.6489, 0.1634, 0.1648)
X0, DXH = 165.0721, (437.3318 - 165.0721) / 72   # first point (26/14 LST) and points per hour
UP = (148.3, 255.6)                              # upper panel: top, bottom y (page units)
LO = (263.1, 351.9)                              # lower panel


def poly(color, ytop, ybot):
    for d in page.get_drawings():
        c = d["color"]
        if c and all(abs(a - b) < 0.01 for a, b in zip(c, color)):
            pts = [it[1] for it in d["items"] if it[0] == "l"] + [d["items"][-1][2]]
            if len(pts) == 73 and ytop - 2 <= d["rect"].y0 and d["rect"].y1 <= ybot + 2:
                return np.array([[p.x, p.y] for p in pts])
    raise SystemExit("curve not found")


def scale(y, top, bot, vtop, vbot):
    return vbot + (bot - y) / (bot - top) * (vtop - vbot)


ws_p = poly(BLUE, *UP); wd_p = poly(RED, *UP); t_p = poly(BLUE, *LO); rh_p = poly(RED, *LO)
assert np.allclose(np.diff(ws_p[:, 0]), DXH, atol=0.05), "points are not hourly"
paper = dict(ws=scale(ws_p[:, 1], *UP, 18, 0), wd=scale(wd_p[:, 1], *UP, 360, 0),
             t2=scale(t_p[:, 1], *LO, 290, 274), rh=scale(rh_p[:, 1], *LO, 100, 0))

# ---------------- 2. HRRR over the same box ----------------
WANT = {("10u", 10): "u", ("10v", 10): "v", ("2t", 2): "t2", ("2r", 2): "rh"}
sel = rot = None


def decode(messages):
    """messages: iterable of GRIB2 bytes; returns dict of wanted fields (full grid)."""
    global sel, rot
    out = {}
    for m in messages:
        h = eccodes.codes_new_from_message(m)
        key = (eccodes.codes_get(h, "shortName"), eccodes.codes_get(h, "level"))
        if key in WANT and eccodes.codes_get(h, "typeOfLevel") == "heightAboveGround":
            if sel is None:
                la = eccodes.codes_get_array(h, "latitudes"); lo = eccodes.codes_get_array(h, "longitudes")
                lo = np.where(lo > 180, lo - 360, lo)
                sel = np.where((lo >= BOX[0]) & (lo <= BOX[2]) & (la >= BOX[1]) & (la <= BOX[3]))[0]
                alpha = np.radians(np.sin(np.radians(38.5)) * (lo[sel] + 97.5))   # grid -> earth winds
                rot = (np.cos(alpha), np.sin(alpha))
            out[WANT[key]] = eccodes.codes_get_values(h)[sel]
        eccodes.codes_release(h)
    return out


def split(data):
    pos, msgs = 0, []
    while True:
        pos = data.find(b"GRIB", pos)
        if pos < 0 or pos + 16 > len(data):
            return msgs
        n = int.from_bytes(data[pos + 8:pos + 16], "big")
        if pos + n > len(data):
            return msgs
        msgs.append(data[pos:pos + n]); pos += n


def get(url, rng=None):
    req = urllib.request.Request(url, headers={"Range": "bytes=%d-%d" % rng} if rng else {})
    for a in range(6):
        try:
            return urllib.request.urlopen(req, timeout=900).read()
        except Exception:
            if a == 5:
                raise


def hrrr_hour(tu):
    day, hh = tu.strftime("%Y%m%d"), tu.hour
    local = os.path.join(raw, "hrrr.%s" % day, "hrrr.t%02dz.wrfprsf00.grib2" % hh)
    if os.path.exists(local):
        with open(local, "rb") as f:
            return decode(split(f.read())), "local wrfprs"
    key = "hrrr.%s/conus/hrrr.t%02dz.wrfprsf00.grib2" % (day, hh)
    idx = get(S3 + key + ".idx").decode().strip().split("\n")
    off = [int(l.split(":")[1]) for l in idx]
    lines = [l.split(":") for l in idx]
    wanted = [i for i, l in enumerate(lines) if (l[3], l[4]) in
              {("UGRD", "10 m above ground"), ("VGRD", "10 m above ground"), ("TMP", "2 m above ground"), ("RH", "2 m above ground")}]
    if len(wanted) == 4:
        msgs = [get(S3 + key, (off[i], off[i + 1] - 1)) for i in wanted]
        return decode(msgs), "S3 byte ranges"
    data = get(S3 + key, (off[-1], off[-1] + 12_500_000))   # truncated .idx: fields follow the last entry
    return decode(split(data)), "S3, read past truncated .idx"


rows = []
for k in range(NH):
    tl = T0_LST + dt.timedelta(hours=k); tu = tl + dt.timedelta(hours=5)
    f, src = hrrr_hour(tu)
    u = f["u"] * rot[0] + f["v"] * rot[1]; v = -f["u"] * rot[1] + f["v"] * rot[0]
    rows.append(dict(time_lst=tl.strftime("%Y-%m-%d %H:%M"), time_utc=tu.strftime("%Y-%m-%d %H:%M"),
                     hrrr_ws=np.hypot(u, v).mean(), hrrr_wd=np.degrees(np.arctan2(-u.mean(), -v.mean())) % 360,
                     hrrr_t2=f["t2"].mean(), hrrr_rh=f["rh"].mean(),
                     paper_ws=paper["ws"][k], paper_wd=paper["wd"][k], paper_t2=paper["t2"][k], paper_rh=paper["rh"][k],
                     hrrr_cells=len(sel), hrrr_source=src))
    print("%s LST  HRRR ws %4.1f wd %3.0f T %5.1f RH %3.0f | paper ws %4.1f wd %3.0f T %5.1f RH %3.0f  (%s)" % (
        rows[-1]["time_lst"], rows[-1]["hrrr_ws"], rows[-1]["hrrr_wd"], rows[-1]["hrrr_t2"], rows[-1]["hrrr_rh"],
        paper["ws"][k], paper["wd"][k], paper["t2"][k], paper["rh"][k], src), flush=True)

with open(outp + ".csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, list(rows[0])); w.writeheader(); w.writerows(rows)

# ---------------- 3. figure in the layout of the paper's Fig. 2 ----------------
B, R = "#352f87", "#a52a2a"
x = np.arange(NH)
H = {k: np.array([r["hrrr_" + k] for r in rows]) for k in ("ws", "wd", "t2", "rh")}
fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 7.4), sharex=True, gridspec_kw=dict(hspace=0.06))
b1 = a1.twinx(); b2 = a2.twinx()
a1.plot(x, paper["ws"], color=B, lw=1.6); a1.plot(x, H["ws"], color=B, lw=1.6, ls="--", marker="o", ms=2.5)
b1.plot(x, paper["wd"], color=R, lw=1.6); b1.plot(x, H["wd"], color=R, lw=1.6, ls="--", marker="o", ms=2.5)
a2.plot(x, paper["t2"], color=B, lw=1.6); a2.plot(x, H["t2"], color=B, lw=1.6, ls="--", marker="o", ms=2.5)
b2.plot(x, paper["rh"], color=R, lw=1.6); b2.plot(x, H["rh"], color=R, lw=1.6, ls="--", marker="o", ms=2.5)
a1.set_ylim(0, 18); a1.set_yticks([0, 4.5, 9, 13.5, 18]); b1.set_ylim(0, 360); b1.set_yticks([0, 90, 180, 270, 360])
a2.set_ylim(274, 290); a2.set_yticks([274, 278, 282, 286, 290]); b2.set_ylim(0, 100); b2.set_yticks([0, 25, 50, 75, 100])
a1.set_ylabel("10-m wind speed [m s$^{-1}$]", color=B); b1.set_ylabel("10-m wind direction [$^\\circ$]", color=R)
a2.set_ylabel("2-m temperature [K]", color=B); b2.set_ylabel("2-m relative humidity [%]", color=R)
for a, c in ((a1, B), (a2, B), (b1, R), (b2, R)):
    a.tick_params(axis="y", colors=c)
ticks = [k for k in x if (T0_LST + dt.timedelta(hours=int(k))).hour % 8 == 0]
a2.set_xticks(ticks); a2.set_xticklabels([(T0_LST + dt.timedelta(hours=int(k))).strftime("%d/%H") for k in ticks])
a2.set_xlim(0, NH - 1); a2.set_xlabel("Time [DD/HH], LST (EST = UTC - 5)")
from matplotlib.lines import Line2D
a1.legend(handles=[Line2D([], [], color="0.25", lw=1.6, label="Jimenez et al. (2018) Fig. 2: WRF-Fire SIM1, 111 m domain mean"),
                   Line2D([], [], color="0.25", lw=1.6, ls="--", marker="o", ms=3, label="Our HRRR 3 km analyses, same 13 x 13 km box")],
          loc="upper left", fontsize=8.5, framealpha=0.95)
fig.suptitle("Domain-mean weather, 26 Nov 14:00 - 29 Nov 14:00 LST 2016: paper vs our HRRR data", fontsize=11.5, y=0.94)
fig.savefig(outp + ".png", dpi=150, bbox_inches="tight")


def stats(k):
    d = H[k] - paper[k]
    if k == "wd":
        d = (d + 180) % 360 - 180
    return d.mean(), np.sqrt((d ** 2).mean()), np.corrcoef(H[k], paper[k])[0, 1] if k != "wd" else float("nan")


for k, u in (("ws", "m/s"), ("wd", "deg"), ("t2", "K"), ("rh", "%")):
    b, r, c = stats(k)
    print("%-3s HRRR - paper: mean %+.2f %s, RMS %.2f %s, correlation %.2f" % (k, b, u, r, u, c))
i = int(np.argmax(H["ws"])); j = int(np.argmax(paper["ws"]))
print("peak wind: HRRR %.1f m/s at %s LST, paper %.1f m/s at %s LST" % (H["ws"][i], rows[i]["time_lst"], paper["ws"][j], rows[j]["time_lst"]))
print("wrote", outp + ".png", outp + ".csv")
sys.stdout.flush(); os._exit(0)
