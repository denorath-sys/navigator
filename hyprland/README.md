# hyprland/

The compositor layer of the Navigator desktop:
[Hyprland](https://hyprland.org) (Wayland).

- `hyprland.conf` — the Phase 1 base configuration: keybindings, workspace
  behaviour, window management and animation settings.
- Colour values kept in sync with the visual identity
  (`theme/palette.json`) — the active border gradient and so on — are
  hard-coded here; they could later be wired to a script that generates them
  from the theme files. This duplication is now **genuinely verified in CI**
  — the `col.active_border` gradient/angle and the `shadow` colour of the
  `hyprland.conf` in the image are compared against the `palette.json` in the
  image (see below).
- The Super+Space shortcut was genuinely wired to `ai-stack/router` in
  Phase 4 (`qs ipc call assistant toggle` → `shell/AssistantPanel.qml`).
- Autostart via `exec-once` (see below).

## Autostart (`exec-once`)

For a long time this file had no `exec-once` at all — nothing was starting
the components present in the image. Once the shell entered the image with
Layer 7, two entries were added:

| Command | Why |
|---|---|
| `qs -p /usr/share/navigator/shell/shell.qml` | The Navigator shell (the path Layer 7 installs it to) |
| `/usr/libexec/polkit-mate-authentication-agent-1` | Without an agent, operations requesting authorisation from the GUI are silently denied without ever asking the user |
| `hyprpaper` | The Navigator wallpaper; without it the desktop was showing the stock Hyprland image |

**Deliberately not added**, with the reasoning also written inside the
config:

- **waybar** — Navigator has its own top panel (`shell/Bar.qml`); running
  both would stack two panels on top of each other.
- **hypridle** — it requires its own config file (`hypridle.conf`), which
  Navigator has not written yet. Starting it without a config would mean a
  daemon that gives up in the first second. (**hyprpaper** was absent for a
  long time for the same reason; it has now joined the list because both its
  `hyprpaper.conf` and the wallpaper asset exist — see below.)
- **NetworkManager, pipewire, wireplumber** — these are managed by systemd
  (a system service and socket-activated user services), and are not the
  compositor's job.

### `hyprpaper.conf` — the wallpaper

`hyprpaper.conf` follows the same path as `hyprland.conf`: it is copied via
`/etc/skel` into a new user's `~/.config/hypr/`, so the user can change the
wallpaper and their choice is not overwritten by image updates.

The asset is `theme/wallpaper.png` (the brand image, placed at
`/usr/share/navigator/theme/wallpaper.png` by Layer 3). For details, and for
how it is verified to really appear on screen, see `theme/README.md`,
"Wallpaper".

The empty monitor field in the `wallpaper = , <path>` line means "all
monitors"; naming a monitor would not be portable (in CI's QEMU VM the
monitor is called `Virtual-1`, and it is something else on real hardware).

CI verifies two separate things: whether the hyprpaper process is really up,
and whether `hyprctl hyprpaper listloaded` reports Navigator's wallpaper.
The real proof, though, is visual — the screenshot is compared block by
block against `theme/wallpaper.png` (see `theme/README.md`); if hyprpaper
never starts, or a different image is shown, that assertion fails.

### `exec-once` targets are verified in CI

Hyprland **silently swallows** an `exec-once` that is misspelled or has
disappeared through a package change: the compositor still comes up, the
desktop merely starts incomplete, and no test breaks. CI therefore parses
the `exec-once` lines out of the `hyprland.conf` in the image and checks
that every target is genuinely executable in the image.

Quickshell is also no longer started **by hand** in CI — Hyprland's own
`exec-once` starts it and the test verifies that. (Had it also been started
by hand there would be a second instance, and it would become unclear which
instance `qs ipc` calls were reaching.)

## Installation path in the image (Layer 4)

