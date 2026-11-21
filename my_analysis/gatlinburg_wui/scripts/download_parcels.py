#!/usr/bin/env python3
"""Download Sevier County parcels (public ArcGIS feature services) for the study box, before and after the fire.

Usage: python download_parcels.py   (from gatlinburg_wui)
Sources (Sevier County GIS, services1.arcgis.com/Qu4yM4JJvNoC2GKw, no login needed):
  pre  = Parcels_m23           building attributes updated 12 Oct 2016 (UPDATED), TAXYR 2017 -> pre-fire snapshot
  post = Parcel_Sevier_County  current county parcels (LASTUPDATE Sept 2026)
Box: lon -83.58..-83.44, lat 35.66..35.78 (same as the building analyses). Geometry requested in UTM 17N (EPSG:32617).
Paged 1000 records at a time (the services' maxRecordCount). Writes data/parcels/parcels_2016.geojson and
parcels_2026.geojson plus download_log.txt (counts, date).
"""
import json, os, time, urllib.parse, urllib.request

BASE = "https://services1.arcgis.com/Qu4yM4JJvNoC2GKw/arcgis/rest/services/%s/FeatureServer/0/query"
BOX = "-83.58,35.66,-83.44,35.78"
LAYERS = {
    "2016": ("Parcels_m23", "PARID,GISLINK,ADDRESS,LANDUSE,PROPTYPE,BLDGS,IMPTYPE,IMP,YRBLT,EFFYRBLT,STORIES,EXTWALL,CONSTCD,"
                            "BASEAREA,SFLA,GRADE,BLDGCOND,TOPO,IMPVAL,LANDVAL,APPRAISAL,TAXYR,UPDATED"),
    "2026": ("Parcel_Sevier_County", "PARID,GISLINK,ADDRESS,LANDUSE,CLASS,BLDGS,IMPTYPE,IMP,YRBLT,STORIES,EXTWALL,BASEAREA,SFLA,"
                                     "GRADE,BLDGCOND,TOPO,IMPVAL,LANDMKTVAL,APPRAISAL,TAXYR,LASTUPDATE"),
}
OUT = "data/parcels"; os.makedirs(OUT, exist_ok=True)
log = []
for tag, (svc, fields) in LAYERS.items():
    feats, off = [], 0
    while True:
        q = dict(where="1=1", geometry=BOX, geometryType="esriGeometryEnvelope", inSR=4326, spatialRel="esriSpatialRelIntersects",
                 outFields=fields, outSR=32617, returnGeometry="true", orderByFields="OBJECTID", resultOffset=off,
                 resultRecordCount=1000, f="geojson")
        with urllib.request.urlopen(BASE % svc + "?" + urllib.parse.urlencode(q), timeout=120) as r:
            page = json.load(r)
        if "error" in page:
            raise SystemExit("%s: %s" % (svc, page["error"]))
        feats += page["features"]
        if len(page["features"]) < 1000:
            break
        off += 1000; time.sleep(0.5)
    fc = {"type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": "EPSG:32617"}}, "features": feats}
    json.dump(fc, open("%s/parcels_%s.geojson" % (OUT, tag), "w"))
    log.append("%s  %-22s %6d parcels  downloaded %s" % (tag, svc, len(feats), time.strftime("%Y-%m-%d")))
    print(log[-1])
open(OUT + "/download_log.txt", "w").write("\n".join(log) + "\n")
