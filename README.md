## What this is

A minimal Qt Quick + MapLibre Native PoC that renders an interactive 2.5D vector map with pan/zoom/rotation/pitch and dark mode. Fully offline: vector tiles (PMTiles) are served by an embedded C++ HTTP server (QTcpServer), no external processes or internet required at runtime (except for font glyphs in the current PoC).

**Stack:** C++17, Qt 6.5+, QML, MapLibre Native for Qt (`maplibre-native-qt` v4), CMake 3.21+, zlib, Python 3.8+ (tile download script only).

## Build

### Prerequisites

- **Qt 6.5+** with modules: Core, Gui, Quick, Location, Positioning, Network
- **CMake 3.21+**
- **C++17 compiler** (MinGW, GCC, Clang)
- **zlib** (bundled with MinGW and most Linux distros)
- **Windows only:** enable long paths for git (maplibre submodules have deep paths):
  ```bash
  git config --global core.longpaths true
  ```

### Build MapLibre (one-time, ~15-40 min)

```powershell
# Windows (PowerShell):
.\scripts\build_maplibre_qt.ps1 -QtDir "C:\Qt\6.9.2\mingw_64\lib\cmake\Qt6"

# Linux/macOS:
bash scripts/build_maplibre_qt.sh
```

This clones, builds and installs `maplibre-native-qt` into `maplibre-install/`.

### Build the PoC

```bash
# Windows MinGW:
cmake -B build -G "MinGW Makefiles" \
  -DCMAKE_PREFIX_PATH="C:\Qt\6.9.2\mingw_64" \
  -DQMapLibre_DIR="maplibre-install/lib/cmake/QMapLibre"
cmake --build build

# Linux/macOS:
cmake -B build -DQMapLibre_DIR="maplibre-install/lib/cmake/QMapLibre"
cmake --build build
```

### Run

```bash
# Run from the project root (so the app finds tiles/ directory):
# Windows:
.\build\poc_map.exe
# Linux:
./build/poc_map
```

The app auto-discovers `tiles/*.pmtiles`, starts an embedded HTTP tile server on a random port, and passes the style URL to MapLibre. No external tile server needed.

The app searches for the `tiles/` directory in: `./tiles`, `../tiles`, `../../tiles` (relative to CWD).

## Offline vector tiles

### Download tiles for a country

```bash
# Poland, zoom 0-14 (~700 MB, ~2 min)
python scripts/download_tiles.py --country poland --max-zoom 14

# Poland, zoom 0-16 (~3.7 GB, ~3 min) — current setup
python scripts/download_tiles.py --country poland --max-zoom 16

# List all available countries with size estimates
python scripts/download_tiles.py --list-countries

# Custom bounding box
python scripts/download_tiles.py --bbox "14.07,49.00,24.15,54.84" --max-zoom 14
```

The script auto-downloads the `pmtiles` CLI if not found. It extracts the region from the Protomaps weekly planet build via HTTP range requests (no full planet download).

Output: `tiles/<country>.pmtiles` + `tiles/vector-style.json`.

### Adding a new country

Add an entry to the `COUNTRIES` dict in `download_tiles.py` with `bbox` (min_lon,min_lat,max_lon,max_lat) and `center` [lat,lon]. Bboxes can be found at https://boundingbox.klokantech.com/ (CSV format).

### Size reference (measured/estimated)

| Country     | z14    | z16    | z18     |
|-------------|--------|--------|---------|
| Poland      | 0.7 GB | 3.7 GB | ~20 GB  |
| Germany     | 1.5 GB | ~8 GB  | ~40 GB  |
| Czechia     | 0.3 GB | 1.5 GB | ~8 GB   |
| Netherlands | 0.2 GB | 1.2 GB | ~6 GB   |

### Tile schema

Tiles use **Protomaps v4 basemap** schema (NOT OpenMapTiles). Key differences:
- Source layers: `earth`, `water`, `landuse`, `roads`, `boundaries`, `places`, `pois`
- Roads use `kind`: `highway`, `major_road`, `medium_road`, `minor_road`, `path`
- Places use `kind`: `city`, `town`, `village`, `suburb`, `hamlet`
- Boundaries use `kind`: `country`, `region`
- No `building` layer at low zooms; `landuse` uses `kind` not `class`

