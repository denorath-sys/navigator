import QtQuick

// Navigator AI asistan paneli anahtarı — PLACEHOLDER.
// Gerçek panel (ai-stack/router ile konuşan Quickshell bileşeni) Faz 3+'ta
// gelecek; şimdilik sadece görsel buton + tıklama logu. hyprland/hyprland.conf
// içindeki Super+Space kısayolu bu paneli açacak (henüz Quickshell IPC'siyle
// bağlanmadı — ikisi bağımsız placeholder olarak duruyor).
Rectangle {
    id: root

    Theme { id: theme }

    implicitWidth: label.implicitWidth + theme.spacing * 2
    implicitHeight: 22
    radius: theme.radius / 2

    gradient: Gradient {
        orientation: Gradient.Horizontal
        GradientStop { position: 0.0; color: theme.teal }
        GradientStop { position: 1.0; color: theme.purple }
    }

    Text {
        id: label
        anchors.centerIn: parent
        text: "Navigator"
        font.pixelSize: 12
        font.bold: true
        color: theme.navy
    }

    MouseArea {
        anchors.fill: parent
        onClicked: console.log("[Navigator] asistan paneli henüz uygulanmadı (Faz 3+)")
    }
}
