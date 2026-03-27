cmake_minimum_required(VERSION 3.21)
project(poc_map VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ── Qt 6 ────────────────────────────────────────────────────────────────────
find_package(Qt6 6.5 REQUIRED COMPONENTS Core Gui Quick Location Positioning)
qt_standard_project_setup(REQUIRES 6.5)

# ── QMapLibre ────────────────────────────────────────────────────────────────
# Priority 1: externally installed (pass -DQMapLibre_DIR=.../lib/cmake/QMapLibre)
# Priority 2: maplibre-native-qt submodule in this directory
find_package(QMapLibre QUIET COMPONENTS Core Location)

if(NOT QMapLibre_FOUND)
    set(_mln_submod "${CMAKE_CURRENT_SOURCE_DIR}/maplibre-native-qt")
    if(EXISTS "${_mln_submod}/CMakeLists.txt")
        message(STATUS "QMapLibre not installed — building from submodule")
        set(MLN_QT_WITH_WIDGETS OFF CACHE BOOL "" FORCE)
        set(MLN_QT_WITH_LOCATION ON  CACHE BOOL "" FORCE)
        add_subdirectory("${_mln_submod}" maplibre-native-qt EXCLUDE_FROM_ALL)
    else()
        message(FATAL_ERROR
            "\n  QMapLibre not found. Choose one option:\n"
            "  A) cmake -B build -DQMapLibre_DIR=<install>/lib/cmake/QMapLibre\n"
            "  B) Run scripts/build_maplibre_qt.sh (or .ps1) first, then re-run cmake\n"
            "  C) git submodule add https://github.com/maplibre/maplibre-native-qt.git\n"
            "     git submodule update --init --recursive\n")
    endif()
endif()

# ── Executable ───────────────────────────────────────────────────────────────
qt_add_executable(poc_map main.cpp)

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
target_link_libraries(poc_map
    PRIVATE
        Qt6::Core
        Qt6::Gui
        Qt6::Quick
        Qt6::Location
        Qt6::Positioning
        QMapLibre::Core
        QMapLibre::Location
)

# Deploy MapLibre geoservices plugin + QML module alongside the binary
qmaplibre_location_setup_plugins(poc_map)

# ── Windows: copy QMapLibre DLLs next to the exe ─────────────────────────────
if(WIN32)
    add_custom_command(TARGET poc_map POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
            $<TARGET_FILE:QMapLibre::Core>
            $<TARGET_FILE:QMapLibre::Location>
            $<TARGET_FILE_DIR:poc_map>
        COMMENT "Copying QMapLibre DLLs"
    )
endif()

# ── Install ──────────────────────────────────────────────────────────────────
install(TARGETS poc_map
    BUNDLE  DESTINATION .
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
)
