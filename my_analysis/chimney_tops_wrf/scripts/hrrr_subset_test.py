#!/usr/bin/env python3
"""TEST-ONLY helper: fetch just the GRIB2 messages that wps/Vtable.HRRR.prs uses from one HRRR
wrfprs object, using the .idx byte offsets and parallel HTTP range requests.
The output is a field SUBSET, not the original file; it is stored under data/hrrr_test/ and is
used only for short WPS/WRF tests. Production forcing uses the full files in data/hrrr_raw/.

Usage: python hrrr_subset_test.py S3_KEY OUT.grib2 [WORKERS]
"""
import sys, urllib.request, time
from concurrent.futures import ThreadPoolExecutor
B = "https://noaa-hrrr-bdp-pds.s3.amazonaws.com/"
key, out = sys.argv[1], sys.argv[2]
workers = int(sys.argv[3]) if len(sys.argv) > 3 else 8
idx = [l.split(":") for l in urllib.request.urlopen(B + key + ".idx", timeout=60).read().decode().strip().split("\n")]


def keep(var, lev):
    return ((lev.endswith(" mb") and var in ("TMP", "UGRD", "VGRD", "RH", "HGT"))
            or (lev == "2 m above ground" and var in ("TMP", "RH", "SPFH"))
            or (lev == "10 m above ground" and var in ("UGRD", "VGRD"))
            or (lev == "surface" and var in ("PRES", "HGT", "WEASD", "SNOD", "TMP", "CNWAT", "ICEC", "LAND"))
            or (lev == "mean sea level" and var == "MSLMA")
            or ("below ground" in lev and var in ("TSOIL", "SOILW")))


# merge adjacent wanted messages into byte ranges
ranges = []
for i, l in enumerate(idx):
    if keep(l[3], l[4]):
        s = int(l[1]); e = int(idx[i + 1][1]) - 1 if i + 1 < len(idx) else None
        if ranges and ranges[-1][1] is not None and ranges[-1][1] + 1 == s:
            ranges[-1][1] = e
        else:
            ranges.append([s, e])


def get(r):
    hdr = {"Range": "bytes=%d-%s" % (r[0], "" if r[1] is None else r[1])}
    for a in range(6):
        try:
            return urllib.request.urlopen(urllib.request.Request(B + key, headers=hdr), timeout=120).read()
        except Exception:
            if a == 5:
                raise
            time.sleep(3 * 2 ** a)


with ThreadPoolExecutor(workers) as ex:
    parts = list(ex.map(get, ranges))
for r, p in zip(ranges, parts):
    assert p[:4] == b"GRIB" and p[-4:] == b"7777" and (r[1] is None or len(p) == r[1] - r[0] + 1)
open(out, "wb").write(b"".join(parts))
print("wrote %s: %d byte ranges, %.0f MB" % (out, len(ranges), sum(map(len, parts)) / 1e6))
