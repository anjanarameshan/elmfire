Robustness of building ignition to the building model and the building fuel class
==================================================================================

Runs (all finished, 79 + Hamada spot2 seed 1 test):
  hamada/<location>/seed_1..10   BLDG_TYPE=1 (Hamada) scripts/run_wui_case.sh, original ELMFIRE binary,
                                 inputs = symlinks to ms_st09/<location>/inputs
  bldg_ST10|11|12/spot2/seed_1..10  WU-E (type 2), inputs as ms_st09/spot2 except bldg_fuel_model.tif = 10|11|12,
                                 pathway build (elmfire_1.1_pathway; diagnostic only)
Queue: robustness/queue.sh. Summary: scripts/summarise_robustness.py PERIMETER.shp -> robustness_summary.csv

Building fuel classes (building_fuel_models.csv): same as ST09 except peak HRRPUA 25 (ST09), 50 (ST10), 100 (ST11),
500 (ST12) kW/m2, with fuel load 360/720/1440/7200, early-growth time 400/450/500/600 s and height 8/8/12/12 m.

Result (buildings ignited inside the MTBS perimeter, of 1609)
case                    locations  runs  buildings mean [min-max]  by embers  burned acres
WU-E, ST09 (baseline)   all 5      50    1073 [929-1289]           0          24757
Hamada (type 1), ST09   all 5      50    1509 [1391-1578]          0          39490
WU-E, ST09 (baseline)   observed   10    1043 [1010-1060]          0          26495
WU-E, ST10              observed   10    1118 [1087-1141]          0          27337
WU-E, ST11              observed   10    1164 [1147-1180]          0          27565
WU-E, ST12              observed   10    1210 [1196-1230]          0          28727
