LANDFIRE 2016 Remap FBFM40 (LF2016_FBFM40_CONUS), second download covering the whole ELMFIRE domain.
Source: C:\Users\DELL\Downloads\landfire_613d98f2-d712-43f1-8478-844e92290560\LF2016_FBFM40_CONUS
        box 35.444-35.813 N, 83.705-83.253 W, EPSG:5070, 30 m.
fbfm40_lf2016.tif           gdalwarp to the ELMFIRE grid (EPSG:32617, 1333 x 1333, 30 m, nearest neighbour).
                            4 cells without data (row 0, cols 1321-1329, far north-east corner).
fbfm40_lf2016_complete.tif  same, those 4 cells given the value of the cell just south of them.
Agrees 100 % with the first, smaller LF2016 download (fuel-test/lf2016/) wherever both have data.
