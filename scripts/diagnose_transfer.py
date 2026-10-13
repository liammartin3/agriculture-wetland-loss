"""Diagnostic (not part of the notebook): why does a single 2020-trained model over-predict wetland in 1990-2010?

This is the experiment that led to dropping 1990 and training one model per snapshot. It trains one model on
2020 training points and applies it to all four snapshots, comparing variants by (a) 2020 held-out accuracy and
(b) predicted class shares per year on 2,000 random points:
  A: 9 features, no sensor adjustment     B: indices only (NDVI, MNDWI, TC wetness)
  C: 9 features, Landsat 8 adjusted to ETM+ (Roy et al. 2016)     D: indices only, adjusted
All four variants mapped wetland on roughly 30-57% of the watershed in 1990-2010 vs. ~18-24% in 2020.

It reads outputs/training_points_2020.geojson, so re-running it after the notebook regenerates those points gives
slightly different numbers. Run from the repo root:  .venv/bin/python scripts/diagnose_transfer.py
"""
import ee
import geopandas as gpd
import geemap
import pandas as pd

ee.Initialize(project="agriculture-wetland-loss")
aoi = ee.FeatureCollection("USGS/WBD/2017/HUC08").filter(ee.Filter.eq("huc8", "10160002")).geometry()
AOI_KM2 = 2772.5
BANDS = ["blue", "green", "red", "nir", "swir1", "swir2"]
TC = [0.0315, 0.2021, 0.3102, 0.1594, -0.6806, -0.6109]
ROY_S = ee.Image.constant([0.8474, 0.8483, 0.9047, 0.8462, 0.8937, 0.9071])
ROY_I = ee.Image.constant([0.0003, 0.0088, 0.0061, 0.0412, 0.0254, 0.0172])


def mask(img):
    qa = img.select("QA_PIXEL")
    return img.updateMask(qa.bitwiseAnd(1 | 2 | 8 | 16 | 32).eq(0)).updateMask(img.select("QA_RADSAT").eq(0))


def prep(bands, harmonize=False):
    def f(img):
        sr = mask(img).select(bands, BANDS).multiply(0.0000275).add(-0.2)
        if harmonize:
            sr = sr.subtract(ROY_I).divide(ROY_S).rename(BANDS)
        return sr
    return f


TM = ["SR_B1", "SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B7"]
OLI = ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"]
SNAP = {1990: (1989, 1991, ["L5"]), 2000: (1999, 2001, ["L5", "L7"]),
        2010: (2009, 2011, ["L5", "L7"]), 2020: (2019, 2021, ["L8"])}
IDS = {"L5": "LANDSAT/LT05/C02/T1_L2", "L7": "LANDSAT/LE07/C02/T1_L2", "L8": "LANDSAT/LC08/C02/T1_L2"}


def composite(year, harmonize):
    y0, y1, sensors = SNAP[year]
    col = ee.ImageCollection([])
    for s in sensors:
        fn = prep(OLI, harmonize) if s == "L8" else prep(TM)
        col = col.merge(ee.ImageCollection(IDS[s]).filterBounds(aoi)
                        .filterDate(f"{y0}-01-01", f"{y1 + 1}-01-01")
                        .filter(ee.Filter.calendarRange(4, 6, "month")).map(fn))
    img = col.median()
    tcw = img.select(BANDS).multiply(ee.Image.constant(TC)).reduce(ee.Reducer.sum()).rename("tcw")
    return img.addBands([img.normalizedDifference(["nir", "red"]).rename("ndvi"),
                         img.normalizedDifference(["green", "swir1"]).rename("mndwi"), tcw])


proj = ee.Image("USDA/NASS/CDL/2020").select("cropland").projection()
pts_gdf = gpd.read_file("outputs/training_points_2020.geojson")[["class", "stratum", "geometry"]]
pts = geemap.gdf_to_ee(pts_gdf)
rand_pts = ee.FeatureCollection.randomPoints(aoi, 2000, seed=1)

ALL9 = BANDS + ["ndvi", "mndwi", "tcw"]
IDX3 = ["ndvi", "mndwi", "tcw"]
variants = {
    "A current (9 feat, no harmonize)": (ALL9, False),
    "B indices only, no harmonize": (IDX3, False),
    "C 9 feat, harmonized": (ALL9, True),
    "D indices only, harmonized": (IDX3, True),
}

rows = []
for name, (feats, harm) in variants.items():
    comps = {y: composite(y, harm) for y in SNAP}
    samp = comps[2020].select(feats).sampleRegions(pts, ["class", "stratum"], projection=proj, scale=30)
    samp = samp.randomColumn("r", seed=7)
    tr, te = samp.filter(ee.Filter.lt("r", 0.7)), samp.filter(ee.Filter.gte("r", 0.7))
    rf = ee.Classifier.smileRandomForest(numberOfTrees=200, seed=42).train(tr, "class", feats)
    oa = te.classify(rf).errorMatrix("class", "classification").accuracy().getInfo()
    row = {"variant": name, "oa_2020": round(oa, 3)}
    for y in SNAP:
        pred = comps[y].select(feats).sampleRegions(rand_pts, projection=proj, scale=30).classify(rf)
        h = pred.aggregate_histogram("classification").getInfo()
        n = sum(h.values())
        for k, lab in (("0", "wet"), ("1", "crop"), ("2", "grass")):
            row[f"{y}_{lab}_km2"] = round(h.get(k, 0) / n * AOI_KM2)
    rows.append(row)
    print(name, row, flush=True)

pd.set_option("display.width", 250)
df = pd.DataFrame(rows).set_index("variant")
print(df[["oa_2020"] + [c for c in df.columns if "wet" in c]].to_string())
print(df[[c for c in df.columns if "crop" in c or "grass" in c]].to_string())
