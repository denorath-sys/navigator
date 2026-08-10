import QtQuick
import QtQuick.Layouts
import Quickshell

// The Navigator top panel: workspace indicator, assistant panel toggle, clock.
// It places itself on the panel layer in Wayland via the wlr-layer-shell protocol
// (bkz. Quickshell PanelWindow: https://quickshell.outfoxxed.me/docs/types/quickshell/panelwindow/).
PanelWindow {
    id: bar

    signal assistantToggled()

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
            onToggled: bar.assistantToggled()
        }

        Clock {
            Layout.alignment: Qt.AlignVCenter
        }
    }
}
