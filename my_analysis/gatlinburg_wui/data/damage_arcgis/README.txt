Damage / perimeter data found on ArcGIS Online (checked 2026-10-29)
==================================================================

1. TN_Wildfires2016 (public, no login)
   https://services4.arcgis.com/QdHwhlbx61LR3TWb/arcgis/rest/services/TN_Wildfires2016/FeatureServer
   One layer, All_TN_Perimeters (52 polygons, GeoMAC). NO structure damage data.
   Saved: chimney2_perimeters_geomac.geojson (WGS84)
     FID 9  "CHIMNEY 2"      perDatTime 11/28/2016 11:23 AM, 35.53 ac (size matches the 35 ac reported for the
                             evening of 27 Nov; probably the 27 Nov mapping carried forward), near 35.63 N 83.48 W
     FID 11 "CHIMNEY TOPS 2" 12/13/2016, 17,140 ac final perimeter
   On the model grid: MTBS 15,003 ac / 1,609 buildings; GeoMAC final 17,144 ac / 1,887 buildings (2,851 ac outside MTBS).
   Model (ms_st09, 50 runs): 79 % of burned area outside MTBS, 75 % outside GeoMAC; 1,209 buildings ignited in GeoMAC.

2. Structure status (damage) layers - OWNER: Sevier County GIS (ArcGIS organisation "SC-GIS"), LOGIN REQUIRED
   Web map "Sevier County Strucutre Status Map" (owner PhilipDusek), item d083c2223533415f9f7cc7531c03b426
     https://services1.arcgis.com/Qu4yM4JJvNoC2GKw/arcgis/rest/services/2016_Structure_Status_Public/FeatureServer
       0 Commercial Buildings, 1 Residential Buildings, 2 Public Facilities
   Web map "Gatlinburg wildfire" (owner tboals14), item 3c7ab04497244e0bbeabb07d7f67aa57, uses
     https://services1.arcgis.com/Qu4yM4JJvNoC2GKw/arcgis/rest/services/StructureStatus_View/FeatureServer
       0 Residential Buildings, 1 Public Facilities, 2 Commercial Buildings
   Both services answer "Token Required" (code 499): access must be requested from Sevier County GIS.
