# Build maplibre-native-qt and install locally (Windows, PowerShell).
# Usage:
#   .\scripts\build_maplibre_qt.ps1 -QtDir "C:\Qt\Qt6.9.2\6.9.2\mingw_64\lib\cmake\Qt6"
#
# After this script: build the PoC with:
#   cmake -B build -G "MinGW Makefiles" -DCMAKE_PREFIX_PATH=... -DQMapLibre_DIR=...
#   cmake --build build

param(
    [string]$QtDir = $env:Qt6_DIR,
    [string]$Generator = "MinGW Makefiles"
)

$ErrorActionPreference = "Stop"

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir    = Split-Path -Parent $ScriptDir
$SourceDir  = Join-Path $RootDir "maplibre-native-qt"
$BuildDir   = Join-Path $RootDir "maplibre-build"
$InstallDir = Join-Path $RootDir "maplibre-install"

Write-Host "Building maplibre-native-qt"
Write-Host "Source:  $SourceDir"
Write-Host "Install: $InstallDir"
Write-Host ""

# Clone if not present
if (-not (Test-Path (Join-Path $SourceDir ".git"))) {
    Write-Host "Cloning (this downloads ~500 MB, please wait)..."
    git clone --recurse-submodules --depth 1 https://github.com/maplibre/maplibre-native-qt.git $SourceDir
} else {
    Write-Host "Source already exists, skipping clone."
}

# Configure
Write-Host ""
Write-Host "Configuring..."

$cmakeArgs = @(
    "-B", $BuildDir,
    "-S", $SourceDir,
    "-G", $Generator,
    "-DCMAKE_BUILD_TYPE=Release",
    "-DCMAKE_INSTALL_PREFIX=$InstallDir",
    "-DMLN_QT_WITH_LOCATION=ON",
    "-DMLN_QT_WITH_WIDGETS=OFF",
    "-DMLN_QT_WITH_QUICK_PLUGIN=ON",
    "-DQT_PACKAGE_NAME=Qt6",
    "-DMLN_WITH_OPENGL=ON"
)

if ($QtDir) {
    # Derive CMAKE_PREFIX_PATH from Qt6_DIR (go up 3 levels: Qt6 -> cmake -> lib -> msvc/mingw dir)
    $QtPrefix = Split-Path (Split-Path (Split-Path $QtDir))
    $cmakeArgs += "-DQt6_DIR=$QtDir"
    $cmakeArgs += "-DCMAKE_PREFIX_PATH=$QtPrefix"
    Write-Host "Qt6_DIR:           $QtDir"
    Write-Host "CMAKE_PREFIX_PATH: $QtPrefix"
}

& cmake @cmakeArgs
if ($LASTEXITCODE -ne 0) { throw "cmake configure failed" }

# Build
Write-Host ""
Write-Host "Building (15-40 min first time)..."
$cores = (Get-CimInstance Win32_Processor).NumberOfLogicalProcessors
cmake --build $BuildDir --parallel $cores
if ($LASTEXITCODE -ne 0) { throw "cmake build failed" }

# Install
Write-Host ""
Write-Host "Installing..."
cmake --install $BuildDir
if ($LASTEXITCODE -ne 0) { throw "cmake install failed" }

$QMapLibreDir = Join-Path $InstallDir "lib\cmake\QMapLibre"
Write-Host ""
Write-Host "Done! QMapLibre_DIR = $QMapLibreDir"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  cmake -B build -G `"MinGW Makefiles`" -DCMAKE_PREFIX_PATH=C:\Qt\Qt6.9.2\6.9.2\mingw_64 -DQMapLibre_DIR=`"$QMapLibreDir`""
Write-Host "  cmake --build build"
