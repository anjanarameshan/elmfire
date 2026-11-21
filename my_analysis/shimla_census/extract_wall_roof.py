"""Shimla Municipal Corporation: wall and roof material by ward, Census of India 2011.

Inputs (raw/, downloaded from censusindia.gov.in NADA):
  HLPCA-02033-2011_H14_census.xlsx  table HH-14, district Shimla (catalog 9331): % of households
  PCA_TV_0211_2011.xlsx             PCA town/village/ward, district Shimla (catalog 6224): No_HH
Output: shimla_mc_wall_roof_by_ward.csv (percent of households; No_HH = households)
"""
from pathlib import Path
import pandas as pd

HERE = Path(__file__).parent
TOWN = 800137  # Shimla (M Corp.)

WALL = ['grass_thatch_bamboo', 'plastic', 'mud_unburnt_brick', 'wood', 'stone_no_mortar',
        'stone_mortar', 'gi_metal_asbestos', 'burnt_brick', 'concrete', 'other']
ROOF = ['grass_thatch_wood_mud', 'plastic', 'handmade_tiles', 'machine_tiles', 'burnt_brick',
        'stone_slate', 'gi_metal_asbestos', 'concrete', 'other']

h = pd.read_excel(HERE / 'raw/HLPCA-02033-2011_H14_census.xlsx', header=None, dtype=str)
h = h[h[6] == str(TOWN)]  # one Urban row per ward; ward 0 = whole town
out = pd.DataFrame({'ward': h[7].astype(int).values, 'area': h[8].values})
for i, n in enumerate(ROOF):
    out['roof_' + n] = h[22 + i].astype(float).values
for i, n in enumerate(WALL):
    out['wall_' + n] = h[31 + i].astype(float).values

p = pd.read_excel(HERE / 'raw/PCA_TV_0211_2011.xlsx')
p = p[p['Town/Village'] == TOWN][['Ward', 'No_HH', 'TOT_P']].rename(columns={'Ward': 'ward'})
out = out.merge(p, on='ward', how='left')

# fire classes for Objective 3: combustible wall vs masonry/concrete
out['wall_combustible'] = out[['wall_wood', 'wall_grass_thatch_bamboo', 'wall_plastic']].sum(axis=1)
out['wall_masonry_concrete'] = out[['wall_stone_mortar', 'wall_stone_no_mortar', 'wall_burnt_brick',
                                    'wall_concrete', 'wall_mud_unburnt_brick']].sum(axis=1)
out.to_csv(HERE / 'shimla_mc_wall_roof_by_ward.csv', index=False)
print(out[['ward', 'No_HH', 'wall_wood', 'wall_stone_mortar', 'wall_burnt_brick', 'wall_concrete',
           'wall_gi_metal_asbestos', 'roof_gi_metal_asbestos', 'roof_stone_slate', 'roof_concrete']].to_string(index=False))