Layer 4 of `image/Containerfile` places this file into the image as
`/etc/skel/.config/hypr/hyprland.conf`. Because `useradd` copies `/etc/skel`
into the home directory when creating a new account, every new Navigator
user starts with this config; afterwards they can freely modify their own
`~/.config/hypr/hyprland.conf`, and image updates do **not** overwrite that
file (`/etc/skel` is read only at account creation time).

It was not assumed that this mechanism really works for accounts created by
bootc-image-builder — it was measured: CI first asked as a diagnostic
([run 30664668160](https://github.com/denorath-sys/navigator/actions/runs/30664668160))
and got a real answer — `navtest`'s home directory is `/var/home/navtest`
(the ostree layout) and it contains `.config/hypr/hyprland.conf` alongside
`.bashrc`/`.bash_profile`, byte-identical to the one in `/etc/skel`. Since
the measurement was conclusive, the check is now an **assertion**: if bib or
the base image changes this behaviour, the test breaks.

## Phase 2 — static syntax review

Because the development environment is Debian/Pardus-based (Hyprland is not
packaged on that distribution), it could not be run in a real Hyprland
compositor session — instead `hyprland.conf` was reviewed statically, line
by line, against Hyprland's documented `hyprlang` syntax:

- Brace balance was checked automatically: **OK**
- The `general`, `decoration` (with nested `blur`/`shadow`), `animations`,
  `dwindle` and `input` (with nested `touchpad`) blocks conform to current
  Hyprland syntax
- ⚠️ **This assessment about the `gestures` block was WRONG** — see "The
  real error the static review missed" below
- Variables (`$mainMod`, `$terminal` and so on) are defined before use — the
  ordering is correct (Hyprlang does simple text substitution)
- All `bind`/`bindm` lines use valid dispatcher names

**Conclusion:** no syntax error was found — **but that conclusion was
incomplete.**

## The real error the static review missed

`gestures { workspace_swipe = true }` was syntactically flawless, and had
been documented that way in Hyprland for years. But **Hyprland 0.51 rewrote
the gesture system and removed the option**; the version in the image
(0.51.1) produced a real config error when it saw it:

```
Config error in file /var/roothome/.config/hypr/hyprland.conf at line 113:
config option <gestures:workspace_swipe> does not exist.
```

This error sat on the user's screen as a **red error banner**. Not because
there was no way to catch it — there were three separate checks, and all
three stayed silent:

1. The static syntax review: valid as far as hyprlang is concerned, and it
   has no way of knowing whether an option exists.
2. The `hyprctl getoption` checks in CI: they asked about only five specific
   options, and the faulty one was not among them.
3. `grep -i "config error" /root/hyprland.log` in CI: it **printed
   "(none)"** — that is, it gave false assurance. Hyprland does not write
   this error to that log with that wording.

What surfaced it was **the first screenshot from the visual correctness
test**: the banner was sitting at the top of the screen. The lesson applies
generally in this project: if a component's output is visual, textual checks
staying silent does not show that it works.

The fix was in two parts: the new syntax in the config
(`gesture = 3, horizontal, workspace`), and a real assertion that asks the
compositor directly (`hyprctl configerrors`) in place of the useless log
grep in CI.

**And that assertion was written wrong on the first attempt** — falling into
the same trap once more: the output format was NOT MEASURED, and a "no
errors" string was expected. Hyprland 0.51 prints nothing at all in the
clean case (empty output), so the check went red even though the config had
been fixed. The rule is now based on measurement: **empty OR "no errors" =
clean.**

This time the check is also proven not to be vacuously green within the same
run: a non-existent option is deliberately added to the config and
`hyprctl reload` is run, `configerrors` is verified to genuinely speak up,
and then it is reverted and the cleanliness re-checked. Without that
self-test, the "empty output = clean" rule would stay green even if the
command never ran at all.

**An open note, now being measured:** workspace switching with
`mouse_down`/`mouse_up` uses `e+1`/`e-1` — that means "go to the next/previous
**empty** workspace", not "the next workspace in order". Whether that is
deliberate was unsettled for a simple reason: nothing could turn a wheel in
the test VM, so the question could only be argued from documentation.

It can be asked now, and asking it took two rounds of finding out that the
test VM could not ask it.

The input injection added for the click test grew a `scroll` action with a
held modifier, and the boot test puts a window on workspace 2 first — without
that the two readings give the same answer and the run proves nothing — then
turns Super+wheel from workspace 1. Landing on 3 means `e+1` skipped the
occupied workspace and the config does what it says; landing on 2 means it
does not.

**Round one (run 32424241261)** moved nothing, and taught something else
instead: an ordinary application window does open in this VM. kitty reached
workspace 2 under llvmpipe, which had never been tested either.

**Round two (run 32426895684)** separated the two ways that could fail, with
throwaway binds added at runtime so the mechanism was under test rather than
the config: an unmodified wheel bound to workspace 5 moved nothing, while
Super+F12 bound to workspace 6 worked. The modifier arrives; the wheel does
not. That is what an absolute pointing device with no wheel button looks like
from inside the guest — the tablet is not a mouse.

So the VM now also has `-device virtio-mouse-pci,id=navwheel`, and wheel
events are addressed to it by id rather than left to QEMU's first-match
routing, which would otherwise be free to hand a left click to a relative
mouse that is not where the pointer was put.

Diagnostic still, on purpose: what the result SHOULD be is a design question,
and answering it is not the same as observing it.

**The limitation at the time (no longer applicable):** this was a static
review and no real compositor was run — runtime verification had been left
to Phase 3. See below.

## Phase 4 — runtime verification on a real compositor (CI)

The `hyprland-test` job in
`.github/workflows/build-disk-and-boot-test.yml` now **genuinely loads**
this file (`hyprland.conf`) into a real Hyprland compositor, inside a real
Navigator disk image — a running compositor, not a static review.

Since Layer 4, the file under test is **the image's own file**: previously
it was copied from the runner to the VM with `scp` (a "CI simulation"), and
now it is taken from `/etc/skel/.config/hypr/hyprland.conf` into
`/root/.config/hypr/` (the test runs as root; since `/etc/skel` is only
copied to new accounts, it has to be taken by hand for root). A separate
step also verifies that the file in the image is **byte-identical** to the
one in the repository — so the test does not stay green if the image is
stale.

Verification is done by checking with `hyprctl getoption -j` whether values
in the config that **differ** from Hyprland's own defaults are genuinely in
effect (the defaults were verified in the Hyprland source —
`ConfigValues.cpp` — so that a match is not a coincidence):

| Setting | Default | `hyprland.conf` | Real result in CI |
|---|---|---|---|
| `general:border_size` | 1 | 2 | ✅ 2 |
| `decoration:rounding` | 0 | 10 | ✅ 10 |
| `decoration:blur:passes` | 1 | 2 | ✅ 2 |
| `general:resize_on_border` | false (0) | true | ✅ 1 |
| `input:touchpad:natural_scroll` | false (0) | true | ✅ 1 |

In addition, `hyprctl binds -j` verified that the
`$mainMod, RETURN, exec, $terminal` binding is genuinely loaded (the RETURN
key running `kitty`), and no "config error"/"syntax error" line was found in
`/root/hyprland.log`.

**Known remaining limitation:** this is proof that the config is *parsed and
applied* — it was not separately tested that the bindings actually fire on
real keyboard/mouse input (e.g. really pressing Super+Enter and kitty
opening), nor that the visual rendering (blur/shadow/animation) looks
correct; over a VNC display in a headless CI run that requires extra
complexity and was not considered necessary for now.

## Status

Phase 2 — passed the static syntax review. In Phase 4 it was **genuinely
loaded into and verified against a real Hyprland compositor** in CI (see
above) — it is no longer only a static review.
