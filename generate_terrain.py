"""
Generate Cesium heightmap terrain tiles from the LOLA 64ppd DEM.

Input:  Lunar_Rasters/LRO_LOLA_DTM/ldem_64_float.img
        Raw float32, 23040 x 11520, Simple Cylindrical, 0-360°E, 90°N to -90°S
        Values are height in km relative to 1737.4 km reference radius.

Output: lunar-map/public/terrain/  with layer.json + {z}/{x}/{y}.terrain
        Cesium "heightmap-1.0" format tiles (65x65, little-endian int16).

Zoom 0-6 to match our imagery tiles.
"""

import json
import os
import struct
import numpy as np

# --- Config ---
DEM_PATH = r"Lunar_Rasters\LRO_LOLA_DTM\ldem_64_float.img"
OUT_DIR = r"lunar-map\public\terrain"
DEM_WIDTH = 23040
DEM_HEIGHT = 11520
TILE_SIZE = 65  # Cesium heightmap tile size (65x65 with 1px overlap)
MAX_ZOOM = 5
# DEM values are in km; convert to meters for Cesium
KM_TO_M = 1000.0
# Reference: heights are relative to 1737.4 km sphere.
# Our globe uses WGS84 equatorial radius (6378137m) as a sphere.
# We need to scale the terrain heights so they look correct on the inflated globe.
# Scale factor = globe_radius / moon_radius
MOON_RADIUS_M = 1_737_400
GLOBE_RADIUS_M = 6_378_137
HEIGHT_SCALE = GLOBE_RADIUS_M / MOON_RADIUS_M  # ~3.67

# The DEM uses 0-360°E longitude. Cesium uses -180 to 180.
# We'll remap during sampling.


def load_dem():
    print(f"Loading DEM from {DEM_PATH} ...")
    data = np.fromfile(DEM_PATH, dtype=np.float32)
    # PDS is big-endian on disk but the label says PC_REAL = little-endian
    dem = data.reshape((DEM_HEIGHT, DEM_WIDTH))
    # Convert km to meters and apply globe scale
    dem = dem * KM_TO_M * HEIGHT_SCALE
    print(f"  Shape: {dem.shape}, range: {dem.min():.1f} to {dem.max():.1f} m (scaled)")
    return dem


def sample_tile(dem, z, x, y):
    """Sample a 65x65 tile from the DEM for tile coordinates (z, x, y).
    
    Cesium geographic tiling at zoom z:
    - 2^(z+1) tiles in X (longitude), 2^z tiles in Y (latitude)
    - Y=0 is the northernmost row
    - Longitude: -180 to 180, Latitude: -90 to 90
    """
    num_tiles_x = 2 ** (z + 1)
    num_tiles_y = 2 ** z

    # Tile bounds in degrees
    tile_width = 360.0 / num_tiles_x
    tile_height = 180.0 / num_tiles_y

    lon_min = -180.0 + x * tile_width
    lat_max = 90.0 - y * tile_height  # top of tile

    # Generate 65x65 sample points
    heights = np.zeros((TILE_SIZE, TILE_SIZE), dtype=np.float64)

    for row in range(TILE_SIZE):
        for col in range(TILE_SIZE):
            # Normalized position within tile [0, 1]
            u = col / (TILE_SIZE - 1)
            v = row / (TILE_SIZE - 1)

            lon = lon_min + u * tile_width     # -180 to 180
            lat = lat_max - v * tile_height    # top to bottom

            # Convert to DEM pixel coordinates
            # DEM: 0-360°E longitude, 90°N at row 0
            dem_lon = lon % 360.0  # shift to 0-360
            dem_col = dem_lon / 360.0 * DEM_WIDTH
            dem_row = (90.0 - lat) / 180.0 * DEM_HEIGHT

            # Bilinear interpolation
            c0 = int(dem_col) % DEM_WIDTH
            c1 = (c0 + 1) % DEM_WIDTH
            r0 = min(int(dem_row), DEM_HEIGHT - 1)
            r1 = min(r0 + 1, DEM_HEIGHT - 1)

            fc = dem_col - int(dem_col)
            fr = dem_row - int(dem_row)

            h00 = dem[r0, c0]
            h01 = dem[r0, c1]
            h10 = dem[r1, c0]
            h11 = dem[r1, c1]

            h = (h00 * (1 - fc) * (1 - fr) +
                 h01 * fc * (1 - fr) +
                 h10 * (1 - fc) * fr +
                 h11 * fc * fr)

            heights[row, col] = h

    return heights


