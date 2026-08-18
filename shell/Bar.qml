import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland

// The Navigator top panel: workspace indicator, assistant panel toggle, clock.
// It places itself on the panel layer in Wayland via the wlr-layer-shell
// protocol (see Quickshell's PanelWindow:
// https://quickshell.outfoxxed.me/docs/types/quickshell/panelwindow/).
PanelWindow {
    id: bar

    // The layer surface's name, as `hyprctl layers` and any Hyprland
    // layerrule will see it. Quickshell's default is "quickshell" for every
    // window it maps, so the bar and the assistant panel were indistinguisha-
    // ble from outside: the click test picked whichever came last and aimed
    // at x=2063 on a 1280-wide screen (run 32089480998). Naming them is what
    // makes "the bar" a thing that can be asked for rather than guessed at.
    WlrLayershell.namespace: "navigator-bar"

    signal assistantToggled()

    // Where the assistant toggle actually sits inside this window, so a test
    // can click it for real. Exposed because the alternative is hardcoding a
    // pixel in CI, which would keep passing after the button moved — the same
    // reasoning that put the workspace data behind an IpcHandler.
    //
    // mapToItem(null, ...) gives window coordinates; the caller adds the
    // window's own position, which it reads from `hyprctl layers`.
    function assistantToggleRect(): string {
        const p = assistantToggle.mapToItem(null, 0, 0)
        return JSON.stringify({
            x: Math.round(p.x),
            y: Math.round(p.y),
            w: Math.round(assistantToggle.width),
            h: Math.round(assistantToggle.height)
        })
    }

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
            id: assistantToggle
            Layout.alignment: Qt.AlignVCenter
            onToggled: bar.assistantToggled()
        }

        Clock {
            Layout.alignment: Qt.AlignVCenter
        }
    }
}
