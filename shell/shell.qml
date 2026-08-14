import Quickshell
import Quickshell.Hyprland
import Quickshell.Io

// Navigator OS — the Quickshell entry point.
//
// In Phase 4 it was run against and verified on a real Hyprland compositor in
// CI (see shell/README.md and the "hyprland-test" job in
// build-disk-and-boot-test.yml) — it is no longer only a static review.
ShellRoot {
    id: root

    // AssistantPanel's visibility — changed by clicking AssistantToggle
    // (Bar.qml) or by the Hyprland Super+Space shortcut (qs ipc call assistant
    // toggle, see hyprland/hyprland.conf).
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

        // Both of these exist so a REAL mouse click can be verified from
        // outside the guest. `toggleRect` says where to aim, `isVisible` says
        // whether the click landed — without them the only way to test the
        // click path would be to hardcode a pixel and hope, which would go on
        // passing after the button moved.
        function isVisible(): bool {
            return root.assistantVisible
        }

        function toggleRect(): string {
            return bar.assistantToggleRect()
        }
    }

    // Makes the Hyprland data WorkspaceIndicator binds to readable from
    // outside. Like getResponse/isLoading on the `assistant` handler: because
    // the indicator is graphical, there is no other way to prove it shows the
    // right data against a real compositor (see the "is WorkspaceIndicator
    // bound to real Hyprland data" step in build-disk-and-boot-test.yml). It
    // also makes the shell's state scriptable.
    IpcHandler {
        target: "workspaces"

        function list(): string {
            // `Hyprland.workspaces` is an ObjectModel; its contents are
            // reached from JS via `values` (direct indexing is not reactive).
            const out = []
            for (const ws of Hyprland.workspaces.values) {
                out.push({
                    id: ws.id,
                    name: ws.name,
                    active: ws.active,
                    focused: ws.focused
                })
            }
            return JSON.stringify(out)
        }

        function focusedId(): int {
            return Hyprland.focusedWorkspace ? Hyprland.focusedWorkspace.id : -1
        }
    }

    Bar {
        id: bar
        onAssistantToggled: root.assistantVisible = !root.assistantVisible
    }

    AssistantPanel {
        id: panel
        visible: root.assistantVisible
    }
}
