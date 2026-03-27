#!/usr/bin/env python3
"""
Download OSM raster tiles for offline use and generate a local style.json.

Usage:
    python3 download_tiles.py [lat] [lon] [radius_km] [max_zoom]

Defaults: Warsaw center (52.2297, 21.0122), 4 km radius, zoom 5-13.

Output:
    tiles/{z}/{x}/{y}.png    — tile images
    tiles/offline-style.json — MapLibre style pointing to localhost:8080

NOTE: Tile downloads are rate-limited to 1 req/s to respect
      tile.openstreetmap.org usage policy. The OSM tile policy
      allows low-volume downloads for development/testing.
      See: https://operations.osmfoundation.org/policies/tiles/

After downloading, start the server:
    cd tiles
    python3 ../scripts/serve_local.py

Then run the PoC:
    ./build/poc_map --offline
"""

import json
import math
import os
import sys
import time
import urllib.request
from pathlib import Path

# ── Defaults ─────────────────────────────────────────────────────────────────
DEFAULT_LAT       = 52.2297   # Warsaw, Poland
DEFAULT_LON       = 21.0122
DEFAULT_RADIUS_KM = 4.0
DEFAULT_MAX_ZOOM  = 13
MIN_ZOOM          = 5

SERVER_PORT  = 8080
USER_AGENT   = "MapLibre-PoC/0.1 (+https://github.com/maplibre/maplibre-native-qt; educational)"
DELAY_SECS   = 1.1            # stay under 1 req/s average

SCRIPT_DIR = Path(__file__).resolve().parent
TILES_DIR  = SCRIPT_DIR.parent / "tiles"


# ── Coordinate helpers ────────────────────────────────────────────────────────
def tile_xy(lat_deg: float, lon_deg: float, zoom: int) -> tuple[int, int]:
    """OSM/XYZ tile coordinates for a lat/lon."""
    lat_r = math.radians(lat_deg)
    n = 1 << zoom
    x = int((lon_deg + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n)
    return x, y


def tiles_in_bbox(
    lat_min: float, lat_max: float,
    lon_min: float, lon_max: float,
    zoom: int,
) -> list[tuple[int, int, int]]:
    x0, y1 = tile_xy(lat_min, lon_min, zoom)   # y1 = bigger y (south)
    x1, y0 = tile_xy(lat_max, lon_max, zoom)   # y0 = smaller y (north)
    return [
        (zoom, x, y)
        for x in range(x0, x1 + 1)
        for y in range(y0, y1 + 1)
    ]


def km_to_deg(km: float, lat: float) -> tuple[float, float]:
    lat_d = km / 111.0
    lon_d = km / (111.0 * math.cos(math.radians(lat)))
    return lat_d, lon_d


# ── Download ──────────────────────────────────────────────────────────────────
def download_tile(z: int, x: int, y: int) -> bool:
    """Download tile; return True if newly fetched, False if already cached."""
    out = TILES_DIR / str(z) / str(x) / f"{y}.png"
    if out.exists():
        return False

    out.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            out.write_bytes(resp.read())
        return True
    except Exception as exc:
        print(f"    ⚠ {z}/{x}/{y}: {exc}")
        return False


# ── Style generation ──────────────────────────────────────────────────────────
def write_offline_style(min_zoom: int, max_zoom: int, port: int = SERVER_PORT) -> Path:
    style = {
        "version": 8,
        "name": "OSM Offline Raster",
        "sources": {
            "osm-raster": {
                "type": "raster",
                "tiles": [f"http://localhost:{port}/{{z}}/{{x}}/{{y}}.png"],
                "tileSize": 256,
                "minzoom": min_zoom,
                "maxzoom": max_zoom,
                "attribution": (
                    "© <a href='https://www.openstreetmap.org/copyright'>"
                    "OpenStreetMap contributors</a>"
                ),
            }
        },
        "layers": [
            {
                "id": "background",
                "type": "background",
                "paint": {"background-color": "#f0ebe3"},
            },
            {
                "id": "osm-raster",
                "type": "raster",
                "source": "osm-raster",
                "paint": {"raster-opacity": 1.0},
            },
        ],
    }
    out = TILES_DIR / "offline-style.json"
    out.write_text(json.dumps(style, indent=2, ensure_ascii=False))
    return out


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    args = sys.argv[1:]
    lat       = float(args[0]) if len(args) > 0 else DEFAULT_LAT
    lon       = float(args[1]) if len(args) > 1 else DEFAULT_LON
    radius_km = float(args[2]) if len(args) > 2 else DEFAULT_RADIUS_KM
    max_zoom  = int(args[3])   if len(args) > 3 else DEFAULT_MAX_ZOOM

    lat_d, lon_d = km_to_deg(radius_km, lat)
    bbox = (lat - lat_d, lat + lat_d, lon - lon_d, lon + lon_d)

    print("═" * 52)
    print("  OSM Raster Tile Downloader for MapLibre PoC")
    print("═" * 52)
    print(f"  Center : {lat}, {lon}")
    print(f"  Radius : {radius_km} km")
    print(f"  Zoom   : {MIN_ZOOM} – {max_zoom}")
    print(f"  Output : {TILES_DIR}")
    print()

    TILES_DIR.mkdir(exist_ok=True)

    # Collect all tiles across zoom levels
    all_tiles: list[tuple[int, int, int]] = []
    for z in range(MIN_ZOOM, max_zoom + 1):
        zl = tiles_in_bbox(*bbox, z)
        all_tiles.extend(zl)
        print(f"  zoom {z:2d}: {len(zl):5d} tiles")

    total = len(all_tiles)
    estimated_mb = total * 0.025   # ~25 KB average per PNG
    print()
    print(f"  Total tiles : {total}")
    print(f"  Estimated   : ~{estimated_mb:.0f} MB")
    print()
    print("  Rate-limited to 1 req/s (OSM tile policy).")
    answer = input("  Continue? [y/N] ").strip().lower()
    if answer not in ("y", "yes"):
        print("Aborted.")
        return

    print()
    downloaded = skipped = errors = 0
    for i, (z, x, y) in enumerate(all_tiles, 1):
        ok = download_tile(z, x, y)
        if ok:
            downloaded += 1
            print(f"  [{i:5d}/{total}] ✓  {z}/{x}/{y}.png")
            time.sleep(DELAY_SECS)
        else:
            skipped += 1

    print()
    print(f"  Downloaded : {downloaded}  |  Cached : {skipped}  |  Errors : {errors}")

    style_path = write_offline_style(MIN_ZOOM, max_zoom)
    print(f"  Style      : {style_path}")

    # Disk usage
    png_files = list(TILES_DIR.rglob("*.png"))
    total_bytes = sum(f.stat().st_size for f in png_files)
    print(f"  Disk usage : {total_bytes / 1024 / 1024:.1f} MB ({len(png_files)} files)")

    print()
    print("═" * 52)
    print("  Done! Next steps:")
    print()
    print("  1. Start tile server:")
    print(f"       cd {TILES_DIR}")
    print(f"       python3 {SCRIPT_DIR}/serve_local.py")
    print()
    print("  2. Run the PoC in offline mode:")
    print("       ./build/poc_map --offline")
    print("═" * 52)


if __name__ == "__main__":
    main()
