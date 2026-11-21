#!/usr/bin/env python3
"""Parcel-based damage proxy (rebuild signal) and building attributes, compared with the imagery damage labels.

Usage: python parcel_damage_proxy.py PERIMETER.shp   (after download_parcels.py)
Inputs: data/parcels/parcels_2016.geojson (pre-fire, building data of 12 Oct 2016), parcels_2026.geojson (current),
        vulnerability/features.csv (1,614 footprints in MTBS: centroid x, y in UTM 17N, labels y_A / review).
Per 2016 parcel: building present in 2016 = YRBLT 1800..2016 or IMPVAL > 0. Matched to the 2026 parcel by PARID,
else by the 2026 parcel containing the 2016 parcel's interior point. Proxy status of the main building:
  rebuilt   2026 YRBLT 2017..2026 (a new main building after the fire)
  gone      no 2026 building (YRBLT missing / 0 and IMPVAL 0)
  same      2026 YRBLT <= 2016 (main building older than the fire, i.e. not replaced)
  unmatched no 2026 parcel found
Control: rebuilt / gone share for 2016-built parcels outside MTBS (same box) = background rate of replacement.
Per footprint: the 2016 parcel containing its centroid -> parcel attributes + proxy; n_fp = footprints in that parcel
(the parcel record describes only its main building, so single-footprint parcels give the cleanest comparison).
Writes vulnerability/parcel_join.csv and vulnerability/parcel_proxy_summary.txt.
"""
import sys, csv, json, collections
from osgeo import ogr, osr

ogr.UseExceptions()
utm = osr.SpatialReference(); utm.ImportFromEPSG(32617); utm.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
wgs = osr.SpatialReference(); wgs.ImportFromEPSG(4326); wgs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)


def load(path):
    out = []
    for f in json.load(open(path))["features"]:
        if not f.get("geometry"):
            continue
        g = ogr.CreateGeometryFromJson(json.dumps(f["geometry"]))
        if g is None or g.IsEmpty():
            continue
        out.append((f["properties"], g))
    return out


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def has_bldg_2016(p):
    return 1800 <= num(p.get("YRBLT")) <= 2016 or num(p.get("IMPVAL")) > 0


def status(p26):
    if p26 is None:
        return "unmatched"
    y = num(p26.get("YRBLT"))
    if 2017 <= y <= 2026:
        return "rebuilt"
    if y < 1800 and num(p26.get("IMPVAL")) <= 0:
        return "gone"
    return "same"


P16, P26 = load("data/parcels/parcels_2016.geojson"), load("data/parcels/parcels_2026.geojson")
by_id26 = {p.get("PARID"): (p, g) for p, g in P26 if p.get("PARID")}
ds26 = ogr.GetDriverByName("MEM").CreateDataSource("")  # keep a reference: the layer dies with its data source
lay26 = ds26.CreateLayer("p26", utm, ogr.wkbUnknown)
lay26.CreateField(ogr.FieldDefn("i", ogr.OFTInteger))
for i, (p, g) in enumerate(P26):
    ft = ogr.Feature(lay26.GetLayerDefn()); ft.SetField("i", i); ft.SetGeometry(g); lay26.CreateFeature(ft)


def match26(p, g):
    if p.get("PARID") in by_id26:
        return by_id26[p["PARID"]][0], "id"
    pt = g.PointOnSurface(); lay26.SetSpatialFilter(pt)
    for ft in lay26:
        if P26[ft.GetField("i")][1].Contains(pt):
            lay26.SetSpatialFilter(None); return P26[ft.GetField("i")][0], "space"
    lay26.SetSpatialFilter(None); return None, "none"


perim = None
pds = ogr.Open(sys.argv[1])
for f in pds.GetLayer():
    g = f.GetGeometryRef().Clone(); g.TransformTo(utm); perim = g if perim is None else perim.Union(g)

recs = []
for i, (p, g) in enumerate(P16):
    if not has_bldg_2016(p):
        continue
    p26, how = match26(p, g)
    recs.append(dict(i=i, inside=perim.Contains(g.PointOnSurface()), status=status(p26), how=how, p16=p, p26=p26))
L = ["Parcel damage proxy (Sevier County parcels, pre-fire 12 Oct 2016 vs current), study box",
     "2016 parcels %d, with a building %d; 2026 parcels %d" % (len(P16), len(recs), len(P26)), "",
     "Main-building status by location (share of 2016 parcels with a building):"]
