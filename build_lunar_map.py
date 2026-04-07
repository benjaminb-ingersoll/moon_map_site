"""
Build an interactive HTML map of the USGS Unified Geologic Map of the Moon.
Uses Folium (Leaflet.js) to render geologic units with official USGS colors,
tooltips, popups, and layer controls by geologic era.
"""

import geopandas as gpd
import folium
from folium import Element
import branca
import csv
import json
import numpy as np
from shapely.ops import transform
from jinja2 import Template

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE = r"c:\Users\benjaminb\Downloads\Unified_Geologic_Map_of_the_Moon_GIS_v2\Unified_Geologic_Map_of_the_Moon_GIS"
SHAPEFILE_DIR = f"{BASE}/Lunar_GIS/Shapefiles"
SYMBOL_DIR = f"{BASE}/Lunar_GIS/Symbol_LayerDefinitions"

# ---------------------------------------------------------------------------
# 1. Read lookup tables
# ---------------------------------------------------------------------------
print("Reading lookup tables...")

colors = {}
with open(f"{SYMBOL_DIR}/GeologyUnit_colors.csv", "r", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        colors[row["unit"]] = row["color_hex"]

descriptions = {}
with open(
    f"{SYMBOL_DIR}/Unified_Geologic_Map_of_the_Moon_DOMU_descriptions.csv",
    "r",
    encoding="utf-8-sig",
) as f:
    for row in csv.DictReader(f):
        descriptions[row["Unit"]] = {
            "name": row["Name"],
            "desc": row["Description"][:200],  # truncate for popup size
        }

# ---------------------------------------------------------------------------
# 2. Read shapefiles
# ---------------------------------------------------------------------------
print("Reading GeoUnits shapefile (12,247 polygons)...")
geo_units = gpd.read_file(f"{SHAPEFILE_DIR}/GeoUnits.shp")

print("Reading Linear Features shapefile (3,800 lines)...")
linear = gpd.read_file(f"{SHAPEFILE_DIR}/Linear_Features.shp")

# ---------------------------------------------------------------------------
# 3. Convert from Moon Equidistant Cylindrical (meters) -> lon/lat degrees
#    For equirectangular with std_parallel=0, central_meridian=0:
#      x = R * lon_rad   =>  lon_deg = x / R * (180/pi)
#      y = R * lat_rad   =>  lat_deg = y / R * (180/pi)
# ---------------------------------------------------------------------------
MOON_R = 1_737_400.0
SCALE = 180.0 / (MOON_R * np.pi)

print("Reprojecting to lunar lon/lat...")
geo_units["geometry"] = geo_units["geometry"].apply(
    lambda g: transform(lambda x, y, z=None: (x * SCALE, y * SCALE), g)
)
linear["geometry"] = linear["geometry"].apply(
    lambda g: transform(lambda x, y, z=None: (x * SCALE, y * SCALE), g)
)

# ---------------------------------------------------------------------------
# 4. Simplify geometries for web display
# ---------------------------------------------------------------------------
print("Simplifying geometries...")
geo_units["geometry"] = geo_units["geometry"].simplify(0.12)
linear["geometry"] = linear["geometry"].simplify(0.06)

# Drop empty/null geometries
geo_units = geo_units[~geo_units.geometry.is_empty & geo_units.geometry.notna()]
linear = linear[~linear.geometry.is_empty & linear.geometry.notna()]

# ---------------------------------------------------------------------------
# 5. Enrich attributes for popups
# ---------------------------------------------------------------------------
geo_units["Name"] = geo_units["FIRST_Unit"].map(
    lambda u: descriptions.get(u, {}).get("name", "")
)
geo_units["Desc"] = geo_units["FIRST_Unit"].map(
    lambda u: descriptions.get(u, {}).get("desc", "")
)
geo_units["Color"] = geo_units["FIRST_Unit"].map(
    lambda u: colors.get(u, "#888888")
)

# Round area for display
geo_units["Area_km2"] = geo_units["AREA_GEO"].round(1)

# Keep only columns needed for the map
geo_units = geo_units[
    ["FIRST_Unit", "FIRST_Un_1", "FIRST_Un_2", "Name", "Desc", "Color", "Area_km2", "geometry"]
]
linear = linear[["TYPE", "COMMENT", "Preservati", "geometry"]]

# ---------------------------------------------------------------------------
# 6. Build the Folium map
# ---------------------------------------------------------------------------
print("Building interactive map...")

m = folium.Map(
    location=[0, 0],
    zoom_start=1,
    min_zoom=1,
    max_zoom=10,
    tiles=None,
    control_scale=False,
    world_copy_jump=False,
    max_bounds=True,
    max_bounds_viscosity=1.0,
    crs="EPSG4326",
    prefer_canvas=True,
    attr_control=False,
)

# Lock panning to the lunar extent so tiles don't repeat
m.options["maxBounds"] = [[-90, -180], [90, 180]]

# Fit view to the full lunar extent (2:1 rectangle)
m.fit_bounds([[-90, -180], [90, 180]])

# LROC WAC imagery is created directly in JavaScript (see coord_el below)
# so we have a direct JS reference for the toggle button.

# Dark background CSS
m.get_root().html.add_child(Element("""
<style>
    .leaflet-container { background: #0d1117 !important; }
    .legend-box {
        background: rgba(13,17,23,0.92);
        border: 1px solid #444;
        border-radius: 6px;
        padding: 10px 14px;
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 12px;
        color: #e6edf3;
        line-height: 1.6;
        max-height: 400px;
        overflow-y: auto;
    }
    .legend-box h4 { margin: 0 0 6px 0; font-size: 13px; color: #58a6ff; }
    .legend-item { display: flex; align-items: center; gap: 6px; }
    .legend-swatch {
        width: 14px; height: 14px;
        border: 1px solid #555;
        border-radius: 2px;
        flex-shrink: 0;
    }
    .info-title {
        background: rgba(13,17,23,0.92);
        border: 1px solid #444;
        border-radius: 6px;
        padding: 8px 14px;
        font-family: 'Segoe UI', Arial, sans-serif;
        color: #e6edf3;
    }
    .info-title h3 { margin: 0; font-size: 15px; color: #58a6ff; }
    .info-title p { margin: 2px 0 0 0; font-size: 11px; color: #8b949e; }
    .leaflet-popup-content-wrapper {
        background: #161b22 !important;
        color: #e6edf3 !important;
        border: 1px solid #30363d !important;
        border-radius: 8px !important;
    }
    .leaflet-popup-tip { background: #161b22 !important; }
    .leaflet-popup-content { font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; }
    .leaflet-tooltip {
        background: rgba(22,27,34,0.95) !important;
        color: #e6edf3 !important;
        border: 1px solid #30363d !important;
        border-radius: 4px !important;
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 12px;
    }
    .leaflet-tooltip-top:before { border-top-color: #30363d !important; }
    .leaflet-tooltip-bottom:before { border-bottom-color: #30363d !important; }
    .leaflet-control-layers {
        background: rgba(13,17,23,0.92) !important;
        border: 1px solid #444 !important;
        border-radius: 6px !important;
        color: #e6edf3 !important;
    }
    .leaflet-control-layers label { color: #e6edf3 !important; }
    .leaflet-control-zoom a {
        background: #161b22 !important;
        color: #e6edf3 !important;
        border-color: #30363d !important;
    }
    .leaflet-bar a:hover { background: #21262d !important; }
    /* Collapsible legend */
    .legend-box {
        transition: max-height 0.3s ease;
    }
    .legend-box.collapsed .legend-items {
        display: none;
    }
    .legend-toggle {
        cursor: pointer;
        user-select: none;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .legend-toggle .arrow {
        font-size: 10px;
        margin-left: 8px;
        transition: transform 0.2s;
    }
    .legend-box.collapsed .legend-toggle .arrow {
        transform: rotate(-90deg);
    }
</style>
"""))

# Title control
title_el = Element("""
<div style="position:fixed; top:10px; left:55px; z-index:1000;" class="info-title">
    <h3>&#127769; Unified Geologic Map of the Moon</h3>
    <p>USGS 1:5,000,000 &mdash; Fortezzo, Spudis &amp; Harrel (2020)</p>
</div>
""")
m.get_root().html.add_child(title_el)

# Coordinate display + layer persistence
coord_el = Element("""
<div id="coord-display" style="position:fixed; bottom:10px; left:10px; z-index:1000;
     background:rgba(13,17,23,0.85); color:#8b949e; padding:4px 10px;
     border-radius:4px; font-family:monospace; font-size:12px;">
    Lat: &mdash; &ensp; Lon: &mdash;
</div>
<script>
var _lrocLayer = null;
var _geoLayers = [];
var _mapRef = null;
var _layerNameMap = {};

function _saveState() {
    var visible = {};
    _geoLayers.forEach(function(l) {
        visible[_layerNameMap[L.stamp(l)]] = _mapRef.hasLayer(l);
    });
    try { localStorage.setItem('lunarMapState', JSON.stringify({layers: visible})); } catch(e) {}
}

document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() {
        for (var key in window) {
            try {
                if (window[key] instanceof L.Map) {
                    _mapRef = window[key];
                    break;
                }
            } catch(e) {}
        }
        if (!_mapRef) return;

        // Create LROC WAC tile layer — local tiles with online fallback
        var localTileUrl = 'tiles/LRO_WAC_Mosaic_Global_303ppd_v02/{z}/{y}/{x}.jpg';
        var remoteTileUrl = 'https://trek.nasa.gov/tiles/Moon/EQ/LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0//default/default028mm/{z}/{y}/{x}.jpg';

        var LRO_FallbackLayer = L.TileLayer.extend({
            getTileUrl: function(coords) {
                return L.Util.template(localTileUrl, {z: coords.z, y: coords.y, x: coords.x});
            },
            _tileOnError: function(done, tile, e) {
                var src = tile.getAttribute('data-remote-tried');
                if (!src) {
                    tile.setAttribute('data-remote-tried', '1');
                    var coords = tile._coords || {};
                    tile.src = L.Util.template(remoteTileUrl, {z: coords.z, y: coords.y, x: coords.x});
                    return;
                }
                L.TileLayer.prototype._tileOnError.call(this, done, tile, e);
            },
            createTile: function(coords, done) {
                var tile = L.TileLayer.prototype.createTile.call(this, coords, done);
                tile._coords = coords;
                return tile;
            }
        });

        _lrocLayer = new LRO_FallbackLayer('', {
            maxZoom: 10,
            maxNativeZoom: 8,
            noWrap: true,
            bounds: [[-90, -180], [90, 180]],
            errorTileUrl: ''
        });

        _mapRef.setMaxBounds([[-90, -180], [90, 180]]);
        _lrocLayer.addTo(_mapRef);

        // Coordinate display
        var display = document.getElementById('coord-display');
        _mapRef.on('mousemove', function(e) {
            display.innerHTML = 'Lat: ' + e.latlng.lat.toFixed(2) + '&deg; &ensp; Lon: ' + e.latlng.lng.toFixed(2) + '&deg;';
        });

        // Collect geo FeatureGroup layers
        _mapRef.eachLayer(function(layer) {
            if (layer instanceof L.FeatureGroup && !layer._url) {
                _geoLayers.push(layer);
                var name = layer.options && layer.options.name ? layer.options.name : ('layer_' + L.stamp(layer));
                _layerNameMap[L.stamp(layer)] = name;
            }
        });

        // Restore saved overlay visibility
        var saved = null;
        try { saved = JSON.parse(localStorage.getItem('lunarMapState')); } catch(e) {}
        if (saved && saved.layers) {
            _geoLayers.forEach(function(l) {
                var name = _layerNameMap[L.stamp(l)];
                if (name in saved.layers) {
                    if (saved.layers[name] && !_mapRef.hasLayer(l)) _mapRef.addLayer(l);
                    else if (!saved.layers[name] && _mapRef.hasLayer(l)) _mapRef.removeLayer(l);
                }
            });
        }

        // Listen for layer add/remove to persist state
        _mapRef.on('overlayadd overlayremove', function() {
            _saveState();
        });
    }, 500);
});
</script>
""")
m.get_root().html.add_child(coord_el)

# ---------------------------------------------------------------------------
# 7. Add geologic unit layers grouped by era
# ---------------------------------------------------------------------------
ERA_ORDER = [
    "Copernican",
    "Eratosthenian",
    "Eratosthenian-Imbrian",
    "Imbrian",
    "Imbrian-Nectarian",
    "Nectarian",
    "Pre-Nectarian",
]

ERA_LABEL_COLORS = {
    "Copernican": "#FCDC0A",
    "Eratosthenian": "#A5CF30",
    "Eratosthenian-Imbrian": "#E64D75",
    "Imbrian": "#1C7BF6",
    "Imbrian-Nectarian": "#73B2C2",
    "Nectarian": "#F4C884",
    "Pre-Nectarian": "#7A3E29",
}


def make_popup_html(props):
    unit = props.get("FIRST_Unit", "")
    return f"""
    <div style="min-width:220px">
        <div style="font-size:14px;font-weight:bold;color:#58a6ff;margin-bottom:4px">
            {unit} &mdash; {props.get('Name', '')}
        </div>
        <div style="color:#8b949e;margin-bottom:6px">{props.get('FIRST_Un_1', '')} &bull; {props.get('FIRST_Un_2', '')}</div>
        <div style="margin-bottom:6px">{props.get('Desc', '')}</div>
        <div style="color:#8b949e;font-size:11px">Area: {props.get('Area_km2', '')} km²</div>
    </div>
    """


for era in ERA_ORDER:
    era_data = geo_units[geo_units["FIRST_Un_1"] == era].copy()
    if era_data.empty:
        continue

    n = len(era_data)
    fg = folium.FeatureGroup(name=f"<span style='color:{ERA_LABEL_COLORS.get(era, '#ccc')}'>{era}</span> ({n})")

    # Convert to GeoJSON dict
    era_geojson = json.loads(era_data.to_json())

    # Round coordinates to reduce file size
    def round_coords(coords, precision=2):
        if isinstance(coords[0], (list, tuple)):
            return [round_coords(c, precision) for c in coords]
        return [round(c, precision) for c in coords]

    for feature in era_geojson["features"]:
        geom = feature["geometry"]
        if geom and geom.get("coordinates"):
            geom["coordinates"] = round_coords(geom["coordinates"])

    folium.GeoJson(
        era_geojson,
        style_function=lambda feat: {
            "fillOpacity": 0,
            "color": "rgba(255,255,255,0.5)",
            "weight": 1,
        },
        highlight_function=lambda feat: {
            "weight": 2,
            "color": "#ffffff",
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["FIRST_Unit", "FIRST_Un_1", "FIRST_Un_2"],
            aliases=["Unit:", "Era:", "Type:"],
            sticky=True,
        ),
        popup=folium.GeoJsonPopup(
            fields=["FIRST_Unit", "Name", "FIRST_Un_1", "FIRST_Un_2", "Desc", "Area_km2"],
            aliases=["Unit", "Name", "Era", "Type", "Description", "Area (km²)"],
            max_width=320,
        ),
    ).add_to(fg)

    fg.add_to(m)

print(f"  Added {len(geo_units)} geologic unit polygons across {len(ERA_ORDER)} eras")

# ---------------------------------------------------------------------------
# 8. Add linear features layer (hidden by default)
# ---------------------------------------------------------------------------
linear_geojson = json.loads(linear.to_json())
for feature in linear_geojson["features"]:
    geom = feature["geometry"]
    if geom and geom.get("coordinates"):
        geom["coordinates"] = round_coords(geom["coordinates"])

LINE_COLORS = {
    "Graben/Fossa": "#ff6b6b",
    "Graben/Fossa, Buried": "#ff6b6b",
    "Scarp/Rupes": "#ffa94d",
    "Scarp/Rupes Uncertain": "#ffa94d",
    "Ridge/Dorsum": "#69db7c",
    "Ridge/Dorsum Uncertain": "#69db7c",
    "Rille/Rima": "#74c0fc",
    "Rille/Rima Uncertain": "#74c0fc",
    "Wrinkle Ridge": "#da77f2",
}

LINE_DASH = {
    "Graben/Fossa, Buried": "5 5",
    "Scarp/Rupes Uncertain": "5 5",
    "Ridge/Dorsum Uncertain": "5 5",
    "Rille/Rima Uncertain": "5 5",
}

fg_linear = folium.FeatureGroup(
    name="<span style='color:#ffd43b'>Linear Features</span> (faults, ridges, rilles)",
    show=False,
)

folium.GeoJson(
    linear_geojson,
    style_function=lambda feat: {
        "color": LINE_COLORS.get(feat["properties"].get("TYPE", ""), "#ffd43b"),
        "weight": 1.8,
        "opacity": 0.85,
        "dashArray": LINE_DASH.get(feat["properties"].get("TYPE", ""), None),
    },
    highlight_function=lambda feat: {
        "weight": 4,
        "opacity": 1,
    },
    tooltip=folium.GeoJsonTooltip(
        fields=["TYPE", "COMMENT", "Preservati"],
        aliases=["Type:", "Comment:", "Preservation:"],
        sticky=True,
    ),
).add_to(fg_linear)

fg_linear.add_to(m)
print(f"  Added {len(linear)} linear features")

# ---------------------------------------------------------------------------
# 9. Layer control
# ---------------------------------------------------------------------------
folium.LayerControl(collapsed=False, position="topright").add_to(m)

# ---------------------------------------------------------------------------
# 10. Legend
# ---------------------------------------------------------------------------
legend_items = ""
for unit_code in sorted(colors.keys(), key=lambda u: (
    0 if u.startswith("C") else
    1 if u.startswith("E") else
    2 if u.startswith("I") else
    3 if u.startswith("N") else 4
)):
    hex_color = colors[unit_code]
    name = descriptions.get(unit_code, {}).get("name", unit_code)
    legend_items += f'<div class="legend-item"><div class="legend-swatch" style="background:{hex_color}"></div><span>{unit_code} &ndash; {name}</span></div>\n'

legend_el = Element(f"""
<div id="legend" style="position:fixed; bottom:30px; right:10px; z-index:1000;" class="legend-box collapsed">
    <div class="legend-toggle" onclick="var el=document.getElementById('legend'); el.classList.toggle('collapsed');">
        <h4 style="margin:0; font-size:13px; color:#58a6ff;">Geologic Units</h4>
        <span class="arrow">&#9660;</span>
    </div>
    <div class="legend-items" style="margin-top:6px">
    {legend_items}
    </div>
</div>
""")
m.get_root().html.add_child(legend_el)

# ---------------------------------------------------------------------------
# 11. Save
# ---------------------------------------------------------------------------
output_path = f"{BASE}/lunar_geologic_map.html"
m.save(output_path)

import os
size_mb = os.path.getsize(output_path) / (1024 * 1024)
print(f"\nMap saved to: {output_path}")
print(f"File size: {size_mb:.1f} MB")
print("Open in a web browser to explore!")
