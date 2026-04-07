#!/usr/bin/env python3
"""
Download vector tiles (MBTiles) for offline MapLibre use.

Usage:
    python3 download_tiles.py                                  # Poland, zoom 0-14
    python3 download_tiles.py --country germany                # Germany, zoom 0-14
    python3 download_tiles.py --country poland --max-zoom 16   # Poland, zoom 0-16 (~8-15 GB!)
    python3 download_tiles.py --bbox "14.07,49.00,24.15,54.84" --max-zoom 14
    python3 download_tiles.py --list-countries

Requires:
    pmtiles CLI (Go binary, ~10 MB).
    Download from: https://github.com/protomaps/go-pmtiles/releases
    Place pmtiles.exe (Windows) or pmtiles (Linux/macOS) in:
      - next to this script (scripts/pmtiles.exe), OR
      - anywhere in your PATH

Output:
    tiles/<country>.mbtiles    — vector tiles (OpenMapTiles schema, ~1-2 GB for Poland z14)
    tiles/vector-style.json    — MapLibre style using mbtiles:// (no tile server needed!)

Next steps after downloading:
    python3 scripts/serve_local.py   # serves style.json on port 8080
    .\\build\\...\\poc_map.exe
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent
TILES_DIR  = SCRIPT_DIR.parent / "tiles"

# Protomaps weekly planet build — update date if you get 404
# Check latest at: https://maps.protomaps.com/builds/
PLANET_URL = "https://build.protomaps.com/20260331.pmtiles"

# bbox format: "min_lon,min_lat,max_lon,max_lat" (EPSG:4326)
COUNTRIES: dict[str, dict] = {
    "poland":      {"bbox": "14.07,49.00,24.15,54.84", "center": [52.23, 21.01], "name": "Poland"},
    "germany":     {"bbox": "5.87,47.27,15.04,55.06",  "center": [51.16, 10.45], "name": "Germany"},
    "france":      {"bbox": "-5.14,41.33,9.56,51.09",  "center": [46.23,  2.21], "name": "France"},
    "czechia":     {"bbox": "12.09,48.55,18.86,51.06", "center": [49.82, 15.47], "name": "Czechia"},
    "ukraine":     {"bbox": "22.14,44.39,40.23,52.38", "center": [48.38, 31.17], "name": "Ukraine"},
    "netherlands": {"bbox": "3.31,50.80,7.09,53.51",   "center": [52.13,  5.29], "name": "Netherlands"},
    "austria":     {"bbox": "9.53,46.37,17.16,49.02",  "center": [47.52, 14.55], "name": "Austria"},
    "sweden":      {"bbox": "10.96,55.34,24.17,69.07", "center": [59.33, 18.07], "name": "Sweden"},
    "norway":      {"bbox": "4.09,57.81,31.29,71.20",  "center": [60.47,  8.47], "name": "Norway"},
    "spain":       {"bbox": "-9.39,35.95,3.34,43.97",  "center": [40.42, -3.70], "name": "Spain"},
    "italy":       {"bbox": "6.63,35.49,18.52,47.09",  "center": [41.90, 12.49], "name": "Italy"},
}

# Size estimates in GB (approximate — actual depends on data density and Protomaps compression).
# Measured: Poland zoom 16 ≈ 4 GB actual vs 9 GB estimated previously.
SIZE_ESTIMATES: dict[str, dict[int, float]] = {
    "poland":      {14: 0.7, 16: 4,   18: 20},
    "germany":     {14: 1.5, 16: 8,   18: 40},
    "france":      {14: 1.2, 16: 7,   18: 35},
    "czechia":     {14: 0.3, 16: 1.5, 18: 8},
    "ukraine":     {14: 1.0, 16: 5,   18: 25},
    "netherlands": {14: 0.2, 16: 1.2, 18: 6},
    "austria":     {14: 0.2, 16: 1.2, 18: 6},
    "sweden":      {14: 0.7, 16: 4,   18: 20},
    "norway":      {14: 0.6, 16: 3.5, 18: 18},
    "spain":       {14: 1.0, 16: 5,   18: 25},
    "italy":       {14: 1.0, 16: 5,   18: 25},
}


PMTILES_VERSION = "1.30.1"
PMTILES_RELEASES = {
    ("Windows", "AMD64"):  f"https://github.com/protomaps/go-pmtiles/releases/download/v{PMTILES_VERSION}/go-pmtiles_{PMTILES_VERSION}_Windows_x86_64.zip",
    ("Windows", "ARM64"):  f"https://github.com/protomaps/go-pmtiles/releases/download/v{PMTILES_VERSION}/go-pmtiles_{PMTILES_VERSION}_Windows_arm64.zip",
    ("Linux",   "x86_64"): f"https://github.com/protomaps/go-pmtiles/releases/download/v{PMTILES_VERSION}/go-pmtiles_{PMTILES_VERSION}_Linux_x86_64.zip",
    ("Linux",   "aarch64"):f"https://github.com/protomaps/go-pmtiles/releases/download/v{PMTILES_VERSION}/go-pmtiles_{PMTILES_VERSION}_Linux_arm64.zip",
    ("Darwin",  "x86_64"): f"https://github.com/protomaps/go-pmtiles/releases/download/v{PMTILES_VERSION}/go-pmtiles_{PMTILES_VERSION}_Darwin_x86_64.zip",
    ("Darwin",  "arm64"):  f"https://github.com/protomaps/go-pmtiles/releases/download/v{PMTILES_VERSION}/go-pmtiles_{PMTILES_VERSION}_Darwin_arm64.zip",
}


def find_pmtiles_cli() -> Optional[str]:
    """Find pmtiles binary next to this script or in PATH."""
    for candidate in [SCRIPT_DIR / "pmtiles.exe", SCRIPT_DIR / "pmtiles"]:
        if candidate.exists():
            return str(candidate)
    return shutil.which("pmtiles")


def download_pmtiles_cli() -> str:
    """Auto-download pmtiles binary for the current platform into scripts/."""
    system   = platform.system()                  # Windows / Linux / Darwin
    machine  = platform.machine()                 # AMD64 / x86_64 / aarch64 / arm64

    # Normalise machine name
    machine_norm = {"AMD64": "AMD64", "x86_64": "x86_64", "aarch64": "aarch64", "ARM64": "ARM64", "arm64": "arm64"}.get(machine, machine)

    url = PMTILES_RELEASES.get((system, machine_norm))
    if not url:
        print(f"ERROR: No prebuilt pmtiles binary for {system}/{machine}.")
        print(f"  Download manually: https://github.com/protomaps/go-pmtiles/releases")
        sys.exit(1)

    exe_name = "pmtiles.exe" if system == "Windows" else "pmtiles"
    dest = SCRIPT_DIR / exe_name

    print(f"  Downloading pmtiles v{PMTILES_VERSION} for {system}/{machine_norm}...")
    print(f"  From: {url}")

    def _progress(count: int, block: int, total: int) -> None:
        pct = min(100, count * block * 100 // total) if total > 0 else 0
        print(f"\r  Progress: {pct}%", end="", flush=True)

    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "pmtiles.zip"
        urllib.request.urlretrieve(url, zip_path, reporthook=_progress)
        print()  # newline after progress

        with zipfile.ZipFile(zip_path) as zf:
            # Find the pmtiles binary inside the zip
            names = zf.namelist()
            binary = next((n for n in names if n.endswith(exe_name) or n == "pmtiles"), None)
            if not binary:
                print(f"ERROR: Could not find '{exe_name}' inside the zip. Contents: {names}")
                sys.exit(1)
            zf.extract(binary, tmp)
            extracted = Path(tmp) / binary
            shutil.copy2(extracted, dest)

    if system != "Windows":
        dest.chmod(0o755)

    print(f"  Saved to: {dest}")
    return str(dest)


def run_cmd(cmd: list[str]) -> None:
    """Run a subprocess, stream output live, raise on non-zero exit."""
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    subprocess.run(cmd, check=True)


def bbox_center(bbox: str) -> list[float]:
    min_lon, min_lat, max_lon, max_lat = (float(x) for x in bbox.split(","))
    return [(min_lat + max_lat) / 2, (min_lon + max_lon) / 2]


def write_vector_style(pmtiles_path: Path, center: list[float], max_zoom: int,
                       port: int = 8080) -> Path:
    """
    Generate tiles/vector-style.json.
    Uses standard {z}/{x}/{y} tile URL — same pattern as raster tiles that worked.
    serve_local.py reads each tile from the PMTiles archive on demand.
    """
    archive_name = pmtiles_path.stem          # e.g. "poland"
    mbtiles_uri  = f"http://localhost:{port}/{archive_name}/{{z}}/{{x}}/{{y}}"

    style: dict = {
        "version": 8,
        "name": "Offline Vector (OpenMapTiles schema)",
        "center": [center[1], center[0], 10],        # [lon, lat, zoom]
        # NOTE: glyphs are fetched from the internet for PoC.
        # Replace with local path once download_fonts.py is implemented.
        "glyphs": "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
        "sources": {
            "openmaptiles": {
                "type": "vector",
                "tiles": [mbtiles_uri],
                "maxzoom": max_zoom,
                "attribution": "© <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap contributors</a>",
            }
        },
        "layers": _build_layers(),
    }

    out = TILES_DIR / "vector-style.json"
    out.write_text(json.dumps(style, indent=2, ensure_ascii=False))
    return out


def _build_layers() -> list[dict]:
    """
    Layer set for Protomaps v4 basemap schema.
    Source layers: earth, water, landuse, roads, boundaries, places, pois
    Road kind values: highway, major_road, medium_road, minor_road, path
    """
    return [
        # ── Background ────────────────────────────────────────────────────────
        {
            "id": "background",
            "type": "background",
            "paint": {"background-color": "#f0ebe3"},
        },

        # ── Land (earth layer = landmass polygon) ─────────────────────────────
        {
            "id": "earth",
            "type": "fill",
            "source": "openmaptiles",
            "source-layer": "earth",
            "paint": {"fill-color": "#f0ebe3"},
        },

        # ── Water ─────────────────────────────────────────────────────────────
        {
            "id": "water",
            "type": "fill",
            "source": "openmaptiles",
            "source-layer": "water",
            "paint": {"fill-color": "#a8c8f0"},
        },

        # ── Landuse ───────────────────────────────────────────────────────────
        {
            "id": "landuse-green",
            "type": "fill",
            "source": "openmaptiles",
            "source-layer": "landuse",
            "filter": ["in", ["get", "kind"], ["literal", ["park", "grass", "garden", "playground", "national_park", "nature_reserve"]]],
            "paint": {"fill-color": "#d8f0c8"},
        },
        {
            "id": "landuse-forest",
            "type": "fill",
            "source": "openmaptiles",
            "source-layer": "landuse",
            "filter": ["in", ["get", "kind"], ["literal", ["forest", "wood"]]],
            "paint": {"fill-color": "#c0dca8"},
        },
        {
            "id": "landuse-industrial",
            "type": "fill",
            "source": "openmaptiles",
            "source-layer": "landuse",
            "filter": ["==", ["get", "kind"], "industrial"],
            "paint": {"fill-color": "#e8ddd0"},
        },

        # ── Roads — casing (outline) ──────────────────────────────────────────
        {
            "id": "road-highway-casing",
            "type": "line",
            "source": "openmaptiles",
            "source-layer": "roads",
            "filter": ["==", ["get", "kind"], "highway"],
            "paint": {
                "line-color": "#c87030",
                "line-width": ["interpolate", ["linear"], ["zoom"], 6, 3, 14, 10],
                "line-cap": "round",
                "line-join": "round",
            },
        },
        {
            "id": "road-major-casing",
            "type": "line",
            "source": "openmaptiles",
            "source-layer": "roads",
            "filter": ["==", ["get", "kind"], "major_road"],
            "minzoom": 8,
            "paint": {
                "line-color": "#d0a060",
                "line-width": ["interpolate", ["linear"], ["zoom"], 8, 2, 14, 7],
                "line-cap": "round",
            },
        },

        # ── Roads — fill ──────────────────────────────────────────────────────
        {
            "id": "road-highway",
            "type": "line",
            "source": "openmaptiles",
            "source-layer": "roads",
            "filter": ["==", ["get", "kind"], "highway"],
            "paint": {
                "line-color": "#f09050",
                "line-width": ["interpolate", ["linear"], ["zoom"], 6, 1.5, 14, 7],
                "line-cap": "round",
                "line-join": "round",
            },
        },
        {
            "id": "road-major",
            "type": "line",
            "source": "openmaptiles",
            "source-layer": "roads",
            "filter": ["==", ["get", "kind"], "major_road"],
            "minzoom": 8,
            "paint": {
                "line-color": "#ffd080",
                "line-width": ["interpolate", ["linear"], ["zoom"], 8, 1, 14, 5],
                "line-cap": "round",
            },
        },
        {
            "id": "road-medium",
            "type": "line",
            "source": "openmaptiles",
            "source-layer": "roads",
            "filter": ["==", ["get", "kind"], "medium_road"],
            "minzoom": 10,
            "paint": {
                "line-color": "#ffffff",
                "line-width": ["interpolate", ["linear"], ["zoom"], 10, 0.5, 14, 3.5],
                "line-cap": "round",
            },
        },
        {
            "id": "road-minor",
            "type": "line",
            "source": "openmaptiles",
            "source-layer": "roads",
            "filter": ["in", ["get", "kind"], ["literal", ["minor_road", "path"]]],
            "minzoom": 13,
            "paint": {
                "line-color": "#ffffff",
                "line-width": 1,
            },
        },

        # ── Boundaries ────────────────────────────────────────────────────────
        {
            "id": "boundary-country",
            "type": "line",
            "source": "openmaptiles",
            "source-layer": "boundaries",
            "filter": ["==", ["get", "kind"], "country"],
            "paint": {
                "line-color": "#8080c0",
                "line-width": 1.5,
                "line-dasharray": [4, 2],
            },
        },
        {
            "id": "boundary-region",
            "type": "line",
            "source": "openmaptiles",
            "source-layer": "boundaries",
            "filter": ["==", ["get", "kind"], "region"],
            "minzoom": 6,
            "paint": {
                "line-color": "#b0b0d0",
                "line-width": 0.8,
                "line-dasharray": [3, 2],
            },
        },

        # ── Labels ────────────────────────────────────────────────────────────
        {
            "id": "label-city",
            "type": "symbol",
            "source": "openmaptiles",
            "source-layer": "places",
            "filter": ["in", ["get", "kind"], ["literal", ["city", "town"]]],
            "layout": {
                "text-field": ["get", "name"],
                "text-font": ["Noto Sans Regular"],
                "text-size": ["interpolate", ["linear"], ["zoom"], 6, 10, 14, 14],
                "text-max-width": 8,
                "text-anchor": "center",
            },
            "paint": {
                "text-color": "#333333",
                "text-halo-color": "#ffffff",
                "text-halo-width": 1.5,
            },
        },
        {
            "id": "label-village",
            "type": "symbol",
            "source": "openmaptiles",
            "source-layer": "places",
            "filter": ["in", ["get", "kind"], ["literal", ["village", "suburb", "hamlet"]]],
            "minzoom": 11,
            "layout": {
                "text-field": ["get", "name"],
                "text-font": ["Noto Sans Regular"],
                "text-size": 11,
                "text-max-width": 8,
            },
            "paint": {
                "text-color": "#555555",
                "text-halo-color": "#ffffff",
                "text-halo-width": 1.5,
            },
        },
        {
            "id": "label-road",
            "type": "symbol",
            "source": "openmaptiles",
            "source-layer": "roads",
            "filter": ["has", "name"],
            "minzoom": 14,
            "layout": {
                "text-field": ["get", "name"],
                "text-font": ["Noto Sans Regular"],
                "text-size": 11,
                "symbol-placement": "line",
                "text-max-angle": 30,
            },
            "paint": {
                "text-color": "#555555",
                "text-halo-color": "#ffffff",
                "text-halo-width": 1,
            },
        },
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download vector tiles (MBTiles) for offline MapLibre use.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--country", default="poland", metavar="NAME",
        help="Country to download (default: poland). Use --list-countries to see all options.",
    )
    group.add_argument(
        "--bbox", metavar="'MIN_LON,MIN_LAT,MAX_LON,MAX_LAT'",
        help="Custom bounding box, e.g. '14.07,49.00,24.15,54.84'",
    )
    parser.add_argument(
        "--max-zoom", type=int, default=14,
        help="Maximum zoom level (default: 14). WARNING: 16 = ~8-15 GB for Poland; 18 = ~40-60 GB",
    )
    parser.add_argument(
        "--list-countries", action="store_true",
        help="Print available country names with bbox and size estimates, then exit.",
    )
    parser.add_argument(
        "--source", default=PLANET_URL, metavar="URL",
        help=f"Protomaps planet PMTiles URL (default: {PLANET_URL})",
    )
    args = parser.parse_args()

    if args.list_countries:
        print()
        print("Available countries (--country NAME):")
        print()
        col = max(len(k) for k in COUNTRIES) + 2
        for key, info in COUNTRIES.items():
            est = SIZE_ESTIMATES.get(key, {})
            sizes = "  ".join(f"z{z}≈{est[z]}GB" for z in sorted(est)) if est else "unknown"
            print(f"  {key:<{col}} bbox: {info['bbox']}")
            print(f"  {'':>{col}} size: {sizes}")
            print()
        return

    # ── Resolve country / custom bbox ─────────────────────────────────────────
    if args.bbox:
        bbox         = args.bbox.strip()
        country_key  = "custom"
        center       = bbox_center(bbox)
        country_name = f"custom region ({bbox})"
        size_hint    = None
    else:
        country_key = args.country.lower()
        if country_key not in COUNTRIES:
            print(f"Unknown country '{args.country}'. Use --list-countries to see options.")
            sys.exit(1)
        info         = COUNTRIES[country_key]
        bbox         = info["bbox"]
        center       = info["center"]
        country_name = info["name"]
        size_hint    = SIZE_ESTIMATES.get(country_key, {}).get(args.max_zoom)

    TILES_DIR.mkdir(exist_ok=True)

    pmtiles_out = TILES_DIR / f"{country_key}.pmtiles"

    # ── Check pmtiles CLI (auto-download if missing) ──────────────────────────
    pmtiles_bin = find_pmtiles_cli()
    if not pmtiles_bin:
        print()
        print("  'pmtiles' CLI not found — downloading automatically...")
        pmtiles_bin = download_pmtiles_cli()
        print()

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("=" * 62)
    print("  Vector Tile Downloader  (Protomaps -> MBTiles)")
    print("=" * 62)
    print(f"  Country  : {country_name}")
    print(f"  BBox     : {bbox}")
    print(f"  Max zoom : {args.max_zoom}")
    print(f"  Output   : {pmtiles_out}")
    print(f"  Source   : {args.source}")
    print()
    if size_hint:
        print(f"  WARNING: estimated size ~{size_hint} GB")
    if args.max_zoom >= 16:
        print(f"  WARNING: zoom {args.max_zoom} produces large files and takes a long time.")
        print(f"           Consider --max-zoom 14 for an initial test.")
    print()

    if pmtiles_out.exists():
        size_mb = pmtiles_out.stat().st_size / 1024 / 1024
        print(f"  PMTiles already exists ({size_mb:.0f} MB). Skipping download.")
        print(f"  Delete '{pmtiles_out.name}' to re-download.")
        print()
    else:
        answer = input("  Continue? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted.")
            return
        print()

        print("  Extracting region from Protomaps planet...")
        print("  (streams over HTTP range requests — fast, no full planet download)")
        print()
        run_cmd([
            pmtiles_bin, "extract",
            args.source,
            str(pmtiles_out),
            f"--bbox={bbox}",
            f"--maxzoom={args.max_zoom}",
        ])
        print()

    # ── Show file size ────────────────────────────────────────────────────────
    if pmtiles_out.exists():
        size_mb = pmtiles_out.stat().st_size / 1024 / 1024
        print(f"  PMTiles size : {size_mb:.0f} MB  ({size_mb / 1024:.2f} GB)")

    # ── Generate style.json ───────────────────────────────────────────────────
    style_path = write_vector_style(pmtiles_out, center, args.max_zoom)
    print(f"  Style        : {style_path}")
    print()
    print("=" * 62)
    print("  Done! Next steps:")
    print()
    print("  1. Start style server (for style.json):")
    print(f"       python {SCRIPT_DIR}\\serve_local.py")
    print()
    print("  2. Run the PoC:")
    print(f"       .\\build\\Desktop_Qt_6_9_2_MinGW_64_bit-Debug\\poc_map.exe")
    print()
    print("  NOTE: City/road labels require internet (CDN glyphs).")
    print("  The map tiles themselves are fully offline via mbtiles://")
    print("=" * 62)
    print()


if __name__ == "__main__":
    main()
