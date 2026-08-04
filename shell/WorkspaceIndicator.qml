pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell.Hyprland

// Workspace göstergesi — gerçek Hyprland IPC'sine bağlı.
//
// Quickshell'in `Quickshell.Hyprland` modülü compositor'ın event soketini
// (socket2) kendisi dinliyor, yani burada polling YOK: workspace açılıp
// kapandığında veya odak değiştiğinde `Hyprland.workspaces` ve
// `focused`/`active` özellikleri kendiliğinden güncelleniyor.
//
// Önceki hali 1-10 arası statik, tıklanamayan pillerdi. Gerçek veriye
// bağlanmanın görünür bir sonucu var: artık SADECE VAR OLAN workspace'ler
// gösteriliyor (Hyprland boş workspace'leri raporlamaz), yani liste
// kullanımla birlikte büyüyüp küçülüyor. hyprland.conf'taki
// Super+[1-9,0] kısayolları 1-10'u oluşturmaya devam ediyor; gösterge
// onları oluştuklarında gösterir.
RowLayout {
    id: root
    spacing: 4

    Theme { id: theme }

    Repeater {
        model: Hyprland.workspaces

        Rectangle {
            id: pill
            required property var modelData

            // Özel workspace'ler (scratchpad vb.) negatif id taşır ve
            // numaralı listeye ait değil. Görünmeyen öğeler QtQuick
            // Layouts tarafından zaten atlanır, ayrıca yer tutmazlar.
            visible: pill.modelData.id > 0

            implicitWidth: Math.max(20, label.implicitWidth + 8)
            implicitHeight: 20
            radius: theme.radius / 2

            // `focused` = bu workspace kendi monitöründe aktif VE o monitör
            // odakta. `active` = kendi monitöründe aktif ama monitör odakta
            // olmayabilir (çok monitörlü kurulumda ikisi ayrışır).
            color: pill.modelData.focused ? theme.teal : "transparent"
            border.color: pill.modelData.active ? theme.teal : theme.textMuted
            border.width: pill.modelData.focused ? 0 : 1

            Text {
                id: label
                anchors.centerIn: parent
                // Hyprland workspace adları her zaman sayı değildir
                // (`workspace name:web` gibi adlandırılmış olabilirler),
                // bu yüzden id değil name gösteriliyor.
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
