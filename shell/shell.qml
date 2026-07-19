import Quickshell
import Quickshell.Io

// Navigator OS — Quickshell giriş noktası.
//
// Faz 4'te CI'da gerçek bir Hyprland compositor'a karşı çalıştırılıp
// doğrulandı (bkz. shell/README.md, build-disk-and-boot-test.yml
// "hyprland-test" job'ı) — artık sadece statik incelemeden ibaret değil.
ShellRoot {
    id: root

    // AssistantPanel'in görünürlüğü — AssistantToggle tıklaması (Bar.qml)
    // veya Hyprland Super+Space kısayolu (qs ipc call assistant toggle,
    // bkz. hyprland/hyprland.conf) ile değişir.
    property bool assistantVisible: false

    IpcHandler {
        target: "assistant"

        function toggle(): void {
            root.assistantVisible = !root.assistantVisible
        }

        function ask(prompt: string): void {
            root.assistantVisible = true
            panel.ask(prompt)
        }

        function getResponse(): string {
            return panel.responseText
        }

        function isLoading(): bool {
            return panel.loading
        }
    }

    Bar {
        onAssistantToggled: root.assistantVisible = !root.assistantVisible
    }

    AssistantPanel {
        id: panel
        visible: root.assistantVisible
    }
}
