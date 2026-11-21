# HRRR inventory and WRF forcing strategy — Chimney Tops II (Nov 2016)

Status: **pilot download in progress** (written before bulk transfer, as required by the handoff).
Last updated: 2026-10-13.

## 1. Source and access

- Archive: NOAA HRRR, `s3://noaa-hrrr-bdp-pds/`, read anonymously over HTTPS
  (`https://noaa-hrrr-bdp-pds.s3.amazonaws.com/`). No AWS account or credentials used.
- Listing method: S3 `list-type=2` REST listing with pagination (`scripts/hrrr_s3_inventory.py`).
- Full listing of all GRIB2 objects for `hrrr.20161122` … `hrrr.20161130`:
  `data/hrrr_inventory/s3_listing.csv` (13,224 objects; key, bytes, last-modified, cycle, product, lead, valid time).

## 2. What exists for 2016

Products per hourly cycle: `wrfprs` (pressure levels), `wrfsfc` (surface), `wrfnat` (native/hybrid levels),
`wrfsubh` (15-min surface), plus a few `class1` files. Forecast leads f00–f18 (2016 HRRR v2).

Coverage of zero-lead (f00) files for the recommended window **2016-11-22 00 UTC → 2016-11-30 12 UTC (205 valid hours)**
(`data/hrrr_inventory/expected_objects.csv`, `logs/s3_inventory_f00.log`):

| Product | f00 hours available | Missing | Size (f00 only) |
|---|---|---|---|
| `wrfprs` | **205 / 205** | none | 77.5 GB |
| `wrfsfc` | 122 / 205 | 83 | 14.0 GB |
| `wrfnat` | 122 / 205 | 83 | 77.3 GB |

- `wrfprs`: all 216 cycles from 22 Nov 00Z to 30 Nov 23Z have the complete f00–f18 set.
- `wrfsfc` and `wrfnat`: a continuous gap **24 Nov 10 UTC → 27 Nov 12 UTC** (both products), plus scattered
  missing hours inside the critical window, e.g. `wrfsfc` 28 Nov 06, 19, 20 UTC and `wrfnat` 28 Nov 07, 09 UTC
  and 29 Nov 03 UTC. Full list in `logs/s3_inventory_f00.log`.

## 3. Field content (test file 2016-11-28 18 UTC, all three products, verified)

Inventory: `data/hrrr_inventory/test_prs_inventory.csv` (ecCodes, header-only).

- `wrfprs` (684 messages, 400 MB): on **40 isobaric levels (1013, 1000 … 50 hPa)**: HGT, TMP, RH, SPFH, DPT,
  UGRD, VGRD, VVEL, cloud/rain/snow/ice/graupel mixing ratios. Surface / near-surface: PRES (sfc), HGT (sfc
  terrain), skin TMP, 2 m TMP/RH/SPFH/DPT, 10 m UGRD/VGRD, 80 m winds, gust, MSLMA, snow (WEASD, SNOD),
  CNWAT, LAND, ICEC, PBL height, and **RUC soil temperature and moisture on 9 levels
  (0, 1, 4, 10, 30, 60, 100, 160, 300 cm; GRIB2 level type 106)**.
- `wrfsfc` (132 messages, 123 MB): a subset of the `wrfprs` surface fields plus 6 isobaric levels. Every
  surface field in `wrfsfc` is also in `wrfprs`.
- `wrfnat` (1,107 messages, 659 MB): 50 hybrid levels; this is what WPS's bundled `Vtable.raphrrr` expects
  (level type 105).

## 4. Chosen strategy

**Forcing product: `wrfprs` only.** It is the only product with no gaps across the whole window, and it contains
all fields WPS/WRF need (3-D atmosphere on pressure levels, surface fields, 9-level soil). Using `wrfnat` would
require filling 83 missing hours from another product or lead, which the handoff says not to do silently.

**Vtable:** `wps/Vtable.HRRR.prs`, built from WPS v4.7.0's `Vtable.RAP.pressure.ncep` (3-D, 2 m, 10 m, PSFC,
PMSL, terrain, snow, skin T) and `Vtable.raphrrr` (snow depth, canopy water, 9-level soil, sea ice, land mask).
Two documented changes, each checked against the GRIB2 codes in the test file: 2 m RH enabled (it is present in
the 2016 `wrfprs`), and canopy water mapped to parameter 2/0/13 (as encoded in 2016) instead of 2/0/196.
**Not yet proven:** must pass `ungrib.exe` on the pilot.

