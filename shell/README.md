# shell/

Navigator's custom desktop shell (panel, notification centre, assistant
panel, application launcher and so on) lives here.

## Technology

**[Quickshell](https://quickshell.outfoxxed.me/)** (Qt6/QML) — a custom
shell that talks directly to Hyprland. It was preferred over AGS/Astal
(GTK4/GJS); the reasoning: QML's performance/rendering advantage, and the
preference to build Navigator's own identity from scratch with less
dependence on ready-made templates. Its installation into the image is
defined in Layer 2 of `image/Containerfile` (the
`errornointernet/quickshell` COPR, Fedora-specific).

## Installation path in the image (Layer 7)

Layer 2 installs Quickshell itself (the runner); **Layer 7** places the
`.qml` files in this directory into the image:

```
/usr/share/navigator/shell/*.qml
```

To run: `qs -p /usr/share/navigator/shell/shell.qml`

**Why `/usr/share/navigator/` and not `/etc/skel`:** these are program code,
not user configuration. Had they been placed in `/etc/skel`, every user
would get their own frozen copy and image updates could never update the
shell. In `hyprland.conf` (Layer 4) we wanted exactly the opposite — there
*not overwriting* the user's file was right; here *being able to update* is
right. A user who wants to run their own shell can copy this directory and
point `qs -p` at their own path.

`README.md` does not go into the image (it is developer documentation). The
layer order is not a dependency but follows the order in which the layers
became real; since `shell/` is the most frequently changing COPY content,
having it last also preserves the build cache of the layers above it.

After this layer, the **only thing** copied from the runner to the VM in
`build-disk-and-boot-test.yml` is the test script itself — every Navigator
component under test comes from the image.

## Files

- `shell.qml` — the Quickshell entry point (`ShellRoot`); it holds the
  `assistantVisible` state and two `IpcHandler`s:
  - `target: "assistant"` — `toggle()`/`ask(prompt)`/`getResponse()`/
    `isLoading()`; connects both the click in `Bar.qml` and the Hyprland
    Super+Space shortcut (`qs ipc call assistant toggle`) to
    `AssistantPanel`. Plus `isVisible()`/`toggleRect()`, which exist so a
    real mouse click can be aimed and its effect read from outside the
    guest (see "Real input").
  - `target: "workspaces"` — `list()`/`focusedId()`; makes the live
    Hyprland data that `WorkspaceIndicator` binds to readable from the
    outside (see below).
- `Theme.qml` — the Navigator brand palette (kept in manual sync with
  `../theme/palette.json`, the same as the colour sync method of
  `hyprland/hyprland.conf`). That manual sync is now **genuinely verified**
  in CI: the four colour constants are compared against the `palette.json`
  in the image (see `theme/README.md`).
- `Bar.qml` — the top panel (`PanelWindow`, wlr-layer-shell)
- `WorkspaceIndicator.qml` — the workspace indicator, **bound to real
  Hyprland IPC** (`Quickshell.Hyprland`); clickable (see
  "WorkspaceIndicator — real Hyprland data")
- `AssistantToggle.qml` — the AI assistant panel switch; emits a `toggled()`
  signal when clicked (connected to `shell.qml` via `Bar.qml`)
- `AssistantPanel.qml` — the assistant panel, **genuinely wired to
  `ai-stack/router`**: a text input, the logic that invokes
  `ai-stack/router` as a subprocess via `Quickshell.Io.Process`, and an area
  showing the real response (route + content, or a graceful error) — see
  "AssistantPanel — real router integration" below
- `Clock.qml` — a live clock display

## Runtime verification on a real compositor (CI, Phase 4)

Because Quickshell is a Fedora-specific COPR package (it requires Qt 6.10),
it still cannot be installed in this development environment
(Debian-based, Qt 6.8.2) — but it is now verified against a real compositor
in CI.

The `hyprland-test` job in `.github/workflows/build-disk-and-boot-test.yml`
genuinely starts the shell **from its path in the image** —
`qs -p /usr/share/navigator/shell/shell.qml` — once Hyprland has really
started (before Layer 7, this directory was copied from the runner to the
VM; that last simulation is now gone). It connects to the real Wayland
socket Hyprland created via `WAYLAND_DISPLAY`, and verifies not merely that
"the process did not crash" but, with `hyprctl layers -j`, that `Bar.qml`
(`PanelWindow`, wlr-layer-shell) genuinely mapped a surface. The real
result:

```
INFO: Configuration Loaded
```
```
Layer level 2 (top):
    Layer 55b9230bbd30: xywh: 0 20 1280 32, namespace: quickshell, pid: 1516
```

(`w=1280` matches the real monitor width and `h=32` matches `barHeight` in
`Theme.qml` exactly — not a mock, but a real render.) Two harmless warnings
were seen: `libEGL warning: egl: failed to create dri2 screen` (expected
because virtio-gpu is software-only; it did not prevent rendering).

**What this does and does not prove:** it is proof that `Bar.qml` genuinely
maps and renders. `WorkspaceIndicator`'s DATA is verified separately (see
below). The click path is a separate question again, and it now has its own
machinery — see "Real input" below.

