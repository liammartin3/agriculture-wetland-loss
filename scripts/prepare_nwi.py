"""Prepare National Wetlands Inventory (NWI) polygons for upload to Earth Engine.

Input:  USFWS NWI HUC8 download for Pipestem (10160002), unzipped into data/raw/nwi/
        https://documentst.ecosphere.fws.gov/wetlands/downloads/watershed/HU8_10160002_Watershed.zip
Output: data/processed/nwi_pipestem.zip (zipped shapefile, EPSG:4326)

Run from the repo root:  .venv/bin/python scripts/prepare_nwi.py
"""
import os
import zipfile

import ee
import geopandas as gpd
import shapely

GDB = "data/raw/nwi/HU8_10160002_Watershed/HU8_10160002.gdb"
OUT_DIR = "data/processed/nwi_pipestem"
OUT_ZIP = "data/processed/nwi_pipestem.zip"
SIMPLIFY_M = 2  # vertex tolerance in metres; far below the 30 m Landsat pixel

# 1. Use the exact WBD boundary Earth Engine uses, so NWI and the composites line up
ee.Initialize(project="agriculture-wetland-loss")
geom = (ee.FeatureCollection("USGS/WBD/2017/HUC08")
        .filter(ee.Filter.eq("huc8", "10160002")).geometry().getInfo())
boundary = gpd.GeoDataFrame(geometry=[shapely.geometry.shape(geom)], crs="EPSG:4326")

# 2. Load NWI wetland polygons (already in an Albers equal-area projection, units = metres)
w = gpd.read_file(GDB, layer="HU8_10160002_Wetlands", columns=["ATTRIBUTE", "WETLAND_TYPE"])
print("NWI polygons in USFWS HUC8 file:", len(w))

# 3. Clip to the watershed and flag farmed wetlands ("Pf" = palustrine farmed)
w = gpd.clip(w, boundary.to_crs(w.crs))
w = w[~w.geometry.is_empty].copy()
w["farmed"] = (w["ATTRIBUTE"] == "Pf").astype(int)
w["area_m2"] = w.area.round(1)  # true area, measured before reprojecting
print(f"after clip: {len(w)} polygons | farmed (Pf): {w.farmed.sum()} | "
      f"total {w.area_m2.sum() / 1e6:.1f} km2 | non-farmed {w[w.farmed == 0].area_m2.sum() / 1e6:.1f} km2")

# 4. Simplify vertices, reproject to WGS84, and make sure geometries are valid for Earth Engine
w["geometry"] = w.geometry.simplify(SIMPLIFY_M, preserve_topology=True)
w = w.rename(columns={"ATTRIBUTE": "attribute", "WETLAND_TYPE": "wet_type"}).to_crs("EPSG:4326")
w["geometry"] = shapely.make_valid(w.geometry.values)

# 5. Write a zipped shapefile (the format the Earth Engine Code Editor uploader accepts)
os.makedirs(OUT_DIR, exist_ok=True)
w.to_file(f"{OUT_DIR}/nwi_pipestem.shp")
with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
    for f in os.listdir(OUT_DIR):
        z.write(f"{OUT_DIR}/{f}", f)
print(f"wrote {OUT_ZIP}: {os.path.getsize(OUT_ZIP) / 1e6:.1f} MB")
