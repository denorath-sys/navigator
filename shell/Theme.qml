import QtQuick

// Navigator marka paleti — ../theme/palette.json ile manuel senkron tutulur
// (hyprland/hyprland.conf'un renk değerlerini senkron tutma yöntemiyle aynı).
//
// Basit sabitler için şimdilik her bileşen kendi Theme {} örneğini
// oluşturuyor (bkz. Bar.qml, Clock.qml vb.). Shell büyüdükçe bunun yerine
// gerçek bir `pragma Singleton` + qmldir kaydı düşünülebilir.
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
