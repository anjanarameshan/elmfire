Perimeter-constrained runs: identical to ms_st09/spot2 (observed spot fire 2, 28 Nov 11:00 -> 29 Nov 03:00 EST)
except adj.tif = 1 inside the MTBS burn perimeter and 0 outside, so no cell outside the observed burn
area can burn (surface spread or ember ignition; ELMFIRE requires ADJ > 0). inputs_spot2/ holds symlinks
to ms_st09/spot2/inputs plus the masked adj.tif.
receptiveXX/spot2 (XX = 100 80 60 40 20): variant build (my_analysis/elmfire_variant), forest cells
ember-receptive with probability XX % (one draw per cell). Seeds 1-3.
RESULTS (28 Oct 2026, seeds 1-3 means): f / burned ac / outside ac / perimeter covered / buildings ignited
inside / buildings ignited outside / max ember load on a building in the perimeter (g/cm2)
  100%  4,765   9   32%  1,040  30  0.00065
   80%  4,520   7   30%    968  24  0.00064
   60%  4,032   6   27%    835  18  0.00066
   40%  3,054   2   20%    558   8  0.00064
   20%    798   0    5%     73   0  0.00044
Note: a few building cells OUTSIDE the perimeter still ignite (by heat): the WU-E building spread does
not appear to be stopped by adj = 0. Map: perimeter_constrained_map.png (seed 1).

exposureXXXX/spot2 (XXXX = 0100 0300 0600 0900 1000): 100 % case (original program elmfire_1.1; at 100 %
the variant is identical), perimeter-constrained, TAU_EMBERGEN = XXXX s instead of 10 s (each burning
cell emits embers for this long). 600-1000 s = upper bound (full intensity held for 10-17 min). Seeds 1-3.
Run: TAU=300 scripts/run_wui_case.sh perimeter_constrained/exposure0300/spot2 <seed> 16
RESULTS exposure series (28 Oct 2026, seeds 1-3 means; peak memory < 4 GB):
  TAU   acres  bldgs ignited in perimeter  by embers  max ember load on a building (x threshold 0.0077)
  10 s  4,765   1,040   0     0.00065 (0.08x)
  100   4,836   1,056   0     0.0065  (0.8x)
  300   5,025   1,064   4.0   0.019   (2.5x)
  600   4,875   1,059   5.0   0.039   (5x)
  900   5,187   1,070   5.7   0.058   (7.6x)
  1000  5,228   1,055   5.7   0.065   (8.4x)
Seed 1: building cells whose final pile >= 0.0077 g/cm2: 7 (300 s), 36 (1000 s); ember-ignited 4 and 12
cells; the rest were ignited by heat first. Map: exposure_time_map.png (seed 1; magenta circles = ember-ignited).