for nm, sel in (("inside MTBS", True), ("outside MTBS (control)", False)):
    c = collections.Counter(r["status"] for r in recs if r["inside"] == sel); n = sum(c.values())
    L.append("  %-24s n=%5d  " % (nm, n) + "  ".join("%s %d (%.0f%%)" % (k, c[k], 100 * c[k] / max(n, 1))
                                                     for k in ("same", "rebuilt", "gone", "unmatched")))
    yrs = collections.Counter(int(num(r["p26"].get("YRBLT"))) for r in recs if r["inside"] == sel and r["status"] == "rebuilt")
    L.append("  %-24s rebuilt by year: %s" % ("", ", ".join("%d: %d" % (y, yrs[y]) for y in sorted(yrs))))

# footprints -> 2016 parcel
ds16 = ogr.GetDriverByName("MEM").CreateDataSource("")  # keep a reference: the layer dies with its data source
lay16 = ds16.CreateLayer("p16", utm, ogr.wkbUnknown)
lay16.CreateField(ogr.FieldDefn("i", ogr.OFTInteger))
for i, (p, g) in enumerate(P16):
    ft = ogr.Feature(lay16.GetLayerDefn()); ft.SetField("i", i); ft.SetGeometry(g); lay16.CreateFeature(ft)
rec_by_i = {r["i"]: r for r in recs}
B = list(csv.DictReader(open("vulnerability/features.csv")))
hit = []
for b in B:
    pt = ogr.Geometry(ogr.wkbPoint); pt.AddPoint_2D(float(b["x"]), float(b["y"])); lay16.SetSpatialFilter(pt); j = None
    for ft in lay16:
        if P16[ft.GetField("i")][1].Contains(pt):
            j = ft.GetField("i"); break
    hit.append(j)
lay16.SetSpatialFilter(None)
nfp = collections.Counter(j for j in hit if j is not None)
cols16 = ["PARID", "LANDUSE", "IMPTYPE", "YRBLT", "STORIES", "EXTWALL", "CONSTCD", "SFLA", "GRADE", "BLDGCOND", "IMPVAL"]
with open("vulnerability/parcel_join.csv", "w") as f:
    w = csv.writer(f)
    w.writerow(["id", "review", "y_A", "n_fp", "proxy", "match", "yrblt_2026", "impval_2026"] + [c.lower() + "_2016" for c in cols16])
    for b, j in zip(B, hit):
        r = rec_by_i.get(j)
        p16 = P16[j][0] if j is not None else {}
        proxy = r["status"] if r else ("no_parcel" if j is None else "no_bldg_2016")
        p26 = r["p26"] if r and r["p26"] else {}
        w.writerow([b["id"], b["review"], b["y_A"], nfp.get(j, 0) if j is not None else 0, proxy, r["how"] if r else "",
                    p26.get("YRBLT", ""), p26.get("IMPVAL", "")] + [p16.get(c, "") for c in cols16])

rows = list(csv.DictReader(open("vulnerability/parcel_join.csv")))
L += ["", "Footprints in MTBS: %d; in a 2016 parcel with a building: %d; single-footprint parcels: %d" % (
    len(rows), sum(r["proxy"] in ("same", "rebuilt", "gone", "unmatched") for r in rows),
    sum(r["n_fp"] == "1" and r["proxy"] in ("same", "rebuilt", "gone") for r in rows))]
for nm, sel in (("all footprints", lambda r: True), ("single-footprint parcels", lambda r: r["n_fp"] == "1")):
    L.append(""); L.append("Imagery label (rows) vs parcel proxy (columns), %s:" % nm)
    L.append("  %-10s %7s %8s %6s   destroyed-like share" % ("label", "same", "rebuilt", "gone"))
    for lab in ("destroyed", "damaged", "survived", "new", "unsure"):
        c = collections.Counter(r["proxy"] for r in rows if r["review"] == lab and sel(r) and r["proxy"] in ("same", "rebuilt", "gone"))
        n = sum(c.values())
        L.append("  %-10s %7d %8d %6d   %.0f%% (n=%d)" % (lab, c["same"], c["rebuilt"], c["gone"],
                                                       100 * (c["rebuilt"] + c["gone"]) / max(n, 1), n))
txt = "\n".join(L); print(txt); open("vulnerability/parcel_proxy_summary.txt", "w").write(txt + "\n")
