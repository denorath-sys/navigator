pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io

// Navigator AI asistan paneli — ai-stack/router'a gerçekten bağlı.
// AssistantToggle (Bar.qml) tıklamasıyla veya Hyprland Super+Space
// kısayoluyla (qs ipc call assistant toggle, bkz. hyprland/hyprland.conf
// ve shell.qml'deki IpcHandler) açılıp kapanır.
//
// Aşağıdaki workingDirectory artık bir varsayım değil: image/Containerfile
// Katman 5, ai-stack'in altı modülünü /usr/share/navigator/ai-stack/ altına
// gerçekten kopyalıyor. CI, bu yolun imajın kendisinden geldiğini
// (/usr salt-okunur, hiçbir scp/usroverlay devrede değil) doğruluyor —
// bkz. build-disk-and-boot-test.yml, "ai-stack'in imajın kendisinde
// olduğunu doğrula" adımı.
PanelWindow {
    id: panel

    property string responseText: ""
    property bool loading: false

    anchors {
        top: true
        right: true
    }
    margins {
        top: theme.barHeight + theme.spacing
        right: theme.spacing
    }

    implicitWidth: 380
    implicitHeight: 280
    color: theme.panelBackground

    Theme { id: theme }

    function ask(promptText) {
        const trimmed = promptText.trim()
        if (trimmed.length === 0 || panel.loading)
            return

        panel.loading = true
        panel.responseText = ""
        routerProcess.running = false
        routerProcess.command = ["python3", "-m", "router", "--prompt", trimmed]
        routerProcess.running = true
    }

    Process {
        id: routerProcess
        workingDirectory: "/usr/share/navigator/ai-stack/router"

        property int lastExitCode: -1

        onExited: (exitCode, exitStatus) => {
            routerProcess.lastExitCode = exitCode
        }

        stdout: StdioCollector {
            id: outCollector
            waitForEnd: true
            onStreamFinished: {
                panel.loading = false
                const out = outCollector.text
                if (out.length === 0) {
                    // Boş stdout — çıkış kodu ve stderr'i olduğu gibi göster,
                    // sessizce "Ayrıştırma hatası" deyip stderr'i gizleme.
                    panel.responseText = "HATA: router'dan çıktı gelmedi (exit=" + routerProcess.lastExitCode
                        + ", stderr=" + (errCollector.text.length > 0 ? errCollector.text : "(boş)") + ")"
                    return
                }
                try {
                    const parsed = JSON.parse(out)
                    const result = parsed.route === "cloud" ? parsed.cloud_bridge : parsed.local_runtime
                    if (result && result.status === "ok") {
                        panel.responseText = result.content
                    } else if (result) {
                        panel.responseText = "[" + parsed.route + "] " + (result.status || "hata") + ": "
                            + (result.reason || result.error || "bilinmeyen")
                    } else {
                        panel.responseText = "Beklenmeyen yanıt: " + out
                    }
                } catch (e) {
                    panel.responseText = "Ayrıştırma hatası (" + e + "): " + out
                }
            }
        }

        stderr: StdioCollector {
            id: errCollector
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: theme.spacing
        spacing: theme.spacing

        RowLayout {
            Layout.fillWidth: true
            spacing: theme.spacing

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 28
                radius: theme.radius / 2
                color: Qt.rgba(1, 1, 1, 0.08)
                border.color: theme.textMuted

                TextInput {
                    id: input
                    anchors.fill: parent
                    anchors.margins: 6
                    color: theme.textPrimary
                    font.pixelSize: 12
                    clip: true
                    onAccepted: panel.ask(text)
                }
            }

            Rectangle {
                implicitWidth: 64
                implicitHeight: 28
                radius: theme.radius / 2
                color: theme.teal

                Text {
                    anchors.centerIn: parent
                    text: "Sor"
                    font.pixelSize: 12
                    font.bold: true
                    color: theme.navy
                }

                MouseArea {
                    anchors.fill: parent
                    onClicked: panel.ask(input.text)
                }
            }
        }

        Text {
            Layout.fillWidth: true
            Layout.fillHeight: true
            wrapMode: Text.WordWrap
            color: theme.textPrimary
            font.pixelSize: 12
            text: panel.loading ? "Düşünüyor..." : (panel.responseText.length > 0 ? panel.responseText : "Bir soru sor.")
        }
    }
}