## Architecture

```
main.cpp
  Forces OpenGL (QSGRendererInterface::OpenGL) on non-Apple
  Auto-discovers tiles/ directory, starts embedded TileServer
  Exposes initialStyleUrl (dynamic port) + isOfflineMode to QML
  Falls back to online demo tiles if no .pmtiles found

src/pmtiles_reader.h/.cpp
  PMTiles v3 binary format reader:
    127-byte header parsing (offsets, compression, zoom range)
    Hilbert curve tile ID: zxyToTileId(z,x,y) via hilbertXy2d()
    Varint-encoded directory parsing (delta-coded tile IDs, contiguous offsets)
    Two-level lookup: root directory -> leaf directory -> tile data
    gzip decompression via zlib inflateInit2(MAX_WBITS + 16)

src/tile_server.h/.cpp
  QTcpServer-based HTTP server (async, main thread):
    GET /<archive>/<z>/<x>/<y> -> PMTiles reader -> raw PBF
    GET /*.json -> style file with localhost:PORT auto-substitution
    Per-socket buffering for partial HTTP reads
    CORS headers, keep-alive connections
    Port 0 = OS auto-assignment

qml/main.qml
  Plugin { name: "maplibre" } with maplibre.map.styles -> vector-style.json
  MapView with zoom/rotate/tilt controls
  MapLibre.Location 4.0: Style { LayerParameter { paint: ... } }
    -> Runtime dark mode via reactive paint property overrides
    -> No plugin recreation, no OpenGL teardown
  Screen-space position marker + status overlay

scripts/serve_local.py        (legacy — no longer needed at runtime)
scripts/download_tiles.py     (tile download, still needed)
```

**QMapLibre resolution (CMakeLists.txt):**
External install via `-DQMapLibre_DIR=...` (run the build script first).

On Windows, post-build copies `QMapLibre*.dll`, `geoservices` plugin, `MapLibre`+`MapLibre.Location` QML modules (with `qmldir`), and runs `windeployqt`.

## Dark mode

Implemented via `MapLibre.Location 4.0` QML API — `LayerParameter.paint` is a reactive `QJsonObject`. When `darkMode` property flips, the binding re-evaluates, triggering:

```
paint binding -> setPaint() -> paintUpdated -> updateNotify() -> updated()
  -> onStyleParameterUpdated -> map->setPaintProperty() -> repaint
```

No Loader/Timer/plugin recreation. Colors defined inline in `qml/main.qml`.

## Key limitations and notes for Yocto

- **OpenGL required**: MapLibre Native renders via OpenGL. The Yocto image needs working OpenGL ES 2.0+ (Mesa, proprietary GPU driver, or software renderer like `llvmpipe`).
- **Qt modules needed**: `qtbase`, `qtdeclarative` (Quick/QML), `qtlocation`, `qtpositioning`. For dark mode: the `MapLibre.Location` QML module must be deployed alongside the app.
- **Font glyphs**: Labels currently fetch glyphs from `demotiles.maplibre.org` (online). For true offline, download glyph PBFs and serve locally or bundle them. See: https://github.com/openmaptiles/fonts
- **Tile server is embedded**: The C++ PMTiles reader + QTcpServer are built into the app. No Python or external server needed at runtime. Only `zlib` is required as an additional build dependency (bundled with MinGW and most Linux distros).
- **Max zoom**: Tiles go up to the `--max-zoom` used during download. Map zoom is capped at 16.9 in QML. No overzoom/upscale beyond tile data (MapLibre Native Qt limitation).
- **`pmtiles://` protocol**: MapLibre Native Qt does NOT support `pmtiles://` for local file access. Tiles are served over localhost HTTP by the embedded server.
- **Style URL**: Dynamically constructed at startup with the actual server port. No hardcoded port.
