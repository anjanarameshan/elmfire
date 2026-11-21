Spread-reduction tests (input changes only; no source edits, no tuning to the perimeter).
Baseline = ms_st09/spot2 (observed spot fire 2, 28 Nov 11:00 -> 29 Nov 03:00 EST, 16 h, seeds 1-10).
Every test uses the same inputs (symlinked to ms_st09/spot2/inputs) and changes one setting.

step1_dtmax60   SIMULATION_DTMAX = 60 s (ELMFIRE default 600 s). Numerical check: is the burned
                area inflated by long late-run time steps? Seeds 1-3.
                Run: DTMAX=60 scripts/run_wui_case.sh spread_reduction/step1_dtmax60/spot2 <seed> 16
                RESULT (28 Oct 2026, seeds 1-3 vs baseline seeds 1-3): burned area 26,748 vs 26,496 ac
                (+0.9 %), buildings ignited in MTBS perimeter 1,038 vs 1,049 (-1.1 %), forest ignited
                by embers 95.7 vs 95.8 %. Within seed scatter -> over-spread is NOT numerical.

step2_embercons USE_EMBER_CONSUMPTION = .TRUE. (ember piles burn out; ELMFIRE default off). Seeds 1-3.
                Note from the code (elmfire_spotting.f90, EMBER_CONSUMPTION): burnout rate =
                N / MAX(T_LIFETIME, MIN_LIFETIME) with MIN_LIFETIME = 1E9 s, so the modelled lifetime
                is overridden and piles lose ~0.006 % over 16 h. Expected effect: negligible.
                Run: EMBER_CONS=1 scripts/run_wui_case.sh spread_reduction/step2_embercons/spot2 <seed> 16
                RESULT (28 Oct 2026, seeds 1-3): burned area, buildings and ember share IDENTICAL to
                baseline (26,496 ac, 1,049 buildings, 95.8 %). Burnout was active: total embers on the
                grid 0.0005 % lower (seed 1). Confirms the 1E9 s cap makes burnout ineffective.

step3_lag100    ACCUMULATION_MODEL = 'LAGRANGIAN' (whole embers), EMBER_SAMPLING_FACTOR = 100 (1 particle
                = 100 real embers; ms_st09 used 2000). Everything else as baseline (PHYSICAL, any-ember
                forest rule). Seeds 1-3.
                Why: ember_tests/C_lagrangian (factor 2000) launched only 9 particles in 16 h because the
                spot fire is weak (median 15 kW/m) -> ~150 embers per cell -> 0.075 particles.
                Run: ACCUM=LAGRANGIAN SAMPLING=100 scripts/run_wui_case.sh spread_reduction/step3_lag100/spot2 <seed> 16
step3_lag10     as step3_lag100 with EMBER_SAMPLING_FACTOR = 10.
                RESULTS (28 Oct 2026, seeds 1-3, observed spot; baseline Eulerian 26,496 ac, 1,049 bldgs):
                  factor 2000 (ember_tests/C_lagrangian, barriers on): 23.6 ac, 9 particles landed
                  factor 100 : 51 / 27 / 28 ac (mean 35),  buildings 0, forest by embers 6-15 %
                  factor 10  : 251 / 252 / 212 ac (mean 238), buildings 0-1, forest by embers ~52 %
                  peak memory with factor 10 ~8.6 GB of 15.8 GB -> factor 1 not attempted (memory).
                Fire size grows as particles get finer -> the Lagrangian result is NOT converged in the
                sampling factor. Map: spread_tests_map.png (seed 1).

