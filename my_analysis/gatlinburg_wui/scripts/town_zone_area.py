#!/usr/bin/env python3
"""Area of the burn perimeter that lies in the built-up (town) zone vs in forest without buildings.

Usage: python town_zone_area.py PERIMETER.shp
Buildings: Microsoft footprints (2019) in the study box, minus those the reviewer marked 'new' (not built in 2016).
Town zone = morphological closing of the footprints: buffer 100 m, union, shrink by 50 m (joins houses up to
~100-200 m apart into one built-up area; the zone edge = "the line where the buildings are").
Checks: area within 50 m and within 100 m of any footprint edge.
Writes timeline/../vulnerability/town_zone.txt and town_zone.png.
"""
import sys, os, json, glob
from osgeo import ogr, osr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ogr.UseExceptions()
OUT = "vulnerability"; AC = 4046.856
utm = osr.SpatialReference(); utm.ImportFromEPSG(32617); utm.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
wgs = osr.SpatialReference(); wgs.ImportFromEPSG(4326); wgs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
to_utm = osr.CoordinateTransformation(wgs, utm)

pds = ogr.Open(sys.argv[1]); perim = None
for f in pds.GetLayer():
    g = f.GetGeometryRef().Clone(); g.TransformTo(utm); perim = g if perim is None else perim.Union(g)
new = set()
for d in ("labels", "labels2"):
    for f in glob.glob("damage/review_answers/%s/b*.json" % d):
        if json.load(open(f))["label"] == "new":
            new.add(int(os.path.basename(f)[1:-5]))
sds = ogr.Open("data/ms_buildings.gpkg"); src = sds.GetLayer(); src.SetSpatialFilterRect(-83.58, 35.66, -83.44, 35.78)
fps, nin, skipped = [], 0, 0
for f in src:
    g = f.GetGeometryRef().Clone(); g.Transform(to_utm)
    if perim.Contains(g.Centroid()):
        nin += 1
        if nin in new:
            skipped += 1; continue
    fps.append(g)


def union_buffer(d):
    m = ogr.Geometry(ogr.wkbMultiPolygon)
    for g in fps:
        b = g.Buffer(d, 4)
        for k in range(b.GetGeometryCount()) if b.GetGeometryType() == ogr.wkbMultiPolygon else [None]:
            m.AddGeometry(b if k is None else b.GetGeometryRef(k))
    return m.UnionCascaded()


town = union_buffer(100).Buffer(-50, 4)
b50, b100 = union_buffer(50), union_buffer(100)
P = perim.GetArea()
L = ["Burn perimeter (MTBS) split into town zone and forest without buildings",
     "footprints used: %d (left out %d built after 2016)" % (len(fps), skipped),
     "MTBS perimeter area: %.0f ac (%.1f km2)" % (P / AC, P / 1e6), ""]
for nm, z in (("town zone (buffer 100 m, shrink 50 m)", town), ("within 50 m of a building", b50), ("within 100 m of a building", b100)):
    a = perim.Intersection(z).GetArea()
    L.append("%-40s in MTBS %7.0f ac (%5.1f km2, %4.1f %% of MTBS); forest part %7.0f ac (%4.1f %%)" % (
        nm, a / AC, a / 1e6, 100 * a / P, (P - a) / AC, 100 * (P - a) / P))
tz = perim.Intersection(town)
L.append(""); L.append("Town zone outside MTBS (built-up area that did not burn, same box): %.0f ac" % (town.Difference(perim).GetArea() / AC))
txt = "\n".join(L); print(txt); open(OUT + "/town_zone.txt", "w").write(txt + "\n")


def draw(ax, g, **kw):
    if g.GetGeometryType() in (ogr.wkbPolygon, ogr.wkbPolygon25D):
        g = [g]
    else:
        g = [g.GetGeometryRef(k) for k in range(g.GetGeometryCount())]
    for p in g:
        for k in range(p.GetGeometryCount()):
            r = p.GetGeometryRef(k).GetPoints()
            ax.fill([q[0] / 1000 for q in r], [q[1] / 1000 for q in r], **(kw if k == 0 else dict(color="white", lw=0)))


fig, ax = plt.subplots(figsize=(8, 8))
draw(ax, perim, color="#e8d8c3", lw=0)
draw(ax, town.Difference(perim), color="#d9dde3", lw=0)
draw(ax, tz, color="#c2410c", lw=0, alpha=0.85)
r = perim.GetBoundary()
for k in range(max(r.GetGeometryCount(), 1)):
    pts = (r.GetGeometryRef(k) if r.GetGeometryCount() else r).GetPoints()
    ax.plot([q[0] / 1000 for q in pts], [q[1] / 1000 for q in pts], color="#57606a", lw=0.8)
env = perim.GetEnvelope(); ax.set_xlim(env[0] / 1000 - 1, env[1] / 1000 + 1); ax.set_ylim(env[2] / 1000 - 1, env[3] / 1000 + 1)
ax.set_aspect("equal"); ax.set_xlabel("UTM 17N easting (km)", color="#57606a"); ax.set_ylabel("northing (km)", color="#57606a")
ax.spines[["top", "right"]].set_visible(False); ax.tick_params(colors="#57606a", labelsize=8.5)
a_tz = tz.GetArea()
ax.legend(handles=[Patch(color="#c2410c", label="burned, town zone: %.0f ac (%.0f %%)" % (a_tz / AC, 100 * a_tz / P)),
                   Patch(color="#e8d8c3", label="burned, forest without buildings: %.0f ac" % ((P - a_tz) / AC)),
                   Patch(color="#d9dde3", label="town zone outside the burn perimeter")], frameon=False, fontsize=9, loc="lower left")
ax.set_title("MTBS burn perimeter (%.0f ac): town zone vs forest" % (P / AC), loc="left", fontsize=11)
fig.tight_layout(); fig.savefig(OUT + "/town_zone.png", dpi=160, facecolor="white")
print("wrote", OUT + "/town_zone.txt, town_zone.png")
