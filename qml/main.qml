// MapLibre PoC — main QML window
// SPDX-License-Identifier: MIT

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtLocation
import QtPositioning

// Context properties injected from main.cpp:
//   initialStyleUrl : string  — MapLibre style.json URL
//   isOfflineMode   : bool    — true when --offline flag passed

ApplicationWindow {
    id: root
    visible: true
    width:  1280
    height:  800
    title: "MapLibre PoC — " + (isOfflineMode ? "OFFLINE  ●" : "ONLINE  ◉")

    // Default center: Warsaw, Poland
    readonly property var defaultCenter: QtPositioning.coordinate(52.2297, 21.0122)

    // ── MapLibre plugin ───────────────────────────────────────────────────
    Plugin {
        id: mapPlugin
        name: "maplibre"

        PluginParameter {
            name: "maplibre.map.styles"
            value: initialStyleUrl
        }
        // Cache in memory only (no disk cache writes during the PoC)
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

                Label {
                    text:  isOfflineMode ? "● OFFLINE" : "◉ ONLINE"
                    color: isOfflineMode ? "#e67e22"   : "#2ecc71"
                    font.bold: true
                }

                Item { Layout.fillWidth: true }

                // ── Zoom controls ─────────────────────────────────────────
                Button {
                    text: "+"
                    implicitWidth: 34
                    onClicked: mapView.map.zoomLevel = Math.min(mapView.map.zoomLevel + 1, 22)
                    ToolTip.text: "Zoom in"
                    ToolTip.visible: hovered
                }
                Label {
                    text: mapView.map.zoomLevel.toFixed(1)
                    horizontalAlignment: Text.AlignHCenter
                    implicitWidth: 38
                }
                Button {
                    text: "−"
                    implicitWidth: 34
                    onClicked: mapView.map.zoomLevel = Math.max(mapView.map.zoomLevel - 1, 0)
                    ToolTip.text: "Zoom out"
                    ToolTip.visible: hovered
                }

                Rectangle { width: 1; height: 22; color: "#666"; Layout.leftMargin: 2; Layout.rightMargin: 2 }

                // ── Bearing reset ─────────────────────────────────────────
                Button {
                    text: "⊕ N"
                    implicitWidth: 46
                    onClicked: mapView.map.bearing = 0
                    ToolTip.text: "Reset bearing to North"
                    ToolTip.visible: hovered
                }

                // ── Pitch toggle ──────────────────────────────────────────
                Button {
                    id: tiltBtn
                    text: "Tilt " + Math.round(mapView.map.tilt) + "°"
                    implicitWidth: 80
                    onClicked: mapView.map.tilt = mapView.map.tilt < 5 ? 45 : 0
                    ToolTip.text: "Toggle pitch  0° ↔ 45°\n(requires MapLibre tilt support)"
                    ToolTip.visible: hovered
                }

                Rectangle { width: 1; height: 22; color: "#666"; Layout.leftMargin: 2; Layout.rightMargin: 2 }

                // ── Reset home ────────────────────────────────────────────
                Button {
                    text: "⌂"
                    implicitWidth: 34
                    onClicked: {
                        mapView.map.center    = root.defaultCenter
                        mapView.map.zoomLevel = 10
                        mapView.map.bearing   = 0
                        mapView.map.tilt      = 0
                    }
                    ToolTip.text: "Reset view (Warsaw, zoom 10)"
                    ToolTip.visible: hovered
                }
            }
        }

        // ── Map area ──────────────────────────────────────────────────────
        Item {
            Layout.fillWidth:  true
            Layout.fillHeight: true

            // Main map — gestures (pan/pinch-zoom/two-finger-rotate) built into MapView
            MapView {
                id: mapView
                anchors.fill: parent

                map.plugin:           mapPlugin
                map.center:           root.defaultCenter
                map.zoomLevel:        10
                map.copyrightsVisible: true

                // Log plugin errors to console for debugging
                map.onErrorStringChanged: {
                    if (map.errorString !== "")
                        console.warn("Map error:", map.errorString)
                }
            }

            // ── Simulated "current position" marker (screen-space overlay) ──
            // Geo-positioned MapQuickItem requires MapLibre-compatible map items
            // API; a fixed screen dot is simpler and always works.
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

                // Accuracy ring
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
                        return "Lat: %1   Lon: %2   Bearing: %3°   Tilt: %4°"
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
                padding: 4

                Label {
                    color:          "white"
                    font.pixelSize: 10
                    text: initialStyleUrl.length > 60
                          ? "…" + initialStyleUrl.slice(-57)
                          : initialStyleUrl
                }
            }
        }
    }
}
