SIMPLE (probabilistic) ember ignition vs PHYSICAL (De Beer threshold), observed spot point (spot2), 3 seeds, 16 h
==========================================================================================================
Runs: simple_ignition/run.sh  ->  IGN_MODEL=SIMPLE PIGN=90 scripts/run_wui_case.sh simple_ignition/spot2 <seed> 16
Inputs: symlink to ms_st09/spot2/inputs (all buildings ST09: P_IGNITION 70 %, hardening 7, tau_ign 60 s).
Only change from ms_st09: IGNITION_MODEL = 'SIMPLE' (vegetation PIGN = 90 % = the 0.9 used under PHYSICAL with
DIFF_WILDLAND_IGNITION, so vegetation ignition is unchanged; buildings: any ember load -> P_IGNITION 70 % over 60 s,
no load threshold). Reference: physical_ref/spot2/seed_1..3 = symlinks to ms_st09/spot2/seed_1..3.

compare_summary.txt   scripts/compare_ignition_models.py (acres, buildings in / out of MTBS, ember-ignited buildings)
building_exposure_*   scripts/building_exposure_map.py, for SIMPLE (here) and PHYSICAL (physical_ref/)

Result (means of 3 seeds)          PHYSICAL      SIMPLE
burned area (ac)                     26,496      33,577
buildings ignited inside MTBS         1,049       1,415
buildings ignited outside MTBS        5,881       7,953
ember-ignited buildings inside            0       1,284 (91 %)
observed burned lost (P >= 2/3)        67 %        88 %
observed survived lost (false alarm)   64 %        86 %
AUC P(lost)                            0.52        0.52
AUC ember load                         0.62        0.62