step4_critflin200 / step4_critflin2000
                Eulerian (as baseline) with CRITICAL_SPOTTING_FIRELINE_INTENSITY = 200 / 2000 kW/m
                (baseline 0: every burning cell emits embers). Values are the guide's own examples
                (validation example, printed p. 101; spotting example, printed p. 26). Seeds 1-3.
                Run: CRITFLIN=200 scripts/run_wui_case.sh spread_reduction/step4_critflin200/spot2 <seed> 16
                CORRECTION (28 Oct 2026): the first step-4 runs wrote "(:) = 200" in the namelist; Fortran
                fills only element 0 (fuel 0) from a single value, so fuels 1-303 kept 0 and nothing
                changed (results byte-identical to baseline; even 1E9 gave 26,578 ac). Fixed by writing
                "(:) = 304*value". Check with 304*1E9 (step4_critflin1e9_check): 25.4 ac, i.e. no spotting.
                Step-4 runs re-done with the fix.
                RESULT (corrected, seeds 1-3): 200 kW/m -> 25.4 / 25.1 / 25.1 ac; 2000 kW/m -> same.
                No embers launched at all: no burning cell of the spot fire exceeded 200 kW/m (surface
                fire in litter fuels, median ~15 kW/m), so the fire stays at surface-spread size.
                Map: spread_tests_map_step4.png.

step5_receptiveXX  (XX = 100, 80, 60, 40, 20 %)
                Variant build in my_analysis/elmfire_variant (copy of the source; the original source
                and build/linux/bin/elmfire_1.1 are untouched). Change in EMBER_IGNITION only: each forest
                cell is ember-receptive with probability f, decided ONCE per cell per run (one draw per
                cell, not per time step); non-receptive forest cells cannot ignite from embers but can
                still burn by surface spread. Buildings unaffected. f = 100 % reproduces the original.
                Everything else as baseline (Eulerian, PHYSICAL, any-ember rule). Seeds 1-3.
                Run: ELMFIRE_EXE=<abs path>/my_analysis/elmfire_variant/build/linux/bin/elmfire_1.1_receptive \
                     ELMFIRE_EMBER_RECEPTIVE_FRAC=0.4 scripts/run_wui_case.sh spread_reduction/step5_receptive40/spot2 <seed> 16
                RESULT (28 Oct 2026, seeds 1-3, means; MTBS perimeter 15,003 ac on grid):
                  f      total    inside   outside  out%  cover%  bldgs (by embers)
                  100%  26,496    4,848   21,648    82    32     1,049 (0)   = baseline, byte-identical
                  80%   25,454    4,576   20,878    82    31       987 (0)
                  60%   22,412    4,114   18,299    82    27       870 (0)
                  40%   12,591    3,056    9,535    76    20       519 (0)
                  20%    1,678      830      848    51     6        77 (0)
                Smaller fire, but it still runs north out of the perimeter; summary: scripts/summarise_receptive.py
                Map: receptive_map.png (seed 1).

step5_receptive30  as step5, f = 30 % (requested 29 Oct 2026 to see the run between 20 % and 40 %; NOT a calibrated value).
                Run: ELMFIRE_EXE=.../elmfire_1.1_receptive ELMFIRE_EMBER_RECEPTIVE_FRAC=0.3 scripts/run_wui_case.sh spread_reduction/step5_receptive30/spot2 <seed> 16
                RESULT (29 Oct 2026, seeds 1-3, means): total 6,796 ac (seeds 8,077 / 3,336 / 8,974), inside MTBS 1,996,
                outside 4,800 (71 %), north of the building line 6,585 ac (observed 6,428), Sorensen north 0.27,
                buildings ignited in MTBS 282. Map: receptive30_map.png (scripts/plot_receptive30.py, 20/30/40 %).
                CAVEATS seen on the map: (1) in all 3 seeds the fire reaches row 2 of the grid = northern domain edge
                (3,965.6 km), so outside area is cut off; (2) straight burned-area edges at y 3,960.82 / 3,955.42 km and
                x 275.97 km = exactly 600 m weather-grid cell boundaries, while ws/wd/m1/m10 change little across them
                (<= 1.6 mph, <= 5 deg, <= 0.4 %) -> a gridding artefact, cause not yet identified (also visible at 40 %).
