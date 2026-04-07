"""
Download Moon imagery tiles from NASA Moon Trek for offline use.

Dataset: LRO WAC Mosaic Global 303ppd v02 (highest resolution available)
Source:   NASA Moon Trek WMTS
Tiles:    256x256 JPEG, geographic tiling (EPSG:4326)
Max zoom: 8 (~100m/pixel at equator)

Configure MIN_ZOOM / MAX_ZOOM below to control how many tiles to download.

Tile counts per zoom level:
  Zoom 0:        2 tiles  |  cumulative:        2
  Zoom 1:        8 tiles  |  cumulative:       10
  Zoom 2:       32 tiles  |  cumulative:       42
  Zoom 3:      128 tiles  |  cumulative:      170
  Zoom 4:      512 tiles  |  cumulative:      682
  Zoom 5:    2,048 tiles  |  cumulative:    2,730  (~80 MB)
  Zoom 6:    8,192 tiles  |  cumulative:   10,922  (~300 MB)
  Zoom 7:   32,768 tiles  |  cumulative:   43,690  (~1.3 GB)
  Zoom 8:  131,072 tiles  |  cumulative:  174,762  (~5 GB)
"""

import os
import sys
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# ===========================================================================
# CONFIGURATION
# ===========================================================================
MIN_ZOOM = 0
MAX_ZOOM = 7          # Change this to download more/fewer zoom levels (max: 8)
MAX_WORKERS = 8       # Parallel download threads
RETRY_COUNT = 3       # Retries per failed tile
RETRY_DELAY = 1.0     # Seconds between retries

DATASET = "LRO_WAC_Mosaic_Global_303ppd_v02"
TILE_URL = f"https://trek.nasa.gov/tiles/Moon/EQ/{DATASET}/1.0.0//default/default028mm/{{z}}/{{y}}/{{x}}.jpg"

# Output directory (relative to this script)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "lunar-map", "public", "tiles", DATASET)
# ===========================================================================


def get_tile_counts(min_zoom, max_zoom):
    """Calculate tile grid dimensions for each zoom level.
    At zoom 0: 2 columns x 1 row (360/180 degree coverage with 256px tiles).
    Each subsequent zoom doubles both dimensions.
    """
    counts = {}
    for z in range(min_zoom, max_zoom + 1):
        cols = 2 * (2 ** z)   # MatrixWidth
        rows = 1 * (2 ** z)   # MatrixHeight
        counts[z] = (cols, rows)
    return counts


def download_tile(z, y, x, session):
    """Download a single tile, with retries. Returns (z, y, x, success)."""
    tile_path = os.path.join(OUTPUT_DIR, str(z), str(y), f"{x}.jpg")

    # Skip if already downloaded
    if os.path.exists(tile_path):
        return (z, y, x, True, "cached")

    url = TILE_URL.format(z=z, y=y, x=x)
    os.makedirs(os.path.dirname(tile_path), exist_ok=True)

    for attempt in range(RETRY_COUNT):
        try:
            r = session.get(url, timeout=15)
            if r.status_code == 200 and len(r.content) > 0:
                with open(tile_path, "wb") as f:
                    f.write(r.content)
                return (z, y, x, True, "downloaded")
            elif r.status_code == 404:
                return (z, y, x, False, "404")
        except (requests.RequestException, IOError):
            pass
        if attempt < RETRY_COUNT - 1:
            time.sleep(RETRY_DELAY)

    return (z, y, x, False, "failed")


def main():
    tile_counts = get_tile_counts(MIN_ZOOM, MAX_ZOOM)

    total_tiles = sum(cols * rows for cols, rows in tile_counts.values())
    print(f"Moon Tile Downloader")
    print(f"  Dataset:    {DATASET}")
    print(f"  Zoom range: {MIN_ZOOM}-{MAX_ZOOM}")
    print(f"  Total tiles: {total_tiles:,}")
    print(f"  Output:     {OUTPUT_DIR}")
    print(f"  Workers:    {MAX_WORKERS}")
    print()

    # Build task list
    tasks = []
    for z in range(MIN_ZOOM, MAX_ZOOM + 1):
        cols, rows = tile_counts[z]
        for y in range(rows):
            for x in range(cols):
                tasks.append((z, y, x))

    downloaded = 0
    cached = 0
    failed = 0
    start_time = time.time()

    session = requests.Session()
    session.headers["User-Agent"] = "MoonGeologyMap/1.0 (educational use)"

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(download_tile, z, y, x, session): (z, y, x)
            for z, y, x in tasks
        }

        for i, future in enumerate(as_completed(futures), 1):
            z, y, x, success, status = future.result()
            if status == "downloaded":
                downloaded += 1
            elif status == "cached":
                cached += 1
            else:
                failed += 1

            if i % 100 == 0 or i == len(tasks):
                elapsed = time.time() - start_time
                rate = i / elapsed if elapsed > 0 else 0
                pct = i / len(tasks) * 100
                print(
                    f"  [{pct:5.1f}%] {i:,}/{len(tasks):,} tiles  "
                    f"| {downloaded:,} new, {cached:,} cached, {failed:,} failed  "
                    f"| {rate:.0f} tiles/s",
                    flush=True,
                )

    elapsed = time.time() - start_time
    print()
    print(f"Done in {elapsed:.1f}s")
    print(f"  Downloaded: {downloaded:,}")
    print(f"  Cached:     {cached:,}")
    print(f"  Failed:     {failed:,}")

    # Calculate total size on disk
    total_bytes = 0
    for root, dirs, files in os.walk(OUTPUT_DIR):
        for f in files:
            total_bytes += os.path.getsize(os.path.join(root, f))
    print(f"  Disk usage: {total_bytes / (1024*1024):.1f} MB")


if __name__ == "__main__":
    main()