def encode_terrain_tile(heights):
    """Encode 65x65 float heights as Cesium heightmap-1.0 format.
    
    Format: 65*65 little-endian int16 values + 1 byte water mask (all land).
    Heights are quantized: stored_value = (height - min) / (max - min) * 32767
    But actually Cesium's heightmap-1.0 is simpler:
    Each value is height in meters encoded as int16, with the range info in layer.json.
    
    Actually, the heightmap-1.0 format stores raw int16 values and uses
    layer.json's heightScale and heightOffset to convert:
      real_height = stored_value * heightScale + heightOffset
    
    We'll use: heightOffset = -10000, heightScale = 0.625
    This gives range -10000 to (-10000 + 32767*0.625) = 10479 meters
    Which covers the Moon's range of about -9125m to +10773m (scaled up by ~3.67)
    Scaled: -33489 to +39536 -- too big for that scheme.
    
    Let's use a larger scale. Moon heights scaled: approx -33500 to +39500 m
    heightOffset = -35000, heightScale = 2.5
    Range: -35000 to (-35000 + 32767*2.5) = 46917 -- covers it.
    """
    h_offset = -35000.0
    h_scale = 2.5

    quantized = np.clip((heights - h_offset) / h_scale, 0, 32767).astype(np.int16)
    
    # Pack as little-endian int16
    raw = quantized.tobytes()
    
    # Append 1-byte water mask (all land = 0xFF for each quad, but simplest:
    # 1 byte 0xFF meaning "all land")
    # Actually for heightmap-1.0 with includeWaterMask:false, no water mask needed.
    
    return raw, h_offset, h_scale


def main():
    dem = load_dem()

    # Compute actual height offset/scale based on data range
    h_min = float(dem.min())
    h_max = float(dem.max())
    print(f"  Scaled height range: {h_min:.1f} to {h_max:.1f} m")
    
    # Choose offset and scale to cover the range with int16 (0-32767)
    h_offset = h_min - 100  # small padding below
    h_scale = (h_max - h_offset + 100) / 32767.0
    print(f"  Encoding: offset={h_offset:.1f}, scale={h_scale:.4f}")

    os.makedirs(OUT_DIR, exist_ok=True)

    # Write layer.json
    layer = {
        "tilejson": "2.1.0",
        "format": "heightmap-1.0",
        "version": "1.0.0",
        "scheme": "tms",
        "tiles": ["{z}/{x}/{y}.terrain"],
        "minzoom": 0,
        "maxzoom": MAX_ZOOM,
        "bounds": [-180, -90, 180, 90],
        "projection": "EPSG:4326",
        "heightOffset": h_offset,
        "heightScale": h_scale,
        "tileSize": TILE_SIZE,
    }
    
    with open(os.path.join(OUT_DIR, "layer.json"), "w") as f:
        json.dump(layer, f, indent=2)
    print("Wrote layer.json")

    total_tiles = 0
    for z in range(MAX_ZOOM + 1):
        num_x = 2 ** (z + 1)
        num_y = 2 ** z
        total_tiles += num_x * num_y
    print(f"Generating {total_tiles} tiles for zoom 0-{MAX_ZOOM}...")

    generated = 0
    for z in range(MAX_ZOOM + 1):
        num_x = 2 ** (z + 1)
        num_y = 2 ** z
        
        for x in range(num_x):
            tile_dir = os.path.join(OUT_DIR, str(z), str(x))
            os.makedirs(tile_dir, exist_ok=True)
            
            for y in range(num_y):
                heights = sample_tile(dem, z, x, y)
                
                # Quantize
                quantized = np.clip(
                    (heights - h_offset) / h_scale, 0, 32767
                ).astype(np.uint16)
                
                # Write as raw little-endian uint16
                tile_path = os.path.join(tile_dir, f"{y}.terrain")
                quantized.tofile(tile_path)
                
                generated += 1
        
        print(f"  Zoom {z}: {num_x}x{num_y} = {num_x * num_y} tiles")

    print(f"Done! Generated {generated} tiles in {OUT_DIR}")
    print(f"Use heightOffset={h_offset:.1f}, heightScale={h_scale:.6f} in Globe.jsx")


if __name__ == "__main__":
    main()
