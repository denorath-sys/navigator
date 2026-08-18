#!/usr/bin/env python3
"""Work out the screen pixel to click for the assistant toggle.

    aim-at-toggle.py LAYERS_JSON RECT_JSON NAMESPACE

LAYERS_JSON is `hyprctl layers -j` from inside the guest: the compositor's
view of where the bar's layer surface sits on screen. RECT_JSON is the
shell's own `toggleRect`: where the button sits inside that surface. NAMESPACE
is the layer surface to aim at, "navigator-bar" for the bar. Nothing here is
guessed and nothing is hardcoded — a hardcoded pixel would keep passing after
the button moved, which is the failure the click test exists to catch.

The namespace has to be given because it has to be right: Quickshell names
every window it maps "quickshell" unless told otherwise, so the bar and the
assistant panel were the same name from outside, and picking one of them by
position in a list aimed at x=2063 on a 1280-wide screen (run 32089480998).
Bar.qml and AssistantPanel.qml name themselves now.

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
        # Fatal on purpose. Picking one of several is what produced an
        # off-screen coordinate in the first place, and a duplicate namespace
        # means the shell is not saying what it means.
        die(
            f"{len(found)} layer surfaces are named {namespace!r}; "
            "the name is supposed to identify one window"
        )
    return found[0]


def main(argv):
    if len(argv) != 4:
        die(f"usage: {argv[0]} LAYERS_JSON RECT_JSON NAMESPACE")

    layers = load(argv[1], "layer list")
    rect = load(argv[2], "toggle rect")

    surface = find_surface(layers, argv[3])

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