## Real input — clicking from outside the guest

Every test before this one drove the desktop from *inside* the guest, with
`hyprctl dispatch` and `qs ipc call`. Those prove the compositor and the
shell agree with each other; they cannot prove that a human pointing at the
button would hit anything, because the click path is never exercised.

The reason it had never been tested turned out to be simpler than "it is
hard": **the test VM had no input device at all.** With nothing for libinput
to bind, "the button does not respond" and "there is no mouse" looked
identical from inside the guest. The VM now gets `-device virtio-tablet-pci`,
an absolute pointing device.

Events are injected over QEMU's **QMP** socket rather than the HMP monitor
used for screenshots, because HMP's `mouse_move` is relative while
`input-send-event` takes absolute axes — which is what makes "click at this
pixel" expressible at all.
[`.github/scripts/qemu-input.py`](../.github/scripts/qemu-input.py) does the
handshake and the coordinate mapping (QEMU's absolute axes are a fixed
0..32767 range, so the caller has to say how big the screen is).

**Where to aim is asked for, not hardcoded.** `Bar.qml` exposes
`assistantToggleRect()` and `shell.qml` publishes it as
`qs ipc call assistant toggleRect`, alongside `isVisible`. CI combines that
with the bar surface's own geometry from `hyprctl layers -j`. A hardcoded
pixel would keep passing after the button moved, which is exactly the failure
this is meant to catch — the same reasoning that put the workspace data
behind an `IpcHandler` in the first place.

**Status: measured, not yet asserted.** The injection script's own failure
paths were exercised locally against a fake QMP server — a missing socket, a
non-QMP socket, an out-of-range coordinate and a QMP error all exit 1 — so a
failure from the script fails the step. What happens *inside* the guest
(virtio-tablet → libinput → Hyprland → layer surface → the QML `MouseArea`)
is a diagnostic on this first round, because none of that chain is a
documented guarantee. It gets hardened once the real numbers have been read,
which is the same order everything else here followed.

## Visual correctness — the real image of the screen (CI)

Every verification up to this point was TEXTUAL: `hyprctl` output, IPC
responses, process states. Whether the desktop actually LOOKED right had
never been measured.

The boot test now genuinely captures the screen's current contents. The
method is deliberately lightweight: `screendump` is called over **QEMU's own
HMP monitor** (`-monitor unix:...`) and QEMU writes the raw PPM straight to
the HOST. There is no need to install a VNC client, run a screenshot tool
inside the guest, or add a package to the image — and because the capture is
independent of the guest, it is exactly what "the user sees".

Two small stdlib-only scripts live in the repository rather than being
embedded in the workflow's `run:` block (so they can be exercised locally):

- `.github/scripts/qemu-screendump.py` — connects to the monitor socket,
  runs `screendump`, and waits until the file stabilises. All four paths
  were exercised locally against a fake HMP server: normal, monitor error,
  the file never being written, and no socket.
