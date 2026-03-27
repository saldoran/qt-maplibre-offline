#!/usr/bin/env bash
# Build maplibre-native-qt and install it locally.
# After running this script, build the PoC with:
#   cmake -B build -DQMapLibre_DIR="$(pwd)/maplibre-install/lib/cmake/QMapLibre"
#   cmake --build build
#
# Prerequisites (Debian/Ubuntu):
#   sudo apt-get install -y cmake ninja-build git \
#       libgl1-mesa-dev libcurl4-openssl-dev libssl-dev \
#       pkg-config ccache
#
# Prerequisites (Fedora/RHEL):
#   sudo dnf install -y cmake ninja-build git \
#       mesa-libGL-devel libcurl-devel openssl-devel pkg-config ccache

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR/.."

SOURCE_DIR="$ROOT_DIR/maplibre-native-qt"
BUILD_DIR="$ROOT_DIR/maplibre-build"
INSTALL_DIR="$ROOT_DIR/maplibre-install"

# ── Parallel jobs ─────────────────────────────────────────────────────────
JOBS=${JOBS:-$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)}

echo "========================================"
echo "  Building maplibre-native-qt"
echo "  Source:  $SOURCE_DIR"
echo "  Install: $INSTALL_DIR"
echo "  Jobs:    $JOBS"
echo "========================================"
echo ""

# ── Clone / update ────────────────────────────────────────────────────────
if [ ! -d "$SOURCE_DIR/.git" ]; then
    echo ">>> Cloning maplibre-native-qt (with submodules — may take a while)..."
    git clone --recurse-submodules \
        --depth 1 \
        https://github.com/maplibre/maplibre-native-qt.git \
        "$SOURCE_DIR"
else
    echo ">>> Source exists, updating submodules..."
    cd "$SOURCE_DIR"
    git submodule update --init --recursive
    cd -
fi

# ── Configure ─────────────────────────────────────────────────────────────
echo ""
echo ">>> Configuring..."
cmake -B "$BUILD_DIR" \
    -S "$SOURCE_DIR" \
    -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="$INSTALL_DIR" \
    -DMLN_QT_WITH_LOCATION=ON \
    -DMLN_QT_WITH_WIDGETS=OFF \
    -DMLN_QT_WITH_QUICK_PLUGIN=ON \
    -DQT_PACKAGE_NAME=Qt6 \
    ${CCACHE_PROGRAM:+-DCMAKE_C_COMPILER_LAUNCHER=ccache} \
    ${CCACHE_PROGRAM:+-DCMAKE_CXX_COMPILER_LAUNCHER=ccache}

# ── Build ──────────────────────────────────────────────────────────────────
echo ""
echo ">>> Building (this takes ~10-30 min on first run)..."
cmake --build "$BUILD_DIR" --parallel "$JOBS"

# ── Install ────────────────────────────────────────────────────────────────
echo ""
echo ">>> Installing to $INSTALL_DIR ..."
cmake --install "$BUILD_DIR"

# ── Summary ───────────────────────────────────────────────────────────────
QMAPLIBRE_CMAKE="$INSTALL_DIR/lib/cmake/QMapLibre"
echo ""
echo "========================================"
echo "  Build complete!"
echo "========================================"
echo ""
echo "  QMapLibre_DIR = $QMAPLIBRE_CMAKE"
echo ""
echo "  Next: build the PoC"
echo "    cd $(realpath "$ROOT_DIR")"
echo "    cmake -B build -DQMapLibre_DIR=\"$QMAPLIBRE_CMAKE\""
echo "    cmake --build build"
echo ""