**Time strategy (pilot): hourly zero-lead (f00) analyses**, i.e. successive HRRR analyses, used both for the WRF
initial state and for hourly lateral boundaries. These are independent analyses, not one continuous forecast.
They include HRRR data assimilation each hour, which keeps the boundaries close to observations but can carry
small hour-to-hour jumps.
Alternative (documented, not used for the pilot): one cycle's forecast f00–f18 as a temporally coherent boundary
sequence, re-initialised every ≤ 18 h (cycling/restart). All `wrfprs` cycles have f00–f18, so this is feasible
if the analysis-sequence boundaries prove noisy.

**Pilot window:** 2016-11-27 12 UTC → 2016-11-29 12 UTC (49 hourly files, 18.7 GB), spanning the critical
27–28 Nov growth and the 29 Nov rain onset. The full window would be 205 files / 77.5 GB.

## 5. Download method and checks

`scripts/hrrr_download.py`: anonymous HTTPS; each object written to `*.part`; accepted only if the byte count
equals the S3 listing size, the file starts with `GRIB` and ends with `7777`, and every message decodes as GRIB
edition 2 (ecCodes); then SHA-256 recorded and atomically renamed to its original HRRR file name under
`data/hrrr_raw/hrrr.YYYYMMDD/`. Retries with back-off; 403/404 recorded as failed, not retried. Resumable.
Manifest: `data/hrrr_inventory/hrrr_manifest.csv` (key, cycle, lead, valid time, local file, bytes, messages,
SHA-256, status). Log: `logs/download.log`. S3 ETags are not used as checksums.

Observed throughput: about 0.8 MB/s total on this connection (8 parallel connections), so roughly 6 h for the pilot
and about 26 h for the full window. Possible reduction (not adopted): download only the 233 of 684 messages per
file that the Vtable uses (43 % of bytes) via the `.idx` byte ranges. That would cut the full window to about
33 GB, but stored files would no longer be the unchanged originals.

## 6. Environment

- WSL2 Ubuntu (kernel 6.18), 32 cores, 15 GB RAM, ~910 GB free.
- WRF v4.8.0 (`~/wrf/WRF`, gfortran + MPI, dmpar, em_real); WPS v4.7.0 (`~/wrf/WPS`, gfortran serial,
  `--build-grib2-libs`; `configure.wps` link line edited to add `-lnetcdff`); WPS_GEOG high-res mandatory set.
- Python: `~/venvs/elmfire` with ecCodes; no `aws`, `wgrib2` or `boto3` (not needed).

## 7. Open items

- ~~Verify the ignition coordinate~~ done, see section 8.
- d02/d03 terrain: replace GMTED2010 30" with USGS 3DEP 1 arc-second (~30 m) via a custom GEOGRID.TBL entry.
- Disk: the WSL virtual disk lives on C: (68 GB free); move it to D: (442 GB free) before the full window.
- Run `ungrib.exe` on the pilot with `Vtable.HRRR.prs`; check that all soil levels and fields are written.
- Generate `data/hrrr_inventory/grib_inventory.csv` for all pilot files when the download completes.

## 8. Ignition point (checked 2026-10-13)

| Source | Location | Time |
|---|---|---|
| NPS fire page (nps.gov/grsm/learn/chimney-tops-2-fire.htm) | "remote location of the park (Chimney Tops) in steep terrain" | reported ~5:30 p.m. EST, 23 Nov 2016 |
| MTBS record TN3563108347820161123 (`BURNBNDLAT/LON` in the burn-area shapefile) | 35.631 N, −83.478 W | ignition date 2016-11-23 |
| Chimney Tops summit (GNIS coordinates via Wikipedia) | 35.6307 N, −83.4782 W, 1,440 m | — |
| Handoff provisional value | 35.629 N, −83.478 W | — |

The MTBS point is within ~40 m of the Chimney Tops summit; the handoff value is ~200 m south of it.
**Adopted: 35.631 N, −83.478 W (MTBS)**, accuracy ~±200 m (summit-level description, no surveyed point of
origin published). This is far below the WRF nest resolution, so it does not affect domain placement.
NPS also gives ~11,000 ac burned inside the park and ~6,000 ac outside (≈17,000 ac), versus 15,003 ac in MTBS.

