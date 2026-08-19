# theme/

Navigator's visual identity: a nautical/sky aesthetic themed around the
compass, the lighthouse, the Orion constellation and the North Star.

## Contents

- `palette.json` — the brand colour palette (teal `#4fd1c5`, purple
  `#8b7cf6`, gold `#e8d9a8`, navy base `#0b0f1a`) and gradient definitions.
  Kept in manual sync with `hyprland/hyprland.conf`.
- `logo.svg` — the Navigator mark (see below).
- `logo-wordmark.svg` — the horizontal lockup: mark + wordmark.
- `wallpaper.png` — the brand wallpaper (see "Wallpaper" below).
- `gtk/` — GTK3 and GTK4/libadwaita colour overrides (see "The widget theme").
- `qt/` — the qt6ct configuration and Qt colour scheme.

## The mark

An eight-point compass rose whose north point is the North Star, on the navy
of the night sky — the same nautical/sky identity as the palette and the
wallpaper.

Two things in it are deliberate rather than decorative:

- **Each arm is split into a lit half (teal) and a shaded half (purple), and
  the light stays on the same side of every arm.** That is what gives a
  compass rose depth; light applied inconsistently makes the star read as
  flat noise. The first draft used a diagonal gradient across the whole mark
  and had exactly that problem.
- **The intercardinal points are narrow and dimmed.** At full size they fill
  the rose out; at small sizes they recede so the four cardinals still lead.

It was checked by rendering, not by eye on the source: at 48px the navy disc,
the bezel and the gold north point still read, which is enough to recognise
it in a tab or a launcher.

The colours are repeated here by hand, exactly as they are in
`hyprland/hyprland.conf` and `shell/Theme.qml` — and, like those two, that
duplication **is verified in CI**.

The logos are checked separately from the compositor and shell copies, because
they are deliberately not in the image (nothing at runtime needs a logo), so
the in-VM check cannot see them.
[`.github/workflows/brand-check.yml`](../.github/workflows/brand-check.yml)
runs [`check-brand-colors.py`](../.github/scripts/check-brand-colors.py) on a
plain checkout in seconds, over the logos **and** the GTK/Qt theme files. It
asserts two things per asset:

- the palette group that asset is required to carry is present in full — the
  brand `colors` for a logo, the `ui` surfaces for a theme file — and
- the asset contains **no colour that is neither in the palette nor listed as
  a documented derivation**. The second half is what stops the palette quietly
  ceasing to be the source of truth — a hand-picked hex is caught even though
  nothing is "missing".

The extractor understands Qt's `#AARRGGBB` as well as `#RRGGBB`. That is not
a detail: a six-digit-only pattern matches *nothing* in a Qt colour scheme, so
the Qt file would have gone unchecked while the run still went green.

The derivations it does allow are named in the script with a reason: the lit
and shaded halves of the gold north point, and the lighter stop of the sky
gradient. Those are logo-internal shading the palette does not claim to own.

As the repository's convention requires, the check was proven to fail before
it was trusted: a drifted palette, a hand-picked colour in a logo and a
missing asset all exit 1, and CI re-proves this on every run by injecting a
deliberate deviation into a throwaway copy and requiring rejection.

`logo-wordmark.svg` keeps its text as live text rather than outlines, so it
stays diffable in the repository. That means it renders with whatever
sans-serif the viewer has; convert the text to paths before using it anywhere
the exact letterforms matter.

## Installation path in the image (Layer 3)

Layer 3 takes the machine-readable **data** from here into the image:
`palette.json` and `wallpaper.png` → `/usr/share/navigator/theme/`.

`gtk/` and `qt/` take a different route on purpose. They are user
**configuration**, not data, so Layer 4 installs them under `/etc/skel` —
exactly the reasoning `hyprland.conf` follows. A user must be able to restyle
their desktop and keep that across image updates, which `/usr/share` would
not allow.

## The widget theme

`gtk/` and `qt/` make GTK and Qt applications look like they belong to the
same desktop as the shell. Navigator ships two GTK3 apps of its own — waybar
and wofi — and everything else the user installs lands in one of these two
toolkits.

**None of it is a widget theme, on purpose.** Each file redefines the named
colours its toolkit already resolves at load time:

| File | Mechanism |
|---|---|
| `gtk/gtk-3.0/gtk.css` | GTK3's `theme_bg_color`, `theme_fg_color`, `borders`, … |
| `gtk/gtk-3.0/settings.ini` | dark preference, icon and cursor theme |
| `gtk/gtk-4.0/gtk.css` | libadwaita's `window_bg_color`, `accent_bg_color`, … |
| `qt/qt6ct/colors/Navigator.conf` | a Qt colour scheme: three lists of 21 `QPalette` roles |
| `qt/qt6ct/qt6ct.conf` | selects that scheme and the Fusion style |

