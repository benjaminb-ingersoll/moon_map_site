"""
One-time conversion of USGS Lunar Geologic Map shapefiles + CSVs
into static JSON files for the React/CesiumJS app.

Outputs (written to lunar-map/public/data/):
  - geo_units.json         GeoJSON FeatureCollection (12,247 polygons)
  - linear_features.json   GeoJSON FeatureCollection (3,800 lines)
  - unit_colors.json       { unitCode: "#hex" }
  - unit_descriptions.json { unitCode: { name, desc } }
"""

import csv
import json
import os

import geopandas as gpd
import numpy as np
from shapely.ops import transform

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE = os.path.dirname(os.path.abspath(__file__))
SHP_DIR = os.path.join(BASE, "Lunar_GIS", "Shapefiles")
SYM_DIR = os.path.join(BASE, "Lunar_GIS", "Symbol_LayerDefinitions")
OUT_DIR = os.path.join(BASE, "lunar-map", "public", "data")

os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# 1. Read lookup tables
# ---------------------------------------------------------------------------
print("Reading lookup tables...")

colors = {}
with open(os.path.join(SYM_DIR, "GeologyUnit_colors.csv"), "r", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        colors[row["unit"]] = row["color_hex"]

descriptions = {}
with open(
    os.path.join(SYM_DIR, "Unified_Geologic_Map_of_the_Moon_DOMU_descriptions.csv"),
    "r",
    encoding="utf-8-sig",
) as f:
    for row in csv.DictReader(f):
        descriptions[row["Unit"]] = {
            "name": row["Name"],
            "desc": row["Description"][:200],
        }

# Write lookup JSONs
with open(os.path.join(OUT_DIR, "unit_colors.json"), "w") as f:
    json.dump(colors, f)
print(f"  unit_colors.json: {len(colors)} units")

with open(os.path.join(OUT_DIR, "unit_descriptions.json"), "w") as f:
    json.dump(descriptions, f)
print(f"  unit_descriptions.json: {len(descriptions)} units")

# ---------------------------------------------------------------------------
# 2. Read and transform shapefiles
# ---------------------------------------------------------------------------
MOON_R = 1_737_400.0
SCALE = 180.0 / (MOON_R * np.pi)


def reproject(gdf):
    """Convert Moon equidistant cylindrical meters to lon/lat degrees."""
    gdf["geometry"] = gdf["geometry"].apply(
        lambda g: transform(lambda x, y, z=None: (x * SCALE, y * SCALE), g)
    )
    return gdf


def round_coords(coords, precision=2):
    if isinstance(coords[0], (list, tuple)):
        return [round_coords(c, precision) for c in coords]
    return [round(c, precision) for c in coords]


def round_geojson(geojson_dict, precision=2):
    for feature in geojson_dict["features"]:
        geom = feature["geometry"]
        if geom and geom.get("coordinates"):
            geom["coordinates"] = round_coords(geom["coordinates"], precision)
    return geojson_dict


# --- GeoUnits ---
print("Reading GeoUnits shapefile...")
geo_units = gpd.read_file(os.path.join(SHP_DIR, "GeoUnits.shp"))
print(f"  {len(geo_units)} features loaded")

print("  Reprojecting...")
geo_units = reproject(geo_units)

print("  Simplifying (tolerance=0.05)...")
geo_units["geometry"] = geo_units["geometry"].simplify(0.05, preserve_topology=True)
geo_units = geo_units[~geo_units.geometry.is_empty & geo_units.geometry.notna()]

# Enrich attributes
geo_units["Name"] = geo_units["FIRST_Unit"].map(
    lambda u: descriptions.get(u, {}).get("name", "")
)
geo_units["Desc"] = geo_units["FIRST_Unit"].map(
    lambda u: descriptions.get(u, {}).get("desc", "")
)
geo_units["Color"] = geo_units["FIRST_Unit"].map(
    lambda u: colors.get(u, "#888888")
)
geo_units["Area_km2"] = geo_units["AREA_GEO"].round(1)

# Keep only needed columns
geo_units = geo_units[
    ["FIRST_Unit", "FIRST_Un_1", "FIRST_Un_2", "Name", "Desc", "Color", "Area_km2", "geometry"]
]

# Convert to GeoJSON dict and round coordinates
geo_units_json = json.loads(geo_units.to_json())
geo_units_json = round_geojson(geo_units_json)

out_path = os.path.join(OUT_DIR, "geo_units.json")
with open(out_path, "w") as f:
    json.dump(geo_units_json, f)
size_mb = os.path.getsize(out_path) / (1024 * 1024)
print(f"  geo_units.json: {len(geo_units_json['features'])} features, {size_mb:.1f} MB")

# --- Linear Features ---
print("Reading Linear Features shapefile...")
linear = gpd.read_file(os.path.join(SHP_DIR, "Linear_Features.shp"))
print(f"  {len(linear)} features loaded")

print("  Reprojecting...")
linear = reproject(linear)

linear["geometry"] = linear["geometry"].simplify(0.03, preserve_topology=True)
linear = linear[~linear.geometry.is_empty & linear.geometry.notna()]

linear = linear[["TYPE", "COMMENT", "Preservati", "geometry"]]

linear_json = json.loads(linear.to_json())
linear_json = round_geojson(linear_json)

out_path = os.path.join(OUT_DIR, "linear_features.json")
with open(out_path, "w") as f:
    json.dump(linear_json, f)
size_mb = os.path.getsize(out_path) / (1024 * 1024)
print(f"  linear_features.json: {len(linear_json['features'])} features, {size_mb:.1f} MB")

print("\nDone! Files written to:", OUT_DIR)
