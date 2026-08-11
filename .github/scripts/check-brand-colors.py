#!/usr/bin/env python3
"""Verify that the brand and theme assets still use the palette's colours.

theme/palette.json is the machine-readable single source. Several files repeat
those hexes BY HAND — hyprland/hyprland.conf, shell/Theme.qml, the logos, and
the GTK and Qt theme files. That duplication can drift silently, which is
exactly the failure this repository refuses to leave unguarded.

The compositor and shell copies are checked inside a booted VM by
build-disk-and-boot-test.yml, because there the point is to verify what the
*image* ships. The files here get this check instead: it runs on a plain
checkout in seconds, with no VM.

Two rules per asset, and the second matters more than the first:

  * every colour the asset is REQUIRED to carry is present, and
  * the asset contains NO colour that is neither in the palette nor a
    documented derivation.

The second is what catches a hand-picked hex — a failure where nothing is
missing, so a presence-only check would stay green while the palette quietly
stopped being the source of truth.

Why a script in the repository rather than a `run:` block: the same reason as
the screenshot scripts — its failure paths can be exercised locally, without
spending a CI round.

Usage:
    check-brand-colors.py [--palette theme/palette.json] [asset ...]

Exit status is 1 if any asset fails either rule.
"""
import argparse
import json
import re
import sys

# Colours the logos derive from the palette rather than using directly: the
# lit and shaded halves of the gold north point, and the lighter stop of the
# sky gradient. They are intentionally not in palette.json — asserting them
# there would mean the palette claiming ownership of a shading detail internal
# to one asset.
LOGO_DERIVED = {"f2e6c0", "c8b47e", "18223d"}

# require: which palette group the asset must carry in full.
# extra:   hexes allowed beyond the palette, with a reason above.
#
# The logos carry the brand and must show every brand colour. The theme files
# carry the interface, so they must define every "ui" surface — but they are
# also allowed the brand colours, since accents, links and focus rings are
# where the brand shows up in a widget theme.
ASSETS = {
    "theme/logo.svg": {"require": ["colors"], "extra": LOGO_DERIVED},
    "theme/logo-wordmark.svg": {"require": ["colors"], "extra": LOGO_DERIVED},
    "theme/gtk/gtk-3.0/gtk.css": {"require": ["ui"], "extra": set()},
    "theme/gtk/gtk-4.0/gtk.css": {"require": ["ui"], "extra": set()},
    "theme/qt/qt6ct/colors/Navigator.conf": {"require": ["ui"], "extra": set()},
}

# Both #RRGGBB and Qt's #AARRGGBB. The alpha-first form has to be handled
# explicitly: a plain six-digit pattern silently matches nothing in a Qt
# colour scheme, which would have left that file unchecked while the run
# still went green.
HEX_RE = re.compile(r"#([0-9a-fA-F]{8}|[0-9a-fA-F]{6})\b")


def hexes_in(text: str) -> set[str]:
    found = set()
    for h in HEX_RE.findall(text):
        found.add((h[2:] if len(h) == 8 else h).lower())
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--palette", default="theme/palette.json")
    ap.add_argument("assets", nargs="*", default=None)
    args = ap.parse_args()
    paths = args.assets or list(ASSETS)

    palette = json.load(open(args.palette, encoding="utf-8"))
    groups = {
        g: {name: spec["hex"].lstrip("#").lower() for name, spec in palette.get(g, {}).items()}
        for g in ("colors", "ui")
    }
    known = {h for grp in groups.values() for h in grp.values()}

    for g, members in groups.items():
        print(f"palette[{g}]: " + "  ".join(f"{n}=#{h}" for n, h in sorted(members.items())))

    failures = []
    for path in paths:
        rule = ASSETS.get(path, {"require": ["colors"], "extra": set()})
        try:
            found = hexes_in(open(path, encoding="utf-8").read())
        except OSError as e:
            failures.append(f"{path}: could not be read ({e})")
            continue

        if not found:
            # An asset with no colours at all is almost certainly a path typo
            # or a file that stopped being what this check thinks it is.
            failures.append(f"{path}: no colours found at all — is this still the right file?")
            continue

        for group in rule["require"]:
            missing = {n: h for n, h in groups[group].items() if h not in found}
            if missing:
                failures.append(
                    f"{path}: missing palette[{group}] colours -> "
                    + ", ".join(f"{n} (#{h})" for n, h in sorted(missing.items()))
                )

        stray = sorted(found - known - rule["extra"])
        if stray:
            failures.append(
                f"{path}: colours that are neither in the palette nor documented as derived -> "
                + ", ".join("#" + s for s in stray)
                + "  (add them to palette.json, or to this script with a reason)"
            )

        if not any(f.startswith(f"{path}:") for f in failures):
            print(f"OK: {path} — {len(found)} distinct colours, all accounted for.")

    if failures:
        print("\nERROR: the assets are out of sync with the palette:")
        for f in failures:
            print("  -", f)
        return 1

    print(f"OK: all {len(paths)} assets are in sync with {args.palette}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
