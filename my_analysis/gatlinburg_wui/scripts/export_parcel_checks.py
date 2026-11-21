#!/usr/bin/env python3
"""Files for the two manual checks that cannot be automated (state assessor sites block scripts; Google Earth is visual).

Usage: python export_parcel_checks.py   (after label_versions_parcel.py)
1. Disagreements between the imagery label (A) and the parcel proxy (D): damage/disagreements_A_vs_D.kml (open in Google
   Earth Pro, View > Historical Imagery, December 2016) and disagreements_A_vs_D.csv (with a Google Earth web link and an
   empty 'final_label' column to fill in: destroyed / damaged / survived / unsure).
2. Example parcels for decoding EXTWALL / CONSTCD / IMPTYPE (look each PARID or address up at
   https://assessment.cot.tn.gov/TPAD, Sevier County, and note the description): vulnerability/parcel_code_examples.csv
"""
import csv, collections
from xml.sax.saxutils import escape

R = {r["id"]: r for r in csv.DictReader(open("vulnerability/features.csv"))}
LV = {r["id"]: r for r in csv.DictReader(open("vulnerability/features_labels.csv"))}
J = {r["id"]: r for r in csv.DictReader(open("vulnerability/parcel_join.csv"))}
dis = [i for i in LV if LV[i]["y_A"] in ("0", "1") and LV[i]["y_D"] in ("0", "1") and LV[i]["y_A"] != LV[i]["y_D"]]
dis.sort(key=lambda i: (LV[i]["y_A"], int(i)))
kind = lambda i: "label burned, parcel unchanged" if LV[i]["y_A"] == "1" else "label survived, parcel rebuilt/gone"
with open("damage/disagreements_A_vs_D.csv", "w") as f:
    w = csv.writer(f)
    w.writerow(["id", "lat", "lon", "imagery_label", "parcel_proxy", "yrblt_2016", "yrblt_2026", "case", "google_earth_web", "final_label"])
    for i in dis:
        r, j = R[i], J[i]
        w.writerow([i, r["lat"], r["lon"], r["review"], j["proxy"], j["yrblt_2016"], j["yrblt_2026"], kind(i),
                    "https://earth.google.com/web/@%s,%s,600a,500d,35y,0h,0t,0r" % (r["lat"], r["lon"]), ""])
style = {"label burned, parcel unchanged": "ff2f2fd0", "label survived, parcel rebuilt/gone": "ffd07a2b"}  # aabbggrr
with open("damage/disagreements_A_vs_D.kml", "w") as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document>\n'
            '<name>Gatlinburg: imagery label vs parcel proxy (%d disagreements)</name>\n' % len(dis))
    for k, c in style.items():
        f.write('<Style id="%s"><IconStyle><color>%s</color><scale>0.8</scale></IconStyle></Style>\n' % (k[:5] + k[-4:].replace("/", ""), c))
    for k in style:
        f.write("<Folder><name>%s</name>\n" % escape(k))
        for i in [i for i in dis if kind(i) == k]:
            r, j = R[i], J[i]
            f.write('<Placemark><name>%s</name><styleUrl>#%s</styleUrl><description>%s</description>'
                    '<Point><coordinates>%s,%s,0</coordinates></Point></Placemark>\n' % (
                        i, k[:5] + k[-4:].replace("/", ""), escape("imagery: %s | parcel: %s | year built 2016: %s, now: %s" % (
                            r["review"], j["proxy"], j["yrblt_2016"], j["yrblt_2026"])), r["lon"], r["lat"]))
        f.write("</Folder>\n")
    f.write("</Document></kml>\n")
c = collections.Counter(kind(i) for i in dis)
print("disagreements:", len(dis), dict(c))

# examples per building-code value (most common codes first, 3 parcels each, single-footprint parcels in MTBS)
ex = []
for fld in ("extwall_2016", "constcd_2016", "imptype_2016"):
    cnt = collections.Counter(j[fld].strip() for j in J.values() if j[fld].strip())
    for code, n in cnt.most_common(10):
        picks = [i for i in J if J[i][fld].strip() == code and J[i]["n_fp"] == "1"][:3]
        for i in picks:
            ex.append([fld.replace("_2016", "").upper(), code, n, J[i]["parid_2016"], R[i]["lat"], R[i]["lon"], ""])
with open("vulnerability/parcel_code_examples.csv", "w") as f:
    w = csv.writer(f); w.writerow(["field", "code", "buildings_with_code_in_MTBS", "parid", "lat", "lon", "description_from_TPAD"])
    w.writerows(ex)
print("code examples:", len(ex), "rows")
for fld in ("extwall_2016", "constcd_2016", "imptype_2016"):
    print(fld, collections.Counter(j[fld].strip() for j in J.values()).most_common(10))
