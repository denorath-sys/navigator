pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io

// The Navigator AI assistant panel — genuinely wired to ai-stack/router.
// Toggled by clicking AssistantToggle (Bar.qml) or by the Hyprland Super+Space
// shortcut (qs ipc call assistant toggle, see hyprland/hyprland.conf and the
// IpcHandler in shell.qml).
//
// The workingDirectory below is no longer an assumption: Layer 5 of
// image/Containerfile genuinely copies ai-stack's six modules under
// /usr/share/navigator/ai-stack/. CI verifies that this path comes from the
// image itself (/usr read-only, with no scp/usroverlay involved) — see the
// "Verify that ai-stack is in the image itself" step in
// build-disk-and-boot-test.yml.
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

    // Translates ai-stack's machine-readable `reason` strings into sentences
    // that mean something to the user. Unknown reasons are shown AS IS —
    // rounding an unmatched reason to "unknown error" here would delete the
    // one piece of information needed to diagnose it.
    // For the credential path see ai-stack/cloud-bridge/cloud_bridge/config.py.
    function explainReason(reason) {
        switch (reason) {
        case "credentials_not_configured":
            return "No Claude credentials — write ANTHROPIC_API_KEY=... into "
                 + "~/.config/navigator/env and chmod 600 the file."
        case "credentials_file_insecure":
            return "~/.config/navigator/env is readable by others, so it was "
                 + "ignored — run chmod 600 ~/.config/navigator/env."
        case "credentials_file_unreadable":
            return "~/.config/navigator/env could not be read (permissions, or corrupt text?)."
        case "credentials_file_malformed":
            return "~/.config/navigator/env could not be parsed — every line must be KEY=VALUE."
        default:
            return reason
        }
    }

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
                    // Empty stdout — show the exit code and stderr as they are;
                    // do not silently say "Parse error" and hide stderr.
                    panel.responseText = "ERROR: no output from router (exit=" + routerProcess.lastExitCode
                        + ", stderr=" + (errCollector.text.length > 0 ? errCollector.text : "(empty)") + ")"
                    return
                }
                try {
                    const parsed = JSON.parse(out)
                    const result = parsed.route === "cloud" ? parsed.cloud_bridge : parsed.local_runtime
                    if (result && result.status === "ok") {
                        panel.responseText = result.content
                    } else if (result) {
                        panel.responseText = "[" + parsed.route + "] " + (result.status || "error") + ": "
                            + panel.explainReason(result.reason || result.error || "unknown")
                    } else {
                        panel.responseText = "Unexpected response: " + out
                    }
                } catch (e) {
                    panel.responseText = "Parse error (" + e + "): " + out
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
            text: panel.loading ? "Thinking..." : (panel.responseText.length > 0 ? panel.responseText : "Ask a question.")
        }
    }
}
