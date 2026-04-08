cmake_minimum_required(VERSION 3.21)
project(poc_map VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ── Qt 6 ────────────────────────────────────────────────────────────────────
find_package(Qt6 6.5 REQUIRED COMPONENTS Core Gui Quick Location Positioning Network)

# ── zlib (for PMTiles gzip decompression) ───────────────────────────────────
find_package(ZLIB QUIET)
if(NOT ZLIB_FOUND)
    # MinGW bundles zlib in sysroot; create an interface target for -lz
    add_library(ZLIB::ZLIB INTERFACE IMPORTED)
    set_target_properties(ZLIB::ZLIB PROPERTIES INTERFACE_LINK_LIBRARIES "z")
    message(STATUS "System zlib not found via find_package — falling back to -lz")
endif()
qt_standard_project_setup(REQUIRES 6.5)

# ── QMapLibre ────────────────────────────────────────────────────────────────
# Priority 1: externally installed (pass -DQMapLibre_DIR=.../lib/cmake/QMapLibre)
# Priority 2: maplibre-native-qt submodule in this directory
find_package(QMapLibre QUIET COMPONENTS Core Location)

if(NOT QMapLibre_FOUND)
    message(FATAL_ERROR
        "\n"
        "  QMapLibre not found. Build it first (one-time, ~15-40 min):\n"
        "\n"
        "  Windows (PowerShell):\n"
        "    .\\scripts\\build_maplibre_qt.ps1 -QtDir \"<Qt>/lib/cmake/Qt6\"\n"
        "\n"
        "  Linux / macOS:\n"
        "    bash scripts/build_maplibre_qt.sh\n"
        "\n"
        "  Then re-run cmake with:\n"
        "    -DQMapLibre_DIR=maplibre-install/lib/cmake/QMapLibre\n")
endif()

# ── Executable ───────────────────────────────────────────────────────────────
qt_add_executable(poc_map
    main.cpp
    src/pmtiles_reader.h
    src/pmtiles_reader.cpp
    src/tile_server.h
    src/tile_server.cpp
)

qt_add_qml_module(poc_map
    URI PocMap
    VERSION 1.0
    RESOURCE_PREFIX "/"
    QML_FILES
        qml/main.qml
)

set_target_properties(poc_map PROPERTIES
    WIN32_EXECUTABLE ON
    MACOSX_BUNDLE    ON
)

# ── Link ─────────────────────────────────────────────────────────────────────
target_include_directories(poc_map PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)

target_link_libraries(poc_map
    PRIVATE
        Qt6::Core
        Qt6::Gui
        Qt6::Quick
        Qt6::Location
        Qt6::Positioning
        Qt6::Network
        QMapLibre::Core
        QMapLibre::Location
        ZLIB::ZLIB
)

# Deploy MapLibre geoservices plugin + QML module alongside the binary
# (only available when QMapLibre was found via find_package, not from source)
if(QMapLibre_FOUND AND COMMAND qmaplibre_location_setup_plugins)
    qmaplibre_location_setup_plugins(poc_map)
endif()

# ── Windows: deploy DLLs and plugins next to the exe ────────────────────────
if(WIN32)
    # windeployqt copies all Qt DLLs and runtime dependencies automatically
    find_program(_windeployqt windeployqt
        HINTS "${Qt6_DIR}/../../../bin"
    )
    if(_windeployqt)
        add_custom_command(TARGET poc_map POST_BUILD
            COMMAND "${_windeployqt}"
                --no-translations
                --no-system-d3d-compiler
                --qmldir "${CMAKE_CURRENT_SOURCE_DIR}/qml"
                "$<TARGET_FILE:poc_map>"
            COMMENT "Running windeployqt"
        )
    endif()

    # Copy QMapLibre DLLs from external install (Priority 1 only)
    set(_mln_install "${CMAKE_CURRENT_SOURCE_DIR}/maplibre-install")
    if(EXISTS "${_mln_install}/bin")
        add_custom_command(TARGET poc_map POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
                "${_mln_install}/bin/QMapLibre.dll"
                "${_mln_install}/bin/QMapLibreLocation.dll"
                "${_mln_install}/bin/QMapLibreQuickPrivate.dll"
                $<TARGET_FILE_DIR:poc_map>
            COMMENT "Copying QMapLibre DLLs"
        )
        add_custom_command(TARGET poc_map POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E make_directory
                "$<TARGET_FILE_DIR:poc_map>/plugins/geoservices"
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
                "${_mln_install}/plugins/geoservices/qtgeoservices_maplibre.dll"
                "$<TARGET_FILE_DIR:poc_map>/plugins/geoservices/"
            COMMENT "Copying MapLibre geoservices plugin"
        )
        add_custom_command(TARGET poc_map POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E make_directory
                "$<TARGET_FILE_DIR:poc_map>/qml/MapLibre"
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
                "${_mln_install}/qml/MapLibre/declarative_maplibre.dll"
                "${_mln_install}/qml/MapLibre/qmldir"
                "$<TARGET_FILE_DIR:poc_map>/qml/MapLibre/"
            COMMAND ${CMAKE_COMMAND} -E make_directory
                "$<TARGET_FILE_DIR:poc_map>/qml/MapLibre/Location"
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
                "${_mln_install}/qml/MapLibre/Location/declarative_maplibre_locationplugin.dll"
                "${_mln_install}/qml/MapLibre/Location/qmldir"
                "$<TARGET_FILE_DIR:poc_map>/qml/MapLibre/Location/"
            COMMENT "Copying MapLibre QML plugins"
        )
    endif()
endif()

# ── Install ──────────────────────────────────────────────────────────────────
install(TARGETS poc_map
    BUNDLE  DESTINATION .
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
)
