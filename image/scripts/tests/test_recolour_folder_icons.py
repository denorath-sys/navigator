"""Exercises for recolour-folder-icons.py, which runs inside the image build.

The point of having these at all: the script edits somebody else's artwork in
a place that only exists during a build, and its failure mode is silent —
folders that stay the wrong colour while the build goes green. Every guard it
has is fired here, on a fake Papirus tree, in under a second.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "recolour-folder-icons.py")

_spec = importlib.util.spec_from_file_location("recolour_folder_icons", SCRIPT)
recolour = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(recolour)

# The real thing, trimmed to the parts that carry colour. Taken from
# Papirus/64x64/places/folder-teal.svg at tag 20250501.
FOLDER_TEAL = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" version="1">\n'
    ' <rect style="opacity:0.2" width="56" height="36" x="4" y="22" rx="2.8"/>\n'
    ' <path style="fill:#12806a" d="M 4,46.2 C 4,47.751 5.2488,49 6.8,49 Z"/>\n'
    ' <rect style="fill:#e4e4e4" width="48" height="22" x="8" y="16" rx="2.8"/>\n'
    ' <rect style="fill:#16a085" width="56" height="36" x="4" y="21" rx="2.8"/>\n'
    '</svg>\n'
)


class TestShade(unittest.TestCase):
    def test_papirus_pair_reproduces_itself(self):
        """The ratio is taken from Papirus's own two hexes, so applying it to
        Papirus's face has to give Papirus's flap back. If this ever fails,
        the derivation has stopped being a derivation."""
        self.assertEqual(recolour.shade("#16a085"), "#12806a")

    def test_brand_teal_gets_the_documented_tone(self):
        self.assertEqual(recolour.shade("#4fd1c5"), "#41a79d")

    def test_shade_is_darker_in_every_channel(self):
        for colour in ("#4fd1c5", "#ffffff", "#8b7cf6", "#010101"):
            shaded = recolour.shade(colour)
            for i in (1, 3, 5):
                self.assertLessEqual(
                    int(shaded[i:i + 2], 16), int(colour[i:i + 2], 16), colour
                )


class TestRecolourTree(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        self.theme = os.path.join(self.root, "Papirus")
        self.palette = os.path.join(self.root, "palette.json")
        self.write_palette("#4fd1c5")
        self.build_tree()

    def write_palette(self, teal, key="teal"):
        with open(self.palette, "w", encoding="utf-8") as handle:
            json.dump({"colors": {key: {"hex": teal}}}, handle)

    def build_tree(self, sizes=("64x64", "32x32"), names=("", "-documents")):
        for size in sizes:
            places = os.path.join(self.theme, size, "places")
            os.makedirs(places, exist_ok=True)
            for name in names:
                with open(os.path.join(places, f"folder-teal{name}.svg"), "w") as handle:
                    handle.write(FOLDER_TEAL)
                with open(os.path.join(places, f"folder-blue{name}.svg"), "w") as handle:
                    handle.write(FOLDER_TEAL.replace("#16a085", "#5294e2"))
                # Papirus ships the plain name as a symlink to a colour, which
                # is the state this has to overwrite rather than trip over.
                plain = os.path.join(places, f"folder{name}.svg")
                os.symlink(f"folder-blue{name}.svg", plain)

    def run_script(self, theme=None, palette=None):
        return subprocess.run(
            [sys.executable, SCRIPT, theme or self.theme, palette or self.palette],
            capture_output=True, text=True,
        )

    def test_happy_path(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)

        places = os.path.join(self.theme, "64x64", "places")
        plain = os.path.join(places, "folder.svg")
        self.assertEqual(os.readlink(plain), "folder-navigator.svg")

        with open(plain, encoding="utf-8") as handle:
            body = handle.read()
        self.assertIn("#4fd1c5", body)
        self.assertIn("#41a79d", body)
        self.assertNotIn("#16a085", body)
        self.assertNotIn("#12806a", body)
        # Everything that is not the folder's own colour is left alone.
        self.assertIn("#e4e4e4", body)

        # Both sizes, and the named variants alongside the plain one.
        self.assertEqual(
            os.readlink(os.path.join(self.theme, "32x32", "places", "folder-documents.svg")),
            "folder-navigator-documents.svg",
        )
        self.assertIn("recoloured 4 folder icons across 2 sizes", result.stdout)

    def test_papirus_teal_variants_renamed_away(self):
        for size in ("64x64", "32x32"):
            for name in ("", "-documents"):
                os.remove(os.path.join(self.theme, size, "places", f"folder-teal{name}.svg"))
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("renamed its colour variants", result.stderr)

    def test_missing_theme_directory(self):
        result = self.run_script(theme=os.path.join(self.root, "nope"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("no icon theme", result.stderr)

    def test_palette_without_teal(self):
        self.write_palette("#4fd1c5", key="turquoise")
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("no colors.teal.hex", result.stderr)

    def test_palette_teal_is_not_a_hex(self):
        self.write_palette("teal")
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("not a #rrggbb hex", result.stderr)

    def test_palette_missing(self):
        result = self.run_script(palette=os.path.join(self.root, "nope.json"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("cannot read the palette", result.stderr)

    def test_svg_without_papirus_teal_is_caught(self):
        """A folder-teal file that does not actually contain Papirus's teal
        would be copied through unchanged, and the brand colour would never
        reach it. The guard reads the result rather than trusting the
        substitution."""
        places = os.path.join(self.theme, "64x64", "places")
        with open(os.path.join(places, "folder-teal.svg"), "w", encoding="utf-8") as handle:
            handle.write(FOLDER_TEAL.replace("#16a085", "#123456"))
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("does not contain the brand teal", result.stderr)


if __name__ == "__main__":
    unittest.main()
