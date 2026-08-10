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
- `gtk/` — placeholder for GTK3/GTK4 theme assets (Phase 2).
- `qt/` — placeholder for Qt5/Qt6 (qt5ct/qt6ct) theme assets (Phase 2).

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
plain checkout in seconds. It asserts two things:

- every palette colour still appears in each logo, and
- each logo contains **no colour that is neither in the palette nor listed as
  a documented derivation**. The second half is what stops the palette
  quietly ceasing to be the source of truth — a hand-picked hex is caught even
  though nothing is "missing".

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

Layer 3 of `image/Containerfile` takes **only `palette.json`** from here into
the image → `/usr/share/navigator/theme/palette.json`. `gtk/` and `qt/` are
still empty skeletons (containing only a `.gitkeep`) and so are not layered:
putting empty directories into the image would make a non-existent GTK/Qt
theme look as though it were there.

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

Phase 1 — the palette definition is real and now in the image; the wallpaper
is real too (the brand image, in the image, verified by screenshot). `gtk/`
and `qt/` are still empty skeletons. Real GTK/Qt theme production (icon set,
cursor theme, GTK CSS, Qt Kvantum/QQC2 style) will be tackled as part of
Phase 2.
