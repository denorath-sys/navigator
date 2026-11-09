pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

// The Navigator AI assistant panel — wired to ai-stack/assistant.
// Toggled by clicking AssistantToggle (Bar.qml) or by the Hyprland Super+Space
// shortcut (qs ipc call assistant toggle, see hyprland/hyprland.conf and the
// IpcHandler in shell.qml).
//
// It used to call ai-stack/router, which answers one prompt at a time with no
// tools and no memory. ai-stack/assistant runs the same routing decision and
// then a real tool-use loop over mcp-tools, and keeps the conversation in
// ~/.local/state/navigator/assistant-history.json (`--default-history`; the
// path is resolved by the assistant, not here). Typing /reset clears it.
//
// The workingDirectory below is no longer an assumption: Layer 5 of
// image/Containerfile genuinely copies ai-stack's six modules under
// /usr/share/navigator/ai-stack/. CI verifies that this path comes from the
// image itself (/usr read-only, with no scp/usroverlay involved) — see the
// "Verify that ai-stack is in the image itself" step in
// build-disk-and-boot-test.yml.
PanelWindow {
    id: panel

    // See the note in Bar.qml: both windows were called "quickshell" from
    // outside, which is fine until something has to tell them apart.
    WlrLayershell.namespace: "navigator-assistant"

    property string responseText: ""
    property bool loading: false

    // Must match RESET_COMMANDS in ai-stack/assistant/assistant/__main__.py.
    readonly property var resetCommands: ["/reset", "/yeni"]
    readonly property var assistantCommand: ["python3", "-m", "assistant", "--default-history"]

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
        case "history_file_malformed":
            return "The conversation history could not be read — type /reset to start a new conversation."
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
        assistantProcess.running = false
        assistantProcess.streamsFinished = 0
        assistantProcess.lastExitCode = -1
        if (panel.resetCommands.indexOf(trimmed) !== -1)
            assistantProcess.command = panel.assistantCommand.concat(["--reset"])
        else
            assistantProcess.command = panel.assistantCommand.concat(["--prompt", trimmed])
        assistantProcess.running = true
    }

    // The assistant reports a failed turn as JSON on STDERR with an empty
    // stdout ({"status": "error", "error": ..., "reason"?: ...}, see
    // _print_error() in ai-stack/assistant/assistant/__main__.py).
    function explainFailure(stderrText) {
        try {
            const parsed = JSON.parse(stderrText)
            if (parsed.status === "error")
                return "Error: " + panel.explainReason(parsed.reason || parsed.error || "unknown")
        } catch (e) {
            // Not JSON (e.g. a Python traceback) — fall through and show it as is.
        }
        return null
    }

    Process {
        id: assistantProcess
        workingDirectory: "/usr/share/navigator/ai-stack/assistant"

        property int lastExitCode: -1

        onExited: (exitCode, exitStatus) => {
            assistantProcess.lastExitCode = exitCode
        }

        // Both streams must have ended before the result is read: a failed
        // turn is explained from STDERR, and stdout ending first does not mean
        // stderr has been fully collected.
        property int streamsFinished: 0

        function streamFinished() {
            assistantProcess.streamsFinished += 1
            if (assistantProcess.streamsFinished === 2)
                panel.handleResult()
        }

        stdout: StdioCollector {
            id: outCollector
            waitForEnd: true
            onStreamFinished: assistantProcess.streamFinished()
        }

        stderr: StdioCollector {
            id: errCollector
            waitForEnd: true
            onStreamFinished: assistantProcess.streamFinished()
        }
    }

    function handleResult() {
        panel.loading = false
        const out = outCollector.text
        if (out.length === 0) {
            // A structured failure is explained; anything else (no
            // stderr, a traceback) is shown with the exit code as is —
            // do not silently say "Parse error" and hide stderr.
            const explained = panel.explainFailure(errCollector.text)
            panel.responseText = explained !== null ? explained
                : "ERROR: no output from assistant (exit=" + assistantProcess.lastExitCode
                  + ", stderr=" + (errCollector.text.length > 0 ? errCollector.text : "(empty)") + ")"
            return
        }
        try {
            const parsed = JSON.parse(out)
            if (parsed.status === "ok" && parsed.reset === true) {
                panel.responseText = "New conversation — the history was cleared."
            } else if (parsed.status === "ok") {
                const tools = (parsed.tool_calls || []).map(t => t.name)
                panel.responseText = parsed.content
                    + (tools.length > 0 ? "\n\n(tools used: " + tools.join(", ") + ")" : "")
            } else {
                panel.responseText = "Unexpected response: " + out
            }
        } catch (e) {
            panel.responseText = "Parse error (" + e + "): " + out
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
            text: panel.loading ? "Thinking..." : (panel.responseText.length > 0 ? panel.responseText : "Ask a question. Type /reset to start over.")
        }
    }
}