Forking a real theme would mean owning every widget change GTK or libadwaita
makes afterwards. Redefining colours means upstream can rewrite a widget and
Navigator still looks right.

Three decisions worth their reasoning:

- **Fusion for Qt.** It is the style that honours a custom palette on every
  widget; the platform styles override parts of it and would leave Qt apps
  half-themed next to the rest of the desktop.
- **`qt5ct` is not installed.** Navigator ships no Qt5 application, and
  shipping configuration for a toolkit that is not there is exactly the kind
  of "looks done" this repository avoids.
- **Destructive actions keep the toolkit's red.** Gold carries warnings and
  teal carries success, but a brand colour must never be the only signal that
  an action destroys something.

`QT_QPA_PLATFORMTHEME=qt6ct` is exported from `hyprland/hyprland.conf`;
without it `~/.config/qt6ct/` is read by nothing. GTK needs no equivalent —
with no settings daemon running it reads `settings.ini` itself — and
`GTK_THEME` is deliberately **not** set, because it would override that file
and take the choice away from the user.

### Where the interface colours come from

A four-colour brand palette does not contain a foreground, surfaces or
borders, and a widget theme needs all three. Rather than invent them inside
each theme file — three files quietly drifting apart is precisely the failure
this directory is built to prevent — `palette.json` grew a **`ui`** section
alongside `colors`:

| | |
|---|---|
| `text` `#e6ecf5` | near-white with a blue cast, so it belongs to the night sky |
| `text_muted` `#97a3b8` | secondary text, placeholders, disabled labels |
| `surface` `#121826` | text views, entries, tooltips, menus |
| `surface_alt` `#0f1522` | buttons, header bars, alternating rows |
| `border` `#1d2740` | separators and widget borders |

`colors` is the brand and appears in the logo, wallpaper and compositor; `ui`
is the interface. The GTK files may use both — accents, links and focus rings
are where the brand shows up in a widget theme — and the CI check enforces
exactly that split.

Everything in `ui` except `text` is a shade of navy. They are literal hexes
rather than computed, because a Qt colour scheme cannot express a formula and
GTK and Qt reading different numbers would defeat the point. Where GTK *can*
derive a value it does, with `shade()` and `alpha()`, so no hand-picked hex
appears in the CSS.

### The colour duplication is now genuinely verified

`palette.json` is the machine-readable single source, but the same hex
values are repeated **by hand** in `hyprland/hyprland.conf` and
`shell/Theme.qml`. That was a duplication that could drift silently; CI now
compares them on every run (`build-disk-and-boot-test.yml`, the
"Layer 3/4/7" step):

- `col.active_border` gradient stops **and** angle ↔
  `gradients.assistant.stops` / `.angle`
- `decoration:shadow:color` ↔ `colors.navy`
- `teal`/`purple`/`gold`/`navy` in `shell/Theme.qml` ↔ `colors.*`

Since Layer 7, **all three are read from the image** (`palette.json`,
`hyprland.conf`, `Theme.qml`) — meaning what is compared is the content the
user will actually run. The check was proven to do real work by injecting a
deliberate deviation — all three of the gradient stop, the angle and the
`Theme.qml` deviations were caught.

