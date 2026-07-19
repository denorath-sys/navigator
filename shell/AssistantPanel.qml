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
// router'ın kurulum yolu image/Containerfile'da henüz kararlaştırılmadı
// (Katman 5 hâlâ PLACEHOLDER, Faz 2+) — theme/ ile aynı /usr/share/
// navigator/ kuralı (bkz. Containerfile Katman 3 yorumu) izlenerek
// /usr/share/navigator/ai-stack/router varsayıldı. CI'da bu yol, ai-stack/'i
// aynı hiyerarşiyle VM'e kopyalayarak gerçekten test ediliyor (bkz.
// build-disk-and-boot-test.yml).
PanelWindow {
    id: panel

    property string responseText: ""
    property bool loading: false
    // Teşhis amaçlı: ask()'e gerçekten hangi argümanın ulaştığını (varsa)
    // dışarıdan (IpcHandler.debugLastArg() üzerinden) gözlemlemek için —
    // beşinci gerçek CI denemesinde ask()'in hiç çalışmadığından şüphelenildi
    // (routerProcess hiç başlamadı, console.log hiç görünmedi).
    property string debugLastArg: "(hiç çağrılmadı)"
    // qs log, Quickshell'in kendi qslog dosyasını okuyor ve pratikte
    // (muhtemelen tamponlama nedeniyle) yeni yazılan satırları göstermedi
    // — bu yüzden ask()'in NE KADAR ilerlediğini IPC ile canlı okunan
    // property'lerle izliyoruz (tamponlama sorunu olmayan, senkron okuma).
    property string debugStage: "(hiç çağrılmadı)"

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
        panel.debugStage = "başladı"
        panel.debugLastArg = "typeof=" + (typeof promptText) + " value=" + JSON.stringify(promptText)
        const trimmed = promptText.trim()
        panel.debugStage = "trim tamam, len=" + trimmed.length
        if (trimmed.length === 0 || panel.loading) {
            panel.debugStage = "guard'da durdu (len=" + trimmed.length + " loading=" + panel.loading + ")"
            return
        }

        panel.loading = true
        panel.responseText = ""
        routerProcess.running = false
        panel.debugStage = "guard geçildi, command set ediliyor"
        routerProcess.command = ["python3", "-m", "router", "--prompt", trimmed]
        panel.debugStage = "command set edildi: " + JSON.stringify(routerProcess.command)
        routerProcess.running = true
        panel.debugStage = "running=true set edildi, routerProcess.running=" + routerProcess.running
    }

    Process {
        id: routerProcess
        workingDirectory: "/usr/share/navigator/ai-stack/router"

        property int lastExitCode: -1

        onExited: (exitCode, exitStatus) => {
            routerProcess.lastExitCode = exitCode
            console.log("[AssistantPanel] routerProcess exited: exitCode=" + exitCode + " exitStatus=" + exitStatus)
        }

        stdout: StdioCollector {
            id: outCollector
            waitForEnd: true
            onStreamFinished: {
                panel.loading = false
                const out = outCollector.text
                console.log("[AssistantPanel] stdout finished, length=" + out.length
                    + " stderr_length=" + errCollector.text.length)
                if (out.length === 0) {
                    // Boş stdout — çıkış kodu ve stderr'i olduğu gibi göster,
                    // sessizce "Ayrıştırma hatası" deyip stderr'i gizleme
                    // (ilk gerçek CI denemesinde tam olarak bu oldu: boş
                    // yanıt "Ayrıştırma hatası: " olarak raporlandı ve
                    // gerçek nedeni gizledi).
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
