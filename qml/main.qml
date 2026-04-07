// MapLibre PoC — main QML window
// SPDX-License-Identifier: MIT

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtLocation
import QtPositioning

import MapLibre.Location 4.0

// Context properties injected from main.cpp:
//   initialStyleUrl : string  — MapLibre style.json URL
//   isOfflineMode   : bool    — true when --offline flag passed

ApplicationWindow {
    id: root
    visible: true
    width:  1280
    height:  800
    title: "MapLibre PoC"

    // Default center: Warsaw, Poland
    readonly property var defaultCenter: QtPositioning.coordinate(52.2297, 21.0122)

    // ── Dark mode ─────────────────────────────────────────────────────────
    property bool darkMode: false

    // ── MapLibre plugin ───────────────────────────────────────────────────
    Plugin {
        id: mapPlugin
        name: "maplibre"

        PluginParameter {
            name: "maplibre.map.styles"
            value: initialStyleUrl
        }
        PluginParameter {
            name: "maplibre.cache.memory"
            value: "true"
        }
    }

    // ── Layout ────────────────────────────────────────────────────────────
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── Toolbar ───────────────────────────────────────────────────────
        ToolBar {
            Layout.fillWidth: true

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin:  8
                anchors.rightMargin: 8
                spacing: 6

                Label {
                    text: "MapLibre PoC"
                    font.bold:      true
                    font.pixelSize: 15
                }

                Item { Layout.fillWidth: true }

                // ── Zoom controls ─────────────────────────────────────────
                Button {
                    text: "+"
                    width: 34
                    onClicked: mapView.map.zoomLevel = Math.min(mapView.map.zoomLevel + 1, mapView.map.maximumZoomLevel)
                    ToolTip.text: "Zoom in"
                    ToolTip.visible: hovered
                }
                Label {
                    text: mapView.map.zoomLevel.toFixed(1)
                    horizontalAlignment: Text.AlignHCenter
                    width: 38
                }
                Button {
                    text: "\u2212"
                    width: 34
                    onClicked: mapView.map.zoomLevel = Math.max(mapView.map.zoomLevel - 1, 0)
                    ToolTip.text: "Zoom out"
                    ToolTip.visible: hovered
                }

                Rectangle { width: 1; height: 22; color: "#666"; Layout.leftMargin: 2; Layout.rightMargin: 2 }

                // ── Rotation controls ─────────────────────────────────────
                Button {
                    text: "\u21BA"
                    width: 34
                    onClicked: mapView.map.bearing = mapView.map.bearing - 15
                    ToolTip.text: "Rotate left 15\u00B0"
                    ToolTip.visible: hovered
                }
                Button {
                    text: "\u2295 N"
                    width: 46
                    onClicked: mapView.map.bearing = 0
                    ToolTip.text: "Reset bearing to North"
                    ToolTip.visible: hovered
                }
                Button {
                    text: "\u21BB"
                    width: 34
                    onClicked: mapView.map.bearing = mapView.map.bearing + 15
                    ToolTip.text: "Rotate right 15\u00B0"
                    ToolTip.visible: hovered
                }

                Rectangle { width: 1; height: 22; color: "#666"; Layout.leftMargin: 2; Layout.rightMargin: 2 }

                // ── Pitch toggle ──────────────────────────────────────────
                Button {
                    text: "Tilt " + Math.round(mapView.map.tilt) + "\u00B0"
                    width: 80
                    onClicked: mapView.map.tilt = mapView.map.tilt < 5 ? 45 : 0
                    ToolTip.text: "Toggle pitch  0\u00B0 \u2194 45\u00B0"
                    ToolTip.visible: hovered
                }

                Rectangle { width: 1; height: 22; color: "#666"; Layout.leftMargin: 2; Layout.rightMargin: 2 }

                // ── Reset home ────────────────────────────────────────────
                Button {
                    text: "\u2302"
                    width: 34
                    onClicked: {
                        mapView.map.center    = root.defaultCenter
                        mapView.map.zoomLevel = 10
                        mapView.map.bearing   = 0
                        mapView.map.tilt      = 0
                    }
                    ToolTip.text: "Reset view (Warsaw, zoom 10)"
                    ToolTip.visible: hovered
                }

                // ── Dark mode toggle ──────────────────────────────────────
                Button {
                    text: root.darkMode ? "Light" : "Dark"
                    width: 46
                    onClicked: root.darkMode = !root.darkMode
                    ToolTip.text: root.darkMode ? "Switch to light mode" : "Switch to dark mode"
                    ToolTip.visible: hovered
                }
            }
        }

        // ── Map area ──────────────────────────────────────────────────────
        Item {
            Layout.fillWidth:  true
            Layout.fillHeight: true

            MapView {
                id: mapView
                anchors.fill: parent

                map.plugin:           mapPlugin
                map.center:           root.defaultCenter
                map.zoomLevel:        10
                map.copyrightsVisible: true
                map.maximumZoomLevel: 16.9

                map.onErrorStringChanged: {
                    if (map.errorString !== "")
                        console.warn("Map error:", map.errorString)
                }

                // ── Runtime paint overrides via MapLibre.Location API ─────
                // LayerParameter.paint is reactive: when darkMode changes,
                // setPaint → paintUpdated → setPaintProperty on the live map.
                // No plugin recreation, no OpenGL context teardown.
                MapLibre.style: Style {

                    LayerParameter {
                        styleId: "background"
                        paint: root.darkMode
                            ? {"background-color": "#1a1a2e"}
                            : {"background-color": "#f0ebe3"}
                    }
                    LayerParameter {
                        styleId: "earth"
                        paint: root.darkMode
                            ? {"fill-color": "#16213e"}
                            : {"fill-color": "#f0ebe3"}
                    }
                    LayerParameter {
                        styleId: "water"
                        paint: root.darkMode
                            ? {"fill-color": "#0a2a4a"}
                            : {"fill-color": "#a8c8f0"}
                    }
                    LayerParameter {
                        styleId: "landuse-green"
                        paint: root.darkMode
                            ? {"fill-color": "#1a2e1a"}
                            : {"fill-color": "#d8f0c8"}
                    }
                    LayerParameter {
                        styleId: "landuse-forest"
                        paint: root.darkMode
                            ? {"fill-color": "#142214"}
                            : {"fill-color": "#c0dca8"}
                    }
                    LayerParameter {
                        styleId: "landuse-industrial"
                        paint: root.darkMode
                            ? {"fill-color": "#252535"}
                            : {"fill-color": "#e8ddd0"}
                    }
                    LayerParameter {
                        styleId: "road-highway-casing"
                        paint: root.darkMode
                            ? {"line-color": "#604020"}
                            : {"line-color": "#c87030"}
                    }
                    LayerParameter {
                        styleId: "road-major-casing"
                        paint: root.darkMode
                            ? {"line-color": "#504020"}
                            : {"line-color": "#d0a060"}
                    }
                    LayerParameter {
                        styleId: "road-highway"
                        paint: root.darkMode
                            ? {"line-color": "#c08040"}
                            : {"line-color": "#f09050"}
                    }
                    LayerParameter {
                        styleId: "road-major"
                        paint: root.darkMode
                            ? {"line-color": "#907030"}
                            : {"line-color": "#ffd080"}
                    }
                    LayerParameter {
                        styleId: "road-medium"
                        paint: root.darkMode
                            ? {"line-color": "#3a3a4a"}
                            : {"line-color": "#ffffff"}
                    }
                    LayerParameter {
                        styleId: "road-minor"
                        paint: root.darkMode
                            ? {"line-color": "#2a2a3a"}
                            : {"line-color": "#ffffff"}
                    }
                    LayerParameter {
                        styleId: "boundary-country"
                        paint: root.darkMode
                            ? {"line-color": "#7070c0"}
                            : {"line-color": "#8080c0"}
                    }
                    LayerParameter {
                        styleId: "boundary-region"
                        paint: root.darkMode
                            ? {"line-color": "#404070"}
                            : {"line-color": "#b0b0d0"}
                    }
                    LayerParameter {
                        styleId: "label-city"
                        paint: root.darkMode
                            ? {"text-color": "#e8e8e8", "text-halo-color": "#1a1a2e"}
                            : {"text-color": "#333333", "text-halo-color": "#ffffff"}
                    }
                    LayerParameter {
                        styleId: "label-village"
                        paint: root.darkMode
                            ? {"text-color": "#b8b8c8", "text-halo-color": "#1a1a2e"}
                            : {"text-color": "#555555", "text-halo-color": "#ffffff"}
                    }
                    LayerParameter {
                        styleId: "label-road"
                        paint: root.darkMode
                            ? {"text-color": "#909090", "text-halo-color": "#1a1a2e"}
                            : {"text-color": "#555555", "text-halo-color": "#ffffff"}
                    }
                }
            }

            // ── Simulated "current position" marker (screen-space overlay) ──
            Rectangle {
                anchors.centerIn: parent
                width: 14; height: 14
                radius: 7
                color: "#2980b9"
                border.color: "white"
                border.width: 2
                z: 10

                Rectangle {
                    anchors.centerIn: parent
                    width: 4; height: 4
                    radius: 2
                    color: "white"
                }

                Rectangle {
                    anchors.centerIn: parent
                    width: 40; height: 40
                    radius: 20
                    color: "transparent"
                    border.color: "#602980b9"
                    border.width: 2
                }
            }

            // ── Status overlay (bottom-left) ──────────────────────────────
            Rectangle {
                anchors.left:    parent.left
                anchors.bottom:  parent.bottom
                anchors.margins: 8
                color:  "#bb000000"
                radius: 4
                width:  statusLabel.implicitWidth  + 14
                height: statusLabel.implicitHeight + 10

                Label {
                    id: statusLabel
                    anchors.centerIn: parent
                    color:          "white"
                    font.pixelSize: 11
                    text: {
                        const c = mapView.map.center
                        return "Lat: %1   Lon: %2   Bearing: %3\u00B0   Tilt: %4\u00B0"
                            .arg(c.latitude.toFixed(5))
                            .arg(c.longitude.toFixed(5))
                            .arg(mapView.map.bearing.toFixed(1))
                            .arg(mapView.map.tilt.toFixed(1))
                    }
                }
            }

            // ── Style URL overlay (top-right, debug) ─────────────────────
            Rectangle {
                anchors.right:   parent.right
                anchors.top:     parent.top
                anchors.margins: 8
                color:  "#99000000"
                radius: 4
                width:  urlLabel.implicitWidth + 8
                height: urlLabel.implicitHeight + 8

                Label {
                    id: urlLabel
                    anchors.centerIn: parent
                    color:          "white"
                    font.pixelSize: 10
                    text: initialStyleUrl.length > 60
                          ? "..." + initialStyleUrl.slice(-57)
                          : initialStyleUrl
                }
            }
        }
    }
}
