#!/usr/bin/env python3
"""GRIB2 message inventory (header-only, ecCodes) for downloaded HRRR files.

Usage:
  python grib_inventory.py OUT.csv FILE.grib2 [FILE.grib2 ...]

One row per GRIB message: file, message number, discipline/category/number (the GRIB2 codes a
WPS Vtable matches on), shortName, name, units, level type, level, cycle (dataDate/dataTime),
forecast step, valid time.
"""
import csv, sys, os, datetime as dt
import eccodes

KEYS = ["discipline", "parameterCategory", "parameterNumber", "shortName", "name", "units",
        "typeOfFirstFixedSurface", "typeOfLevel", "level", "stepRange", "dataDate", "dataTime"]


def main():
    out, files = sys.argv[1], sys.argv[2:]
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["file", "msg"] + KEYS + ["cycle_utc", "valid_utc"])
        for path in files:
            with open(path, "rb") as g:
                n = 0
                while True:
                    h = eccodes.codes_grib_new_from_file(g, headers_only=True)
                    if h is None:
                        break
                    n += 1
                    vals = []
                    for k in KEYS:
                        try:
                            vals.append(eccodes.codes_get(h, k))
                        except eccodes.KeyValueNotFoundError:
                            vals.append("")
                    d = dict(zip(KEYS, vals))
                    cyc = dt.datetime.strptime("%08d%04d" % (int(d["dataDate"]), int(d["dataTime"])), "%Y%m%d%H%M")
                    end = str(d["stepRange"]).split("-")[-1]
                    valid = cyc + dt.timedelta(hours=int(end)) if end.isdigit() else ""
                    w.writerow([os.path.basename(path), n] + vals +
                               [cyc.strftime("%Y-%m-%dT%H:%MZ"), valid.strftime("%Y-%m-%dT%H:%MZ") if valid else ""])
                    eccodes.codes_release(h)
            print("%s: %d messages" % (os.path.basename(path), n))


if __name__ == "__main__":
    main()
