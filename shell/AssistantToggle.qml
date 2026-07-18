import QtQuick

// Navigator AI asistan paneli anahtarı — AssistantPanel.qml'i (ai-stack/router'a
// gerçekten bağlı) açıp kapatır. hyprland/hyprland.conf'taki Super+Space
// kısayolu da aynı paneli Quickshell IPC üzerinden açar (bkz. shell.qml).
Rectangle {
    id: root

    signal toggled()

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
        onClicked: root.toggled()
    }
}
