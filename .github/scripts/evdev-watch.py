#!/usr/bin/env python3
"""Print what the guest KERNEL receives on its input devices (stdlib-only).

Runs INSIDE the guest, unlike everything else in this directory. It exists
because four rounds of asking "does the wheel arrive" were answered by what
the compositor did afterwards, and a compositor that does nothing has three
different reasons for it: the event never left QEMU, it reached the kernel
on a device nobody expected, or it arrived and the bind under test was not
the one it fires. Only the first two are visible from here, which is the
point — this separates them from the third.

It reads every /dev/input/event* for a few seconds and reports, per device,
how many events of each kind arrived. Reading evdev does not consume the
events; libinput and the compositor see them as before.

Usage:
    evdev-watch.py [SECONDS]
"""
import glob
import os
import select
import struct
import sys
import time

# struct input_event on a 64-bit kernel: two longs of timestamp, then
# type, code, value.
EVENT = struct.Struct("llHHi")

EV_SYN, EV_KEY, EV_REL, EV_ABS = 0, 1, 2, 3

NAMES = {
    (EV_REL, 0): "REL_X",
    (EV_REL, 1): "REL_Y",
    (EV_REL, 6): "REL_HWHEEL",
    (EV_REL, 8): "REL_WHEEL",
    (EV_REL, 11): "REL_WHEEL_HI_RES",
    (EV_ABS, 0): "ABS_X",
    (EV_ABS, 1): "ABS_Y",
    (EV_KEY, 0x110): "BTN_LEFT",
    (EV_KEY, 0x111): "BTN_RIGHT",
    (EV_KEY, 0x112): "BTN_MIDDLE",
    (EV_KEY, 0x150): "BTN_GEAR_DOWN",
    (EV_KEY, 0x151): "BTN_GEAR_UP",
    (EV_KEY, 125): "KEY_LEFTMETA",
}


def decode(buf: bytes) -> list[tuple[int, int, int]]:
    """(type, code, value) for every whole event in buf, EV_SYN left out."""
    events = []
    for offset in range(0, len(buf) - EVENT.size + 1, EVENT.size):
        _, _, etype, code, value = EVENT.unpack_from(buf, offset)
        if etype != EV_SYN:
            events.append((etype, code, value))
    return events


def describe(etype: int, code: int) -> str:
    return NAMES.get((etype, code), f"type={etype} code={code}")


def summarise(events: list[tuple[int, int, int]]) -> list[str]:
    """One line per kind of event, in first-seen order, with the values."""
    seen: dict[tuple[int, int], list[int]] = {}
    for etype, code, value in events:
        seen.setdefault((etype, code), []).append(value)
    return [
        f"{describe(etype, code)} x{len(values)} values={values[:8]}"
        for (etype, code), values in seen.items()
    ]


def device_name(node: str) -> str:
    path = f"/sys/class/input/{os.path.basename(node)}/device/name"
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return "?"


def main() -> int:
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 6.0
    nodes = sorted(glob.glob("/dev/input/event*"))
    if not nodes:
        print("no /dev/input/event* devices at all")
        return 1

    fds = {}
    for node in nodes:
        try:
            fds[os.open(node, os.O_RDONLY | os.O_NONBLOCK)] = node
        except OSError as e:
            print(f"{node}: cannot open ({e})")

    collected: dict[str, list[tuple[int, int, int]]] = {n: [] for n in fds.values()}
    deadline = time.monotonic() + seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        ready, _, _ = select.select(list(fds), [], [], remaining)
        for fd in ready:
            try:
                buf = os.read(fd, EVENT.size * 64)
            except OSError:
                continue
            collected[fds[fd]].extend(decode(buf))

    for node in nodes:
        if node not in collected:
            continue
        print(f"{node} [{device_name(node)}]")
        lines = summarise(collected[node])
        for line in lines:
            print(f"    {line}")
        if not lines:
            print("    (nothing)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
