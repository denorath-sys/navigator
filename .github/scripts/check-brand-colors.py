#!/usr/bin/env python3
"""Verify that the brand assets still use the palette's colours (stdlib-only).

theme/palette.json is the machine-readable single source of the brand colours.
Several files repeat those hexes BY HAND: hyprland/hyprland.conf,
shell/Theme.qml, theme/logo.svg and theme/logo-wordmark.svg. That duplication
can drift silently, which is exactly the failure this repository tries not to
allow.

The compositor/shell side of that duplication is already checked inside a
booted VM by build-disk-and-boot-test.yml, because there the point is to
verify the *image's* copies rather than the repository's. The logo cannot be
checked there: it is deliberately not in the image (nothing at runtime needs
it), so it gets this check instead — which runs on a plain checkout in
seconds, with no VM.

Why a script in the repository rather than a `run:` block: the same reason as
the screenshot scripts — it can be exercised locally, including its failure
paths, without spending a CI round.

Usage:
    check-brand-colors.py [--palette theme/palette.json] [asset ...]

Exit status is 1 if any asset is missing a palette colour.
"""
import argparse
import json
import re
import sys

# Colours the logos derive from the palette rather than using directly: the
# lit/shaded halves of the gold north point and the sky gradient's lighter
# stop. They are intentionally not in palette.json — checking them here would
# mean asserting a design detail the palette does not claim to own.
DERIVED = {"f2e6c0", "c8b47e", "18223d"}

DEFAULT_ASSETS = [
    "theme/logo.svg",
    "theme/logo-wordmark.svg",
]


def hexes_in(text: str) -> set[str]:
    return {h.lower() for h in re.findall(r"#([0-9a-fA-F]{6})\b", text)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--palette", default="theme/palette.json")
    ap.add_argument("assets", nargs="*", default=None)
    args = ap.parse_args()
    assets = args.assets or DEFAULT_ASSETS

    palette = json.load(open(args.palette, encoding="utf-8"))
    wanted = {name: spec["hex"].lstrip("#").lower() for name, spec in palette["colors"].items()}

    print(f"palette ({args.palette}): " + "  ".join(f"{n}=#{h}" for n, h in sorted(wanted.items())))

    failures = []
    for path in assets:
        try:
            found = hexes_in(open(path, encoding="utf-8").read())
        except OSError as e:
            failures.append(f"{path}: could not be read ({e})")
            continue

        missing = {n: h for n, h in wanted.items() if h not in found}
        if missing:
            failures.append(
                f"{path}: missing palette colours -> "
                + ", ".join(f"{n} (#{h})" for n, h in sorted(missing.items()))
            )

        # A hex that is neither in the palette nor a documented derivation is
        # most likely a colour someone hand-picked; say so rather than letting
        # the palette quietly stop being the source of truth.
        stray = sorted(found - set(wanted.values()) - DERIVED)
        if stray:
            failures.append(
                f"{path}: colours that are neither in the palette nor documented as derived -> "
                + ", ".join("#" + s for s in stray)
                + "  (add them to palette.json, or to DERIVED in this script with a reason)"
            )

        if not missing and not stray:
            print(f"OK: {path} uses only palette colours (plus documented derivations).")

    if failures:
        print("\nERROR: the brand assets are out of sync with the palette:")
        for f in failures:
            print("  -", f)
        return 1

    print("OK: every brand asset is in sync with theme/palette.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
