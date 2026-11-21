Ember-ignition hardening factor (HARDENING_FACTOR, building_fuel_models.csv column 15) test
==========================================================================================
Runs: hardening/run.sh H [SEEDS]  ->  scripts/run_wui_case.sh hardening/H<H>/spot2 <seed> 16
Inputs: hardening/H<H>/spot2/inputs = symlinks to ms_st09/spot2/inputs, except a copy of building_fuel_models.csv
with ST09's hardening factor changed (default 7.0; ELMFIRE's own table in build/source is untouched).
Set-up otherwise identical to ms_st09/spot2: Eulerian, PHYSICAL ignition, any-ember vegetation, default ember
generation (33.3 / 10 per MW), observed spot point, 16 h.
Criterion (guide eq. 2.19, elmfire_spotting.f90): ignition if H*psi >= 0.211 / ((v+0.073)(4.111-v)), v = near-surface
air speed from the 20-ft wind with fixed F = 1, H_bldg = 8 m (about 0.08 m/s per mph of 20-ft wind).

Result, H = 10 (3 seeds): identical to H = 7 (ms_st09 seeds 1-3): 0 ember-ignited buildings, same burned area and
building counts. Largest ember load on any building cell 0.00075 g/cm2, so H*psi <= 0.0076 g/cm2, about 10x below
psi_crit (~0.076 g/cm2 at the median 27 mph, ~0.061 at the maximum 38 mph). The smallest H that can ignite even one
building is therefore about 80-100.
compare_summary.txt   scripts/compare_ignition_models.py