## 9. WPS domains (geogrid test, 2026-10-13)

`wps/namelist.wps`, geogrid from WPS v4.7.0 completed without errors; map: `reports/wps_domains.png`.
Lambert conformal, true latitudes 30/60 N, centred on the MTBS perimeter (35.687 N, −83.503 W).

| Domain | dx | Grid | Extent | Purpose |
|---|---|---|---|---|
| d01 | 1000 m | 150 × 150 | 149 × 149 km | forced directly by HRRR 3 km (ratio 3); similar to the 1 km / 117 km domain in Jiménez et al. 2018 |
| d02 | 333 m | 180 × 180 | 60 × 60 km | covers the whole 40 km ELMFIRE domain |
| d03 | 111 m | 198 × 198 | 22 × 22 km | covers the MTBS perimeter (7 × 15 km) with ≥ 3.5 km margin; similar to the 111 m nest in Jiménez et al. |

Findings:
- With the default static data, terrain comes from GMTED2010 30" (~900 m). On d03 it is strongly smoothed:
  max 1,879 m vs 2,005 m in the 30 m DEM, and the ridge/valley pattern that drives downslope flow is lost.
  A ≥ 1 arc-second terrain source is needed for d02/d03 (to do).
- d02 (333 m) and d03 (111 m) are in the PBL "grey zone"; the PBL / LES choice must be decided before WRF runs.

## 10. Disk-space estimate

| Item | Pilot (49 h) | Full window (205 h) |
|---|---|---|
| HRRR `wrfprs` raw (kept) | 18.7 GB | 77.5 GB (33 GB if field-subset) |
| ungrib intermediate files (CONUS, ~1.8 GB/h, deletable after metgrid) | ~88 GB if all kept | ~370 GB if all kept |
| met_em files (3 domains) | ~6 GB | ~27 GB |
| WRF output, hourly, 3 domains (estimate) | ~50 GB | ~200 GB |

Available: the Linux file system reports 914 GB, but it is a virtual disk (`ext4.vhdx`, 42 GB now) stored on
**C: with only 68 GB free**. D: has 442 GB free. Even the pilot (~75 GB if ungrib files are deleted per chunk)
does not fit safely on C:. Recommendation: move the WSL disk to D: before the WPS pilot.

## 11. High-resolution terrain for d02 / d03 (2026-10-13)

Jiménez et al. 2018 do not state their terrain dataset; they give only the grid spacing (111 m atmosphere,
27.75 m fire grid). We use USGS 3DEP 1 arc-second (~30 m):

- Source: `https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1/TIFF/current/n36w084/USGS_1_n36w084.tif`
  (58,007,875 bytes, NAD83 lat/lon, 3612 × 3612, 196.9–2024.8 m; SHA-256 in `data/terrain_raw/*.sha256`).
  One tile covers all of d02 and d03 (35–36 N, 84–83 W). Raw file kept unchanged.
- Conversion: `scripts/dem_to_geogrid.py` → `data/terrain_geogrid/topo_usgs_1s/` (geogrid binary, 16-bit,
  decimetres, no resampling).
- `wps/GEOGRID.TBL` = WPS v4.7.0 `GEOGRID.TBL.ARW` plus two lines in the `HGT_M` entry (interp option and
  absolute path for `usgs_1s`). `namelist.wps`: `geog_data_res = 'default','usgs_1s+default','usgs_1s+default'`.
  d01 (1 km) keeps GMTED2010 30". The earlier default-terrain output is kept in `wps/geogrid_default/`.
- Vertical datum: 3DEP is NAVD88, GMTED2010 is EGM96; the difference here is under 1 m and is ignored.

Check against the independent 30 m LANDFIRE elevation used by ELMFIRE (block-averaged to 120 m):

