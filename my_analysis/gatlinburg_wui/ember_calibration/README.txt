Ember generation calibration so that buildings can ignite from accumulated embers (new Eulerian model + PHYSICAL)
=============================================================================================================
Runs: [FACTORS="10 30 100"] ember_calibration/run.sh [SEEDS]  ->  EMBER_VEGE=33.3*f EMBER_BLDG=10*f
      scripts/run_wui_case.sh ember_calibration/x<f>/spot2 <seed> 16   (inputs: symlink to ms_st09/spot2/inputs)
Set-up identical to ms_st09/spot2 (Eulerian accumulation, IGNITION_MODEL PHYSICAL, DIFF_WILDLAND_IGNITION .TRUE.,
P_EPS 0.001, all buildings ST09: hardening 7, tau_ign 60 s); only EMBER_GR_PER_MW_VEGE / _BLDG scaled (defaults
33.3 / 10 g per MW). Vegetation ignites on any ember, so more ember mass leaves vegetation spread ~unchanged and
raises the ember load on building cells, which ignite only above the De Beer / UMD load criterion.
Seed 1 only for x10..x1000; x1 = ms_st09/spot2 seeds 1-3 (via simple_ignition/physical_ref).

compare_summary.txt   scripts/compare_ignition_models.py (ember-ignited buildings inside / outside MTBS)
x<f>/building_exposure_*  scripts/building_exposure_map.py (x100, x1000)

factor  acres   bldg in MTBS  ember-ignited in / out   labelled ember-ignited: obs burned / survived
x1      26,496     1,049          0 /   0               -
x10     26,506     1,037          0 /   0               -
x30     26,749     1,056          3 /  13               -
x100    26,649     1,032         13 /  93               6 / 5
x300    27,159     1,050         17 / 240               -
x1000   27,279     1,080         67 / 656               21 / 25   (base rate of burned among labelled: 29 %)
AUC P(lost): x1 0.52, x100 0.51, x1000 0.53 (single seed for x100 / x1000)

Plausibility of the factors (checked 2026-11-04; corrected the same day)
Guide p. 60: G = 33.3 pcs/MW/s (vegetation), 10 (structures); the ignition criterion uses 0.2 g per firebrand.
Measured / inferred: 3.2-4.2 pcs/MW/s (Wickramasinghe et al. 2022, Fire 5(1) 6, inverse analysis); firebrand mass
yield 0.004-0.027 of fuel burned (Leventon, Ju, Gollner, NIST full-scale vegetation tests; from the abstract only).
A first check assumed a cell emits for its whole burning time and wrongly concluded x10+ breaks mass conservation.
In our runs a cell emits only for TAU_EMBERGEN = 10 s (USE_PHYSICAL_SPOTTING_DURATION = .FALSE.;
elmfire_spotting.f90:1096-1099), while its fuel burns for ~cell size / spread rate. Per vegetation cell:
  firebrand mass = (I_f * dx / 1000) * G * tau * m      fuel mass = I_f * dx^2 / (h * R)   (Byram I_f = h w R)
  yield = G * tau * m * h * R / dx * 1e-3 = 0.041 * R(m/s)   (G 33.3, tau 10 s, m 0.0002 kg, h 18,600 kJ/kg, dx 30 m)
Spread rate of burned vegetation cells (domain_north30/ground_fire_check.txt): median 0.66 ft/min = 0.0034 m/s
(leaf-on), 2.06 ft/min = 0.0105 m/s (leaf-off) -> default yield ~0.00014 (leaf-on) to ~0.0004 (leaf-off), i.e.
10-200x BELOW the measured 0.004-0.027. Factors ~x30 to ~x200 (leaf-on) bring the effective yield into the measured
range; x1000 is above it. (Equivalent view: physical emission time 30 m / 0.0034 m/s ~ 2.4 h vs 10 s.)
So x30-x100 ember generation is consistent with measured firebrand yields, given the 10 s emission time; it is the
better-founded knob than HARDENING_FACTOR, which has no documented basis (see hardening/README.txt).
ms_st09_physdur (physical duration) was stopped after 93 min without outputs, so it cannot be used as a check.

Emission time instead of generation rate (2026-11-04): ember_calibration/tau1000/spot2, seed 1, TAU=1000
(TAU_EMBERGEN 1000 s instead of 10 s; default G; same total embers per cell as x100). Runtime 4.6 min.
           acres   bldg in MTBS   ember-ignited in / out
default   26,496      1,049          0 /  0   (seeds 1-3)
G x100    26,649      1,032         13 / 93   (seed 1)
tau 1000  32,426      1,093          6 / 38   (seed 1)
Unlike G x100, the longer emission also enlarges the forest fire (+22 %): embers keep landing for ~17 min per cell,
on more cells (later wind, more fronts emitting at once), and any-ember vegetation ignition turns each new cell into a
spot fire. Fewer ember-ignited houses than G x100: the same mass is spread over more time and space, so fewer house
cells pass the load threshold. compare_tau.txt
