"""Heat received (flame contact + radiation) on building cells inside a perimeter, vs burned / inner / edge and N_b."""
import sys, os, glob
import numpy as np
from osgeo import gdal
gdal.UseExceptions()
rd = lambda p: gdal.Open(p).ReadAsArray().astype(float)
OFF = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
def sh(a, dy, dx, fill):
    o = np.full_like(a, fill); H, W = a.shape
    o[max(0,-dy):H-max(0,dy), max(0,-dx):W-max(0,dx)] = a[max(0,dy):H-max(0,-dy), max(0,dx):W-max(0,-dx)]
    return o
d, ref_run = sys.argv[1], sys.argv[2]
ref = gdal.Open(d + '/inputs/bldg_footprint_frac.tif'); b = ref.ReadAsArray() > 0
m = gdal.GetDriverByName('MEM').Create('', ref.RasterXSize, ref.RasterYSize, 1, gdal.GDT_Byte)
m.SetGeoTransform(ref.GetGeoTransform()); m.SetProjection(ref.GetProjection())
v = gdal.OpenEx(os.environ['SHP']); gdal.RasterizeLayer(m, [1], v.GetLayer(0), burn_values=[1]); inside = m.ReadAsArray() > 0
L = gdal.Open(d + '/inputs/landscape.tif'); veg = (~b) & (L.GetRasterBand(4).ReadAsArray() >= 100)
o = d + '/outputs/'
dfc = rd(glob.glob(o + 'total_dfc_received_*.tif')[0]); rad = rd(glob.glob(o + 'total_rad_received_*.tif')[0])
toa = rd(glob.glob(o + 'time_of_arrival_*.tif')[0]); burned = toa > 0
toa_ref = rd(glob.glob(ref_run + '/outputs/time_of_arrival_*.tif')[0])
print('TOA identical to reference x100 run:', np.array_equal(toa > 0, toa_ref > 0), ' max |dTOA| s:', np.nanmax(np.abs(np.where((toa>0)&(toa_ref>0), toa - toa_ref, 0))))
print('dfc range', dfc.min(), dfc.max(), ' rad range', rad.min(), rad.max())
heat = (np.clip(dfc, 0, None) + np.clip(rad, 0, None)) / 900.0   # per m2 of the 30 m cell
t = np.where(burned, toa, np.inf)
nveg = sum(sh(veg, dy, dx, False).astype(int) for dy, dx in OFF)
nb = sum((sh(np.where(b, t, np.inf), dy, dx, np.inf) < np.where(burned, t, np.inf)).astype(int) for dy, dx in OFF)
B = b & inside
print('veg cells with heat>0 (whole domain):', (veg & (heat > 0)).sum(), ' of burned veg', (veg & burned).sum())
q = lambda x: 'median %9.3g  p10 %9.3g  p90 %9.3g' % (np.median(x), np.percentile(x, 10), np.percentile(x, 90)) if x.size else '-'
for name, sel in [('all', B), ('burned', B & burned), ('not burned', B & ~burned),
                  ('inner burned', B & burned & (nveg == 0)), ('edge burned', B & burned & (nveg > 0)),
                  ('burned, N_b=0', B & burned & (nb == 0)), ('burned, N_b>=1', B & burned & (nb >= 1))]:
    x = heat[sel]
    print(f'  {name:16s} n={sel.sum():5d} zero heat={(x == 0).sum():5d} ({(x == 0).mean() if x.size else 0:.0%})  {q(x)}')
print('share of heat from flame contact (burned bldg):', (np.clip(dfc,0,None)[B&burned].sum() / (900*heat[B&burned].sum())).round(3))
