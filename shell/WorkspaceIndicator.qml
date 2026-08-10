pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell.Hyprland

// The workspace indicator — bound to real Hyprland IPC.
//
// Quickshell's `Quickshell.Hyprland` module listens to the compositor's event
// socket (socket2) itself, so there is NO polling here: when a workspace is
// created or destroyed, or the focus changes, `Hyprland.workspaces` and the
// `focused`/`active` properties update on their own.
//
// It used to be static, unclickable pills numbered 1-10. Binding to real data
// has a visible consequence: only workspaces that EXIST are now shown
// (Hyprland does not report empty workspaces), so the list grows and shrinks
// with use. The Super+[1-9,0] shortcuts in hyprland.conf still create 1-10;
// the indicator shows them as they are created.
RowLayout {
    id: root
    spacing: 4

    Theme { id: theme }

    Repeater {
        model: Hyprland.workspaces

        Rectangle {
            id: pill
            required property var modelData

            // Special workspaces (scratchpad and the like) carry a negative
            // id and do not belong in the numbered list. Invisible items are
            // already skipped by QtQuick Layouts and take up no space.
            visible: pill.modelData.id > 0

            implicitWidth: Math.max(20, label.implicitWidth + 8)
            implicitHeight: 20
            radius: theme.radius / 2

            // `focused` = this workspace is active on its own monitor AND
            // that monitor has focus. `active` = active on its own monitor but
            // the monitor may not be focused (the two diverge on multi-monitor
            // setups).
            color: pill.modelData.focused ? theme.teal : "transparent"
            border.color: pill.modelData.active ? theme.teal : theme.textMuted
            border.width: pill.modelData.focused ? 0 : 1

            Text {
                id: label
                anchors.centerIn: parent
                // Hyprland workspace names are not always numbers (they can
                // be named, as in `workspace name:web`), so the name is shown
                // rather than the id.
                text: pill.modelData.name
                font.pixelSize: 11
                color: pill.modelData.focused ? theme.navy : theme.textMuted
            }

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                // activate() = Hyprland `dispatch workspace <id>`.
                onClicked: pill.modelData.activate()
            }
        }
    }
}
