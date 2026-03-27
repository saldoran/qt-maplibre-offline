# Build maplibre-native-qt and install it locally (Windows, PowerShell).
# After running this script, build the PoC with:
#   cmake -B build -DQMapLibre_DIR="<PoC_Map>\maplibre-install\lib\cmake\QMapLibre"
#   cmake --build build --config Release
#
# Prerequisites:
#   - Visual Studio 2019 or 2022 (with "Desktop development with C++" workload)
#   - Qt 6.5+ (MSVC build) installed via Qt Installer
#   - CMake 3.21+ (can be bundled with Visual Studio or installed separately)
#   - Git
#   - Ninja (optional but faster: winget install Ninja-build.Ninja)
#
# Make sure Qt's cmake directory is in CMAKE_PREFIX_PATH or Qt6_DIR is set.
# Example: $env:Qt6_DIR = "C:\Qt\6.6.0\msvc2019_64\lib\cmake\Qt6"

param(
    [string]$QtDir = $env:Qt6_DIR
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir   = Split-Path -Parent $ScriptDir

$SourceDir  = Join-Path $RootDir "maplibre-native-qt"
$BuildDir   = Join-Path $RootDir "maplibre-build"
$InstallDir = Join-Path $RootDir "maplibre-install"

Write-Host "========================================"
Write-Host "  Building maplibre-native-qt"
Write-Host "  Source:  $SourceDir"
Write-Host "  Install: $InstallDir"
Write-Host "========================================"
Write-Host ""

# ── Clone / update ────────────────────────────────────────────────────────
if (-not (Test-Path (Join-Path $SourceDir ".git"))) {
    Write-Host ">>> Cloning maplibre-native-qt (with submodules — may take a while)..."
    git clone --recurse-submodules --depth 1 `
        https://github.com/maplibre/maplibre-native-qt.git `
        $SourceDir
} else {
    Write-Host ">>> Source exists, updating submodules..."
    Push-Location $SourceDir
    git submodule update --init --recursive
    Pop-Location
}

# ── Configure ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host ">>> Configuring..."

$cmakeArgs = @(
    "-B", $BuildDir,
    "-S", $SourceDir,
    "-DCMAKE_BUILD_TYPE=Release",
    "-DCMAKE_INSTALL_PREFIX=$InstallDir",
    "-DMLN_QT_WITH_LOCATION=ON",
    "-DMLN_QT_WITH_WIDGETS=OFF",
    "-DMLN_QT_WITH_QUICK_PLUGIN=ON",
    "-DQT_PACKAGE_NAME=Qt6"
)

if ($QtDir) {
    $cmakeArgs += "-DQt6_DIR=$QtDir"
    Write-Host "    Qt6_DIR: $QtDir"
}

# Use Ninja if available
if (Get-Command ninja -ErrorAction SilentlyContinue) {
    $cmakeArgs += "-G", "Ninja"
    Write-Host "    Generator: Ninja"
}

& cmake @cmakeArgs

# ── Build ──────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host ">>> Building Release (this takes ~15-40 min on first run)..."
cmake --build $BuildDir --config Release --parallel

# ── Install ────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host ">>> Installing to $InstallDir ..."
cmake --install $BuildDir --config Release

# ── Summary ───────────────────────────────────────────────────────────────
$QMapLibreDir = Join-Path $InstallDir "lib\cmake\QMapLibre"
Write-Host ""
Write-Host "========================================"
Write-Host "  Build complete!"
Write-Host "========================================"
Write-Host ""
Write-Host "  QMapLibre_DIR = $QMapLibreDir"
Write-Host ""
Write-Host "  Next: build the PoC"
Write-Host "    cd $RootDir"
Write-Host "    cmake -B build -DQMapLibre_DIR=`"$QMapLibreDir`""
Write-Host "    cmake --build build --config Release"
Write-Host ""
