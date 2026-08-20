#!/usr/bin/env python3
"""Give Papirus's folder icons Navigator's teal, at image build time.

    recolour-folder-icons.py THEME_DIR PALETTE_JSON

Papirus ships its default folders as symlinks (folder.svg -> folder-blue.svg)
so that they can be repointed, which is all papirus-folders does on an
ordinary system. Navigator repointed them at Papirus's own teal variants
first; this goes one step further and makes the folders carry the brand
colour rather than the nearest colour somebody else had.

The substitution is two hexes, because Papirus's folder SVGs are flat fills:

    #16a085  the front face   ->  the palette's teal
    #12806a  the back flap    ->  the same teal, shaded

WHERE THE SHADED TONE COMES FROM. Not from taste. Papirus's own pair encodes
a lighting decision — the flap is the face at 0.818 / 0.800 / 0.797 of its
red, green and blue — and applying those same three ratios to the brand teal
keeps that decision intact while changing the colour. For #4fd1c5 it gives
#41a79d. It is deliberately NOT added to theme/palette.json: the palette owns
the brand, not a shading detail internal to one derived asset, which is the
same line the logos' derived tones sit on (see LOGO_DERIVED in
.github/scripts/check-brand-colors.py).

The teal itself is read from the palette in the image rather than written
here, so there is exactly one place the brand colour lives.

This is a repository script rather than a line inside the Containerfile for
the reason the aiming script learned the hard way: work that cannot be
exercised without a build has exactly one failure mode, the one nobody sees.
Its guards are below and all of them are exercised in image/scripts/tests/.
"""

import json
import os
import re
import sys

# Papirus's teal pair. Substituting known hexes rather than detecting colours
# keeps this predictable: if Papirus repaints its teal variants, nothing
# matches, and the guard at the end fails the build loudly instead of shipping
# folders in somebody else's colour.
PAPIRUS_FACE = "#16a085"
PAPIRUS_FLAP = "#12806a"

VARIANT = "navigator"


def die(message):
    print(f"recolour-folder-icons: {message}", file=sys.stderr)
    raise SystemExit(1)


def shade(hex_colour, source_face=PAPIRUS_FACE, source_flap=PAPIRUS_FLAP):
    """The brand colour at the same face-to-flap ratio Papirus drew with."""
    face = [int(source_face[i:i + 2], 16) for i in (1, 3, 5)]
    flap = [int(source_flap[i:i + 2], 16) for i in (1, 3, 5)]
    base = [int(hex_colour[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(
        f"{min(255, round(b * f / c)):02x}" for b, c, f in zip(base, face, flap)
    )


def read_teal(palette_path):
    try:
        with open(palette_path, encoding="utf-8") as handle:
            palette = json.load(handle)
    except OSError as err:
        die(f"cannot read the palette: {err}")
    except json.JSONDecodeError as err:
        die(f"the palette is not JSON: {err}")
    try:
        teal = palette["colors"]["teal"]["hex"]
    except (KeyError, TypeError):
        die("the palette has no colors.teal.hex")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", teal):
        die(f"the palette's teal is not a #rrggbb hex: {teal!r}")
    return teal.lower()


def recolour_tree(theme_dir, face, flap):
    """Write folder-navigator*.svg beside every folder-teal*.svg, and point
    the plain folder names at them."""
    written = 0
    linked = 0
    for entry in sorted(os.listdir(theme_dir)):
        places = os.path.join(theme_dir, entry, "places")
        if not os.path.isdir(places):
            continue
        for name in sorted(os.listdir(places)):
            if not (name.startswith("folder-teal") and name.endswith(".svg")):
                continue
            source = os.path.join(places, name)
            try:
                with open(source, encoding="utf-8") as handle:
                    svg = handle.read()
            except OSError as err:
                die(f"cannot read {source}: {err}")

            recoloured = svg.replace(PAPIRUS_FACE, face).replace(PAPIRUS_FLAP, flap)

            suffix = name[len("folder-teal"):]          # ".svg" or "-documents.svg"
            target = os.path.join(places, f"folder-{VARIANT}{suffix}")
            with open(target, "w", encoding="utf-8") as handle:
                handle.write(recoloured)
            written += 1

            plain = os.path.join(places, f"folder{suffix}")
            if os.path.lexists(plain):
                os.remove(plain)
            os.symlink(os.path.basename(target), plain)
            linked += 1
    return written, linked


def main(argv):
    if len(argv) != 3:
        die(f"usage: {argv[0]} THEME_DIR PALETTE_JSON")
    theme_dir, palette_path = argv[1], argv[2]

    if not os.path.isdir(theme_dir):
        die(f"no icon theme at {theme_dir}")

    face = read_teal(palette_path)
    flap = shade(face)
    print(f"recolour-folder-icons: {PAPIRUS_FACE} -> {face}, {PAPIRUS_FLAP} -> {flap}")

    written, linked = recolour_tree(theme_dir, face, flap)
    if written == 0:
        die(
            f"no folder-teal*.svg anywhere under {theme_dir}. Papirus renamed its "
            "colour variants, and the folders would have stayed blue with the "
            "build still green."
        )

    # The guards, in the order they would catch a mistake: did the plain name
    # end up at our file, does that file carry the brand colour, and is any of
    # Papirus's teal still in it.
    probe_dirs = [
        os.path.join(theme_dir, entry, "places")
        for entry in sorted(os.listdir(theme_dir))
        if os.path.isdir(os.path.join(theme_dir, entry, "places"))
    ]
    for places in probe_dirs:
        plain = os.path.join(places, "folder.svg")
        if not os.path.islink(plain):
            die(f"{plain} is not a symlink; the repoint did not happen")
        target = os.readlink(plain)
        if target != f"folder-{VARIANT}.svg":
            die(f"{plain} points at {target}, not folder-{VARIANT}.svg")
        with open(plain, encoding="utf-8") as handle:
            body = handle.read()
        if face not in body:
            die(f"{plain} does not contain the brand teal {face}")
        for leftover in (PAPIRUS_FACE, PAPIRUS_FLAP):
            if leftover in body:
                die(f"{plain} still contains Papirus's {leftover}")

    print(
        f"recolour-folder-icons: recoloured {written} folder icons across "
        f"{len(probe_dirs)} sizes and repointed {linked} names"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
