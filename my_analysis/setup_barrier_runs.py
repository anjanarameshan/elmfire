#!/usr/bin/env python3
"""Run A (chimney-tops-2016-nov27-cloudfire-all-adj1) variants: Eulerian embers and/or road+river barriers.

Usage: python setup_barrier_runs.py RUN_A_DIR BARRIER.tif OUT_PARENT [CASE ...]
Creates OUT_PARENT/<case>/ with inputs/ (links to Run A inputs + barrier.tif) and elmfire.data for:
  eulerian             Eulerian ember accumulation (as in the Gatlinburg runs), no barriers
  eulerian-barriers    Eulerian + USE_BARRIERS (OpenStreetMap roads and rivers)
  lagrangian-barriers  Run A's Lagrangian embers + USE_BARRIERS
Everything else (CloudFire fuel and weather, 6 ac start, 49 h, seed) is Run A's.
"""
import sys, os, re

runa, barrier, parent = sys.argv[1:4]
base = open(os.path.join(runa, "inputs", "elmfire.data")).read()

EULERIAN = """&SPOTTING
! Eulerian ember model, as in the Gatlinburg structure runs (guide 1.11): embers per MW of fire,
! Sardoy/Himoto distances, Eulerian accumulation, physical ignition (vegetation ignites once embers land)
ENABLE_SPOTTING                          = .TRUE.
ENABLE_SURFACE_FIRE_SPOTTING             = .TRUE.
USE_SUPERSEDED_SPOTTING                  = .FALSE.
GENERATION_MODEL                         = 'PER-MW'
SPOTTING_DISTANCE_MODEL                  = 'EMPIRICAL'
ACCUMULATION_MODEL                       = 'EULERIAN'
IGNITION_MODEL                           = 'PHYSICAL'
DIFF_WILDLAND_IGNITION                   = .TRUE.
CRITICAL_SPOTTING_FIRELINE_INTENSITY(:)  = 0.
GLOBAL_SURFACE_FIRE_SPOTTING_PERCENT     = 100.
GLOBAL_SURFACE_FIRE_SPOTTING_PERCENT_MAX = 100.
GLOBAL_SURFACE_FIRE_SPOTTING_PERCENT_MIN = 100.
TAU_EMBERGEN                             = 10.0
P_EPS                                    = 0.001
/
"""


def make(case, eulerian, barriers):
    d = os.path.join(parent, case)
    os.makedirs(os.path.join(d, "inputs"), exist_ok=True); os.makedirs(os.path.join(d, "outputs"), exist_ok=True)
    os.makedirs(os.path.join(d, "scratch"), exist_ok=True)
    for f in os.listdir(os.path.join(runa, "inputs")):
        if f.endswith((".tif", ".csv")):
            dst = os.path.join(d, "inputs", f)
            if not os.path.exists(dst):
                os.symlink(os.path.abspath(os.path.join(runa, "inputs", f)), dst)
    if barriers and not os.path.exists(os.path.join(d, "inputs", "barrier.tif")):
        os.symlink(os.path.abspath(barrier), os.path.join(d, "inputs", "barrier.tif"))
    s = base
    s = re.sub(r"CONVERT_TO_GEOTIFF\s*=\s*\.FALSE\.", "CONVERT_TO_GEOTIFF   = .TRUE.\nDUMP_EMBER_IGNITION  = .TRUE.\nDUMP_EMBER_FLUX      = .TRUE.", s)
    if barriers:
        s = s.replace("MLW_FILENAME                   = 'lw'",
                      "MLW_FILENAME                   = 'lw'\nUSE_BARRIERS                   = .TRUE.   ! OSM roads + rivers, width in m\nBARRIER_FILENAME               = 'barrier'")
    if eulerian:
        s = re.sub(r"&SPOTTING.*?\n/\n", EULERIAN, s, flags=re.S)
    open(os.path.join(d, "elmfire.data"), "w").write(s)
    print("set up", d)


for case in (sys.argv[4:] or ["eulerian", "eulerian-barriers", "lagrangian-barriers"]):
    make(case, case.startswith("eulerian"), case.endswith("barriers"))
