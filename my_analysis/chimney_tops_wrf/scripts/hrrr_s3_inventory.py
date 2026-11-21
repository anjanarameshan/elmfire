#!/usr/bin/env python3
"""List the NOAA HRRR archive (s3://noaa-hrrr-bdp-pds, anonymous HTTPS) for a date range
and write what actually exists, plus the expected-object manifest for the chosen strategy.

Usage:
  python hrrr_s3_inventory.py START END [PRODUCTS] [LEAD]
    START, END  valid-time window in UTC, e.g. 2016-11-22T00 2016-11-30T12
    PRODUCTS    comma list of HRRR products (default wrfprs,wrfsfc,wrfnat)
    LEAD        forecast lead used for forcing (default 0 = analysis / zero-lead)

Writes (relative to the project folder, i.e. the parent of scripts/):
  data/hrrr_inventory/s3_listing.csv          every GRIB2 object found under the date prefixes
  data/hrrr_inventory/expected_objects.csv    one row per (valid hour, product): key, size, available/missing
No credentials are used; nothing is downloaded.
"""
import csv, sys, os, datetime as dt, urllib.request, urllib.parse, xml.etree.ElementTree as ET, time

BUCKET = "https://noaa-hrrr-bdp-pds.s3.amazonaws.com"
NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INV = os.path.join(PROJ, "data", "hrrr_inventory")


def list_prefix(prefix):
    """All objects under a prefix (handles S3 pagination). Returns list of (key, size, lastmod)."""
    out, token = [], None
    while True:
        q = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
        if token:
            q["continuation-token"] = token
        url = BUCKET + "/?" + urllib.parse.urlencode(q)
        for attempt in range(5):
            try:
                with urllib.request.urlopen(url, timeout=60) as r:
                    root = ET.fromstring(r.read())
                break
            except Exception as e:  # transient network error -> back off and retry
                if attempt == 4:
                    raise
                time.sleep(2 ** attempt)
        for c in root.findall(NS + "Contents"):
            out.append((c.find(NS + "Key").text, int(c.find(NS + "Size").text), c.find(NS + "LastModified").text))
        if root.find(NS + "IsTruncated").text == "true":
            token = root.find(NS + "NextContinuationToken").text
        else:
            return out


def parse_key(key):
    """hrrr.YYYYMMDD/conus/hrrr.tHHz.<product>fFF.grib2 -> (cycle datetime, product, lead) or None."""
    try:
        day, _, name = key.split("/")
        parts = name.split(".")
        if parts[-1] != "grib2":
            return None
        cyc = dt.datetime.strptime(day[5:] + parts[1][1:3], "%Y%m%d%H")
        prodlead = parts[2]
        i = prodlead.rindex("f")
        return cyc, prodlead[:i], int(prodlead[i + 1:])
    except (ValueError, IndexError):
        return None


def main():
    start = dt.datetime.strptime(sys.argv[1], "%Y-%m-%dT%H")
    end = dt.datetime.strptime(sys.argv[2], "%Y-%m-%dT%H")
    products = (sys.argv[3] if len(sys.argv) > 3 else "wrfprs,wrfsfc,wrfnat").split(",")
    lead = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    os.makedirs(INV, exist_ok=True)

    # list every day whose cycles can produce a valid time in the window at this lead
    d0 = (start - dt.timedelta(hours=lead)).date()
    days = [d0 + dt.timedelta(days=i) for i in range((end.date() - d0).days + 1)]
    found = {}
    with open(os.path.join(INV, "s3_listing.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["key", "bytes", "last_modified", "cycle_utc", "product", "lead_h", "valid_utc"])
        for d in days:
            objs = list_prefix("hrrr.%s/conus/" % d.strftime("%Y%m%d"))
            print("hrrr.%s/conus/: %d objects" % (d.strftime("%Y%m%d"), len(objs)))
            for key, size, lm in objs:
                p = parse_key(key)
                if not p:
                    continue
                cyc, prod, ld = p
                valid = cyc + dt.timedelta(hours=ld)
                w.writerow([key, size, lm, cyc.strftime("%Y-%m-%dT%H:%MZ"), prod, ld, valid.strftime("%Y-%m-%dT%H:%MZ")])
                found[key] = size

    rows, total, missing = [], 0, []
    t = start
    while t <= end:
        cyc = t - dt.timedelta(hours=lead)
        for prod in products:
            key = "hrrr.%s/conus/hrrr.t%02dz.%sf%02d.grib2" % (cyc.strftime("%Y%m%d"), cyc.hour, prod, lead)
            ok = key in found
            rows.append([t.strftime("%Y-%m-%dT%H:%MZ"), cyc.strftime("%Y-%m-%dT%H:%MZ"), lead, prod, key,
                         found.get(key, ""), "available" if ok else "missing: key not in S3 listing"])
            if ok:
                total += found[key]
            else:
                missing.append((t, prod))
        t += dt.timedelta(hours=1)
    with open(os.path.join(INV, "expected_objects.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["valid_utc", "cycle_utc", "lead_h", "product", "s3_key", "s3_bytes", "s3_status"])
        w.writerows(rows)

    nh = int((end - start).total_seconds() // 3600) + 1
    print("window %s .. %s UTC: %d valid hours, lead f%02d, products %s" % (start, end, nh, lead, ",".join(products)))
    for prod in products:
        sz = sum(int(r[5]) for r in rows if r[3] == prod and r[5] != "")
        n = sum(1 for r in rows if r[3] == prod and r[5] != "")
        print("  %-7s %3d/%d hours available, %.1f GB" % (prod, n, nh, sz / 1e9))
    print("  total %.1f GB" % (total / 1e9))
    for t, prod in missing:
        print("  MISSING %s %s" % (t.strftime("%Y-%m-%d %H UTC"), prod))


if __name__ == "__main__":
    main()
