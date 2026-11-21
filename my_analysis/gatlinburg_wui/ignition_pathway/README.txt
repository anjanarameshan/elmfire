Ignition pathway of buildings: heat from burning forest vs heat from burning neighbouring buildings
================================================================================================

Runs: <location>/seed_1..10 for spot2, spot2_N1km, spot2_S1km, spot2_E1km, spot2_W1km (50 runs).
Same set-up and inputs as ms_st09 (inputs are symlinks to ms_st09/<location>/inputs), run with
  ELMFIRE_EXE=my_analysis/elmfire_variant/build/linux/bin/elmfire_1.1_pathway scripts/run_wui_case.sh ignition_pathway/<loc> <seed> 16

Pathway build (my_analysis/elmfire_variant only; original source and binary untouched), diagnostic only:
  CALC_WUI_HEATFLUX   also adds heat from burning building cells (FBFM 91) to TRANSIENT_FROMBLDG_WUI
  UMD_UCB_BLDG_SPREAD while a building cell is unignited, stores its heat split each step
  final dump          path_frac_bldg_*.tif  share of heat from burning buildings (rest: burning vegetation)
                      path_frac_dfc_*.tif   share of heat by direct flame contact (rest: radiation)
                      path_q_*.tif          total heat flux, kW/m2
  Check: time_of_arrival identical to ms_st09 for all 50 runs; spot2 seed 1 also ember_flux, ember_ignition, flin.

Analysis: scripts/analyse_ignition_pathway.py PERIMETER.shp  ->  pathway_summary.csv, ignition_pathway.png
Classes (buildings inside MTBS perimeter): mostly forest (<25 % of heat from buildings), mixed, mostly buildings (>75 %).

Result (mean of 10 runs per location; buildings ignited inside the perimeter)
location   ignited  mostly forest  mixed      mostly buildings  heat from bldg  flame contact
observed   1043     292 (28%)      144 (14%)  608 (58%)         65%             74%
N 1 km      981     272 (28%)      149 (15%)  559 (57%)         64%             73%
S 1 km     1270     309 (24%)      165 (13%)  796 (63%)         68%             75%
E 1 km      984     290 (29%)      141 (14%)  553 (56%)         62%             73%
W 1 km     1086     251 (23%)      127 (12%)  708 (65%)         70%             76%
all 50     1073     283 (26%)      145 (14%)  645 (60%)         66%             74%
Every ignited building cell has a heat record (0 without).