| Domain | Terrain source | Max height | Bias | RMSE | Slope 99th pct | Max slope |
|---|---|---|---|---|---|---|
| d02 (333 m) | GMTED 30" | 1,889 m | +14.1 m | 53.0 m | 16.3° | 22.2° |
| d02 (333 m) | USGS 1" | 1,961 m | +0.4 m | 27.1 m | 22.2° | 31.6° |
| d03 (111 m) | GMTED 30" | 1,879 m | +14.5 m | 51.0 m | 19.1° | 24.2° |
| d03 (111 m) | USGS 1" | 1,987 m | +0.3 m | 13.4 m | 34.7° | 45.6° |

(d02 is compared only over the 42 % of its area covered by the ELMFIRE DEM.) Map: `reports/wps_domains_usgs1s.png`.

**Risk to handle before the WRF run:** d03 now has slopes up to 45.6° (1 % of cells above 34.7°). WRF's
terrain-following coordinate can become unstable on slopes of this size. Options to test, in order: a short
time step and stronger off-centring (`epssm`), then extra terrain smoothing passes on d03 only. Any smoothing
must be reported with its effect on the numbers above.

## 12. Pipeline test: ungrib → metgrid → real → WRF, 2016-11-28 18–19 UTC (2026-10-13)

Inputs: full `wrfprs` f00 for 18 UTC; for 19 UTC a **test-only field subset** (`data/hrrr_test/…SUBSET.grib2`,
only the 233 messages the Vtable uses, fetched by byte range with `scripts/hrrr_subset_test.py`). Production
runs use full files from `data/hrrr_raw/`.

- **ungrib** (`wps/Vtable.HRRR.prs`): no errors; every Vtable field found: TT/UU/VV/RH/HGT on 40 pressure
  levels, 2 m T/RH/q, 10 m wind, PSFC, PMSL, terrain, snow, skin T, canopy water, 9 soil-moisture and 9
  soil-temperature levels, sea ice, land mask. Intermediate file 1.7 GB per hour. → **Vtable demonstrated.**
- **metgrid**: no errors; 41 levels, 9 soil levels; value ranges physically plausible on all domains.
- **real.exe**: `SUCCESS COMPLETE REAL_EM INIT`; wrfinput_d01–d03, wrfbdy_d01 written.
- **WRF Test A** (`wrf/test_stability/namelist.input.A`): 51 levels, top 50 hPa, time step 6 s / 2 s / 0.67 s,
  `epssm = 0.1` (default), no extra terrain smoothing, one-way nests (`feedback = 0`).
  Physics: WSM6, RRTM LW, Dudhia SW, revised MM5 surface layer, Noah LSM (as in Jiménez et al. 2018);
  PBL: YSU on d01 and d02, LES (1.5-order TKE, `km_opt = 2`) on d03.
  **Deviation from the paper:** they used MYNN on the 1 km domain; WRF v4.8.0 refuses MYNN on domain 1
  together with an LES nest (`check_a_mundo`), so YSU is used. d02 (333 m) with YSU is a grey-zone choice.
  Result: `SUCCESS COMPLETE WRF`, no CFL messages, no NaN. The 46° slopes did not destabilise the run,
  so no shorter time step, extra damping or terrain smoothing was applied. Caveat: one hour only, which
  includes model spin-up; the long run must still be watched.

  | Domain | 10 m wind at 19 UTC: mean | 99th pct | max | max \|w\| |
  |---|---|---|---|---|
  | d01 (1 km) | 7.1 m/s | 18.3 | 23.0 | 10.2 m/s |
  | d02 (333 m) | 7.5 m/s | 22.2 | 29.9 | 15.7 m/s |
  | d03 (111 m) | 10.8 m/s | 25.8 | 37.6 | 17.2 m/s |

  (HRRR 10 m wind interpolated to d03 at 18 UTC: mean 8.1, max 13.8 m/s.) Not yet validated against stations.
- **Cost:** 87 min wall-clock for 60 min simulated on 16 MPI tasks (i9-14900K) → 1.45× slower than real time;
  output ~0.6 GB per simulated hour with 10-min history on d02/d03. A 49 h pilot would take ~3 days.

## 13. Incidents (2026-10-13)

- The editor's background `git add -A` copied the large untracked GRIB/WRF files into `.git/objects`
  (153 GB of temporary packs and unreferenced blobs). Fixed: ignore rules added in `my_analysis/.gitignore`,
  `git prune --expire=now` → `.git` back to 326 MB; history and working tree unchanged.
