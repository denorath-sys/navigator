pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts

// Workspace göstergesi — PLACEHOLDER.
// Gerçek Hyprland IPC entegrasyonu (aktif/dolu workspace tespiti,
// hyprctl/socket2 üzerinden) Faz 3'te eklenecek; şimdilik 1-10 arası
// statik, tıklanamayan pilller. hyprland/hyprland.conf içindeki
// Super+[1-9,0] kısayoluyla aynı numaralandırmayı kullanır.
RowLayout {
    id: root
    spacing: 4

    Theme { id: theme }

    Repeater {
        model: 10

        Rectangle {
            required property int index

            width: 20
            height: 20
            radius: theme.radius / 2
            color: index === 0 ? theme.teal : "transparent"
            border.color: theme.textMuted
            border.width: index === 0 ? 0 : 1

            Text {
                anchors.centerIn: parent
                text: parent.index + 1
                font.pixelSize: 11
                color: parent.index === 0 ? theme.navy : theme.textMuted
            }
        }
    }
}
