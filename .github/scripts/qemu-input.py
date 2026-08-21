#!/usr/bin/env python3
"""Inject real pointer input into a QEMU guest over QMP (stdlib-only).

Every Navigator test so far has driven the desktop from *inside* the guest —
`hyprctl dispatch`, `qs ipc call`. Those prove the compositor and the shell
agree with each other, but they cannot prove that a human pointing at a button
would hit anything: the click path itself is never exercised.

This sends the events at the hardware level instead, the same way
qemu-screendump.py takes the picture from outside. Nothing runs in the guest,
so what is tested is the whole path — virtio-tablet -> libinput -> Hyprland ->
layer surface -> the MouseArea in the QML.

QMP rather than the HMP monitor on purpose: HMP's mouse_move is relative and
tied to the legacy mouse interface, while `input-send-event` takes absolute
axes, which is what makes "click at this pixel" expressible at all. It needs
an absolute pointing device in the guest — see -device virtio-tablet-pci in
build-disk-and-boot-test.yml. Without one the events go nowhere and, worse,
QMP still reports success.

Absolute axes are a fixed 0..32767 range that QEMU maps onto the screen, so
the caller has to say how big the screen is; there is no way to ask.

Usage:
    qemu-input.py <qmp.sock> move   <W> <H> <X> <Y>
    qemu-input.py <qmp.sock> click  <W> <H> <X> <Y> [--button left|right|middle]
    qemu-input.py <qmp.sock> scroll <W> <H> <X> <Y> --direction up|down
                                    [--modifier super|ctrl|alt|shift]

There is no way to say WHICH emulated input device an event should go to.
input-send-event does take a `device`, but it names the DISPLAY device for a
multi-head setup, not the mouse — and passing an input device's qdev id to it
does not fail politely: QEMU aborts the whole VM with "Property
'qemu-fixed-text-console.device' not found" (run 32428973455). Which device
receives an event is QEMU's choice, based on what each one can handle.
    qemu-input.py <qmp.sock> key    <QCODE> [--modifier super|ctrl|alt|shift]

A wheel notch is a BUTTON in QEMU's input model, not an axis, which is why
scrolling looks like clicking here. The modifier is a real key press held
around it, because that is what a binding like `bind = SUPER, mouse_down` is
waiting for: Hyprland matches the modifier state at the moment the wheel
event arrives, and a wheel with no modifier held is simply a scroll.
"""
import json
import socket
import sys

ABS_MAX = 32767


def _abs(value: int, size: int) -> int:
    if size <= 1:
        raise ValueError(f"screen dimension must be > 1, got {size}")
    if not (0 <= value < size):
        raise ValueError(f"coordinate {value} is outside 0..{size - 1}")
    return round(value * ABS_MAX / (size - 1))


class QMP:
    def __init__(self, path: str):
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.settimeout(10.0)
        self._sock.connect(path)
        self._buf = b""
        greeting = self._recv()
        if "QMP" not in greeting:
            raise RuntimeError(f"not a QMP socket, first message was: {greeting!r}")
        self._execute("qmp_capabilities")

    def _recv(self) -> dict:
        # QMP is one JSON object per line. Events can arrive unsolicited, so
        # the caller loop skips them rather than mistaking one for a reply.
        while b"\n" not in self._buf:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise RuntimeError("QMP socket closed")
            self._buf += chunk
        line, _, self._buf = self._buf.partition(b"\n")
        return json.loads(line)

    def _execute(self, command: str, arguments: dict | None = None) -> dict:
        msg = {"execute": command}
        if arguments:
            msg["arguments"] = arguments
        self._sock.sendall((json.dumps(msg) + "\n").encode())
        while True:
            reply = self._recv()
            if "event" in reply:
                continue
            if "error" in reply:
                raise RuntimeError(f"{command} failed: {reply['error']}")
            return reply

    def send_events(self, events: list[dict]) -> None:
        self._execute("input-send-event", {"events": events})

    def close(self) -> None:
        self._sock.close()


def move_events(w: int, h: int, x: int, y: int) -> list[dict]:
    return [
        {"type": "abs", "data": {"axis": "x", "value": _abs(x, w)}},
        {"type": "abs", "data": {"axis": "y", "value": _abs(y, h)}},
    ]


# Left-hand modifiers, named as QEMU's qcode enum names them. Hyprland's
# SUPER is the meta key.
MODIFIER_QCODES = {
    "super": "meta_l",
    "ctrl": "ctrl",
    "alt": "alt",
    "shift": "shift",
}

WHEEL_BUTTONS = {"up": "wheel-up", "down": "wheel-down"}


