#!/usr/bin/env python3
"""Exterior wall material of each building (2016 parcel EXTWALL code) and observed burned share by wall class.

Usage: python wall_material.py   (after parcel_damage_proxy.py and label_versions_parcel.py)
Code list: Tennessee Comptroller, Division of Property Assessments, Commercial Listing Manual (rev. 2021-08-09),
appendix "Exterior Walls", printed p. 64 (codes 00-19; the same codes occur in the Sevier County parcel EXTWALL field).
The parcel record describes the parcel's main building, so single-footprint parcels (n_fp = 1) are the cleanest match.
Wall classes for fire: combustible siding / cladding, mixed masonry + wood, masonry, metal / glass.
Writes vulnerability/wall_material.csv (id, extwall code, description, class) and vulnerability/wall_material_summary.txt.
"""
import csv, collections

CODES = {"00": "Unfinished", "01": "Corrugated Metal", "02": "Siding Minimum", "03": "Siding Below Average",
         "04": "Siding Average", "05": "Siding Above Average", "06": "Wood Stucco", "07": "Concrete Block",
         "08": "Concrete Block/Wood", "09": "Concrete Block/Stucco", "10": "Concrete Block/Brick", "11": "Common Brick",
         "12": "Brick/Wood", "13": "Stone/Brick", "14": "Cement/Brick", "15": "Prefinished Metal", "16": "Precast Panel",
         "17": "Glass", "18": "Stone/Wood", "19": "Prefinished Metal Crimped"}
CLASS = {c: "combustible siding" for c in ("00", "02", "03", "04", "05", "06")}
CLASS.update({c: "masonry + wood" for c in ("08", "12", "18")})
CLASS.update({c: "masonry" for c in ("07", "09", "10", "11", "13", "14", "16")})
CLASS.update({c: "metal / glass" for c in ("01", "15", "17", "19")})

J = {r["id"]: r for r in csv.DictReader(open("vulnerability/parcel_join.csv"))}
LV = {r["id"]: r for r in csv.DictReader(open("vulnerability/features_labels.csv"))}
rows = []
for i, j in J.items():
    c = j["extwall_2016"].strip()
    rows.append(dict(id=i, extwall=c, description=CODES.get(c, ""), wall_class=CLASS.get(c, "unknown"),
                     n_fp=j["n_fp"], y_A=LV[i]["y_A"], y_D=LV[i]["y_D"]))
with open("vulnerability/wall_material.csv", "w") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

L = ["Exterior wall material (2016 parcel EXTWALL; Tennessee Commercial Listing Manual p. 64) vs observed damage",
     "Buildings with centroid in MTBS: %d; with a wall code: %d; on single-footprint parcels with a code: %d" % (
         len(rows), sum(r["description"] != "" for r in rows), sum(r["description"] != "" and r["n_fp"] == "1" for r in rows)), ""]
for title, sel in (("all buildings", lambda r: True), ("single-footprint parcels", lambda r: r["n_fp"] == "1")):
    for lab in ("y_A", "y_D"):
        L.append("%s, label %s (burned share, n labelled):" % (title, lab[-1]))
        for key, name in (("description", "code"), ("wall_class", "class")):
            g = collections.defaultdict(list)
            for r in rows:
                if sel(r) and r[lab] in ("0", "1"):
                    g[r[key] or "no code"].append(int(r[lab]))
            for k, v in sorted(g.items(), key=lambda kv: -len(kv[1])):
                L.append("  %-6s %-28s n=%4d  burned %.0f %%" % (name, k, len(v), 100 * sum(v) / len(v)))
        L.append("")
txt = "\n".join(L); print(txt); open("vulnerability/wall_material_summary.txt", "w").write(txt + "\n")
