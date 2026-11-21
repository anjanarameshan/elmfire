Heat received by building cells (2026-11-05)
Set-up: ember_calibration/x100 (ember generation x100, PHYSICAL ignition), spot fire 2, 16 h, seed 1, with
DUMP_TOTAL_DFC_RECEIVED and DUMP_TOTAL_RAD_RECEIVED on (input flags only; env HEAT_OUT=1 in scripts/run_wui_case.sh).
Run: heat_received/run.sh 1 (2 min). Fire identical to ember_calibration/x100 seed 1 (same TOA in every cell).
Analysis: SHP=<MTBS shp> scripts/heat_check.py heat_received/x100/spot2/seed_1 ember_calibration/x100/spot2/seed_1

Source (elmfire_spread_rate.f90, CALC_WUI_HEATFLUX): every burning cell (vegetation and buildings) within
BANDTHICKNESS_WUI = 5 cells adds direct flame contact (wind ellipse) and radiation 0.3*HRR*dx^2/(4 pi R^2) to each
target cell, summed over time (x DT x dx^2). No skip for targets that already burned, so totals keep growing after a
building ignites. Read here as kJ per cell, /900 m2 = kJ/m2 (units still to be confirmed in the guide, WU-E p. 81-83).

Building cells inside the MTBS perimeter (heat in kJ/m2 of the 30 m cell):
  group            n     zero heat   median    p10      p90
  all            3119   682 (22%)    1.0e5     0        5.0e5
  burned         1888     0           2.5e5    7.1e4    6.0e5
  not burned     1231   682 (55%)    0         0        1.6e4
  inner burned    438     0           4.2e5    1.9e5    6.5e5   (no vegetation in the 8 neighbours)
  edge burned    1450     0           2.1e5    5.8e4    5.3e5
  burned, N_b=0   398     0           1.4e5    3.1e4    7.0e5
  burned, N_b>=1 1490     0           2.8e5    9.0e4    5.9e5
Flame contact is 76% of the heat on burned building cells.

Reading: unlike flame length (0 on building cells) and ember load (~0 on inner cells), heat received is non-zero
on every burned building cell, and highest on inner cells, so it carries house-to-house exposure in physical units.
Caveat: the total includes heat received after the building's own ignition (neighbours keep burning for hours),
which inflates burned vs not-burned cells. Heat up to the building's own TOA would need finer transient dumps
(DUMP_TRANSIENT_DFC / DUMP_TRANSIENT_RAD at a short DTDUMP) and has not been tested.
