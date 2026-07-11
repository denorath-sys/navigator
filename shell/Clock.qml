import QtQuick

// Basit saat göstergesi — sistem saatini her saniye günceller.
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
