# Wetland Loss to Agriculture in a Prairie Pothole Watershed, 2000–2020

**How much wetland in one North Dakota watershed was converted to cropland between 2000 and 2020?**

**Interactive before/after map:** https://liammartin3.github.io/agriculture-wetland-loss/

A remote sensing project using Google Earth Engine (Python API + geemap), Landsat, and public reference data.
Every number below comes from the code in [`wetland_loss.ipynb`](wetland_loss.ipynb).

## Answer

About **19.4 km²** was persistently converted from wetland to cropland: mapped as wetland/water in 2000 and as
cropland in both 2010 and 2020. That is **3.9% of the 500.2 km² mapped as wetland in 2000**. Over the same period
**26.2 km²** moved the other way (cropland in 2000, wetland in 2010 and 2020), so total mapped wetland area *rose*,
consistent with a run of wetter-than-average years. Before/after aerial photos suggest the conversions are mostly
small, temporary basins now farmed through, not large permanent wetlands.

![Conversion map](outputs/figures/conversion_map.png)

## Study area

**Pipestem watershed**, HUC8 `10160002`, North Dakota: 2,772.5 km² in the James River basin, in the Prairie
Pothole Region. Chosen over Apple Creek (more ranchland, less conversion to find) and Devils Lake (a closed basin
whose lake flooding over the study period would mask the signal).

## Data

| Purpose | Dataset (Earth Engine ID or source) |
|---|---|
| Watershed boundary | USGS WBD, `USGS/WBD/2017/HUC08` |
| Imagery | Landsat Collection 2 Level-2 surface reflectance: `LANDSAT/LT05/C02/T1_L2`, `LANDSAT/LE07/C02/T1_L2`, `LANDSAT/LC08/C02/T1_L2` |
| Cropland labels | USDA NASS Cropland Data Layer, `USDA/NASS/CDL` (1999–2001, 2009–2011, 2019–2021) |
| Wetland labels | USFWS National Wetlands Inventory, HUC8 10160002 download (44,854 polygons, mapped from 2017–2019 imagery), uploaded as an Earth Engine asset |
| Visual checks | USDA NAIP, `USDA/NAIP/DOQQ` (2003, 2010, 2020) |
| Precipitation | PRISM monthly, `OREGONSTATE/PRISM/ANm` |

## Methods

1. **Composites.** For 2000, 2010 and 2020, a median of all clear April–June Landsat pixels over a 3-year window
   (1999–2001 etc.), cloud/shadow/snow masked with `QA_PIXEL`. 43, 57 and 45 scenes; on average 14.5, 23.6 and
   13.2 clear observations per pixel.
2. **Features.** Six reflectance bands plus NDVI, MNDWI and Tasseled Cap wetness.
3. **Training labels, built separately for each snapshot.** Three classes: wetland/water, cropland,
   grassland/other.
   - Wetland: inside a non-farmed NWI polygon and never cropped in that window's three CDL years. Sampled as
     150 open-water + 150 emergent-marsh points so the model doesn't learn "wetland = open water".
   - Cropland: cultivated in all three CDL years, never fallow, outside NWI (300 points).
   - Grassland/other: never cultivated, not CDL water/wetland, outside NWI (300 points).
   - CDL is smoothed with a 3×3 majority filter first, and only "pure" pixels (whole 3×3 block in the class)
     are kept, to avoid edge pixels and CDL speckle.
4. **Classification.** One random forest per snapshot (200 trees), trained on 70% of its points and tested on the
   other 30%. Each model then classifies its own composite; results are saved as Earth Engine assets.
5. **Analysis.** Class areas per snapshot; persistent conversion (wetland 2000 → cropland 2010 and 2020) with
   three plausibility checks; PRISM precipitation for context.

## Results

![Class area by snapshot](outputs/figures/class_area_by_snapshot.png)

| Class (km²) | 2000 | 2010 | 2020 | Change 2000→2020 |
|---|---|---|---|---|
| Wetland/water | 500.2 | 542.2 | 559.5 | +59.4 (+11.9%) |
| Cropland | 1,260.6 | 1,307.0 | 1,414.7 | +154.1 (+12.2%) |
| Grassland/other | 1,011.8 | 923.3 | 798.3 | −213.5 (−21.1%) |

The largest net change is grassland giving way to cropland. Of the land mapped as wetland in 2000, by 2020 78.6%
was still wetland, 8.8% was cropland and 12.6% was grassland.

**How believable is the 19.4 km² of conversion?**
- 78.9% of it is also cultivated in both 2010 and 2020 according to the (raw) CDL.
- 96.0% lies outside any NWI polygon, as expected for basins already farmed when NWI was mapped (2017–2019);
  only 2.0% sits inside a non-farmed NWI wetland, which would contradict the result.
- 47.1% is in patches of at least 11 pixels (≥ 1 ha); 17.1% is isolated single pixels, likely noise.