def key_event(qcode: str, down: bool) -> dict:
    return {"type": "key", "data": {"down": down, "key": {"type": "qcode", "data": qcode}}}


def wheel_events(direction: str) -> list[dict]:
    """One notch. Press and release, because a wheel button that is never
    released leaves the guest scrolling for as long as it believes it."""
    try:
        button = WHEEL_BUTTONS[direction]
    except KeyError:
        raise ValueError(
            f"direction must be one of {sorted(WHEEL_BUTTONS)}, got {direction!r}"
        ) from None
    return [
        {"type": "btn", "data": {"down": True, "button": button}},
        {"type": "btn", "data": {"down": False, "button": button}},
    ]


def modifier_qcode(name: str) -> str:
    try:
        return MODIFIER_QCODES[name]
    except KeyError:
        raise ValueError(
            f"modifier must be one of {sorted(MODIFIER_QCODES)}, got {name!r}"
        ) from None


def send_key(qmp: "QMP", qcode: str, modifier: str | None) -> None:
    """One key press, optionally inside a held modifier.

    Exists to take the pointer out of the question: when a modifier+wheel
    binding does nothing, the useful next question is whether the modifier
    reaches the compositor at all, and a modifier+KEY binding that already
    works answers it without involving the wheel.
    """
    held = modifier_qcode(modifier) if modifier else None
    if held:
        qmp.send_events([key_event(held, True)])
    qmp.send_events([key_event(qcode, True)])
    qmp.send_events([key_event(qcode, False)])
    if held:
        qmp.send_events([key_event(held, False)])
    print(f"pressed {qcode}" + (f" with {modifier} held" if held else ""))


def main() -> int:
    args = sys.argv[1:]
    if len(args) < 3:
        print(__doc__)
        return 2

    sock_path, action = args[0], args[1]

    modifier = None
    if "--modifier" in args:
        modifier = args[args.index("--modifier") + 1]

    if action == "key":
        qcode = args[2]
        try:
            qmp = QMP(sock_path)
        except (OSError, RuntimeError, ValueError) as e:
            print(f"ERROR: could not talk to QMP at {sock_path}: {e}")
            return 1
        try:
            send_key(qmp, qcode, modifier)
        except (OSError, RuntimeError, ValueError) as e:
            print(f"ERROR: sending input failed: {e}")
            return 1
        finally:
            qmp.close()
        return 0

    if len(args) < 6:
        print(__doc__)
        return 2

    w, h, x, y = (int(v) for v in args[2:6])
    button = "left"
    if "--button" in args:
        button = args[args.index("--button") + 1]
    direction = None
    if "--direction" in args:
        direction = args[args.index("--direction") + 1]

    if action not in ("move", "click", "scroll"):
        print(f"unknown action {action!r}")
        return 2

    if action == "scroll" and direction is None:
        print("scroll needs --direction up|down")
        return 2

    try:
        qmp = QMP(sock_path)
    except (OSError, RuntimeError, ValueError) as e:
        print(f"ERROR: could not talk to QMP at {sock_path}: {e}")
        return 1

    try:
        # The move is sent as its own event batch before the button. Sending
        # position and press together works on some devices and not others,
        # and a click that lands at the previous position is the kind of
        # failure that looks like "the button does not respond".
        qmp.send_events(move_events(w, h, x, y))
        print(f"pointer -> ({x}, {y}) on {w}x{h}")

        if action == "click":
            qmp.send_events([{"type": "btn", "data": {"down": True, "button": button}}])
            qmp.send_events([{"type": "btn", "data": {"down": False, "button": button}}])
            print(f"clicked {button} at ({x}, {y})")

        if action == "scroll":
            qcode = modifier_qcode(modifier) if modifier else None
            wheel = wheel_events(direction)
            # The modifier is pressed in its own batch and released in
            # another, with the wheel between them: a binding is matched
            # against the modifier state when the wheel arrives, so the order
            # is the whole point rather than a detail.
            if qcode:
                qmp.send_events([key_event(qcode, True)])
            # Which device carries this is QEMU's decision: a wheel notch
            # goes to something that has a wheel, which is why the VM has a
            # relative mouse alongside the tablet at all.
            qmp.send_events(wheel)
            if qcode:
                qmp.send_events([key_event(qcode, False)])
            held = f" with {modifier} held" if qcode else ""
            print(f"scrolled {direction}{held} at ({x}, {y})")
    except (OSError, RuntimeError, ValueError) as e:
        print(f"ERROR: sending input failed: {e}")
        return 1
    finally:
        qmp.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
