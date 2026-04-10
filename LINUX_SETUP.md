# Running on Linux

## Prerequisites

```bash
sudo apt install build-essential cmake qt6-base-dev qt6-declarative-dev \
  qt6-positioning-dev qt6-location-dev libegl1-mesa libgl1-mesa-dri zlib1g-dev
```

## Build QMapLibre

```bash
bash scripts/build_maplibre_qt.sh
```

## Build the PoC

```bash
cmake -B build -DQMapLibre_DIR="maplibre-install/lib/cmake/QMapLibre"
cmake --build build
```

## Run

```bash
# Set plugin paths (adjust maplibre-install location if needed)
export QT_PLUGIN_PATH="$(pwd)/maplibre-install/plugins"
export QML_IMPORT_PATH="$(pwd)/maplibre-install/qml"

# For VMs without GPU acceleration:
export LIBGL_ALWAYS_SOFTWARE=1

./build/poc_map
```

## Troubleshooting

| Error | Fix |
|-------|-----|
| `geoservices provider is not supported` | Set `QT_PLUGIN_PATH` to `maplibre-install/plugins` |
| `Map error` / blank screen | Set `QML_IMPORT_PATH` to `maplibre-install/qml` |
| `libEGL: failed to get driver name` | `export LIBGL_ALWAYS_SOFTWARE=1` or enable 3D acceleration in VM settings |
| `MESA: error: ZINK` | Same as above — Mesa can't find a GPU |