![Before/after examples](outputs/figures/conversion_examples.png)

**Precipitation.** All three windows were wetter than the 1985–2025 average of 505.0 mm/yr (+11.3%, +18.0%, +3.9%).
Spring rain alone doesn't track wetland area: the 2020 window had the driest springs (−27.0%) but the most mapped
wetland, plausibly because 2019 was the wettest year in the record (814.0 mm) and basins stayed full.

![Precipitation](outputs/figures/precipitation_chart.png)

## Accuracy

Held-out test points (30% of each snapshot's training points):

| | 2000 | 2010 | 2020 |
|---|---|---|---|
| Overall accuracy | 0.955 | 0.986 | 0.933 |
| Kappa | 0.933 | 0.979 | 0.899 |
| Emergent marsh correctly classified | 0.824 | 0.955 | 0.775 |

Most errors are emergent marsh classified as grassland. Against each period's full reference layers, 87.6–90.4% of
NWI wetland area was mapped as wetland and 79.9–90.8% of CDL cultivated land as cropland.
Confusion matrices: `outputs/confusion_matrix_<year>.csv`.

## Limitations

- **30 m pixels vs. small potholes.** 31.1% of NWI polygons in the watershed are smaller than one Landsat pixel
  (median polygon 0.40 acres). Many potholes are mixed with surrounding land or missed entirely.
- **"Wetland" means wet that spring.** A 3-year spring median captures surface water and marsh vegetation, so
  temporarily flooded ground can be mapped as wetland. Some "conversion" is likely grassland that held spring water
  in 1999–2001 and was later cropped (see hotspot 1 above).
- **Accuracy is optimistic.** Test points are "easy" pure pixels from the same rules as the training data, and the
  random split leaves test points near training points. Field edges, small basins and fallow fields aren't tested.
  Areas are mapped, not error-adjusted.
- **Reference data have their own dates and errors.** NWI is from 2017–2019, so using it for 2000 and 2010 assumes
  those wetlands already existed. Older CDL is noisier: the 2000 map agrees less with CDL (79.9% vs. 90.8% in 2010).
- **Different Landsat sensors.** 2000 and 2010 use Landsat 5/7, 2020 uses Landsat 8, with no cross-sensor
  adjustment. Training a separate model per snapshot means each model learns its own sensor's values, which
  avoids most of the problem.
- **Why not 1990?** The original plan trained one model on 2020 and applied it to 1990–2010. That model mapped
  roughly 30–57% of the watershed as wetland in 1990–2010 (vs. about 20% in 2020), including field-shaped
  "wetlands" in the dry 1989–1991 window that followed the 1988 drought. Adding a Landsat 8 → 7 adjustment or using only indices did not fix it
  ([`scripts/diagnose_transfer.py`](scripts/diagnose_transfer.py)). CDL covers this watershed from 1997, so the study
  was narrowed to 2000–2020, where every snapshot gets its own labels.

## Next steps

- Spatially blocked cross-validation and an independent, photo-interpreted accuracy sample, then error-adjusted
  area estimates (Olofsson et al. 2014).
- Extend back to 1990 with labels that don't depend on CDL, e.g. migrating training points that are spectrally
  stable between years.
- Use all spring images per year (not just a median) or add fall imagery to separate wet fields from marsh.
- Sentinel-2 (10 m) for 2016 onward to catch smaller potholes.

## Repository

| Path | Contents |
|---|---|
| `wetland_loss.ipynb` | The full workflow, Steps 0–9, with explanations |
| `scripts/prepare_nwi.py` | Clips the USFWS NWI download to the watershed and prepares the Earth Engine upload |
| `scripts/diagnose_transfer.py` | The experiment that led to dropping 1990 |
| `outputs/figures/` | Charts and maps (PNG) |
| `outputs/rasters/` | `landcover_2000.tif`, `landcover_2020.tif`, `conversion_2000_2020.tif` (30 m, EPSG:5070; 0 wetland/water, 1 cropland, 2 grassland/other; 255 no data) |
| `outputs/*.csv` | Areas, accuracy, confusion matrices, precipitation, training points (GeoJSON) |
| `docs/` | The GitHub Pages before/after map (Leaflet); data in `docs/data/` is written by the notebook |

## Reproduce

```bash
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/earthengine authenticate
# download https://documentst.ecosphere.fws.gov/wetlands/downloads/watershed/HU8_10160002_Watershed.zip,
# unzip into data/raw/nwi/, then:
.venv/bin/python scripts/prepare_nwi.py
# upload data/processed/nwi_pipestem.zip as an Earth Engine table asset (Code Editor: Assets → NEW → Shape files)
.venv/bin/jupyter lab wetland_loss.ipynb
```

Requires a Google Cloud project registered for noncommercial Earth Engine use; set `PROJECT_ID` and the asset
paths in the notebook to your own. To view the web map locally: `cd docs && python3 -m http.server`.
