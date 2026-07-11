import QtQuick
import QtQuick.Layouts
import Quickshell

// Navigator üst paneli: workspace göstergesi, asistan paneli anahtarı, saat.
// wlr-layer-shell protokolü üzerinden Wayland'da panel katmanına yerleşir
// (bkz. Quickshell PanelWindow: https://quickshell.outfoxxed.me/docs/types/quickshell/panelwindow/).
PanelWindow {
    id: bar

    anchors {
        top: true
        left: true
        right: true
    }
    implicitHeight: theme.barHeight
    color: theme.panelBackground

    Theme { id: theme }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: theme.spacing
        anchors.rightMargin: theme.spacing
        spacing: theme.spacing

        WorkspaceIndicator {
            Layout.alignment: Qt.AlignVCenter
        }

        Item { Layout.fillWidth: true }

        AssistantToggle {
            Layout.alignment: Qt.AlignVCenter
        }

        Clock {
            Layout.alignment: Qt.AlignVCenter
        }
    }
}
