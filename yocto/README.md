# Yocto layer: meta-poc-map

Layer providing a `maplibre-native-qt` recipe for Yocto **scarthgap**
(5.0 LTS, Qt 6.6.x from `meta-qt6`).

## Structure

```
meta-poc-map/
├── conf/layer.conf
└── recipes-graphics/maplibre-native-qt/
    └── maplibre-native-qt_4.0.0.bb
```

## Required layers

Add to `bblayers.conf`:

```
BBLAYERS += " \
    .../poky/meta \
    .../poky/meta-poky \
    .../meta-openembedded/meta-oe \
    .../meta-qt6 \
    .../meta-poc-map \
"
```

Both `meta-qt6` and `meta-openembedded` must be on the **scarthgap** branch.

## Before the first build

The recipe builds out of the box, but two fields must be pinned:

### 1. LIC_FILES_CHKSUM

The first run will fail on the license check. The log will print the correct
md5 — copy it into the recipe:

```
bitbake maplibre-native-qt
# ERROR: ... LIC_FILES_CHKSUM mismatch ... md5=abcdef...
```

Replace the `0000...` placeholder with the real value.

### 2. SRCREV

`AUTOREV` is convenient for experiments, but for reproducible builds pin a
specific commit:

```bash
git ls-remote https://github.com/maplibre/maplibre-native-qt.git refs/heads/main
```

Paste the hash into `SRCREV_mlnqt`.

## Image requirements

In `local.conf` or the image recipe:

```
DISTRO_FEATURES:append = " opengl"
IMAGE_INSTALL:append = " \
    maplibre-native-qt \
    maplibre-native-qt-qml \
    maplibre-native-qt-geoservices \
    qtdeclarative-qmlplugins \
    qtlocation-qmlplugins \
"
```

A working GL driver is required (vendor GPU stack, or `mesa` with `llvmpipe`
as a software fallback).

## Building

```bash
source poky/oe-init-build-env
bitbake maplibre-native-qt
```

First run takes 20-40 minutes and pulls ~500 MB of submodules (mapbox-base,
earcut, protozero, wagyu, geometry.hpp, vector-tile, etc.). `gitsm://` is
mandatory.

## Post-build verification

```bash
oe-pkgdata-util list-pkg-files maplibre-native-qt
oe-pkgdata-util list-pkg-files maplibre-native-qt-qml
```

The `-qml` package must contain `qmldir`. Without it, the QML runtime will
not register the types and `import MapLibre 3.0` will fail at runtime on
the target.

## What else is needed to run the PoC on device

This layer builds **only** `maplibre-native-qt`. To run the full PoC on a
target image you also need:

- A recipe for the app itself (`poc-map.bb` with `DEPENDS += "maplibre-native-qt"`)
- Tiles (`tiles/*.pmtiles`) — either as a separate data recipe or mounted
  from an external partition
- Offline glyphs (the PoC currently fetches them from `demotiles.maplibre.org`)

## Known pitfalls

- **`gitsm://` is mandatory** — with plain `git://` the submodules are not
  fetched and configure fails with "mapbox-base not found"
- **`icu` in DEPENDS** — without it text shaping breaks and map labels do
  not render
- **`qtshadertools-native`** — required at build time for Qt Quick shader
  compilation
- **`OE_QMAKE_PATH_QML` / `OE_QMAKE_PATH_PLUGINS`** — these are exported by
  the `qt6-cmake` class. If they are unset, update `meta-qt6` to
  scarthgap-tip