Real CI result
([run 30664668160](https://github.com/denorath-sys/navigator/actions/runs/30664668160)):

```
OK: both are byte-identical to the files in the repo (image is not stale).
OK: palette.json <-> hyprland.conf (from image) <-> shell/Theme.qml in sync.
    teal=4fd1c5 purple=8b7cf6 gold=e8d9a8 navy=0b0f1a, gradient angle=45deg
```

## Wallpaper

`wallpaper.png` (1672x941) is Navigator's brand image: a night sky, a
constellation, mountain silhouettes and a teal-green wave, with the
"Navigator OS" logotype on the right-hand edge. It is the visual counterpart
of the nautical/sky identity in `palette.json`.

In the image: **Layer 3** of `image/Containerfile` places the file at
`/usr/share/navigator/theme/wallpaper.png`. `hyprland/hyprpaper.conf`
(Layer 4, via `/etc/skel`) loads it, and the `exec-once = hyprpaper` added to
`hyprland.conf` starts hyprpaper.

**Why it was needed:** until this point Navigator was showing the **stock
Hyprland wallpaper** ("A day without Hyprland is a day wasted"), meaning the
desktop looked unbranded. No textual test could have seen this; it surfaced
the moment the first real screenshot was taken.

### There was briefly a procedural generator

Before the brand image arrived, the wallpaper was generated procedurally by
`generate-wallpaper.py` (a night-sky gradient plus Orion and the North Star,
reading its colours from `palette.json`, deterministic). Once the real brand
image was supplied, the generator was **removed** — keeping two separate
"wallpaper sources" would have been misleading. It remains in git history
(commit `0a3c4fd`), a single revert away if wanted back.

### How it is verified to really appear on screen

Claiming the wallpaper is loaded is not enough; CI compares the
**screenshot** against this file
(`.github/scripts/analyze-screenshot.py --reference=theme/wallpaper.png`).
The method: both images are divided into 24x15 blocks, the block average
colours are compared, and the **median** of the differences is taken. The
median is robust against windows covering the screen, such as the top bar
and the assistant panel; those spoil a minority of the blocks. hyprpaper's
"cover" cropping is accounted for as well (screen 16:10, image 16:9 → 5% is
cropped from the sides).

The threshold (15) is not a guess, it comes from three real measurements:

| scenario | median block difference |
|---|---|
| the same wallpaper (real screenshot vs its source) | **0.1** |
| a wrong Navigator wallpaper | 37.9 |
| the stock Hyprland wallpaper | 68.7 |

**Why not brightness:** the first version asked "is the desktop dark?"
(stock 85.3, the generated wallpaper 21.6). When the real brand image
arrived that measure collapsed — because of the bright wave in its middle,
the same band's luma is 73.0, i.e. adjacent to stock's 85.3. Brightness was
measuring only a summary of the wallpaper, not its IDENTITY; the block
comparison measures the identity.

### Known limitation: the logotype is cropped on non-wide screens

The image is 16:9 (1672x941, ratio 1.777). Because hyprpaper scales with
"cover", **5% is cropped from the sides on a 16:10 screen**, and since the
"Navigator OS" logotype sits at x≈92-97% its right-hand part is cut off (the
1280x800 VM in CI is exactly this case). There is no problem on 16:9
screens. If a fix is wanted: move the logotype slightly left, or use a
version that leaves more safe area at the edge.

## Status

The palette, the wallpaper, the logo and the widget theme are all real and
in the image. `gtk/` and `qt/` are no longer skeletons.

The **icon and cursor themes** are chosen, installed and verified, and the
distinction matters: they are adopted, not drawn. Navigator ships
**Papirus-Dark** for icons and **Breeze Dark** for cursors, both from Fedora's
own repositories, named in `settings.ini`, `qt6ct.conf` and `hyprland.conf`.

The cursor is configured as `breeze_cursors`, which looks like a typo and is
not: XCursor resolves a theme by the DIRECTORY name, and that is the directory
the package installs. Its `index.theme` calls itself "Breeze Dark". Writing
either of those two prettier names resolves to nothing at all — silently, as
these things do, which is how the first version of this shipped and how the
boot test caught it (run 32291234271).

Drawing them was never the sensible option. An icon set is hundreds of files
that cannot be derived from a four-colour palette, and a partial one would
read as partial — Navigator's icons next to Adwaita's for everything they did
not cover. Adopting finished work and saying whose it is beats a half-drawn
identity.

The one place the palette does reach them is the folders: Layer 3 of
`image/Containerfile` repoints Papirus's folder icons at its own **teal**
variants, which is exactly what `papirus-folders` does on an ordinary system
and is possible only because Papirus ships those defaults as symlinks. Being
precise about it, since this directory is otherwise strict about hexes: that
teal is Papirus's `#16a085`/`#12806a`, not Navigator's `#4fd1c5`. Recolouring
the SVGs to the brand hex is mechanical (they are flat fills) and would put
the folders under the brand check, but it means shipping altered copies of
someone else's artwork — a separate decision, not a side effect of this one.

The cursor is the smaller half and had the worse bug: `hyprland.conf` set
`XCURSOR_SIZE` and `HYPRCURSOR_SIZE` and never named a theme, so the size was
Navigator's and the cursor itself was whatever the compositor fell back to.

What makes any of this more than three lines in three config files is the
verification, and it is built around the failure these have: **a config naming
a theme that is not installed behaves exactly like one naming a theme that
is.** So the boot test reads the names out of the image's own files rather
than hardcoding them, requires GTK, Qt and Hyprland to name the same two,
requires `index.theme` and `cursors/left_ptr` to exist for them in the image,
requires the folder symlink to point at the teal variant, and — because a
variable in a config file is not a variable in a process — reads
`XCURSOR_THEME` out of the environment of the running shell that the
compositor itself started.
