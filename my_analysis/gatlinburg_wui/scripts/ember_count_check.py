"""Ember landings on building cells with non-burnable buildings (ember_count/nobldg), per labelled building.
Usage: python ember_count_check.py RUN_DIR [RUN_DIR ...]
  Each RUN_DIR holds seed_*/outputs/ember_flux.tif. With several RUN_DIRs (e.g. the five ignition locations) all
  their runs are pooled. env FEATURES (default vulnerability/features.csv) gives the building points (x, y in the
  raster CRS) and the aerial-photo label y_A (1 destroyed, 0 not destroyed).
Writes RUN_DIR/ember_count_by_building.csv (one RUN_DIR) or <common parent>/ember_count_by_building_all.csv,
and prints a summary by label.
"""
import sys, os, glob
import numpy as np
import pandas as pd
from osgeo import gdal
gdal.UseExceptions()

runs = [r.rstrip('/') for r in sys.argv[1:]]
feat = os.environ.get('FEATURES', os.path.join(os.path.dirname(__file__), '..', 'vulnerability', 'features.csv'))
out_csv = runs[0] + '/ember_count_by_building.csv' if len(runs) == 1 else os.path.commonpath(runs) + '/ember_count_by_building_all.csv'
seeds = [p for r in runs for p in sorted(glob.glob(r + '/seed_*/outputs/ember_flux.tif'), key=lambda p: int(p.split('seed_')[1].split('/')[0]))]
ref = gdal.Open(seeds[0]); gt = ref.GetGeoTransform()
E = np.stack([gdal.Open(p).ReadAsArray().astype(float) for p in seeds])          # embers landed per cell, per run
T = np.stack([gdal.Open(glob.glob(os.path.dirname(p) + '/time_of_arrival_*.tif')[0]).ReadAsArray() for p in seeds])
burned_nb = np.zeros_like(T, dtype=bool)                                           # any of the 8 neighbours burned
for dy in (-1, 0, 1):
    for dx in (-1, 0, 1):
        if dy or dx:
            burned_nb |= np.roll(np.roll(T > 0, dy, axis=1), dx, axis=2)

f = pd.read_csv(feat)
col = ((f.x - gt[0]) / gt[1]).astype(int); row = ((f.y - gt[3]) / gt[5]).astype(int)
ok = (col >= 0) & (col < E.shape[2]) & (row >= 0) & (row < E.shape[1])
f = f[ok].copy(); col, row = col[ok], row[ok]
e = E[:, row, col].T                                   # buildings x runs
a = burned_nb[:, row, col].T
f['n_runs'] = len(seeds)
f['p_ember'] = (e > 0).mean(1)                          # share of runs with at least one landing
f['p_arrival'] = a.mean(1)                              # share of runs where a neighbour cell burned
f['mean_all'] = e.mean(1)                               # mean landings over all runs
f['mean_nonzero'] = e.sum(1) / np.maximum((e > 0).sum(1), 1)   # mean over runs with landings (Theodori: zeros excluded)
f['max'] = e.max(1)
f['ember_load_g_m2'] = f.mean_all * 0.2 / 900          # 0.2 g per ember (elmfire_spotting.f90), per m2 of the 30 m cell
out = f[['id', 'x', 'y', 'y_A', 'n_runs', 'p_arrival', 'p_ember', 'mean_all', 'mean_nonzero', 'max', 'ember_load_g_m2']]
out = out.round({'x': 1, 'y': 1, 'p_arrival': 2, 'p_ember': 2, 'mean_all': 3, 'mean_nonzero': 3, 'ember_load_g_m2': 6})
out.to_csv(out_csv, index=False)

print(f'{", ".join(os.path.basename(r) for r in runs)}: {len(seeds)} runs, {len(f)} buildings')
for name, sel in [('all', f.y_A >= 0), ('destroyed (y_A=1)', f.y_A == 1), ('not destroyed (y_A=0)', f.y_A == 0)]:
    g = f[sel]
    print(f'  {name:22s} n={len(g):5d}  no embers in any run={(g.p_ember == 0).mean():5.0%}  '
          f'P(ember)={g.p_ember.mean():.2f}  P(arrival)={g.p_arrival.mean():.2f}  '
          f'mean landings: median {g.mean_all.median():.3g}, p90 {g.mean_all.quantile(.9):.3g}  '
          f'| nonzero mean: median {g.mean_nonzero[g.mean_nonzero > 0].median() if (g.mean_nonzero > 0).any() else 0:.3g}')
