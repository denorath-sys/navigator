import QtQuick

// Navigator marka paleti — ../theme/palette.json ile manuel senkron tutulur
// (the same method by which hyprland/hyprland.conf keeps its colour values in sync).
//
// For simple constants each component currently creates its own Theme {}
// instance (see Bar.qml, Clock.qml and so on). As the shell grows, a real
// `pragma Singleton` + qmldir registration could be considered instead.
QtObject {
    readonly property color teal: "#4fd1c5"
    readonly property color purple: "#8b7cf6"
    readonly property color gold: "#e8d9a8"
    readonly property color navy: "#0b0f1a"

    readonly property color panelBackground: Qt.rgba(navy.r, navy.g, navy.b, 0.85)
    readonly property color textPrimary: "#f4f4f5"
    readonly property color textMuted: "#9a9aa2"

    readonly property int barHeight: 32
    readonly property int spacing: 8
    readonly property int radius: 10
}
