#!/usr/bin/env python3
"""Image chips for the by-eye damage review (blind: the page never shows the automatic label).

Usage: python make_review_chips.py PERIMETER.shp [batch2]   (after detect_building_damage.py)
Batch 1 sample: every 'uncertain' building + a random 10 % of survived / destroyed / new_construction (seed 1).
Batch 2 (after batch 1 is reviewed): every building not in batch 1 + 60 random repeats of batch-1 buildings (seed 2),
shuffled together so the repeats are blind; repeats get answer key r<id>, others b<id>.
Batch 2 writes sheet2_NN.jpg, buildings2.json and damage/review_sample2.csv.
Chip: 70 m x 70 m around the footprint centroid, NAIP 2016 (left) | 2018 (right), footprint outlined in yellow,
shown at 200 px. Chips are packed 10 x 6 per JPEG sheet.
Writes damage/review/sheet_NN.jpg, damage/review/buildings.json (order shown on the page) and
damage/review_sample.csv (id, auto label, sheet, slot) - the automatic labels stay out of the page.
"""
import sys, os, json, random
import numpy as np
from osgeo import gdal, ogr, osr
from PIL import Image, ImageDraw

gdal.UseExceptions(); ogr.UseExceptions()
shp = sys.argv[1]; OUT = "damage/review"; os.makedirs(OUT, exist_ok=True)
W, PX, COLS, ROWS = 70, 200, 10, 6
A = gdal.Open("data/naip/bldg4_2016.tif"); B = gdal.Open("data/naip/bldg4_2018.tif")
gt = A.GetGeoTransform(); nx, ny = A.RasterXSize, A.RasterYSize
utm = osr.SpatialReference(); utm.ImportFromEPSG(32617); utm.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
wgs = osr.SpatialReference(); wgs.ImportFromEPSG(4326); wgs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
to_utm = osr.CoordinateTransformation(wgs, utm)

# same footprint order and ids as detect_building_damage.py
pds = ogr.Open(shp); pl = pds.GetLayer(); perim = None
for f in pl:
    g = f.GetGeometryRef().Clone(); g.TransformTo(utm); perim = g if perim is None else perim.Union(g)
sds = ogr.Open("data/ms_buildings.gpkg"); src = sds.GetLayer()
src.SetSpatialFilterRect(-83.58, 35.66, -83.44, 35.78)
geoms = {}
for f in src:
    g = f.GetGeometryRef().Clone(); g.Transform(to_utm)
    if perim.Contains(g.Centroid()):
        geoms[len(geoms) + 1] = g

rows = [l.strip().split(",") for l in open("damage/damage_auto.csv")][1:]
auto = {int(r[0]): (float(r[1]), float(r[2]), float(r[3]), r[-1]) for r in rows}
assert len(auto) == len(geoms)
B2 = len(sys.argv) > 2 and sys.argv[2] == "batch2"
random.seed(1)
pick = [k for k, v in auto.items() if v[3] == "uncertain"]
for lab in ("survived", "destroyed", "new_construction"):
    ks = [k for k, v in auto.items() if v[3] == lab]
    pick += random.sample(ks, max(1, round(0.1 * len(ks))))
random.shuffle(pick)
keys = ["b%d" % k for k in pick]
if B2:
    done = set(pick); random.seed(2)
    rest = [k for k in auto if k not in done]; rep = random.sample(sorted(done), 60)
    items = [("b%d" % k, k) for k in rest] + [("r%d" % k, k) for k in rep]
    random.shuffle(items)
    keys, pick = [i[0] for i in items], [i[1] for i in items]
SH, JS, CSV = ("sheet2_%02d.jpg", "buildings2.json", "damage/review_sample2.csv") if B2 else \
    ("sheet_%02d.jpg", "buildings.json", "damage/review_sample.csv")
print("buildings to review:", len(pick))


def chip(ds, cx, cy, ring):
    c0 = int((cx - W / 2 - gt[0]) / gt[1]); r0 = int((cy + W / 2 - gt[3]) / gt[5])
    c0 = min(max(c0, 0), nx - W); r0 = min(max(r0, 0), ny - W)
    a = np.dstack([ds.GetRasterBand(k).ReadAsArray(c0, r0, W, W) for k in (1, 2, 3)]).astype(np.uint8)
    im = Image.fromarray(a).resize((PX, PX), Image.BILINEAR)
    s = PX / W; d = ImageDraw.Draw(im)
    pts = [((x - (gt[0] + c0 * gt[1])) * s, ((gt[3] + r0 * gt[5]) - y) * s) for x, y in ring]
    d.line(pts + pts[:1], fill=(255, 230, 0), width=2)
    return im


per = COLS * ROWS; out = []; sample = []
for s0 in range(0, len(pick), per):
    sheet = Image.new("RGB", (COLS * 2 * PX, ROWS * PX), (0, 0, 0)); sn = s0 // per
    for j, k in enumerate(pick[s0:s0 + per]):
        g = geoms[k]; c = g.Centroid()
        ring = g.GetGeometryRef(0).GetPoints() if g.GetGeometryType() in (ogr.wkbPolygon, ogr.wkbPolygon25D) \
            else g.GetGeometryRef(0).GetGeometryRef(0).GetPoints()
        ring = [(p[0], p[1]) for p in ring]
        x, y = (j % COLS) * 2 * PX, (j // COLS) * PX
        sheet.paste(chip(A, c.GetX(), c.GetY(), ring), (x, y))
        sheet.paste(chip(B, c.GetX(), c.GetY(), ring), (x + PX, y))
        lo, la, ar, lab = auto[k]
        out.append({"id": k, "k": keys[s0 + j], "lon": round(lo, 6), "lat": round(la, 6), "area": round(ar), "s": sn, "x": x, "y": y})
        sample.append((keys[s0 + j], k, lab, sn, j))
    sheet.save(OUT + "/" + SH % sn, quality=82)
json.dump(out, open(OUT + "/" + JS, "w"), separators=(",", ":"))
with open(CSV, "w") as f:
    f.write("key,id,label_auto,sheet,slot\n")
    for r in sample:
        f.write("%s,%d,%s,%d,%d\n" % r)
print("sheets:", sn + 1, "->", OUT)
