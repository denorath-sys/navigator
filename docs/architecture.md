# Navigator OS — Architecture Summary

This document summarises the final architecture defined in the Phase 1
kick-off brief. Most of the components below are **still to be built**; this
document exists to record the intent at that time. For the current
implementation status, see the READMEs of the relevant directories.

## Layers

### Base operating system

**Fedora Atomic**, installed as an OSTree-based, monthly-updated immutable
image. The user does not modify the system directly; changes arrive through
layered image updates (`rpm-ostree` / `bootc`). Reference base image:
[`ghcr.io/ublue-os/base-main`](https://github.com/ublue-os/main) (Universal
Blue's minimal base with no DE — Hyprland is a layer we add on top).
Definition file: [`image/Containerfile`](../image/Containerfile).

### Desktop environment

**Hyprland** was chosen as a Wayland compositor with dynamic tiling —
prioritising performance and customisability. A custom shell built on
**Quickshell** (Qt6/QML) will be built on top of it (panel, notifications,
assistant panel, launcher) — chosen for QML's performance advantage over
AGS/Astal and for the preference to build an original identity that depends
less on ready-made templates. See [`hyprland/`](../hyprland/) and
[`shell/`](../shell/).

### AI stack

A hybrid local/cloud architecture made up of five components:

1. **hardware-probe** — hardware detection, model tier decision
2. **local-runtime** — running local models via llama.cpp/Ollama
3. **mcp-tools** — tool access based on MCP (Model Context Protocol)
4. **router** — the decision layer routing requests between local and cloud
5. **cloud-bridge** — connection to cloud model providers

Details: [`ai-stack/README.md`](../ai-stack/README.md).

### Brand identity

A nautical/sky identity themed around the compass, the lighthouse, the Orion
constellation and the North Star. Colour palette: teal `#4fd1c5`, purple
`#8b7cf6`, gold `#e8d9a8`, navy base `#0b0f1a`. See
[`theme/palette.json`](../theme/palette.json).

## Design principles

Every feature in Navigator must pass the following questions before being
added. Next to each principle, its current status is given according to real
progress in Phases 1-3.

- **Does this feature genuinely make the user's life easier?**
  If the answer is "no", it does not belong in Navigator, however
  technically impressive it may be.
  *Status:* Not yet testable — there is no user-facing surface (assistant
  panel) yet. The real exam begins in Phase 4.

- **Zero manual configuration.**
  The user should not have to hand-configure Bluetooth headphones, a second
  monitor, a dock, RGB or a touchpad — the system should recognise the
  hardware and prepare itself.
  *Status:* Achieved — `ai-stack/hardware-probe` determines the hardware
  tier itself, without input from the user.

- **No dead ends.**
  When an error occurs, the screen should not show a bare error code but a
  flow along the lines of "this problem occurred, here's how we can fix it,
  shall we do it together?".
  *Status:* Not yet tested (depends on the UI). When the assistant panel is
  designed in Phase 4, this must be treated as a requirement that belongs in
  the architecture from the start, not a feature bolted on at the end.

- **Everything should be discoverable.**
  Rather than searching the web for "how to set up dual monitors on linux",
  the user should be able to ask the Navigator Assistant directly and find
  the solution there.
  *Status:* Foundations laid — Hyprland query tools such as `list_windows`,
  `active_window` and `list_workspaces` are ready. Real proof will come when
  a question is asked in the assistant panel and the right answer comes back.

- **AI is not used where it isn't needed.**
  If a feature can be solved to the same quality without AI, AI is not used.
  *Status:* Partly achieved — the filesystem tools (`read_file`,
  `write_file` and so on) are direct tool calls with no AI making decisions;
  the router's local/cloud choice also aligns with the logic of not using an
  expensive model unnecessarily.

- **Linux is the infrastructure, Navigator is the experience.**
  The Fedora Atomic base remains a technical choice; what the user sees and
  feels is Navigator's own identity.
  *Status:* Clearly achieved — the base is Fedora Atomic and the user-facing
  surface is cleanly separated as Hyprland + Quickshell + the AI stack.

- **Nothing that isn't real is presented as "successful".**
  The system does not pretend to do something it cannot — it says "I
  couldn't try this because X". This is the honesty dimension of the "no
  dead ends" principle.
  *Status:* Achieved — throughout Phases 1-3, real tests were preferred over
  mocks (real Ollama, real Claude API, real KVM boot), and the deferred
  Hyprland/Quickshell compositor test was explicitly documented as a "known
  limitation" rather than presented as successful.

- **Every system-modifying action requires explicit confirmation.**
  Configuration happens automatically (see principle 2), but actions with a
  risk of damage do not — the AI does not modify the system on an assumption
  of consent.
  *Status:* Achieved — path traversal protection and the overwrite/confirm
  mechanism in the MCP filesystem tools, owner approval for downloads over
  200 MB, and never assuming risky CI triggers.

These principles are used as the reference point for every technical and
design decision throughout Phases 1-5. If a proposed new feature conflicts
with this list, it must be discussed here first. The status notes should be
reviewed and updated at the end of each phase.

## Phase status

For the current roadmap, see the root [`README.md`](../README.md#roadmap).
