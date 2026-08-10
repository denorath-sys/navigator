import QtQuick

// A simple clock display — updates the system time every second.
Text {
    id: root

    Theme { id: theme }

    color: theme.textPrimary
    font.pixelSize: 13
    text: Qt.formatDateTime(new Date(), "hh:mm:ss")

    Timer {
        interval: 1000
        running: true
        repeat: true
        onTriggered: root.text = Qt.formatDateTime(new Date(), "hh:mm:ss")
    }
}