- `.github/scripts/analyze-screenshot.py` — parses the PPM, prints
  diagnostics and writes a dependency-free PNG (uploaded as an artifact, so
  **the screenshot can genuinely be looked at**).

**Only two things are deliberately ASSERTED this round:** that the file is a
valid P6 PPM, and that the image is not a single colour (if Hyprland
rendered nothing, or Quickshell crashed, a flat black frame would arrive —
that must not stay silently green). Bar height, brand-colour pixel counts
and row-wise brightness are DIAGNOSTICS for now: they are not promoted to
assertions before the real numbers have been read (a project rule — measure
first, harden second; violating this rule has already cost this project a CI
round before).

The analysis logic was exercised locally without spending CI: a fake
Navigator screen (a dark bar + a teal pill + a gradient desktop) was
generated and verified to produce the right diagnosis, while a completely
black screen and a corrupt file were both rejected; the validity of the
generated PNG was checked separately as well.

### What the first screenshot found

The first real run ([run
30915860029](https://github.com/denorath-sys/navigator/actions/runs/30915860029))
paid for itself immediately. What was measured:

```
size: 1280x800, distinct colour count: 265280
teal #4fd1c5: 1904 pixels     navy #0b0f1a: 2560 pixels
purple #8b7cf6: 10 pixels     gold #e8d9a8: 0 pixels
```

So the brand teal renders **exactly** as specified on screen (the focused
workspace pill + AssistantToggle). The bar, the clock, the workspace pill
and the AssistantPanel's credential message genuinely appear in the image —
the panel's `explainReason()` translation was verified by eye for the first
time.

But the image also showed **two real problems**, both of which had silently
passed every textual test until then:

1. **Hyprland's red config-error banner at the top of the screen**:
   `config option <gestures:workspace_swipe> does not exist`. For the
   details, and why all three separate checks missed it, see
   `hyprland/README.md`, "The real error the static review missed".
2. **The desktop still showing the stock Hyprland wallpaper** (the default
   anime image + "A day without Hyprland is a day wasted"). Navigator had no
   wallpaper of its own — `hyprpaper` had been deliberately left out, but
   this was the first time the unbranded result was actually seen.

## WorkspaceIndicator — real Hyprland data (CI, Phase 4)

`WorkspaceIndicator` was a static placeholder for a long time: fixed,
unclickable pills numbered 1-10. It is now bound to `Quickshell.Hyprland`'s
`Hyprland` singleton — `Hyprland.workspaces` (an `ObjectModel`) is the
`Repeater`'s model directly, the `focused`/`active` states drive the
colours, and a click calls `HyprlandWorkspace.activate()`.

**No polling.** Quickshell listens to the compositor's event socket
(`socket2`) itself, so the model updates on its own when a workspace is
created or destroyed or the focus changes.

**A visible behaviour change:** only workspaces that EXIST are now shown —
Hyprland does not report empty workspaces, so the list grows and shrinks
with use. The fixed 1-10 row of pills is gone; the Super+[1-9,0] shortcuts
in `hyprland.conf` still create those workspaces, and the indicator shows
them as they are created. Special workspaces with negative ids (scratchpad
and the like) are hidden from the numbered list.

### How it is verified

Because the indicator is graphical, the only proof of the claim "it shows
the right data" is reading the data it binds to from the outside: an
`IpcHandler { target: "workspaces" }` was added to `shell.qml` (the same
pattern as `getResponse`/`isLoading` in the `assistant` handler). CI
verifies two separate things:

1. **Agreement** — whether the workspace set and the focus the shell sees
   match the compositor's own report exactly (`hyprctl workspaces -j`,
   `hyprctl activeworkspace -j`).
2. **Liveness** — a real change is made in the compositor with
   `hyprctl dispatch workspace 3` and the shell is expected to see it ON ITS
   OWN (not a fixed sleep, but a loop until `focusedId` becomes 3). A static
   placeholder or a one-shot read cannot pass the second.

The comparison logic was exercised locally with fake data without spending
CI; all three deliberate deviations (the shell missing a workspace, a wrong
focus, and the old fixed 1-10 behaviour) were caught.

**Real CI evidence** ([run
30898836059](https://github.com/denorath-sys/navigator/actions/runs/30898836059)):

```
=== Is WorkspaceIndicator bound to real Hyprland data? ===
  shell: [{"id":1,"name":"1","active":true,"focused":true}]
  OK: sets match [1], focused=1
--- REAL EVENT: hyprctl dispatch workspace 3 ---
OK: the shell saw the workspace change on its own (no polling, socket2 event).
  shell: [{"id":3,"name":"3","active":true,"focused":true}]
  OK: sets match [3], focused=3
```

The set turning from `[1]` into `[3]` is not a coincidence but exactly the
expected behaviour: workspace 1 was destroyed by Hyprland because it was
left empty, while 3 came into existence because it became active. The old
static placeholder would have said `[1..10]` on both readings and could not
even have passed the first check.

## AssistantPanel — real `ai-stack/router` integration (CI, Phase 4)

`AssistantToggle` no longer merely writes a console log — it opens and
closes `AssistantPanel`, and that panel **genuinely** invokes
`ai-stack/router` (`python3 -m router --prompt <question>` via
`Quickshell.Io.Process`, inside `/usr/share/navigator/ai-stack/router`). The
`IpcHandler` in `shell.qml` (`target: "assistant"`) connects both the click
in `Bar.qml` and the Hyprland Super+Space shortcut
(`hyprland/hyprland.conf`: now `exec, qs ipc call assistant toggle`,
previously a placeholder `echo`) to the same panel.

The router's installation path is no longer an assumption: **Layer 5** of
`image/Containerfile` genuinely copies ai-stack's six modules under
`/usr/share/navigator/ai-stack/` (see `ai-stack/README.md`, "Installation
path in the image"). In the first version this path was simulated in CI with
scp + `rpm-ostree usroverlay`; that simulation was removed, and the
`hyprland-test` job now verifies the image's own contents with `/usr`
read-only. A real question is then asked with
`qs ipc -p /usr/share/navigator/shell/shell.qml call assistant ask
"<question>"` and the result is read via `getResponse()`/`isLoading()`.

The real result (CI has neither Ollama nor Claude API credentials, so the
`model_ready=false` rule always falls through to "cloud", and since
`cloud-bridge` has no credentials it returns a graceful "unavailable" — not
a mock, but a real end-to-end failure path):

```
AssistantPanel response: [cloud] unavailable: credentials_not_configured
```

**Reason strings are now translated for the user** (`explainReason()`): a
machine-readable slug such as `credentials_not_configured` told a desktop
user nothing. For known reasons the panel now says what to do — e.g. "No
Claude credentials — write `ANTHROPIC_API_KEY=...` into
`~/.config/navigator/env` and `chmod 600` the file", or, if the permissions
are loose, "it is readable by others, so it was ignored". Unknown reasons
are shown AS IS: rounding an unmatched reason to "unknown error" would
delete the one piece of information needed to diagnose it. For the
credential path itself see `ai-stack/cloud-bridge/README.md`.

**Real problems found and fixed along the way:**
- `qs ipc call` expects `-p`/`--path` to be registered on the `ipc`
  subcommand itself (not on `call`) — verified in its source
  (`launch/parsecommand.cpp`); the correct syntax is
  `qs ipc -p <path> call <target> <fn>`.
- `ai-stack/router` was failing even after being copied to the VM:
  `local-runtime`'s own default `--hardware-probe-path`
  (`../hardware-probe`) dependency had never been copied — this was
  isolated and found directly over SSH, independently of Quickshell (see
  the "test ai-stack/router directly over SSH" step in CI, kept as a
  permanent regression check).

**Real static analysis was done (no compositor required):**
`qt6-declarative-dev-tools` was installed on this machine and the real Qt6
`qmllint` was run against all six QML files:

- `Theme.qml`, `Clock.qml`, `AssistantToggle.qml` — **clean**, no warnings
  at all.
- `WorkspaceIndicator.qml` — qmllint found a real problem: unqualified
  access to the outer `theme` id inside the `Repeater` delegate
  (`[unqualified]`). It was fixed by adding
  `pragma ComponentBehavior: Bound`, and is now **clean**.
- `shell.qml`, `Bar.qml` — because Quickshell's QML plugin is not packaged
  on Debian, `import Quickshell` cannot be resolved; this leads to the
  expected cascade of "unresolved" warnings for `ShellRoot`/`PanelWindow`
  and their custom properties (`anchors`, `implicitHeight` and so on) — not
  a real code error, merely the Quickshell type definitions being absent in
  the local environment. The Quickshell-specific parts of these two files
  still cannot be verified.

This is a real step beyond "just a brace balance check": four files have now
passed a real Qt6 compiler/linter, and the non-Quickshell parts (imports,
general QML syntax) of the remaining two were verified as well. Real
runtime/render verification is now done in CI (see above) — the remaining
limitation is only visual pixel accuracy and interaction testing.

## Running it

Inside the image (the real path since Layer 7):

```sh
qs -p /usr/share/navigator/shell/shell.qml
```

From the repository, while developing:

```sh
cd shell
qs -p shell.qml
```

Running it by hand is generally unnecessary: the `exec-once` in
`hyprland/hyprland.conf` starts the shell when the session opens (see
`hyprland/README.md`, "Autostart"). CI no longer starts it by hand either —
it verifies that Hyprland's `exec-once` genuinely works.

## Static analysis (now, in any Qt6 environment)

```sh
cd shell
for f in *.qml; do qt6-qmllint "$f" || /usr/lib/qt6/bin/qmllint "$f"; done
```

(The package name varies by distribution — `qt6-declarative-dev-tools` on
Debian/Pardus, something like `qt6-qtdeclarative-devel` on Fedora.)

## Scope (future)

- ~~Top panel: workspace indicator, clock~~ — real (the workspace indicator
  is now bound to live Hyprland data)
- ~~AI assistant panel — a real implementation~~ — genuinely wired to
  `ai-stack/router`, verified in CI (see "AssistantPanel — real
  ai-stack/router integration")
- ~~Adding `ai-stack` to `image/Containerfile` as a real layer~~ — Layer 5
  is now real, and CI verifies it with `/usr` read-only
- ~~Layering `shell/` into the image~~ — Layer 7 is now real
- ~~Hyprland starting the shell automatically (`exec-once`)~~ — added, and
  CI genuinely verifies the autostart
- Bottom panel / notification centre
- Application launcher (a custom launcher to replace wofi)
- ~~Real Hyprland IPC integration (detecting active/occupied workspaces)~~ —
  `WorkspaceIndicator` is now bound to `Quickshell.Hyprland`, and CI
  verifies it on a real compositor

## Status

Phase 2 — the first QML files were written (`shell.qml`, `Theme.qml`,
`Bar.qml`, `Clock.qml`, `WorkspaceIndicator.qml`, `AssistantToggle.qml`).
Static analysis was done with the real Qt6 `qmllint` — four completely
clean, one (`WorkspaceIndicator.qml`) where a real warning (unqualified id
access) was found and fixed with `pragma ComponentBehavior: Bound`, and two
(`shell.qml`, `Bar.qml`) verified for their non-Quickshell parts. In Phase 4
it was run against a real Hyprland compositor in CI: `qs -p shell.qml`
genuinely started and `Bar.qml` was mapped as a real layer-shell surface
(verified with `hyprctl layers`) — see the "Runtime verification on a real
compositor" section above. **`AssistantToggle` is now genuinely wired to
`ai-stack/router`** (`AssistantPanel.qml`, new) — verified end to end in the
same CI run (see "AssistantPanel — real ai-stack/router integration"), and
the `/usr/share/navigator/ai-stack/router` path the panel invokes now comes
from the image itself (Containerfile Layer 5). Remaining: visual pixel
accuracy, real Hyprland IPC (workspace/window data), and click/interaction
tests.
