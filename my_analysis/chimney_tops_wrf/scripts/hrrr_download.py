#!/usr/bin/env python3
"""Download HRRR GRIB2 objects listed in data/hrrr_inventory/expected_objects.csv (anonymous HTTPS).

Usage:
  python hrrr_download.py START END PRODUCTS [WORKERS]
    START, END  valid-time window in UTC (inclusive), e.g. 2016-11-27T12 2016-11-29T12
    PRODUCTS    comma list, e.g. wrfprs
    WORKERS     parallel downloads (default 4)

Each file is written to <name>.part (an interrupted transfer is resumed with an HTTP Range
request, not restarted), checked (byte count equals the S3 size, file starts with
'GRIB', every message decodes as GRIB edition 2 and the last message ends with '7777'),
checksummed (SHA-256) and only then renamed to its original HRRR filename under
data/hrrr_raw/hrrr.YYYYMMDD/. Files already present and listed as verified are skipped,
so the script can be re-run to resume. Every expected object gets a row in
data/hrrr_inventory/hrrr_manifest.csv, including missing and failed ones.
"""
import csv, sys, os, time, hashlib, datetime as dt, urllib.request, urllib.error, threading
from concurrent.futures import ThreadPoolExecutor
import eccodes

BUCKET = "https://noaa-hrrr-bdp-pds.s3.amazonaws.com/"
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INV = os.path.join(PROJ, "data", "hrrr_inventory")
RAW = os.path.join(PROJ, "data", "hrrr_raw")
MANIFEST = os.path.join(INV, "hrrr_manifest.csv")
FIELDS = ["s3_key", "cycle_utc", "lead_h", "valid_utc", "product", "local_file", "s3_bytes", "bytes",
          "grib_messages", "sha256", "status", "downloaded_utc"]
lock = threading.Lock()


def log(msg):
    line = "%s %s" % (dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), msg)
    with lock:
        print(line, flush=True)
        with open(os.path.join(PROJ, "logs", "download.log"), "a") as f:
            f.write(line + "\n")


def check_grib2(path):
    """Return number of GRIB2 messages; raise if the file is not a complete GRIB2 file."""
    with open(path, "rb") as f:
        if f.read(4) != b"GRIB":
            raise ValueError("does not start with GRIB")
        f.seek(-4, 2)
        if f.read(4) != b"7777":
            raise ValueError("does not end with 7777 (truncated)")
    n = 0
    with open(path, "rb") as f:
        while True:
            h = eccodes.codes_grib_new_from_file(f, headers_only=True)
            if h is None:
                break
            try:
                if eccodes.codes_get(h, "edition") != 2:
                    raise ValueError("message %d is not GRIB edition 2" % (n + 1))
            finally:
                eccodes.codes_release(h)
            n += 1
    if n == 0:
        raise ValueError("no GRIB messages")
    return n


def fetch(row):
    key, size = row["s3_key"], int(row["s3_bytes"])
    day = key.split("/")[0]
    dest = os.path.join(RAW, day, os.path.basename(key))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    rec = {k: row.get(k, "") for k in ("s3_key", "cycle_utc", "lead_h", "valid_utc", "product", "s3_bytes")}
    rec["local_file"] = os.path.relpath(dest, PROJ)
    part = dest + ".part"
    for attempt in range(1, 13):
        try:
            # resume: keep what an interrupted attempt already wrote and ask S3 for the rest
            have = os.path.getsize(part) if os.path.exists(part) else 0
            if have > size:
                os.remove(part); have = 0
            if have < size:
                req = urllib.request.Request(BUCKET + key, headers={"Range": "bytes=%d-" % have} if have else {})
                with urllib.request.urlopen(req, timeout=120) as r, open(part, "ab" if have else "wb") as out:
                    if have and r.status != 206:
                        raise ValueError("server ignored Range request (HTTP %d)" % r.status)
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        out.write(chunk)
            got = os.path.getsize(part)
            if got != size:
                raise ValueError("size %d != S3 size %d" % (got, size))
            h = hashlib.sha256()  # checksum of the complete local file, not of the stream
            with open(part, "rb") as f:
                for chunk in iter(lambda: f.read(8 << 20), b""):
                    h.update(chunk)
            try:
                n = check_grib2(part)
            except Exception:
                os.remove(part)  # full-size but not valid GRIB2: discard, download again from zero
                raise
            os.replace(part, dest)  # atomic rename only after all checks pass
            rec.update(bytes=got, grib_messages=n, sha256=h.hexdigest(), status="verified",
                       downloaded_utc=dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))
            log("OK   %s  %.0f MB  %d msgs" % (key, got / 1e6, n))
            return rec
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):  # object does not exist: do not keep retrying
                rec.update(status="failed: HTTP %d" % e.code)
                log("FAIL %s HTTP %d" % (key, e.code))
                break
            err = "HTTP %d" % e.code
        except Exception as e:
            err = str(e)
        log("retry %d %s: %s" % (attempt, key, err))
        time.sleep(min(300, 10 * 2 ** (attempt - 1)))
    else:
        rec.update(status="failed: %s" % err)
        log("FAIL %s after 12 attempts: %s (partial file kept for resume)" % (key, err))
    return rec


def main():
    start = dt.datetime.strptime(sys.argv[1], "%Y-%m-%dT%H")
    end = dt.datetime.strptime(sys.argv[2], "%Y-%m-%dT%H")
    products = sys.argv[3].split(",")
    workers = int(sys.argv[4]) if len(sys.argv) > 4 else 4

    manifest = {}
    if os.path.exists(MANIFEST):
        with open(MANIFEST) as f:
            for r in csv.DictReader(f):
                manifest[r["s3_key"]] = r

    todo = []
    with open(os.path.join(INV, "expected_objects.csv")) as f:
        for r in csv.DictReader(f):
            v = dt.datetime.strptime(r["valid_utc"], "%Y-%m-%dT%H:%MZ")
            if not (start <= v <= end and r["product"] in products):
                continue
            old = manifest.get(r["s3_key"])
            if r["s3_status"] != "available":
                manifest[r["s3_key"]] = {k: r.get(k, "") for k in FIELDS} | {"status": r["s3_status"]}
            elif old and old["status"] == "verified" and os.path.exists(os.path.join(PROJ, old["local_file"])):
                continue
            else:
                todo.append(r)
    log("start: %d files to download (%.1f GB), %d workers" %
        (len(todo), sum(int(r["s3_bytes"]) for r in todo) / 1e9, workers))

    def save():
        with open(MANIFEST + ".tmp", "w", newline="") as f:
            w = csv.DictWriter(f, FIELDS)
            w.writeheader()
            for k in sorted(manifest, key=lambda k: (manifest[k]["valid_utc"], manifest[k]["product"])):
                w.writerow({x: manifest[k].get(x, "") for x in FIELDS})
        os.replace(MANIFEST + ".tmp", MANIFEST)

    with ThreadPoolExecutor(workers) as ex:
        for rec in ex.map(fetch, todo):
            with lock:
                manifest[rec["s3_key"]] = rec
                save()
    save()
    bad = [k for k, r in manifest.items() if r["status"] != "verified"]
    log("done: %d verified, %d not verified" % (len(manifest) - len(bad), len(bad)))
    for k in bad:
        log("  not verified: %s (%s)" % (k, manifest[k]["status"]))


if __name__ == "__main__":
    main()
