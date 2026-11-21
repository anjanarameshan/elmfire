"""Classify how each burned building cell ignited: ember, vegetation neighbour, or building neighbour only."""
import sys, glob
import numpy as np
from osgeo import gdal
gdal.UseExceptions()
rd = lambda p: gdal.Open(p).ReadAsArray().astype(float)
OFF = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
def sh(a, dy, dx, fill):
    o = np.full_like(a, fill); H, W = a.shape
    o[max(0,-dy):H-max(0,dy), max(0,-dx):W-max(0,dx)] = a[max(0,dy):H-max(0,-dy), max(0,dx):W-max(0,-dx)]
    return o
tot = {}
import os
SHP = os.environ.get('SHP')
for d in sys.argv[1:]:
    fr = rd(d + '/inputs/bldg_footprint_frac.tif'); b = fr > 0
    if SHP:
        ref = gdal.Open(d + '/inputs/bldg_footprint_frac.tif')
        m = gdal.GetDriverByName('MEM').Create('', ref.RasterXSize, ref.RasterYSize, 1, gdal.GDT_Byte)
        m.SetGeoTransform(ref.GetGeoTransform()); m.SetProjection(ref.GetProjection())
        v = gdal.OpenEx(SHP); gdal.RasterizeLayer(m, [1], v.GetLayer(0), burn_values=[1])
        inside = m.ReadAsArray() > 0
    else:
        inside = np.ones(b.shape, bool)
    L = gdal.Open(d + '/inputs/landscape.tif'); fm = L.GetRasterBand(4).ReadAsArray()
    veg = (~b) & (fm >= 100)
    toa = rd(glob.glob(d + '/outputs/time_of_arrival_*.tif')[0]); burned = toa > 0
    ei = rd(glob.glob(d + '/outputs/ember_ignition_*.tif')[0]) > 0
    t = np.where(burned, toa, np.inf)
    nb_bldg = np.zeros(b.shape, int); nb_veg = np.zeros(b.shape, int)
    earlier_b = np.zeros(b.shape, bool); earlier_v = np.zeros(b.shape, bool)
    for dy, dx in OFF:
        tb = sh(np.where(b, t, np.inf), dy, dx, np.inf); tv = sh(np.where(veg, t, np.inf), dy, dx, np.inf)
        nb_bldg += sh(b, dy, dx, False); nb_veg += sh(veg, dy, dx, False)
        earlier_b |= tb < t; earlier_v |= tv < t
    b0 = b
    b = b & inside
    bb = b & burned
    cls = {
      'building cells': b.sum(), 'burned': bb.sum(),
      'ember-ignited': (bb & ei).sum(),
      'vegetation neighbour burned first': (bb & ~ei & earlier_v).sum(),
      'ONLY building neighbours burned first (house-to-house)': (bb & ~ei & ~earlier_v & earlier_b).sum(),
      'no earlier neighbour': (bb & ~ei & ~earlier_v & ~earlier_b).sum(),
    }
    inner = b & (nb_veg == 0)           # no vegetation in the 8 neighbours
    cls['inner cells (no veg neighbour)'] = inner.sum()
    cls['inner cells burned'] = (inner & burned).sum()
    edge_b = b & burned & (nb_veg > 0)
    cls['edge cells burned (have veg neighbour)'] = edge_b.sum()
    cls['edge cells total'] = (b & (nb_veg > 0)).sum()
    # does fire cross a building: unburned bldg cells next to burned bldg cells
    adj_burned_b = np.zeros(b.shape, bool)
    for dy, dx in OFF: adj_burned_b |= sh(b & burned, dy, dx, False)
    cls['unburned bldg cells next to a burned bldg cell'] = (b & ~burned & adj_burned_b).sum()
    print(d); [print(f'  {k:58s} {v}') for k, v in cls.items()]
