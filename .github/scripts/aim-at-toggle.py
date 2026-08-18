#!/usr/bin/env python3
"""Work out the screen pixel to click for the assistant toggle.

    aim-at-toggle.py LAYERS_JSON RECT_JSON

LAYERS_JSON is `hyprctl layers -j` from inside the guest: the compositor's
view of where the bar's layer surface sits on screen. RECT_JSON is the
shell's own `toggleRect`: where the button sits inside that surface. Neither
is guessed, and neither is hardcoded — a hardcoded pixel would keep passing
after the button moved, which is the failure the click test exists to catch.

Prints "X Y" on stdout. Everything else goes to stderr and exits 1.

This lives in the repository rather than in a run: block because the first
version did not, and it cost a boot test. It was a heredoc into /tmp that
read both JSON documents from one stdin stream, split on the first newline —
and `hyprctl layers -j` prints multi-line JSON, so the first document was cut
to its opening brace and the parse died on it (run 32087531703). An input
protocol nobody could exercise locally had exactly one failure mode nobody
saw. The paths below are exercised instead.
"""

import json
import sys


def die(message):
    print(message, file=sys.stderr)
    raise SystemExit(1)


def load(path, what):
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except OSError as err:
        die(f"cannot read the {what}: {err}")
    if not text.strip():
        die(f"the {what} is empty ({path})")
    try:
        return json.loads(text)
    except json.JSONDecodeError as err:
        # The first line is worth printing: when this goes wrong it is
        # usually because something non-JSON — an ssh warning, a shell
        # message — was captured along with the document.
        first = text.splitlines()[0][:200] if text.splitlines() else ""
        die(f"the {what} is not JSON ({err}); it starts: {first!r}")


def find_surface(layers, namespace):
    """Every layer surface the compositor reports, flattened.

    hyprctl layers -j is keyed by monitor, then by level, then a list:
    {"HDMI-A-1": {"levels": {"2": [{"namespace": "quickshell", ...}]}}}
    """
    found = []
    seen = []
    if not isinstance(layers, dict):
        die(f"the layer list is not an object keyed by monitor: {type(layers).__name__}")
    for monitor in layers.values():
        if not isinstance(monitor, dict):
            continue
        for level in monitor.get("levels", {}).values():
            for surface in level or []:
                seen.append(surface.get("namespace"))
                if surface.get("namespace") == namespace:
                    found.append(surface)
    if not found:
        die(
            f"no layer surface with namespace {namespace!r}; "
            f"the compositor reports: {sorted(n for n in seen if n) or 'none at all'}"
        )
    if len(found) > 1:
        # Not fatal, but it decides where the click lands, so say so.
        print(
            f"note: {len(found)} surfaces named {namespace!r}; using the last",
            file=sys.stderr,
        )
    return found[-1]


def main(argv):
    if len(argv) != 3:
        die(f"usage: {argv[0]} LAYERS_JSON RECT_JSON")

    layers = load(argv[1], "layer list")
    rect = load(argv[2], "toggle rect")

    surface = find_surface(layers, "quickshell")

    missing = [k for k in ("x", "y", "w", "h") if k not in surface]
    if missing:
        die(f"the layer surface has no {', '.join(missing)}: {surface!r}")
    missing = [k for k in ("x", "y", "w", "h") if k not in rect]
    if missing:
        die(f"the toggle rect has no {', '.join(missing)}: {rect!r}")

    if rect["w"] <= 0 or rect["h"] <= 0:
        die(f"the toggle has no area to click: {rect!r}")

    print(surface["x"] + rect["x"] + rect["w"] // 2,
          surface["y"] + rect["y"] + rect["h"] // 2)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