- Download: parallel test fetch starved the pilot connections (timeouts); later DNS failures made the
  downloader mark 20 files failed. Fixed: downloader now resumes partial files with HTTP Range, longer
  back-off, and `scripts/run_download_until_done.sh` re-runs it until all files verify.
  Throughput measured at 08:50 UTC: ~80 kB/s on one connection.

## 14. Pilot WRF run (started 2026-10-14 04:51 UTC)

- Period: **2016-11-27 12 UTC → 2016-11-29 12 UTC (48 h)**, covering the ELMFIRE window (28 Nov 05 UTC →
  29 Nov 08 UTC) with 17 h of spin-up before it. All 49 hourly HRRR `wrfprs` f00 files verified (19.1 GB).
- WPS: `wps/pilot_B/` (ungrib + metgrid in three blocks, all logs error-free; 49 met_em files per domain).
  Intermediate files (83 GB) deleted after metgrid.
- real.exe: SUCCESS, 48 boundary times. WRF: `wrf/pilot/namelist.input`, same physics/dynamics as Test A;
  history 60 / 30 / 10 min (d01/d02/d03); restart files every 3 h; 8 MPI tasks (fastest in the timing test).
- Speed: 7.8 s wall per 6 s model step (1.3× slower than real time) → ~2.6 days.
- If interrupted: `scripts/resume_wrf.sh wrf/pilot 8` restarts from the newest complete restart set.

## 15. Moisture bug found and fixed; pilot restarted (2026-10-14)

- **Bug:** `Vtable.HRRR.prs` v1 included 2 m SPECHUMD. metgrid then wrote a 2-D SPECHUMD with
  `FLAG_SH = 1`, and real.exe took specific humidity as the moisture source; with no SPECHUMD on pressure
  levels, **QVAPOR was 0 everywhere** in wrfinput (test and first pilot launch). Found while testing the station
  comparison (WRF 2 m RH ≈ 0–3 %). The section 12 test (Test A) therefore ran with a dry atmosphere; its
  stability result stands, its wind/temperature values are not representative.
- **Fix:** Vtable v2 without the 2 m SPECHUMD line (v1 kept as `Vtable.HRRR.prs.v1_with_2m_SPECHUMD`).
  Re-test (28 Nov 18 UTC): no FLAG_SH; wrfinput lowest-level RH 66 % (HRRR 65 %), ~1.5 km above d03
  14–45 % (dry air aloft).
- The first pilot launch (dry) was stopped after 11 simulated minutes; its files are in `wrf/pilot/stopped_dry_qv/`.
  WPS, real.exe and WRF are rerun by `scripts/run_pilot_chain.sh` (log `logs/pilot_chain.out`).

## 16. Post-processing scripts (tested on the 1-hour test output)

- `scripts/wrfout_tools.py`: reads wrfout via GDAL + `ncdump`; earth-relative 10 m wind from U10/V10 rotated
  with COSALPHA/SINALPHA; Lambert projection from the file attributes (round-trip error < 0.01 cell).
- `scripts/wrf_station_compare.py`: WRF (domains containing the station ≥ 10 cells inside), HRRR (nearest
  point, winds rotated from the HRRR Lambert grid) and station observations, hourly pairs (obs = mean of
  reports in H ± 30 min). IGGT1 (RAWS, 6.1 m): model speed × 0.87; KGKT (ASOS, 10 m): unchanged.
  **Neither station lies inside d03**: IGGT1 is ~30 km west of the fire near d02's west edge (d01 only after the
  10-cell margin rule), KGKT is in d01/d02. Stations check d01/d02; d03 is checked only indirectly.
- `scripts/wrf_to_elmfire.py`: hourly ELMFIRE `ws` (mph, 20 ft = 10 m × 0.87, ELMFIRE's WS_AT_10M factor) and
  `wd` (deg from) on a 100 m grid over the ELMFIRE domain (400 × 400), from d03 inside its area and d02
  outside (d03 weight 0 within 5 cells of its edge, linear ramp over 10 cells); each band = trapezoid mean of the
  u, v history frames in H ± 30 min; fuel-moisture rasters regridded to the same grid (ELMFIRE needs one
  weather grid). Settings recorded in `wrf_to_elmfire.json`. Test map: `reports/test_wrf_to_elmfire_wind.png`
  (no seam at the d03/d02 transition).
